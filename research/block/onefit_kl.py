#!/usr/bin/env python3
"""Re-derive JOINT-KL under the protocol that won: fit the codebook against KL
on ONE model, once per model, and judge each on the three it never saw.

JOINT-KL exists because two single-model fits failed and the diagnosis was "one
model is not enough".  PLACEMENT_AND_ASYMMETRY_2026-08-12 measured that the
diagnosis was wrong for SELECTION: the failures came from selecting on
perplexity, and one-model KL selection dominates three-model KL selection
(12/12 held-out wins, worst -1.41 %, against 4/4, worst -1.72 %).

Selection and fitting are different problems.  Selection picks among ten
pre-built candidates; fitting searches a six-dimensional continuum and has far
more room to overfit.  This script runs the FITTING version of the experiment so
the two can be compared directly.

The search is kl_optimal_codebook.py's, unchanged in shape: eight magnitudes,
the first pinned to 0.0 and the last to 1.0, six free interior points,
coordinate descent with step 0.06 halving while step > 0.004, EVALS evaluations
per seed, KLWIN calibration windows, objective KL(fp32 || quantised) --
the same objective, window count and reduction joint_kl_codebook.py used.

Nothing on the measurement path is reimplemented: quant / perplexity /
target_modules / load_wikitext / q_e8m0_t come out of block_tnf.py's source up
to its driver marker.

    W=<weights> MDIR=smollm2 EVALS=120 python3 onefit_kl.py
"""
import json
import os
import sys
import time

import numpy as np
import torch
import torch.nn.functional as F

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "block_tnf.py")
MARKER = 'print("загружаю модель…", flush=True)'
_s = open(SRC, encoding="utf-8").read()
if MARKER not in _s:
    raise SystemExit("driver marker not found in block_tnf.py")
ns = {}
exec(compile(_s.split(MARKER)[0], SRC, "exec"), ns)

quant, perplexity, target_modules, load_wikitext = (
    ns[k] for k in ("quant", "perplexity", "target_modules", "load_wikitext"))
K, SEQLEN = ns["K"], ns["SEQLEN"]

import campaignC_books as C

torch.set_grad_enabled(False)
if os.environ.get("THREADS"):
    torch.set_num_threads(int(os.environ["THREADS"]))

MDIR = os.environ["MDIR"]
KLWIN = int(os.environ.get("KLWIN", "2"))
EVALS = int(os.environ.get("EVALS", "120"))
CHUNK = int(os.environ.get("CHUNK", "128"))
SCRATCH = os.environ.get("SCRATCH", os.path.join(os.sep, "tmp"))
WDIR = os.environ.get("W") or os.path.dirname(ns["MODEL"])

ns["load_wikitext"] = load_wikitext = (
    lambda: __import__("pyarrow.parquet", fromlist=["parquet"])
    .read_table(os.path.join(WDIR, "wikitext2-test.parquet"))
    .column("text").to_pylist())

RULERS = {
    "smollm2": {"nwin": 40, "fp32": 14.4874, "MXFP4": 21.9397},
    "qwen":    {"nwin": 20, "fp32": 12.6999, "MXFP4": 15.4374},
    "pythia":  {"nwin": 40, "fp32": 25.9561, "MXFP4": 47.6504},
    "opt":     {"nwin": 40, "fp32": 27.5678, "MXFP4": 30.7871},
}
NWIN = int(os.environ.get("NWIN", RULERS[MDIR]["nwin"]))

# Per-window agreement gate against campaign B's already-published vectors.
# Campaigns B and C measured the SAME arms in two processes and agree to
# 0.00e+00 on qwen and opt, 7.2e-07 on smollm2 and 7.9e-05 on pythia -- pythia's
# forward is not bit-reproducible across runs.  1e-5 would fail on that float
# noise alone, so the gate is 5e-4 nats: six times the observed noise floor,
# 0.05 % of perplexity, and thirty times below the smallest margin this campaign
# quotes.  The observed value is recorded in the output either way.
WTOL = float(os.environ.get("WTOL", "5e-4"))

MXFP4 = list(C.MXFP4)
LLOYD = list(C.LLOYD)


