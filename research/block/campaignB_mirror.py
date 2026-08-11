#!/usr/bin/env python3
"""CAMPAIGN B instrument check: is NF4's win a DIRECTIONAL artefact?

Campaign B measured, on SmolLM2:
    NF4-sym (15 lvl, coarse grid both sides)   +0.61 % vs MXFP4  (a tie)
    NF4     (16 lvl, FINE grid on the POSITIVE side only)  -8.77 % vs MXFP4

and the two books are related exactly: NF4-sym IS NF4's coarse negative branch
mirrored. So the whole 9-point swing comes from replacing the coarse 7-level
positive branch with a fine 8-level one. That is a large effect from one extra
level on ONE SIDE of a weight distribution that ought to be symmetric, and the
obvious failure mode is that something in the harness treats positive and
negative weights differently -- a sign convention, a tie rule, a bucketize
`right=` flag.

The test that separates "real codebook effect" from "directional artefact":
NEGATE the whole NF4 table. NF4-mirror has the fine 8-level branch on the
NEGATIVE side and the coarse 7-level branch on the positive side. Under a
symmetric weight distribution the two must land in the same place. If they do
not, the number is an artefact of the instrument and Campaign B's NF4 row is
withdrawn.

Also reported, with no forward pass: the skewness of the normalised weights the
codebook actually sees, and the occupancy of every level -- so "the distribution
is symmetric" is measured here rather than assumed.

    python3 campaignB_mirror.py
"""
import json
import math
import os
import sys
import time

import numpy as np
import torch

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import campaignB_measure as B  # noqa: E402  (loads the harness path, no model)

quant, perplexity, target_modules = B.quant, B.perplexity, B.target_modules
quant_signed, norm_top1 = B.quant_signed, B.norm_top1
K, SEQLEN, W = B.K, B.SEQLEN, B.W

torch.set_grad_enabled(False)
NWIN = int(os.environ.get("NWIN", "40"))
MDIR = os.environ.get("MDIR", "smollm2")
RULER = {"smollm2": 14.4874, "qwen": 12.6999, "pythia": 25.9561}[MDIR]
MXRULER = {"smollm2": 21.9397, "qwen": 15.4374, "pythia": 47.6504}[MDIR]

NF4 = B.NF4
NF4_MIRROR = sorted(-x for x in NF4)


