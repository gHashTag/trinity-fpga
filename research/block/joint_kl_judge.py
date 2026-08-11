#!/usr/bin/env python3
"""CAMPAIGN A judge -- does the jointly-fitted KL codebook beat MXFP4?

Fitting signal: SUM of KL(fp32 || quantised) over SmolLM2-135M + Qwen2.5-0.5B +
Pythia-160M (joint_kl_codebook.py). Verdict: perplexity at the published window
counts (SmolLM2 40, Qwen 20, Pythia 40) on the three models the fit SAW, plus
OPT-125M -- a model from a fourth family that the fit never touched.

  - beats MXFP4 on all three fitting models AND on the held-out one
        -> the KL objective generalises, the single-model fit was the problem
  - beats MXFP4 on the three it saw but not the fourth   -> still fitting
  - cannot beat MXFP4 on all three at once  -> the objective has no codebook
        that works across models, and that is the answer

Per-window NLL is recorded so every comparison is PAIRED. Aggregate ppl =
exp(mean_i nll_i), identical to what perplexity() returns on the whole slice
(equal token count per window); the identity is asserted in code.

Every codebook is asserted to have top exactly 1.0 (T38 headroom phase phi=0).
Measurement path reused from block_tnf.py, not reimplemented.

    MDIR=qwen NWIN=20 python3 joint_kl_judge.py
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

NWIN = int(os.environ.get("NWIN", "40"))
MDIR = os.environ.get("MDIR", "smollm2")
FIT = os.path.join(HERE, "joint_kl_codebook.json")


def normalise(lv):
    v = sorted(float(x) for x in lv)
    return [x / v[-1] for x in v]


MXFP4 = normalise(fp_levels(2, 1))
LLOYD = normalise([0.0, 0.10334, 0.21079, 0.32491, 0.44963,
                   0.59031, 0.75635, 0.96567])
KLOPT = [0.0, 0.07701, 0.18828, 0.31396, 0.46561, 0.6113, 0.79074, 1.0]
NSSE = [0.0, 0.09083, 0.18167, 0.28750, 0.40833, 0.55250, 0.73417, 1.0]
JOINT = json.load(open(FIT))["joint_fit"]["levels"]

BOOKS = [("MXFP4 (E2M1)", MXFP4),
         ("Lloyd-Max (MSE opt)", LLOYD),
         ("KL-opt (SmolLM2-only fit)", KLOPT),
         ("nSSE-equal (SmolLM2-only fit)", NSSE),
         ("JOINT-KL (3-model fit)", JOINT)]

for nm, lv in BOOKS:
    assert len(lv) == 8, (nm, len(lv))
    assert list(lv) == sorted(lv) and all(b > a for a, b in zip(lv, lv[1:])), nm
    assert float(lv[0]) == 0.0, nm
    assert abs(float(lv[-1]) - 1.0) < 1e-12, f"{nm}: top={lv[-1]} -> phi != 0"
    assert abs(math.log2(float(lv[-1])) % 1.0) < 1e-12, nm
print("all codebooks: top = 1.0 exactly (headroom phase phi=0)", flush=True)
print(f"JOINT-KL levels: {[round(x, 5) for x in JOINT]}", flush=True)

RULERS = {
    "qwen":    {"nwin": 20, "fp32": 12.6999, "MXFP4 (E2M1)": 15.4374,
                "Lloyd-Max (MSE opt)": 16.0703},
    "pythia":  {"nwin": 40, "fp32": 25.9561, "MXFP4 (E2M1)": 47.6504,
                "Lloyd-Max (MSE opt)": 52.9992},
    "smollm2": {"nwin": 40, "fp32": 14.4874, "MXFP4 (E2M1)": 21.9397,
                "Lloyd-Max (MSE opt)": 22.9166},
}


def paired(a, b):
    """a - b per window; negative => a better. Paired t on dNLL."""
    from scipy import stats
    d = np.asarray(a) - np.asarray(b)
    n = len(d)
    mean = float(d.mean())
    sd = float(d.std(ddof=1))
    se = sd / math.sqrt(n)
    t = mean / se if se > 0 else float("nan")
    p = float(stats.t.sf(abs(t), n - 1) * 2) if se > 0 else float("nan")
    tc = float(stats.t.ppf(0.975, n - 1))
    lo, hi = mean - tc * se, mean + tc * se
    return {"n": n, "mean_dnll": mean, "sd": sd, "se": se, "t": t, "p": p,
            "df": n - 1, "n_better": int((d < 0).sum()),
            "n_worse": int((d > 0).sum()),
            "ppl_ratio_pct": 100 * (math.exp(mean) - 1),
            "ci95_pct": [100 * (math.exp(lo) - 1), 100 * (math.exp(hi) - 1)]}


def main():
    from transformers import AutoModelForCausalLM, AutoTokenizer
    path = os.path.join(W, MDIR)
    print(f"\nmodel dir = {path}   NWIN={NWIN}", flush=True)
    tok = AutoTokenizer.from_pretrained(path)
    model = AutoModelForCausalLM.from_pretrained(path, dtype=torch.float32)
    model.eval()
    ids = tok(load_wikitext(), return_tensors="pt").input_ids
    flat = ids.reshape(-1)
    ntot = flat.numel() // SEQLEN
    win = flat[:ntot * SEQLEN].view(-1, SEQLEN)
    if ntot < NWIN:
        raise SystemExit(f"only {ntot} windows available, need {NWIN}")
    lins = target_modules(model)
    if not lins:
        raise SystemExit("zero target modules -- nothing would be quantised")
    npar = sum(m.weight.numel() for _, m in lins)
    print(f"{len(lins)} linear tensors, {npar/1e6:.1f}M weights quantised; "
          f"{ntot} windows available, using [0,{NWIN})", flush=True)
    orig = {n: m.weight.detach().clone() for n, m in lins}

    def apply(lv):
        for n, m in lins:
            m.weight.copy_(orig[n] if lv is None else quant(orig[n], lv))

    def per_window():
        return np.array([math.log(perplexity(model, win[i], 1))
                         for i in range(NWIN)], dtype=np.float64)

    results, nlls = {}, {}
    t0 = time.time()
    apply(None)
    nll0 = per_window()
    results["fp32"] = float(np.exp(nll0.mean()))
    nlls["fp32"] = nll0
    whole = perplexity(model, win[:NWIN].reshape(1, -1), NWIN)
    print(f"\nfp32 = {results['fp32']:.4f}  ({time.time()-t0:.0f}s)")
    print(f"  identity check: whole-slice {whole:.6f} vs "
          f"exp(mean per-window nll) {results['fp32']:.6f}  "
          f"rel {abs(whole-results['fp32'])/results['fp32']:.2e}", flush=True)
    assert abs(whole - results["fp32"]) / results["fp32"] < 1e-9

    for name, lv in BOOKS:
        t0 = time.time()
        apply(lv)
        v = per_window()
        nlls[name] = v
        results[name] = float(np.exp(v.mean()))
        print(f"{name:<32}{results[name]:>10.4f}  ({time.time()-t0:.0f}s)",
              flush=True)
    apply(None)

    # ---- rulers ------------------------------------------------------------
    ok = True
    r = RULERS.get(MDIR)
    print("\n=== RULER CHECK ===")
    if r is None or r["nwin"] != NWIN:
        print(f"  no published figures for MDIR={MDIR} NWIN={NWIN} -- this is a "
              f"first measurement on this model, not a reproduction")
        ruler_status = "none_published"
    else:
        for key in ("fp32", "MXFP4 (E2M1)", "Lloyd-Max (MSE opt)"):
            d = abs(results[key] - r[key]) / r[key]
            good = d < 5e-4
            ok &= good
            print(f"  {key:<32} got {results[key]:>9.4f}  expected {r[key]:>9.4f}"
                  f"  rel {d:.2e}  {'OK' if good else 'MISMATCH'}")
        ruler_status = "reproduce" if ok else "MISMATCH"
        print(f"  RULERS {ruler_status.upper()}", flush=True)

    mx = results["MXFP4 (E2M1)"]
    print(f"\n  {'codebook':<32}{'ppl':>10}{'vs fp32':>10}{'vs MXFP4':>11}")
    print(f"  {'fp32':<32}{results['fp32']:>10.4f}")
    for name, _ in BOOKS:
        p = results[name]
        print(f"  {name:<32}{p:>10.4f}{p-results['fp32']:>+10.4f}"
              f"{100*(p/mx-1):>+10.2f}%")

    tests = {}
    for name in ("JOINT-KL (3-model fit)", "KL-opt (SmolLM2-only fit)",
                 "nSSE-equal (SmolLM2-only fit)", "Lloyd-Max (MSE opt)"):
        tests[name] = paired(nlls[name], nlls["MXFP4 (E2M1)"])
    print(f"\nPAIRED per-window dNLL vs MXFP4 (negative = codebook better)")
    for name, s in tests.items():
        print(f"  {name:<32} mean {s['mean_dnll']:+.6f}  sd {s['sd']:.6f}  "
              f"t {s['t']:+.3f}  p {s['p']:.4f}  "
              f"better/worse {s['n_better']}/{s['n_worse']}  "
              f"[{s['ci95_pct'][0]:+.2f}%,{s['ci95_pct'][1]:+.2f}%]")

    j = results["JOINT-KL (3-model fit)"]
    print(f"\nJOINT-KL on {MDIR}: {100*(j/mx-1):+.2f}% vs MXFP4 -> "
          f"{'BEATS' if j < mx else 'LOSES TO'} MXFP4")

    out = {"model": MDIR, "nwin": NWIN, "ruler_status": ruler_status,
           "rulers_reproduce": bool(ok), "n_linear": len(lins),
           "params_quantised": int(npar), "ppl": results,
           "joint_levels": JOINT,
           "paired_vs_mxfp4": tests,
           "per_window_nll": {k: list(map(float, v)) for k, v in nlls.items()}}
    dst = os.path.join(HERE, f"joint_kl_judge_{MDIR}.json")
    json.dump(out, open(dst, "w"), indent=1)
    print(f"\nwrote {dst}")
    return 0 if (ruler_status in ("reproduce", "none_published")) else 2


if __name__ == "__main__":
    sys.exit(main())
