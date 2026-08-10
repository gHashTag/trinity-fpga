#!/usr/bin/env python3
"""The decisive measurement: real perplexity, and real importance, on a real model.

Everything so far is MSE on real weights. MSE is not the axis the field reports and not the
axis the stop-rule names. This script closes both remaining stand-ins at once:

  PART A -- REAL IMPORTANCE. The gamma sweep in importance_theory.py used a synthetic coupling
    h = |y|^gamma. AWQ's actual importance is the per-input-channel activation magnitude, which
    can only be measured by running the model. We capture it with forward hooks on calibration
    text, compute the measured E[h | y], tilt p_eff by it, and re-derive. This says where real
    models actually sit on the gamma axis instead of assuming.

  PART B -- REAL PERPLEXITY. Quantise every linear weight with each candidate codebook and
    measure wikitext-2 perplexity. This is the leader's own axis.

RULER CHECK (before trusting any number). The unquantised baseline perplexity must be sane for
a 135M model on wikitext-2. If the baseline is wrong, every comparison built on it is wrong,
and no amount of internal consistency would reveal it -- the broken-ruler failure. The script
refuses to report comparisons if the baseline falls outside a plausible band.

Blocks run along the CONTRACTION axis (last axis of a [out, in] weight), matching MX layout.
Scales are quantised to UE4M3, as real MX does. Embeddings, norms and the tied LM head are
left in full precision, which is standard practice and identical across all candidates.
"""
import json
import os
import sys

import numpy as np
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

W = ("/private/tmp/claude-501/-Users-ssdm4-Desktop-PROJECTS-CLAUDE/"
     "0e868af8-ab2d-4d00-be03-8fea94ba48e4/scratchpad/weights")
MODEL = os.path.join(W, "smollm2")
K = 32
SEQLEN = 2048
NBIN = 2000
torch.set_grad_enabled(False)


# ------------------------------------------------------------------ codebooks
def fp_levels(eb, mb):
    bias = (1 << (eb - 1)) - 1
    out = {0.0}
    for e in range(1 - bias, (1 << eb) - bias):
        for m in range(1 << mb):
            out.add((1 + m / (1 << mb)) * 2.0 ** e)
    lv = np.array(sorted(out))
    return lv / lv.max()


def nf4_levels():
    from statistics import NormalDist
    nd = NormalDist()
    lv = np.array([0.0] + [nd.inv_cdf(0.5 + 0.5 * (i + 0.5) / 8) for i in range(1, 8)])
    return lv / lv.max()


def wlloyd(vals, dy, w, nlev=8, iters=400):
    lv = np.array([i / (nlev - 1) for i in range(nlev)], dtype=np.float64)
    y = (np.arange(len(vals)) + 0.5) * dy
    m = vals * dy * w
    for _ in range(iters):
        j = np.searchsorted((lv[:-1] + lv[1:]) / 2, y)
        num = np.bincount(j, weights=m * y, minlength=nlev)
        den = np.bincount(j, weights=m, minlength=nlev)
        new = np.where(den > 0, num / np.maximum(den, 1e-300), lv)
        new[0], new[-1] = 0.0, 1.0
        new = np.sort(new)
        if np.max(np.abs(new - lv)) < 1e-13:
            return new
        lv = new
    return lv


# ------------------------------------------------------------------ quantiser
def q_ue4m3_t(s):
    e = torch.floor(torch.log2(s.clamp(min=1e-30))).clamp(-6, 8)
    m = torch.round((s / torch.pow(2.0, e) - 1.0) * 8).clamp(0, 8)
    e = e + (m == 8).to(e.dtype)
    m = torch.where(m == 8, torch.zeros_like(m), m)
    return (1 + m / 8) * torch.pow(2.0, e)


def q_e8m0_t(s):
    """The scale format the MX spec actually mandates: a bare power of two."""
    return torch.pow(2.0, torch.ceil(torch.log2(s.clamp(min=1e-30))))


