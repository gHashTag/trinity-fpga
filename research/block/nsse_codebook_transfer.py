#!/usr/bin/env python3
"""Does the squared-error-optimised (nSSE-equal) eight-level codebook transfer?

The KL-optimised codebook was fitted to SmolLM2-135M's LOGITS and lost on both
models it was not fitted to (Qwen +1.98%, Pythia +8.63% vs MXFP4). The
nSSE-equal codebook was fitted to SmolLM2's WEIGHT STATISTICS only -- no forward
pass -- so it may transfer where the logit-fitted one did not.

Measurement path is not reimplemented: quant, perplexity, target_modules and
load_wikitext come from block_tnf.py by executing its source up to the driver
marker. Every codebook is asserted to have top level exactly 1.0 so all sit at
headroom phase phi=0 (T38, SCALE_PHASE_THEOREM_2026-08-11.md).

Per-window NLL is recorded so the winner-vs-MXFP4 comparison can be paired.
Aggregate ppl = exp(mean_i nll_i) which is EXACTLY what perplexity() returns on
the whole slice (equal token count per window); the identity is checked in code.

    MDIR=qwen NWIN=20 python3 nsse_codebook_transfer.py
"""
import json
import math
import os
import sys
import time

import numpy as np
import torch

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "block_tnf.py")
MARKER = 'print("загружаю модель…", flush=True)'
_s = open(SRC, encoding="utf-8").read()
if MARKER not in _s:
    raise SystemExit("driver marker not found in block_tnf.py")
ns = {}
exec(compile(_s.split(MARKER)[0], SRC, "exec"), ns)

fp_levels = ns["fp_levels"]
quant, perplexity, target_modules, load_wikitext = (
    ns[k] for k in ("quant", "perplexity", "target_modules", "load_wikitext"))
K, SEQLEN = ns["K"], ns["SEQLEN"]
W = os.path.dirname(ns["MODEL"])

torch.set_grad_enabled(False)

NWIN = int(os.environ.get("NWIN", "20"))
MDIR = os.environ.get("MDIR", "qwen")

# ---- codebooks, every one normalised to top level exactly 1.0 --------------
def normalise(lv):
    v = sorted(float(x) for x in lv)
    return [x / v[-1] for x in v]


MXFP4 = normalise(fp_levels(2, 1))
LLOYD = normalise([0.0, 0.10334, 0.21079, 0.32491, 0.44963,
                   0.59031, 0.75635, 0.96567])
NSSE = [0.0, 0.09083, 0.18167, 0.28750, 0.40833, 0.55250, 0.73417, 1.0]

BOOKS = [("MXFP4 (E2M1)", MXFP4),
         ("Lloyd-Max (MSE opt)", LLOYD),
         ("nSSE-equal (weight-stat fitted)", NSSE)]

for nm, lv in BOOKS:
    assert len(lv) == 8, (nm, len(lv))
    assert lv == sorted(lv), nm
    assert lv[0] == 0.0, nm
    assert abs(lv[-1] - 1.0) < 1e-12, f"{nm}: top={lv[-1]} -- phase phi != 0"
    assert abs(math.log2(lv[-1]) % 1.0) < 1e-12, nm
print("all codebooks normalised to top=1.0 (headroom phase phi=0)", flush=True)

# known figures the run must reproduce before anything new is quoted
RULERS = {
    "qwen":   {"nwin": 20, "fp32": 12.6999, "MXFP4 (E2M1)": 15.4374,
               "Lloyd-Max (MSE opt)": 16.0703},
    "pythia": {"nwin": 40, "fp32": 25.9561, "MXFP4 (E2M1)": 47.6504,
               "Lloyd-Max (MSE opt)": 52.9992},
    "smollm2": {"nwin": 40, "fp32": 14.4874, "MXFP4 (E2M1)": 21.9397,
                "Lloyd-Max (MSE opt)": 22.9166},
}