def t38(lv):
    """Every book normalised so max|level| == 1.0, checked on BOTH tails."""
    v = [float(x) for x in lv]
    assert v == sorted(v), v
    assert len(set(v)) == len(v), v
    assert v[0] == 0.0, v
    pos = max(v)
    neg = max(-x for x in v) if min(v) < 0 else pos     # symmetric book: mirror
    assert abs(pos - 1.0) < 1e-12, f"positive tail {pos}"
    assert abs(neg - 1.0) < 1e-12, f"negative tail {neg}"
    return v


def main():
    from transformers import AutoModelForCausalLM, AutoTokenizer
    t38(MXFP4)
    t38(LLOYD)

    path = os.path.join(WDIR, MDIR)
    print(f"model dir = {path}  NWIN={NWIN}  KLWIN={KLWIN}  EVALS={EVALS}",
          flush=True)
    tok = AutoTokenizer.from_pretrained(path)
    model = AutoModelForCausalLM.from_pretrained(path, dtype=torch.float32)
    model.eval()
    ids = tok("\n\n".join(load_wikitext()), return_tensors="pt").input_ids
    flat = ids.reshape(-1)
    ntot = flat.numel() // SEQLEN
    win = flat[:ntot * SEQLEN].view(-1, SEQLEN)
    print(f"tokens={flat.numel()}  windows={ntot}", flush=True)
    if ntot < NWIN:
        raise SystemExit(f"only {ntot} windows, need {NWIN}")

    lins = target_modules(model)
    orig = {n: m.weight.detach().clone() for n, m in lins}
    print(f"{len(lins)} linear tensors quantised (lm_head excluded)", flush=True)

    def apply(lv):
        if lv is None:
            for n, m in lins:
                m.weight.copy_(orig[n])
            return
        for n, m in lins:
            m.weight.copy_(quant(orig[n], lv))

    def per_window():
        return np.array([float(np.log(perplexity(model, win[i], 1)))
                         for i in range(NWIN)], dtype=np.float64)

    # ---- RULER: reproduce the published fp32 and MXFP4 before anything new --
    bref = json.load(open(os.path.join(HERE, f"campaignB_{MDIR}.json")))
    assert bref["rulers_reproduce"], MDIR
    r = RULERS[MDIR]
    ruler_ok = (NWIN == r["nwin"])
    nll = {}
    drift = {}
    for name, lv in (("fp32", None), ("MXFP4", MXFP4)):
        t0 = time.time()
        apply(lv)
        nll[name] = per_window()
        p = float(np.exp(nll[name].mean()))
        d = abs(p - r[name]) / r[name]
        dw = float(np.abs(nll[name] - np.array(bref["per_window_nll"][name][:NWIN])).max())
        drift[name] = dw
        good = d < 5e-4 and dw < WTOL
        ruler_ok &= good
        print(f"RULER {name:<6} {p:>10.4f}  published {r[name]:>9.4f}  rel {d:.2e}"
              f"   max|per-window - campaignB| = {dw:.2e}  "
              f"{'OK' if good else 'MISMATCH'}   ({time.time()-t0:.0f}s)", flush=True)
    if not ruler_ok:
        print("RULER BROKEN -- refusing to produce numbers.", flush=True)
        return 2

    # ---- KL objective, joint_kl_codebook.py's ------------------------------
    apply(None)
    V = int(model(win[0:1]).logits.shape[-1])
    ref_path = os.path.join(SCRATCH, f"onefit_ref_{MDIR}.f32")
    ref = np.memmap(ref_path, dtype=np.float32, mode="w+",
                    shape=(KLWIN * SEQLEN, V))
    for i in range(KLWIN):
        lg = model(win[i:i + 1]).logits[0]
        for a in range(0, SEQLEN, CHUNK):
            b = min(a + CHUNK, SEQLEN)
            ref[i * SEQLEN + a: i * SEQLEN + b] = \
                F.log_softmax(lg[a:b].double(), dim=-1).float().numpy()
        del lg
    ref.flush()
    print(f"reference log-probs: vocab {V}, {ref.nbytes/1e9:.2f} GB", flush=True)

    def kl_raw():
        tot, cnt = 0.0, 0
        for i in range(KLWIN):
            lg = model(win[i:i + 1]).logits[0]
            for a in range(0, SEQLEN, CHUNK):
                b = min(a + CHUNK, SEQLEN)
                lpr = torch.from_numpy(
                    np.asarray(ref[i * SEQLEN + a: i * SEQLEN + b])).double()
                lpq = F.log_softmax(lg[a:b].double(), dim=-1)
                tot += float((lpr.exp() * (lpr - lpq)).sum())
                cnt += b - a
                del lpr, lpq
            del lg
        return tot / cnt

    apply(None)
    kl_self = kl_raw()
    print(f"self-KL (fp32 vs fp32) = {kl_self:.3e}  "
          f"{'OK' if abs(kl_self) < 1e-9 else 'INSTRUMENT BROKEN'}", flush=True)
    if abs(kl_self) >= 1e-9:
        return 4

    nkl = [0]

    def kl_of(lv):
        t38(lv)
        apply(lv)
        nkl[0] += 1
        return kl_raw()

    t0 = time.time()
    kl_mx = kl_of(MXFP4)
    dt = time.time() - t0
    print(f"KL(MXFP4) = {kl_mx:.6f}   one evaluation costs {dt:.1f}s", flush=True)

    # ---- coordinate descent, kl_optimal_codebook.py's shape ----------------
    seeds = [("MXFP4", MXFP4)]
    if os.environ.get("SEEDS", "mxfp4") == "both":
        seeds.append(("Lloyd-Max", LLOYD))

    runs = []
    for seed_name, seed in seeds:
        lv = list(seed)
        cur = kl_mx if seed_name == "MXFP4" else kl_of(lv)
        start = cur
        print(f"\nsearching from {seed_name}: KL {cur:.6f}", flush=True)
        evals = 0
        step = 0.06
        trace = []
        while evals < EVALS and step > 0.004:
            improved = False
            for i in range(1, len(lv) - 1):          # interior points only
                for d in (+step, -step):
                    cand = list(lv)
                    cand[i] = cand[i] + d
                    lo, hi = cand[i - 1] + 1e-3, cand[i + 1] - 1e-3
                    if not (lo < cand[i] < hi):
                        continue
                    v = kl_of(cand)
                    evals += 1
                    if v < cur - 1e-7:
                        lv, cur, improved = cand, v, True
                        trace.append({"eval": evals, "step": step, "i": i,
                                      "kl": v, "levels": list(lv)})
                        print(f"   eval {evals:3d} step {step:.4f} i={i} "
                              f"KL {v:.6f}  {[round(x,6) for x in lv]}", flush=True)
                    if evals >= EVALS:
                        break
                if evals >= EVALS:
                    break
            if not improved:
                step /= 2
        print(f"  {evals} evaluations, KL {start:.6f} -> {cur:.6f}", flush=True)
        runs.append({"seed": seed_name, "evals": evals, "kl_start": start,
                     "kl": cur, "levels": t38(lv), "trace": trace})

    best = min(runs, key=lambda x: x["kl"])
    print(f"\nFIT-{MDIR} (from {best['seed']}): "
          f"{[round(x,6) for x in best['levels']]}   KL {best['kl']:.6f}"
          f"   (MXFP4 {kl_mx:.6f}, {100*(best['kl']/kl_mx-1):+.2f}%)", flush=True)

    apply(None)
    del ref
    os.unlink(ref_path)

    out = {"model": MDIR, "nwin": NWIN, "klwin": KLWIN, "vocab": V,
           "evals_budget": EVALS, "self_kl": kl_self,
           "ruler_reproduces": True, "ruler_window_drift": drift, "wtol": WTOL,
           "kl_mxfp4": kl_mx, "kl_evaluations_total": nkl[0],
           "runs": runs, "fitted": best["levels"], "fitted_seed": best["seed"],
           "fitted_kl": best["kl"],
           "ppl": {"fp32": float(np.exp(nll["fp32"].mean())),
                   "MXFP4": float(np.exp(nll["MXFP4"].mean()))},
           "per_window_nll": {k: list(map(float, v)) for k, v in nll.items()}}
    dst = os.path.join(HERE, f"onefit_kl_{MDIR}.json")
    json.dump(out, open(dst, "w"), indent=1)
    print(f"wrote {dst}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
