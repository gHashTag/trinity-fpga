#!/usr/bin/env python3
"""Resume campaign C after the first process was killed, and run its controls.

The first run recorded 48 evaluations (stage 0 rulers, the full 11-point
Lloyd-Max -> KL interpolation, and 35 of the 36 one-level perturbations) into
campaignC_sensitivity_smollm2.json before being killed. Every recorded run
carries its level vector, so those points are reused verbatim rather than
re-measured; the quantiser and the perplexity path are deterministic, and this
script CHECKS that by re-measuring MXFP4 in a fresh process and requiring it to
match the value the killed process wrote.

Remaining work:
    stage 2 tail   one perturbation (level 6, +5%)
    stage 3        15 random codebooks at exactly 2% RMS from MXFP4
    nSSE           the published -5.24% codebook, for scale
    control 1      determinism: same codebook, 3 fresh quantisations
    control 2      continuity: one level at +-0.1% / 0.25% / 0.5%
    control 3      fine interpolation: midpoints of the roughest stretch

Written to a temp file and renamed after every measurement so a second kill
cannot corrupt or lose the record.
"""
import json
import math
import os
import sys
import time

# Detach into its own session before doing anything expensive. The first run of
# this campaign was killed together with the shell task that launched it, losing
# the work in flight; a new session means a signal to that process group cannot
# reach this process.
if os.environ.get("CAMPC_DETACH") == "1" and os.fork() > 0:
    os._exit(0)
if os.environ.get("CAMPC_DETACH") == "1":
    os.setsid()
    sys.stdout.flush()

import numpy as np
import torch

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "block_tnf.py")
MARKER = 'print("загружаю модель…", flush=True)'
ns = {}
exec(compile(open(SRC, encoding="utf-8").read().split(MARKER)[0], SRC, "exec"),
     ns)
fp_levels = ns["fp_levels"]
quant, perplexity, target_modules, load_wikitext = (
    ns[k] for k in ("quant", "perplexity", "target_modules", "load_wikitext"))
K, SEQLEN = ns["K"], ns["SEQLEN"]
W = os.path.dirname(ns["MODEL"])
torch.set_grad_enabled(False)

NWIN, MDIR = 40, "smollm2"
OUT = os.path.join(HERE, f"campaignC_sensitivity_{MDIR}.json")
TMP = OUT + ".tmp"


def normalise(lv):
    v = sorted(float(x) for x in lv)
    v = [x / v[-1] for x in v]
    v[-1] = 1.0
    return v


def check(name, lv):
    assert len(lv) == 8 and lv[0] == 0.0, name
    assert all(lv[i] < lv[i + 1] for i in range(7)), (name, lv)
    assert abs(lv[-1] - 1.0) < 1e-12, f"{name}: top={lv[-1]} -- phase phi != 0"
    assert abs(math.log2(lv[-1]) % 1.0) < 1e-12, name
    return lv


MXFP4 = check("MXFP4", normalise(fp_levels(2, 1)))
LLOYD = check("Lloyd", normalise([0.0, 0.10334, 0.21079, 0.32491, 0.44963,
                                  0.59031, 0.75635, 0.96567]))
KL = check("KL", normalise([0.0, 0.07701, 0.18828, 0.31396, 0.46561,
                            0.6113, 0.79074, 1.0]))
NSSE = check("nSSE", normalise([0.0, 0.09083, 0.18167, 0.28750, 0.40833,
                                0.55250, 0.73417, 1.0]))

log = json.load(open(OUT))
cache = {tuple(round(x, 12) for x in r["levels"]): r["ppl"]
         for r in log["runs"] if r["levels"] is not None}
print(f"resuming: {len(log['runs'])} runs already recorded, "
      f"{len(cache)} distinct codebooks cached", flush=True)