def main():
    from transformers import AutoModelForCausalLM, AutoTokenizer
    path = os.path.join(W, MDIR)
    print(f"model dir = {path}   NWIN={NWIN}", flush=True)
    tok = AutoTokenizer.from_pretrained(path)
    model = AutoModelForCausalLM.from_pretrained(path, dtype=torch.float32)
    model.eval()
    ids = tok(load_wikitext(), return_tensors="pt").input_ids
    flat = ids.reshape(-1)
    ntot = flat.numel() // SEQLEN
    win = flat[:ntot * SEQLEN].view(-1, SEQLEN)
    print(f"tokens={flat.numel()}  windows available={ntot}  using [0,{NWIN})",
          flush=True)
    if ntot < NWIN:
        raise SystemExit(f"only {ntot} windows available, need {NWIN}")

    lins = target_modules(model)
    print(f"{len(lins)} linear tensors quantised (lm_head excluded)", flush=True)
    if len(lins) == 0:
        raise SystemExit("zero target modules -- nothing would be quantised")
    orig = {n: m.weight.detach().clone() for n, m in lins}

    def apply(lv):
        for n, m in lins:
            m.weight.copy_(orig[n] if lv is None else quant(orig[n], lv))

    def per_window():
        """NLL of each window separately; ppl_i = exp(nll_i)."""
        out = []
        for i in range(NWIN):
            out.append(math.log(perplexity(model, win[i], 1)))
        return np.array(out, dtype=np.float64)

    results, nlls = {}, {}

    t0 = time.time()
    apply(None)
    nll0 = per_window()
    base = float(np.exp(nll0.mean()))
    nlls["fp32"] = nll0
    results["fp32"] = base
    # identity check: whole-slice perplexity() must equal exp(mean per-window nll)
    whole = perplexity(model, win[:NWIN].reshape(1, -1), NWIN)
    print(f"\nfp32 baseline = {base:.4f}  ({time.time()-t0:.0f}s)", flush=True)
    print(f"  identity check: whole-slice perplexity() = {whole:.6f}  "
          f"exp(mean per-window nll) = {base:.6f}  "
          f"rel diff {abs(whole-base)/base:.2e}", flush=True)
    assert abs(whole - base) / base < 1e-9, "per-window decomposition is wrong"

    for name, lv in BOOKS:
        t0 = time.time()
        apply(lv)
        v = per_window()
        nlls[name] = v
        results[name] = float(np.exp(v.mean()))
        print(f"{name:<34}{results[name]:>10.4f}  ({time.time()-t0:.0f}s)",
              flush=True)
    apply(None)

    # ---- INSTRUMENT CHECK: rulers must reproduce ---------------------------
    ok = True
    r = RULERS.get(MDIR)
    print("\n=== RULER CHECK (must reproduce before anything new counts) ===")
    if r is None or r["nwin"] != NWIN:
        print(f"  no reference figures for MDIR={MDIR} NWIN={NWIN}")
    else:
        for key in ("fp32", "MXFP4 (E2M1)", "Lloyd-Max (MSE opt)"):
            got, exp_ = results[key], r[key]
            d = abs(got - exp_) / exp_
            good = d < 5e-4
            ok &= good
            print(f"  {key:<34} got {got:>9.4f}  expected {exp_:>9.4f}  "
                  f"rel {d:.2e}  {'OK' if good else 'MISMATCH'}")
    print(f"  RULERS {'REPRODUCE' if ok else 'DO NOT REPRODUCE'}", flush=True)

    # ---- paired per-window test, nSSE vs MXFP4 -----------------------------
    a = nlls["nSSE-equal (weight-stat fitted)"]
    b = nlls["MXFP4 (E2M1)"]
    d = a - b                     # negative => nSSE better on that window
    n = len(d)
    mean = float(d.mean())
    sd = float(d.std(ddof=1))
    se = sd / math.sqrt(n)
    t = mean / se if se > 0 else float("nan")
    nbetter = int((d < 0).sum())
    nworse = int((d > 0).sum())

    mx = results["MXFP4 (E2M1)"]
    print(f"\n  {'codebook':<34}{'ppl':>10}{'vs fp32':>10}{'vs MXFP4':>11}")
    print(f"  {'fp32':<34}{base:>10.4f}")
    for name, _ in BOOKS:
        p = results[name]
        print(f"  {name:<34}{p:>10.4f}{p-base:>+10.4f}"
              f"{100*(p/mx-1):>+10.2f}%")

    print(f"\nPAIRED per-window dNLL (nSSE - MXFP4), n={n}")
    print(f"  mean  = {mean:+.6f}")
    print(f"  sd    = {sd:.6f}")
    print(f"  se    = {se:.6f}")
    print(f"  t     = {t:+.3f}   (df={n-1})")
    print(f"  windows nSSE better = {nbetter} / worse = {nworse}")
    print(f"\nTRANSFER: {'HOLDS' if results[BOOKS[2][0]] < mx else 'FAILS'} "
          f"on {MDIR} ({100*(results[BOOKS[2][0]]/mx-1):+.2f}% vs MXFP4)")

    out = {"model": MDIR, "nwin": NWIN, "rulers_reproduce": bool(ok),
           "ppl": results,
           "paired_nsse_vs_mxfp4": {"mean_dnll": mean, "sd": sd, "se": se,
                                    "t": t, "df": n - 1,
                                    "n_better": nbetter, "n_worse": nworse},
           "per_window_nll": {k: list(map(float, v)) for k, v in nlls.items()}}
    dst = os.path.join(HERE, f"nsse_codebook_transfer_{MDIR}.json")
    json.dump(out, open(dst, "w"), indent=1)
    print(f"\nwrote {dst}")
    return 0 if ok else 2


if __name__ == "__main__":
    sys.exit(main())
