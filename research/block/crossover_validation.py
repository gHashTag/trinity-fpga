#!/usr/bin/env python3
"""Testing the crossover rule per-tensor, with thresholds pre-registered from synthetic data.

The rule is currently 2-for-2 on model-level predictions (SmolLM2 +1.12 -> ours wins; Qwen +1.51
-> NF4 wins). Two successes is suggestive and nothing more. Every held-out tensor in both models
has its own kurtosis and its own winner, giving a few hundred independent tests instead of two.

PROTOCOL, fixed before any real tensor is touched:

  STEP A  Locate each pairwise crossover on SYNTHETIC data only (Gaussian scale mixture,
          per-element scale), by bisection on excess kurtosis. These thresholds are then FROZEN.

  STEP B  For each held-out tensor, compute its kurtosis, PREDICT the winner from the frozen
          thresholds, then measure the actual winner. Score the predictions.

Any threshold tuned after seeing step B would make the test circular, so step A writes them out
before step B runs and they are not revisited.

WHICH KURTOSIS? Two candidates, and it is not obvious which the rule should use:

  k_tensor  excess kurtosis of the whole tensor -- what a practitioner would compute, but it
            includes ACROSS-block scale variation, which block-max scaling removes entirely.
  k_block   mean of the per-block excess kurtosis -- measures WITHIN-block tail weight, which
            is what the quantizer actually sees.

The theory says k_block is the right statistic. Both are scored, so if k_tensor predicts equally
well the rule is more usable, and if only k_block works that is itself a confirmation of the
mechanism.

METRIC: MSE. Justified here because all three codebooks contain exact zero, and the earlier
inversion was shown to be caused by a MISSING zero; among zero-containing codebooks the MSE and
perplexity orderings agreed. That is an argument, not a proof, and is flagged as such.
"""
import json
import os
import re
import struct

import numpy as np

from competitors import FP4_E2M1 as E2M1, INT4, NF4

rng = np.random.default_rng(20260810)
W = ("/private/tmp/claude-501/-Users-ssdm4-Desktop-PROJECTS-CLAUDE/"
     "0e868af8-ab2d-4d00-be03-8fea94ba48e4/scratchpad/weights")
K = 32

OURS = np.array([-1.0000, -0.7805, -0.6094, -0.4645, -0.3361, -0.2183, -0.1066, 0.0000,
                 0.0944, 0.1901, 0.2908, 0.3987, 0.5162, 0.6491, 0.8053, 1.0000])
CANDS = {"ours": OURS, "NF4": NF4, "E2M1": E2M1}


def mse(b, lv):
    a = np.abs(b).max(1)
    ok = a > 0
    b, a = b[ok], a[ok]
    if len(b) == 0:
        return float("nan")
    idx = np.searchsorted((lv[:-1] + lv[1:]) / 2, b / a[:, None]).clip(0, len(lv) - 1)
    return float(((lv[idx] * a[:, None] - b) ** 2).mean())


def exkurt(x):
    x = np.asarray(x, dtype=np.float64).ravel()
    s = x.std()
    return float(((x - x.mean()) ** 4).mean() / s ** 4 - 3) if s > 0 else float("nan")


# ---------------------------------------------------------------- STEP A
def synth(sigma_h, n=300000):
    z = rng.standard_normal(n)
    u = rng.standard_normal(n)
    return (z * np.exp(sigma_h * u)).reshape(-1, K)


def gap(sigma_h, a, b):
    """positive when codebook `a` is better (lower MSE) than `b`."""
    x = synth(sigma_h)
    return mse(x, CANDS[b]) - mse(x, CANDS[a])


def bisect(a, b, lo=0.0, hi=1.4, iters=18):
    """Find the sigma_h where a and b swap; return the excess kurtosis there."""
    if gap(lo, a, b) * gap(hi, a, b) > 0:
        return None
    for _ in range(iters):
        mid = (lo + hi) / 2
        if gap(lo, a, b) * gap(mid, a, b) <= 0:
            hi = mid
        else:
            lo = mid
    sh = (lo + hi) / 2
    return exkurt(synth(sh, 600000))


print("STEP A -- crossovers located on SYNTHETIC data, then FROZEN\n")
TH = {}
for a, b in (("ours", "NF4"), ("ours", "E2M1"), ("NF4", "E2M1")):
    k = bisect(a, b)
    TH[(a, b)] = k
    if k is None:
        print(f"  {a:>5} vs {b:<5}  no crossover in range -> one dominates throughout")
    else:
        print(f"  {a:>5} vs {b:<5}  crossover at excess kurtosis {k:7.2f}")
