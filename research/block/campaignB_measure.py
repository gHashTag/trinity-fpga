#!/usr/bin/env python3
"""CAMPAIGN B -- the learned-codebook baselines nobody ran here: NF4 and BOF4.

Every comparison in this repository is against MXFP4, a hardware format. The
class this work belongs to is LEARNED ELEMENT CODEBOOKS, whose leaders are NF4
(QLoRA) and BOF4 (arXiv:2505.06653). This runs them in OUR harness, at OUR block
size, under OUR scale convention, beside MXFP4 and Lloyd-Max.

MEASUREMENT PATH IS NOT REIMPLEMENTED. quant, perplexity, target_modules and
load_wikitext are taken from block_tnf.py by executing its source up to the
driver marker. ONE function is added -- quant_signed -- because the harness
quant() takes 8 MAGNITUDES and applies sign(w), which cannot express a 16-level
ASYMMETRIC book. It is validated, not trusted: on a mirrored symmetric book it
must reproduce quant() to 0.000e+00 over every weight of the model under test,
and that assertion runs on every model before any number is quoted.
(campaignB_probe.py found the one way they differed -- exact dyadic ties at
y = -0.125, 94462 elements in SmolLM2 -- and the tie rule now matches.)

T38 (SCALE_PHASE_THEOREM): every codebook is asserted to have top MAGNITUDE
exactly 1.0, so all arms sit at headroom phase phi = 0 and the comparison cannot
confound codebook shape with headroom waste.

BIT BUDGETS ARE EXPLICIT. All arms spend 4 bits per element (16 codes). The
8-magnitude books spend those 16 codes on 15 distinct values (+-7 magnitudes and
zero); NF4/BOF4 spend them on 16 distinct values. Shared scale is E8M0 = 8 bits
per 32 elements = 0.25 b/elem, except BOF4-S whose SIGNED block maximum needs one
extra bit per block = 0.28125 b/elem. That arm is therefore NOT at equal budget
and is marked.

    MDIR=smollm2 NWIN=40 python3 campaignB_measure.py
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
from campaignB_derive import (bof4_em, blocks_to_xw, make_init,   # noqa: E402
                              FIXED_BOF4, FIXED_BOF4S, derive_nf4,
                              NF4_PUBLISHED, BOF4S_PUB_I32)

torch.set_grad_enabled(False)
NWIN = int(os.environ.get("NWIN", "40"))
MDIR = os.environ.get("MDIR", "smollm2")
NBLK_FIT = 1 << 20


# ---------------------------------------------------------------------------
def quant_signed(w, lv, signed_scale=False):
    """Block quantiser for a FULL signed codebook (levels may be asymmetric).

    Same K, same E8M0 shared scale, same midpoint decision rule and same
    ties-toward-zero rule as quant(). Two differences, both forced by format:
      * the level table carries its own signs, so no sign(w) factor;
      * signed_scale=True is BOF4-S's signed block maximum (their eq. 4), which
        costs ONE EXTRA BIT per block -- charged in the bit-budget column.
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
        s = q_e8m0_t((m.abs() / top).clamp(min=1e-30)).clamp(min=1e-30) * sgn
    else:
        s = q_e8m0_t((amax / top).clamp(min=1e-30)).clamp(min=1e-30)
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


# ---- codebooks ------------------------------------------------------------
MXFP4 = norm_top1(fp_levels(2, 1))
LLOYD = norm_top1([0.0, 0.10334, 0.21079, 0.32491, 0.44963,
                   0.59031, 0.75635, 0.96567])
NF4 = norm_top1(NF4_PUBLISHED)
# bitsandbytes create_normal_map(use_extra_value=False): the SYMMETRIC 15-level
# NormalFloat. Isolates NF4's Gaussian-quantile SHAPE from its asymmetry.
from scipy.stats import norm as _norm  # noqa: E402
_p = _norm.ppf(np.linspace(0.5, 0.9677083, 8)).tolist()
NF4SYM = norm_top1(sorted(set([-x for x in _p if x != 0.0] + _p)))

CB = json.load(open(os.path.join(HERE, "campaignB_codebooks.json")))
BOF4_SMOL = norm_top1(CB["BOF4_smollm2"])
BOF4S_SMOL = norm_top1(CB["BOF4S_smollm2"])
BOF4S_PUB = norm_top1(BOF4S_PUB_I32)

RULERS = {
    "smollm2": {"nwin": 40, "fp32": 14.4874, "MXFP4 (E2M1)": 21.9397,
                "Lloyd-Max (MSE opt, 8 mag)": 22.9166},
    "qwen":    {"nwin": 20, "fp32": 12.6999, "MXFP4 (E2M1)": 15.4374,
                "Lloyd-Max (MSE opt, 8 mag)": 16.0703},
    "pythia":  {"nwin": 40, "fp32": 25.9561, "MXFP4 (E2M1)": 47.6504,
                "Lloyd-Max (MSE opt, 8 mag)": 52.9992},
}