def main():
    from transformers import AutoModelForCausalLM, AutoTokenizer
    path = os.path.join(W, MDIR)
    print(f"model={MDIR} NWIN={NWIN} K={K}", flush=True)
    tok = AutoTokenizer.from_pretrained(path)
    model = AutoModelForCausalLM.from_pretrained(path, dtype=torch.float32)
    model.eval()
    ids = tok(B.load_wikitext(), return_tensors="pt").input_ids
    flat = ids.reshape(-1)
    win = flat[:(flat.numel() // SEQLEN) * SEQLEN].view(-1, SEQLEN)
    lins = target_modules(model)

    # ---- T38 + structure assertions ---------------------------------------
    for lab, lv in (("NF4", NF4), ("NF4-mirror", NF4_MIRROR)):
        assert lv == sorted(lv), lab
        assert len(lv) == 16, lab
        assert abs(max(abs(x) for x in lv) - 1.0) < 1e-12, f"{lab}: top != 1.0"
        assert 0.0 in lv, lab
        npos = sum(1 for x in lv if x > 0)
        nneg = sum(1 for x in lv if x < 0)
        print(f"  {lab:<12} top=1.0 (phi=0)  {npos} positive / {nneg} negative "
              f"levels", flush=True)
    assert NF4_MIRROR == sorted(-x for x in NF4)
    assert sum(1 for x in NF4 if x > 0) == 8
    assert sum(1 for x in NF4_MIRROR if x < 0) == 8

    # ---- is the weight distribution the books see actually symmetric? ------
    print("\n=== the normalised weights the codebook sees (no forward pass) ===")
    tot = n_pos = 0
    s1 = s2 = s3 = 0.0
    occ_nf4 = np.zeros(16, dtype=np.int64)
    occ_mir = np.zeros(16, dtype=np.int64)
    t_nf4 = torch.tensor(NF4, dtype=torch.float64)
    t_mir = torch.tensor(NF4_MIRROR, dtype=torch.float64)
    b_nf4 = (t_nf4[:-1] + t_nf4[1:]) / 2
    b_mir = (t_mir[:-1] + t_mir[1:]) / 2
    for _, m in lins:
        w = m.weight.detach()
        c = (w.shape[1] // K) * K
        if c == 0:
            continue
        head = w[:, :c].reshape(-1, K).double()
        s = B.q_e8m0_t((head.abs().amax(dim=1)).clamp(min=1e-30)).clamp(min=1e-30)
        y = (head / s[:, None]).reshape(-1)
        tot += y.numel()
        n_pos += int((y > 0).sum())
        s1 += float(y.sum())
        s2 += float((y * y).sum())
        s3 += float((y ** 3).sum())
        for t, bnd, occ in ((t_nf4, b_nf4, occ_nf4), (t_mir, b_mir, occ_mir)):
            idx = torch.where(y < 0, torch.bucketize(y, bnd, right=True),
                              torch.bucketize(y, bnd, right=False))
            occ += np.bincount(idx.numpy(), minlength=16)
    mean = s1 / tot
    var = s2 / tot - mean * mean
    skew = (s3 / tot - 3 * mean * var - mean ** 3) / var ** 1.5
    print(f"  N = {tot}   fraction > 0 = {n_pos/tot:.6f}   "
          f"mean = {mean:.3e}   skewness = {skew:+.5f}")
    print("  -> a symmetric distribution has fraction 0.5 and skewness 0; "
          "NF4 and NF4-mirror must then tie.")
    print("\n  level        NF4 value   occupancy      mirror value   occupancy")
    for i in range(16):
        print(f"   {i:2d}     {NF4[i]:+.6f}   {occ_nf4[i]/tot:9.6f}      "
              f"{NF4_MIRROR[i]:+.6f}   {occ_mir[i]/tot:9.6f}")
    print(f"  occupancy of the 8 fine-branch levels: NF4 "
          f"{occ_nf4[8:].sum()/tot:.6f}  mirror {occ_mir[:8].sum()/tot:.6f}",
          flush=True)

    orig = {n: m.weight.detach().clone() for n, m in lins}

    def per_window():
        return np.array([math.log(perplexity(model, win[i], 1))
                         for i in range(NWIN)], dtype=np.float64)

    ARMS = [("MXFP4 (E2M1)", B.MXFP4, "mag8"),
            ("NF4 (published)", NF4, "sgn16"),
            ("NF4-mirror (negated table)", NF4_MIRROR, "sgn16")]
    nlls, ppl = {}, {}
    t0 = time.time()
    nlls["fp32"] = per_window()
    ppl["fp32"] = float(np.exp(nlls["fp32"].mean()))
    print(f"\nfp32 = {ppl['fp32']:.4f}  ({time.time()-t0:.0f}s)  "
          f"ruler {RULER}  rel {abs(ppl['fp32']-RULER)/RULER:.2e}", flush=True)
    assert abs(ppl["fp32"] - RULER) / RULER < 5e-4, "fp32 ruler missed"

    for lab, lv, kind in ARMS:
        t0 = time.time()
        for n, m in lins:
            m.weight.copy_(quant(orig[n], lv) if kind == "mag8"
                           else quant_signed(orig[n], lv))
        nlls[lab] = per_window()
        ppl[lab] = float(np.exp(nlls[lab].mean()))
        print(f"{lab:<30}{ppl[lab]:>10.4f}  ({time.time()-t0:.0f}s)", flush=True)
    for n, m in lins:
        m.weight.copy_(orig[n])
    d = abs(ppl["MXFP4 (E2M1)"] - MXRULER) / MXRULER
    print(f"MXFP4 ruler {MXRULER} rel {d:.2e} {'OK' if d < 5e-4 else 'MISMATCH'}")
    assert d < 5e-4, "MXFP4 ruler missed"

    from scipy import stats
    mx = nlls["MXFP4 (E2M1)"]
    print(f"\n{'arm':<30}{'ppl':>10}{'vs MXFP4':>11}{'t':>9}{'p':>10}{'better':>9}")
    out = {}
    for lab in ("NF4 (published)", "NF4-mirror (negated table)"):
        dd = nlls[lab] - mx
        t = dd.mean() / (dd.std(ddof=1) / math.sqrt(len(dd)))
        p = float(2 * stats.t.sf(abs(t), len(dd) - 1))
        out[lab] = dict(ppl=ppl[lab], pct=100 * (ppl[lab] / ppl["MXFP4 (E2M1)"] - 1),
                        t=float(t), p=p, nbetter=int((dd < 0).sum()))
        print(f"{lab:<30}{ppl[lab]:>10.4f}"
              f"{out[lab]['pct']:>+10.2f}%{t:>+9.2f}{p:>10.3g}"
              f"{out[lab]['nbetter']:>6}/{len(dd)}")

    dd = nlls["NF4-mirror (negated table)"] - nlls["NF4 (published)"]
    t = dd.mean() / (dd.std(ddof=1) / math.sqrt(len(dd)))
    p = float(2 * stats.t.sf(abs(t), len(dd) - 1))
    pct = 100 * (ppl["NF4-mirror (negated table)"] / ppl["NF4 (published)"] - 1)
    print(f"\nMIRROR TEST   NF4-mirror vs NF4: {pct:+.3f}%  t={t:+.2f}  p={p:.3g}")
    verdict = ("SYMMETRIC -- the win is the codebook, not a sign convention"
               if abs(pct) < 1.0 else
               "DIRECTIONAL -- the NF4 row is an instrument artefact, withdraw it")
    print(f"  -> {verdict}")

    json.dump({"model": MDIR, "nwin": NWIN, "ppl": ppl, "vs_mxfp4": out,
               "skewness": skew, "frac_positive": n_pos / tot,
               "mirror_vs_nf4_pct": pct, "mirror_t": float(t), "mirror_p": p,
               "verdict": verdict,
               "occupancy_nf4": (occ_nf4 / tot).tolist(),
               "occupancy_mirror": (occ_mir / tot).tolist(),
               "per_window_nll": {k: list(map(float, v)) for k, v in nlls.items()}},
              open(os.path.join(HERE, f"campaignB_mirror_{MDIR}.json"), "w"),
              indent=1)
    print(f"\nwrote campaignB_mirror_{MDIR}.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