print("\n  FROZEN. Not revisited after real data is seen.\n")

t_on = TH[("ours", "NF4")]
t_oe = TH[("ours", "E2M1")]
t_ne = TH[("NF4", "E2M1")]


def predict(k):
    """Rule: below a crossover the first-named codebook wins, above it the second."""
    score = {}
    score["ours"] = (1 if (t_on is None or k < t_on) else 0) + \
                    (1 if (t_oe is None or k < t_oe) else 0)
    score["NF4"] = (0 if (t_on is None or k < t_on) else 1) + \
                   (1 if (t_ne is None or k < t_ne) else 0)
    score["E2M1"] = (0 if (t_oe is None or k < t_oe) else 1) + \
                    (0 if (t_ne is None or k < t_ne) else 1)
    return max(score, key=lambda n: score[n])


# ---------------------------------------------------------------- STEP B
def st_open(p):
    f = open(p, "rb")
    n = struct.unpack("<Q", f.read(8))[0]
    return f, json.loads(f.read(n)), 8 + n


def st_tensor(f, h, b, nm):
    e = h[nm]
    s, t = e["data_offsets"]
    f.seek(b + s)
    raw = f.read(t - s)
    if e["dtype"] == "BF16":
        return ((np.frombuffer(raw, dtype="<u2").astype(np.uint32) << 16)
                .view(np.float32).reshape(e["shape"]))
    return np.frombuffer(raw, dtype="<f4").reshape(e["shape"])


def layer_index(nm):
    m = re.search(r"layers?\.(\d+)\.", nm)
    return int(m.group(1)) if m else -1


print("STEP B -- per-tensor prediction on held-out layers of both models\n")
rows = []
for fn, label in (("smollm2-135m.safetensors", "SmolLM2-135M"),
                  ("qwen25-05b.safetensors", "Qwen2.5-0.5B")):
    p = os.path.join(W, fn)
    if not os.path.exists(p):
        continue
    f, h, base = st_open(p)
    names = [nm for nm, e in h.items() if isinstance(e, dict) and len(e.get("shape", [])) == 2
             and not any(x in nm.lower() for x in ("embed", "lm_head", "wte", "wpe"))]
    names.sort(key=lambda nm: (layer_index(nm), nm))
    nl = max(layer_index(nm) for nm in names) + 1
    test = [nm for nm in names if layer_index(nm) >= nl // 2]
    for nm in test:
        t = st_tensor(f, h, base, nm)
        if t.shape[1] < K:
            continue
        n = (t.shape[1] // K) * K
        b = t[:, :n].reshape(-1, K).astype(np.float64)
        a = np.abs(b).max(1)
        ok = a > 0
        if ok.sum() < 10:
            continue
        yb = b[ok] / a[ok][:, None]
        k_tensor = exkurt(t)
        k_block = float(np.nanmean([exkurt(r) for r in yb[:2000]]))
        vals = {nname: mse(b, lv) for nname, lv in CANDS.items()}
        actual = min(vals, key=lambda x: vals[x])
        rows.append((label, nm, k_tensor, k_block, actual,
                     predict(k_tensor), predict(k_block)))
    f.close()

for stat, idx in (("k_tensor", 5), ("k_block", 6)):
    hits = sum(1 for r in rows if r[4] == r[idx])
    print(f"  {stat:<10} accuracy {hits}/{len(rows)} = {hits/len(rows)*100:.1f}%")

base_rate = max(sum(1 for r in rows if r[4] == c) for c in CANDS) / len(rows)
print(f"  {'baseline':<10} always-predict-most-common = {base_rate*100:.1f}%\n")

print("  distribution of actual winners:")
for c in CANDS:
    n = sum(1 for r in rows if r[4] == c)
    print(f"    {c:<6}{n:>5} / {len(rows)}")

print("\n  kurtosis ranges observed:")
kt = [r[2] for r in rows]
kb = [r[3] for r in rows]
print(f"    k_tensor  {min(kt):7.2f} .. {max(kt):7.2f}   median {np.median(kt):7.2f}")
print(f"    k_block   {min(kb):7.2f} .. {max(kb):7.2f}   median {np.median(kb):7.2f}")
print(f"    frozen thresholds: ours/NF4 {t_on}, ours/E2M1 {t_oe}, NF4/E2M1 {t_ne}")