def fit_bof4(lins, tag, signed, seed=0):
    """Run BOF4's EM on THIS model's own weight distribution."""
    chunks = []
    for _, m in lins:
        w = m.weight.detach()
        c = (w.shape[1] // K) * K
        if c:
            chunks.append(w[:, :c].reshape(-1, K).clone())
    allb = torch.cat(chunks, 0)
    del chunks
    g = torch.Generator().manual_seed(seed)
    nb = min(NBLK_FIT, allb.shape[0])
    blk = allb[torch.randperm(allb.shape[0], generator=g)[:nb]].contiguous()
    del allb
    x, wsq = blocks_to_xw(blk, signed=signed)
    fixed = FIXED_BOF4S if signed else FIXED_BOF4
    lv = bof4_em(x, wsq, fixed, make_init(fixed), tag=tag)
    del x, wsq, blk
    return norm_top1(lv)


def main():
    from transformers import AutoModelForCausalLM, AutoTokenizer
    path = os.path.join(W, MDIR)
    print(f"model={MDIR}  NWIN={NWIN}  K={K}  SEQLEN={SEQLEN}", flush=True)
    tok = AutoTokenizer.from_pretrained(path)
    model = AutoModelForCausalLM.from_pretrained(path, dtype=torch.float32)
    model.eval()
    ids = tok(load_wikitext(), return_tensors="pt").input_ids
    flat = ids.reshape(-1)
    ntot = flat.numel() // SEQLEN
    win = flat[:ntot * SEQLEN].view(-1, SEQLEN)
    if ntot < NWIN:
        raise SystemExit(f"only {ntot} windows, need {NWIN}")
    lins = target_modules(model)
    print(f"{len(lins)} linear tensors quantised (lm_head excluded)", flush=True)
    if not lins:
        raise SystemExit("zero target modules")

    # ---- BOF4 fitted to THIS model (in-sample upper bound for the class) ----
    print("\n=== BOF4 EM fitted to THIS model's weights (in-sample arm) ===",
          flush=True)
    bof4_self = fit_bof4(lins, f"BOF4(MSE) {MDIR}", signed=False)

    ARMS = [
        # (label, levels, signed_scale, kind, elem_bits, scale_bits_per_block,
        #  fitted_on)
        ("MXFP4 (E2M1)", MXFP4, False, "mag8", 4, 8, "hand-designed"),
        ("Lloyd-Max (MSE opt, 8 mag)", LLOYD, False, "mag8", 4, 8, "smollm2"),
        ("NF4 (bitsandbytes, 16 lvl)", NF4, False, "sgn16", 4, 8, "N(0,1) prior"),
        ("NF4-sym (15 lvl, 8 mag)", NF4SYM, False, "sgn15", 4, 8, "N(0,1) prior"),
        ("BOF4 (my impl of their method)", BOF4_SMOL, False, "sgn16", 4, 8,
         "smollm2"),
        ("BOF4-S (signed scale, +1b/blk)", BOF4S_SMOL, True, "sgn16", 4, 9,
         "smollm2"),
        ("BOF4-S paper Table7 I=32", BOF4S_PUB, True, "sgn16", 4, 9,
         "N(0,1) Gaussian"),
        (f"BOF4 refit on {MDIR} (IN-SAMPLE)", bof4_self, False, "sgn16", 4, 8,
         MDIR),
    ]

    # ---- T38 + budget assertions ------------------------------------------
    print("\n=== T38 phase check: every book top magnitude exactly 1.0 ===")
    for lab, lv, ss, kind, eb, sb, fit in ARMS:
        assert lv == sorted(lv), lab
        assert 0.0 in lv or -0.0 in lv, f"{lab}: no zero level"
        t = max(abs(x) for x in lv)
        assert abs(t - 1.0) < 1e-12, f"{lab}: top={t} -> phase phi != 0"
        assert abs(math.log2(t) % 1.0) < 1e-12, lab
        exp_n = {"mag8": 8, "sgn15": 15, "sgn16": 16}[kind]
        assert len(lv) == exp_n, f"{lab}: {len(lv)} levels, expected {exp_n}"
        assert len(lv) <= 16, lab
        print(f"  {lab:<34} n={len(lv):2d} top={t:.12f} phi=0 "
              f"budget={eb + sb / K:.5f} b/elem")

    # ---- the new code path must equal the harness path on THIS model -------
    print("\n=== quant_signed validated against harness quant() on "
          f"{MDIR} weights ===")
    for nm, mag in (("MXFP4", MXFP4), ("Lloyd-Max", LLOYD)):
        worst = 0.0
        for _, m in lins:
            w = m.weight.detach()
            worst = max(worst, float((quant(w, mag)
                                      - quant_signed(w, mirror(mag))).abs().max()))
        print(f"  {nm:<12} max|quant - quant_signed(mirror)| = {worst:.3e}")
        assert worst == 0.0, f"{nm}: new path is not the harness map"
    print("  -> identical map, so any difference below is the CODEBOOK", flush=True)

    orig = {n: m.weight.detach().clone() for n, m in lins}

    def per_window():
        return np.array([math.log(perplexity(model, win[i], 1))
                         for i in range(NWIN)], dtype=np.float64)

    results, nlls = {}, {}
    for n, m in lins:
        m.weight.copy_(orig[n])
    t0 = time.time()
    nll0 = per_window()
    base = float(np.exp(nll0.mean()))
    nlls["fp32"], results["fp32"] = nll0, base
    whole = perplexity(model, win[:NWIN].reshape(1, -1), NWIN)
    print(f"\nfp32 = {base:.4f}  ({time.time()-t0:.0f}s)")
    print(f"  identity check: whole-slice = {whole:.6f}  "
          f"exp(mean per-window nll) = {base:.6f}  "
          f"rel {abs(whole-base)/base:.2e}", flush=True)
    assert abs(whole - base) / base < 1e-9, "per-window decomposition wrong"

    for lab, lv, ss, kind, eb, sb, fit in ARMS:
        t0 = time.time()
        for n, m in lins:
            m.weight.copy_(quant(orig[n], lv) if kind == "mag8"
                           else quant_signed(orig[n], lv, signed_scale=ss))
        v = per_window()
        nlls[lab], results[lab] = v, float(np.exp(v.mean()))
        print(f"{lab:<34}{results[lab]:>10.4f}  ({time.time()-t0:.0f}s)",
              flush=True)
    for n, m in lins:
        m.weight.copy_(orig[n])

    # ---- RULER CHECK -------------------------------------------------------
    ok = True
    r = RULERS.get(MDIR)
    print("\n=== RULER CHECK (must reproduce or nothing counts) ===")
    if r is None or r["nwin"] != NWIN:
        print(f"  no reference for MDIR={MDIR} NWIN={NWIN}")
        ok = False
    else:
        for key in ("fp32", "MXFP4 (E2M1)", "Lloyd-Max (MSE opt, 8 mag)"):
            got, exp_ = results[key], r[key]
            d = abs(got - exp_) / exp_
            good = d < 5e-4
            ok &= good
            print(f"  {key:<34} got {got:>9.4f} expected {exp_:>9.4f} "
                  f"rel {d:.2e} {'OK' if good else 'MISMATCH'}")
    print(f"  RULERS {'REPRODUCE' if ok else 'DO NOT REPRODUCE'}", flush=True)

    # ---- paired per-window tests vs MXFP4 ----------------------------------
    mxn = nlls["MXFP4 (E2M1)"]
    mxp = results["MXFP4 (E2M1)"]
    print(f"\n{'arm':<34}{'ppl':>9}{'b/elem':>9}{'vs MXFP4':>10}"
          f"{'t':>9}{'better':>8}")
    print(f"{'fp32':<34}{base:>9.4f}{32.0:>9.2f}{'':>10}")
    pair = {}
    for lab, lv, ss, kind, eb, sb, fit in ARMS:
        d = nlls[lab] - mxn
        n = len(d)
        mean, sd = float(d.mean()), float(d.std(ddof=1))
        se = sd / math.sqrt(n)
        t = mean / se if se > 0 else float("nan")
        nb = int((d < 0).sum())
        pair[lab] = {"mean_dnll": mean, "sd": sd, "se": se, "t": t,
                     "df": n - 1, "n_better": nb, "n_worse": int((d > 0).sum()),
                     "pct_vs_mxfp4": 100 * (results[lab] / mxp - 1),
                     "bits_per_elem": eb + sb / K, "fitted_on": fit}
        print(f"{lab:<34}{results[lab]:>9.4f}{eb + sb / K:>9.5f}"
              f"{100*(results[lab]/mxp-1):>+9.2f}%{t:>+9.2f}{nb:>5d}/{n}",
              flush=True)

    out = {"model": MDIR, "nwin": NWIN, "rulers_reproduce": bool(ok),
           "ppl": results, "paired_vs_mxfp4": pair,
           "codebooks": {lab: lv for lab, lv, *_ in ARMS},
           "per_window_nll": {k: list(map(float, v)) for k, v in nlls.items()}}
    dst = os.path.join(HERE, f"campaignB_measure_{MDIR}.json")
    json.dump(out, open(dst, "w"), indent=1)
    print(f"\nwrote {dst}")
    return 0 if ok else 2


if __name__ == "__main__":
    sys.exit(main())