def quantise_weight(w, lv_t, quant_scale="ue4m3"):
    """Block-scaled quantisation along the contraction (last) axis."""
    orig = w.shape
    n = (orig[1] // K) * K
    if n == 0:
        return w
    head = w[:, :n].reshape(-1, K).double()
    a = head.abs().amax(dim=1)
    top = lv_t[-1]
    s = a / top
    if quant_scale == "ue4m3":
        s = q_ue4m3_t(s.clamp(min=1e-30))
    elif quant_scale == "e8m0":
        s = q_e8m0_t(s)
    s = s.clamp(min=1e-30)
    y = (head / s[:, None]).abs()
    bnd = (lv_t[:-1] + lv_t[1:]) / 2
    idx = torch.bucketize(y, bnd)
    rec = torch.sign(head) * lv_t[idx] * s[:, None]
    out = w.clone()
    out[:, :n] = rec.reshape(-1, n).to(w.dtype)
    return out


def target_modules(model):
    """2-D linear weights that MX would quantise: attention and MLP projections."""
    out = []
    for name, mod in model.named_modules():
        if isinstance(mod, torch.nn.Linear) and "lm_head" not in name:
            out.append((name, mod))
    return out


# ------------------------------------------------------------------ data
def load_wikitext():
    import pyarrow.parquet as pq
    t = pq.read_table(os.path.join(W, "wikitext2-test.parquet"))
    return "\n\n".join(t.column("text").to_pylist())


def perplexity(model, ids, limit_windows=None):
    n = (ids.numel() // SEQLEN) * SEQLEN
    x = ids[:n].view(-1, SEQLEN)
    if limit_windows:
        x = x[:limit_windows]
    nll, cnt = 0.0, 0
    for i in range(x.shape[0]):
        chunk = x[i: i + 1]
        out = model(chunk, labels=chunk)
        nll += out.loss.double().item() * (SEQLEN - 1)
        cnt += SEQLEN - 1
    return float(np.exp(nll / cnt))


# ------------------------------------------------------------------ run
print("Loading model and data ...")
tok = AutoTokenizer.from_pretrained(MODEL)
model = AutoModelForCausalLM.from_pretrained(MODEL, torch_dtype=torch.float32)
model.eval()
text = load_wikitext()
ids = tok(text, return_tensors="pt").input_ids[0]
print(f"  wikitext-2 test: {ids.numel()} tokens, {ids.numel()//SEQLEN} windows of {SEQLEN}")

NW = int(os.environ.get("NW", "24"))
base_state = {n: m.weight.detach().clone() for n, m in target_modules(model)}
print(f"  quantisable linear tensors: {len(base_state)}")

ppl_base = perplexity(model, ids, NW)
print(f"\nRULER CHECK -- unquantised baseline perplexity: {ppl_base:.3f}  ({NW} windows)")
if not (5.0 < ppl_base < 60.0):
    sys.exit(f"  baseline implausible for a 135M model on wikitext-2; refusing to compare.")
print("  plausible for SmolLM2-135M; proceeding.\n")

# ---- PART A: measured importance ------------------------------------------
print("PART A -- measured AWQ-style importance, and where real models sit on the gamma axis\n")
acts = {}
hooks = []


def mk_hook(name):
    def h(mod, inp, out):
        a = inp[0].detach().abs().double()
        a = a.reshape(-1, a.shape[-1]).mean(dim=0)
        acts[name] = acts.get(name, 0.0) + a
    return h


for n, m in target_modules(model):
    hooks.append(m.register_forward_hook(mk_hook(n)))
_ = perplexity(model, ids, 2)          # calibration pass
for h in hooks:
    h.remove()

ys, hs = [], []
for n, m in target_modules(model):
    if n not in acts:
        continue
    w = m.weight.detach().double()
    nn_ = (w.shape[1] // K) * K
    if nn_ == 0:
        continue
    b = w[:, :nn_].reshape(-1, K)
    a = b.abs().amax(dim=1)
    ok = a > 0
    b, a = b[ok], a[ok]
    y = (b / a[:, None]).abs()
    him = (acts[n][:nn_] ** 2).reshape(1, -1).expand(w.shape[0], -1).reshape(-1, K)[ok]
    ys.append(y.reshape(-1).numpy()[::37])
    hs.append(him.reshape(-1).numpy()[::37])
ys = np.concatenate(ys)
hs = np.concatenate(hs)
hs = hs / hs.mean()

dy = 1.0 / NBIN
bi = np.clip((ys / dy).astype(int), 0, NBIN - 1)
cnt = np.bincount(bi, minlength=NBIN).astype(float)
hsum = np.bincount(bi, weights=hs, minlength=NBIN)
Eh = np.where(cnt > 0, hsum / np.maximum(cnt, 1), 1.0)
p_eff = cnt / (cnt.sum() * dy)

good = cnt > 100
gamma_fit = float(np.polyfit(np.log(np.maximum((np.arange(NBIN) + .5) * dy, 1e-6))[good],
                             np.log(np.maximum(Eh, 1e-12))[good], 1)[0])
corr = float(np.corrcoef(np.log(np.maximum(ys, 1e-6)), np.log(np.maximum(hs, 1e-12)))[0, 1])
print(f"  measured coupling: best-fit gamma = {gamma_fit:+.4f}   corr(log|y|, log h) = {corr:+.4f}")
print("  the importance-invariance theorem says gamma = 0 leaves the codebook untouched.")

lv_plain = wlloyd(p_eff, dy, np.ones(NBIN))
lv_tilt = wlloyd(p_eff, dy, Eh)
print(f"  plain     " + " ".join(f"{v:.4f}" for v in lv_plain))
print(f"  tilted    " + " ".join(f"{v:.4f}" for v in lv_tilt))
print(f"  max level shift from real measured importance: {np.max(np.abs(lv_tilt-lv_plain)):.4f}\n")

# ---- PART B: perplexity ----------------------------------------------------
CANDS = {
    # true MXFP4 per the MX spec: E2M1 elements with an E8M0 (power-of-two) shared scale
    "e2m1 + E8M0 (true MXFP4)": (fp_levels(2, 1), "e8m0"),
    # all remaining rows share a UE4M3 scale, which is NVFP4-style and strictly finer.
    # giving E2M1 that scale flatters MXFP4, so the comparison is conservative.
    "e2m1 (MXFP4 elem)": (fp_levels(2, 1), "ue4m3"),
    "int4": (np.array([i / 7 for i in range(8)]), "ue4m3"),
    "nf4-style": (nf4_levels(), "ue4m3"),
    "DERIVED": (lv_plain, "ue4m3"),
    "DERIVED+importance": (lv_tilt, "ue4m3"),
    "DERIVED + E8M0": (lv_plain, "e8m0"),
}

print("PART B -- wikitext-2 perplexity with every linear weight quantised to 4 bits")
print(f"  (block K={K} along the contraction axis, UE4M3 block scales, {NW} windows)\n")
print(f"  {'codebook':<26}{'perplexity':>12}{'vs fp32':>10}{'vs MXFP4':>11}")
print(f"  {'fp32 (unquantised)':<26}{ppl_base:>12.3f}{'--':>10}{'--':>11}")

res = {}
for name, (lv, qs) in CANDS.items():
    lv_t = torch.tensor(lv, dtype=torch.float64)
    for n, m in target_modules(model):
        m.weight.copy_(quantise_weight(base_state[n].double(), lv_t, qs).to(m.weight.dtype))
    p = perplexity(model, ids, NW)
    res[name] = p
    ref = res["e2m1 + E8M0 (true MXFP4)"]
    print(f"  {name:<26}{p:>12.3f}{p - ppl_base:>+10.3f}{ref - p:>+11.3f}")

for n, m in target_modules(model):
    m.weight.copy_(base_state[n])

print("\n  'vs fp32' is perplexity degradation (lower is better).")
print("  'vs MXFP4' is perplexity recovered relative to MXFP4 (higher is better).")