def main():
    from transformers import AutoModelForCausalLM, AutoTokenizer
    path = os.path.join(W, MDIR)
    tok = AutoTokenizer.from_pretrained(path)
    model = AutoModelForCausalLM.from_pretrained(path, dtype=torch.float32)
    model.eval()
    ids = tok(load_wikitext(), return_tensors="pt").input_ids
    flat = ids.reshape(-1)
    win = flat[:(flat.numel() // SEQLEN) * SEQLEN].view(-1, SEQLEN)
    lins = target_modules(model)
    assert len(lins) == log["n_linear"], (len(lins), log["n_linear"])
    orig = {n: m.weight.detach().clone() for n, m in lins}

    def save():
        json.dump(log, open(TMP, "w"), indent=1)
        os.replace(TMP, OUT)

    def raw(lv):
        """One measurement, no cache, fresh quantisation from pristine weights."""
        for n, m in lins:
            m.weight.copy_(orig[n] if lv is None else quant(orig[n], lv))
        p = perplexity(model, win[:NWIN].reshape(1, -1), NWIN)
        for n, m in lins:
            m.weight.copy_(orig[n])
        return p

    def measure(tag, lv):
        key = tuple(round(x, 12) for x in lv)
        if key in cache:
            print(f"  {tag:<40}{cache[key]:>11.4f}   (cached)", flush=True)
            return cache[key]
        t0 = time.time()
        p = raw(lv)
        cache[key] = p
        log["runs"].append({"tag": tag, "ppl": p, "levels": list(lv),
                            "sec": time.time() - t0})
        save()
        print(f"  {tag:<40}{p:>11.4f}   ({time.time()-t0:.0f}s)", flush=True)
        return p

    # --- cross-process reproduction check -----------------------------------
    print("\n=== CROSS-PROCESS CHECK: re-measure MXFP4 in a fresh process ===",
          flush=True)
    was = log["baseline"]["MXFP4"]
    t0 = time.time()
    now = raw(MXFP4)
    print(f"  killed process wrote {was:.8f}", flush=True)
    print(f"  this process measures {now:.8f}   ({time.time()-t0:.0f}s)",
          flush=True)
    # Tolerance is RELATIVE. A first attempt used an absolute 1e-9 and fired:
    # the two processes differed by 1.3e-07 ppl = 6e-09 relative, because they
    # ran with different OMP thread counts and CPU reductions are not
    # associative. Thread count is now pinned to match the first run. The
    # smallest effect this campaign discusses is ~0.05 ppl, five orders of
    # magnitude above this floor, so the bar is set there and the measured
    # floor is recorded rather than hidden.
    rel = abs(now - was) / was
    good = rel < 1e-6
    print(f"  |diff| = {abs(now-was):.3e} ppl = {rel:.3e} relative   "
          f"{'REPRODUCES' if good else 'DOES NOT REPRODUCE'}", flush=True)
    log["cross_process_mxfp4"] = {"first": was, "second": now,
                                  "absdiff": abs(now - was), "reldiff": rel,
                                  "threads": torch.get_num_threads()}
    save()
    if not good:
        print("STOP: cached points from the killed run are not trustworthy.")
        return 2
    mx = now

    # --- stage 2 tail -------------------------------------------------------
    print("\n=== STAGE 2 TAIL ===", flush=True)
    DELTAS = (-0.05, -0.02, -0.01, 0.01, 0.02, 0.05)
    perturb = []
    for j in range(1, 7):
        for d in DELTAS:
            lv = list(MXFP4)
            lv[j] = MXFP4[j] * (1 + d)
            lv = check("p", normalise(lv))
            assert all(abs(lv[q] - MXFP4[q]) < 1e-12
                       for q in range(8) if q != j), "more than one level moved"
            p = measure(f"MXFP4 level[{j}]={MXFP4[j]:.5f} {d:+.0%}", lv)
            perturb.append({"level": j, "base": MXFP4[j], "delta": d,
                            "value": lv[j], "ppl": p})
    log["perturb"] = perturb
    save()

    # --- stage 3: random ----------------------------------------------------
    print("\n=== STAGE 3: 15 random codebooks at exactly 2% RMS from MXFP4 ===",
          flush=True)
    RMS = 0.02
    rng = np.random.default_rng(20260811)
    rand = []
    for s in range(15):
        while True:
            e = rng.standard_normal(6)
            e = e / math.sqrt(float((e ** 2).mean())) * RMS
            lv = list(MXFP4)
            for j in range(1, 7):
                lv[j] = MXFP4[j] * (1 + float(e[j - 1]))
            if all(lv[i] < lv[i + 1] for i in range(7)):
                break
        lv = check(f"rand{s}", normalise(lv))
        got = math.sqrt(float(np.mean([(lv[j] / MXFP4[j] - 1) ** 2
                                       for j in range(1, 7)])))
        assert abs(got - RMS) < 1e-12, got
        p = measure(f"random #{s:02d} (2% RMS)", lv)
        rand.append({"seed_idx": s, "rms": got, "levels": lv, "ppl": p,
                     "eps": [float(x) for x in e]})
    rp = np.array([r["ppl"] for r in rand])
    rel = 100 * (rp / mx - 1)
    log["random"] = rand
    log["random_stats"] = {
        "n": len(rp), "mean_ppl": float(rp.mean()),
        "sd_ppl": float(rp.std(ddof=1)), "min_ppl": float(rp.min()),
        "max_ppl": float(rp.max()), "mean_pct": float(rel.mean()),
        "sd_pct": float(rel.std(ddof=1)), "min_pct": float(rel.min()),
        "max_pct": float(rel.max()), "n_better": int((rp < mx).sum()),
        "n_worse": int((rp > mx).sum()),
        "range_pct": float(rel.max() - rel.min())}
    save()

    print("\n=== nSSE-equal, the published -5.24% codebook ===", flush=True)
    log["nsse_ppl"] = measure("nSSE-equal", NSSE)
    save()

    # --- control 1: determinism --------------------------------------------
    print("\n=== CONTROL 1: DETERMINISM (3 fresh quantisations, no cache) ===",
          flush=True)
    reps = [now]
    for i in range(2):
        t0 = time.time()
        reps.append(raw(MXFP4))
        print(f"  MXFP4 repeat {i+2}: {reps[-1]:.8f}   ({time.time()-t0:.0f}s)",
              flush=True)
    spread = max(reps) - min(reps)
    det = spread < 1e-9
    log["determinism"] = {"reps": reps, "spread": spread, "deterministic": det}
    save()
    print(f"  spread = {spread:.3e} ppl -> DETERMINISTIC: {det}", flush=True)
    if not det:
        print("STOP: instrument is not deterministic; roughness is not safe.")
        return 2

    # --- control 2: continuity at small scale -------------------------------
    print("\n=== CONTROL 2: CONTINUITY at 0.1% / 0.25% / 0.5% ===", flush=True)
    cont = []
    for j in (1, 4):
        for d in (-0.005, -0.0025, -0.001, 0.001, 0.0025, 0.005):
            lv = list(MXFP4)
            lv[j] = MXFP4[j] * (1 + d)
            lv = check("c", normalise(lv))
            p = measure(f"level[{j}] {d:+.2%}", lv)
            cont.append({"level": j, "delta": d, "ppl": p,
                         "pct": 100 * (p / mx - 1)})
    log["continuity"] = cont
    save()

    # --- control 3: fine interpolation --------------------------------------
    print("\n=== CONTROL 3: interpolation midpoints on [0, 0.5] ===",
          flush=True)
    fine = []
    for t in (0.05, 0.15, 0.25, 0.35, 0.45):
        lv = check(f"t={t}", normalise(
            [(1 - t) * a + t * b for a, b in zip(LLOYD, KL)]))
        fine.append({"t": t, "ppl": measure(f"interp t={t:.2f}", lv)})
    log["fine_interp"] = fine
    save()
    print(f"\nwrote {OUT}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
