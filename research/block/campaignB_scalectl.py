#!/usr/bin/env python3
"""CAMPAIGN B control: is the learned-codebook class handicapped by OUR scale?

The main campaign runs NF4 and BOF4 under this repository's E8M0 shared scale,
which rounds UP to a power of two. NF4 and BOF4 were both designed for a
REAL-VALUED absolute block maximum, under which the block max lands on exactly
+-1 and the pinned top level is used by construction. Under E8M0 the normalised
block max lands anywhere in (0.5, 1.0], so the top of every codebook is
systematically under-used. That is a property of the harness, not of the
codebooks, and it is the obvious objection to the main result.

So run the same arms again under the scale kind those formats were designed for.
This is NOT the repository's operating point and NOT equal budget with it -- a
real-valued scale is a BF16 number per block, 16 b/32 = 0.5 b/elem, so every arm
here costs 4.5 b/elem against 4.25 b/elem for E8M0. Within this control all arms
pay the same, so the RANKING is what it can speak to.

Two instrument checks run before any number is quoted:
  1. quant_gen(e8m0, mirror(mag)) must equal the harness quant(mag) EXACTLY --
     the same assertion the main campaign makes, so this file is on the harness
     path and not a private reimplementation.
  2. Under a real-valued absmax scale, T38's headroom phase must VANISH:
     quantising with a codebook and with that codebook scaled by any constant
     must give bit-identical results, because top divides out exactly. This is
     T38's own claim ("a real-valued scale has no headroom phase at all"), and
     here it is an assertion rather than a remark.

    MDIR=smollm2 NWIN=40 python3 campaignB_scalectl.py
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
quant, perplexity, target_modules, load_wikitext = (
    ns[k] for k in ("quant", "perplexity", "target_modules", "load_wikitext"))
fp_levels, q_e8m0_t = ns["fp_levels"], ns["q_e8m0_t"]
K, SEQLEN = ns["K"], ns["SEQLEN"]
W = os.path.dirname(ns["MODEL"])

sys.path.insert(0, HERE)
from campaignB_derive import NF4_PUBLISHED, BOF4S_PUB_I32          # noqa: E402

torch.set_grad_enabled(False)
NWIN = int(os.environ.get("NWIN", "40"))
MDIR = os.environ.get("MDIR", "smollm2")

FP32_RULER = {"smollm2": (40, 14.4874), "qwen": (20, 12.6999),
              "pythia": (40, 25.9561)}


def quant_gen(w, lv, scale_kind="e8m0", signed_scale=False):
    """Block quantiser, generalised over the SHARED SCALE KIND.

    scale_kind='e8m0'  -> s = 2^ceil(log2(a_max / top)), the repository's rule.
    scale_kind='real'  -> s = a_max / top, a real number per block (BF16 in the
                          NF4/BOF4 literature). No rounding, so no headroom phase.
    signed_scale=True  -> BOF4-S's signed block maximum (their eq. 4). Under a
                          REAL scale the sign is just the float's own sign bit,
                          so unlike the E8M0 case it costs NOTHING extra -- which
                          is exactly the paper's setting (they note that double
                          quantisation would be what forces the extra bit).

    Decision rule and tie rule are the harness's: midpoint boundaries, ties
    toward zero on both sides of the origin.
    """
    lv_t = torch.tensor(sorted(lv), dtype=torch.float64)
    top = float(lv_t.abs().max())
    n = (w.shape[1] // K) * K
    if n == 0:
        return w
    head = w[:, :n].reshape(-1, K).double()
    amax, arg = head.abs().max(dim=1)
    if signed_scale:
        m = torch.gather(head, 1, arg[:, None])[:, 0]
        sgn = torch.where(m < 0, -1.0, 1.0).double()
        mag = (m.abs() / top).clamp(min=1e-30)
    else:
        sgn = 1.0
        mag = (amax / top).clamp(min=1e-30)
    if scale_kind == "e8m0":
        s = q_e8m0_t(mag).clamp(min=1e-30) * sgn
    elif scale_kind == "real":
        s = mag.clamp(min=1e-30) * sgn
    else:
        raise ValueError(scale_kind)
    y = head / s[:, None]
    bnd = (lv_t[:-1] + lv_t[1:]) / 2
    idx = torch.where(y < 0,
                      torch.bucketize(y, bnd, right=True),
                      torch.bucketize(y, bnd, right=False))
    rec = lv_t[idx] * s[:, None]
    out = w.clone()
    out[:, :n] = rec.reshape(-1, n).to(w.dtype)
    return out


def mirror(mag):
    return sorted(set([-x for x in mag if x != 0.0] + list(mag)))


def norm_top1(lv):
    v = sorted(float(x) for x in lv)
    t = max(abs(x) for x in v)
    return [x / t for x in v]


MXFP4 = norm_top1(fp_levels(2, 1))
LLOYD = norm_top1([0.0, 0.10334, 0.21079, 0.32491, 0.44963,
                   0.59031, 0.75635, 0.96567])
NF4 = norm_top1(NF4_PUBLISHED)
BOF4S_PUB = norm_top1(BOF4S_PUB_I32)
CB = json.load(open(os.path.join(HERE, "campaignB_codebooks.json")))
BOF4_SMOL = norm_top1(CB["BOF4_smollm2"])
BOF4S_SMOL = norm_top1(CB["BOF4S_smollm2"])


def main():
    from transformers import AutoModelForCausalLM, AutoTokenizer
    path = os.path.join(W, MDIR)
    print(f"model={MDIR}  NWIN={NWIN}  K={K}  SEQLEN={SEQLEN}", flush=True)
    tok = AutoTokenizer.from_pretrained(path)
    model = AutoModelForCausalLM.from_pretrained(path, dtype=torch.float32)
    model.eval()
    ids = tok(load_wikitext(), return_tensors="pt").input_ids
    flat = ids.reshape(-1)
    win = flat[:(flat.numel() // SEQLEN) * SEQLEN].view(-1, SEQLEN)
    lins = target_modules(model)
    print(f"{len(lins)} linear tensors quantised (lm_head excluded)", flush=True)

    # ---- instrument check 1: this file is on the harness path --------------
    print("\n=== check 1: quant_gen(e8m0) == harness quant() ===", flush=True)
    for nm, mag in (("MXFP4", MXFP4), ("Lloyd-Max", LLOYD)):
        worst = 0.0
        for _, m in lins:
            w = m.weight.detach()
            worst = max(worst, float((quant(w, mag) -
                                      quant_gen(w, mirror(mag), "e8m0")
                                      ).abs().max()))
        print(f"  {nm:<12} max|diff| = {worst:.3e}")
        assert worst == 0.0, f"{nm}: not the harness map"

    # ---- instrument check 2: T38 says a real scale has no phase ------------
    print("\n=== check 2: under a REAL scale the headroom phase vanishes ===")
    print("    (codebook scaled by an arbitrary constant must be bit-identical)")
    for nm, lv in (("NF4", NF4), ("MXFP4", MXFP4)):
        for c in (6.0, 0.96567, 0.5):
            worst = 0.0
            for _, m in lins[:20]:
                w = m.weight.detach()
                a = quant_gen(w, lv, "real")
                b = quant_gen(w, [x * c for x in lv], "real")
                worst = max(worst, float((a - b).abs().max()))
            assert worst == 0.0, f"{nm} x{c}: real scale IS phase-sensitive"
        print(f"  {nm:<12} invariant to codebook rescaling  (0.000e+00)")
    print("  -> so under 'real' the T38 normalisation is a no-op, and every")
    print("     arm below is compared on SHAPE alone, by construction.",
          flush=True)

    ARMS = [
        ("MXFP4 (E2M1)",                   MXFP4,      "mag8",  False),
        ("Lloyd-Max (MSE opt, 8 mag)",     LLOYD,      "sgn15", False),
        ("NF4 (bitsandbytes, 16 lvl)",     NF4,        "sgn16", False),
        ("BOF4 (my impl, smollm2-fit)",    BOF4_SMOL,  "sgn16", False),
        ("BOF4-S (my impl, smollm2-fit)",  BOF4S_SMOL, "sgn16", True),
        ("BOF4-S paper Table7 I=32",       BOF4S_PUB,  "sgn16", True),
    ]
    for lab, lv, kind, ss in ARMS:
        t = max(abs(x) for x in lv)
        assert abs(t - 1.0) < 1e-12, lab
        assert len(lv) == {"mag8": 8, "sgn15": 15, "sgn16": 16}[kind], lab

    orig = {n: m.weight.detach().clone() for n, m in lins}

    def per_window():
        return np.array([math.log(perplexity(model, win[i], 1))
                         for i in range(NWIN)], dtype=np.float64)

    results, nlls = {}, {}
    nll0 = per_window()
    base = float(np.exp(nll0.mean()))
    nlls["fp32"], results["fp32"] = nll0, base
    nw_exp, ppl_exp = FP32_RULER[MDIR]
    ok = (NWIN == nw_exp) and abs(base - ppl_exp) / ppl_exp < 5e-4
    print(f"\nfp32 = {base:.4f}  (ruler {ppl_exp}, "
          f"{'OK' if ok else 'MISMATCH'})", flush=True)

    for lab, lv, kind, ss in ARMS:
        # The E8M0 column is already measured by campaignB_measure.py in the
        # identical harness; re-running every arm here would only burn time.
        # MXFP4 IS re-run under E8M0 as a cross-process consistency check --
        # it must land on the ruler 21.9397 / 15.4374 / 47.6504 again.
        kinds = ("e8m0", "real") if lab.startswith("MXFP4") else ("real",)
        for scale_kind in kinds:
            key = f"{lab} | {scale_kind}"
            t0 = time.time()
            for n, m in lins:
                if kind == "mag8" and scale_kind == "e8m0":
                    m.weight.copy_(quant(orig[n], lv))       # harness path
                else:
                    m.weight.copy_(quant_gen(orig[n], mirror(lv) if kind == "mag8"
                                             else lv, scale_kind,
                                             signed_scale=ss))
            v = per_window()
            nlls[key], results[key] = v, float(np.exp(v.mean()))
            print(f"  {key:<45}{results[key]:>10.4f}  ({time.time()-t0:.0f}s)",
                  flush=True)
    for n, m in lins:
        m.weight.copy_(orig[n])

    mxe = results["MXFP4 (E2M1) | e8m0"]
    mxr = results["MXFP4 (E2M1) | real"]
    print(f"\nMXFP4 E8M0 re-measured here = {mxe:.4f} "
          f"(main campaign / ruler must agree)")
    print("\n" + "=" * 76)
    print(f"{'arm (REAL absmax scale, 4.5 b/elem)':<40}{'ppl':>12}"
          f"{'vs MXFP4-real':>16}")
    print("=" * 76)
    out_rows = {}
    for lab, lv, kind, ss in ARMS:
        r = results[f"{lab} | real"]
        out_rows[lab] = dict(real=r, pct_real=100 * (r / mxr - 1))
        print(f"{lab:<40}{r:>12.4f}{100*(r/mxr-1):>+15.2f}%")

    # paired per-window tests under the real scale, vs MXFP4-real
    from scipy import stats
    print("\nPAIRED per-window vs MXFP4, REAL scale "
          f"(n={NWIN} windows, {MDIR})")
    pair = {}
    mxr_n = nlls["MXFP4 (E2M1) | real"]
    for lab, lv, kind, ss in ARMS:
        if lab.startswith("MXFP4"):
            continue
        d = nlls[f"{lab} | real"] - mxr_n
        n = len(d)
        mean, se = float(d.mean()), float(d.std(ddof=1) / math.sqrt(n))
        t = mean / se
        p = float(2 * stats.t.sf(abs(t), n - 1))
        c = float(stats.t.ppf(0.975, n - 1))
        pair[lab] = dict(pct=100 * (math.exp(mean) - 1),
                         lo=100 * (math.exp(mean - c * se) - 1),
                         hi=100 * (math.exp(mean + c * se) - 1),
                         t=t, p=p, nbetter=int((d < 0).sum()), n=n)
        s = pair[lab]
        print(f"  {lab:<34}{s['pct']:>+8.2f}%  "
              f"CI[{s['lo']:+.2f},{s['hi']:+.2f}]  t={s['t']:+.2f}  "
              f"p={s['p']:.3g}  better {s['nbetter']}/{n}")

    dst = os.path.join(HERE, f"campaignB_scalectl_{MDIR}.json")
    json.dump({"model": MDIR, "nwin": NWIN, "fp32": base,
               "fp32_ruler_ok": bool(ok), "ppl": results, "rows": out_rows,
               "paired_real_vs_mxfp4": pair,
               "per_window_nll": {k: list(map(float, v))
                                  for k, v in nlls.items()}},
              open(dst, "w"), indent=1)
    print(f"\nwrote {dst}")
    return 0 if ok else 2


if __name__ == "__main__":
    sys.exit(main())
