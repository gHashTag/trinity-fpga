#!/usr/bin/env python3
"""Controls for campaign C. The main run says the Lloyd-Max -> KL path is rough.
Before that is believed, three things have to be ruled out.

  1. DETERMINISM. The whole claim is that the variation is surface structure and
     not measurement noise. That requires the same codebook to give the SAME
     perplexity on a re-run, with a fresh quantisation each time and no cache.
     If it does not, every roughness number in the campaign is noise.

  2. CONTINUITY AT SMALL SCALE. ppl as a function of the codebook should be
     continuous (bin boundaries move continuously). Perturbing one level by
     0.1%, 0.25%, 0.5% must produce correspondingly small, ordered changes. If a
     0.1% move produces a 1% perplexity jump, the surface is not merely steep --
     it is discontinuous, and nothing measured on it is stable.

  3. THE ROUGHNESS IS NOT AN ARTEFACT OF THE STEP SIZE. Fill in the midpoints of
     the roughest stretch of the interpolation. Genuine structure keeps the
     shape; an artefact of sampling every 0.1 will not.
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
OUT = os.path.join(HERE, f"campaignC_controls_{MDIR}.json")


def normalise(lv):
    v = sorted(float(x) for x in lv)
    v = [x / v[-1] for x in v]
    v[-1] = 1.0
    return v


def check(name, lv):
    assert len(lv) == 8 and lv[0] == 0.0, name
    assert all(lv[i] < lv[i + 1] for i in range(7)), (name, lv)
    assert abs(lv[-1] - 1.0) < 1e-12, f"{name}: top={lv[-1]}"
    return lv


MXFP4 = check("MXFP4", normalise(fp_levels(2, 1)))
LLOYD = check("Lloyd", normalise([0.0, 0.10334, 0.21079, 0.32491, 0.44963,
                                  0.59031, 0.75635, 0.96567]))
KL = check("KL", normalise([0.0, 0.07701, 0.18828, 0.31396, 0.46561,
                            0.6113, 0.79074, 1.0]))


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
    orig = {n: m.weight.detach().clone() for n, m in lins}
    log = {"model": MDIR, "nwin": NWIN}

    def measure(tag, lv):
        """NO CACHE -- every call re-quantises from the pristine weights."""
        t0 = time.time()
        for n, m in lins:
            m.weight.copy_(orig[n] if lv is None else quant(orig[n], lv))
        p = perplexity(model, win[:NWIN].reshape(1, -1), NWIN)
        for n, m in lins:
            m.weight.copy_(orig[n])
        print(f"  {tag:<40}{p:>12.8f}   ({time.time()-t0:.0f}s)", flush=True)
        return p

    print("=== CONTROL 1: DETERMINISM (same codebook, 3 fresh runs) ===",
          flush=True)
    reps = [measure(f"MXFP4 repeat {i+1}", MXFP4) for i in range(3)]
    spread = max(reps) - min(reps)
    log["determinism"] = {"reps": reps, "spread": spread}
    print(f"  spread across repeats = {spread:.3e} ppl "
          f"({100*spread/reps[0]:.2e}% )")
    det = spread < 1e-9
    print(f"  DETERMINISTIC: {det}"
          + ("" if det else "  <-- roughness claims are NOT safe"), flush=True)
    log["is_deterministic"] = bool(det)
    json.dump(log, open(OUT, "w"), indent=1)
    if not det:
        print("STOP: the instrument is not deterministic.")
        return 2
    mx = reps[0]

    print("\n=== CONTROL 2: CONTINUITY at 0.1% / 0.25% / 0.5% on level 3 ===",
          flush=True)
    cont = []
    for j in (3, 5):
        for d in (-0.005, -0.0025, -0.001, 0.001, 0.0025, 0.005):
            lv = list(MXFP4)
            lv[j] = MXFP4[j] * (1 + d)
            lv = check("c", normalise(lv))
            p = measure(f"level[{j}]={MXFP4[j]:.5f} {d:+.2%}", lv)
            cont.append({"level": j, "delta": d, "ppl": p,
                         "pct": 100 * (p / mx - 1)})
    log["continuity"] = cont
    json.dump(log, open(OUT, "w"), indent=1)
    print(f"\n  {'lvl':>4}{'delta':>9}{'ppl':>12}{'vs MXFP4':>11}"
          f"{'ppl% per 1% level':>20}")
    for c in cont:
        amp = c["pct"] / (100 * c["delta"])
        print(f"  {c['level']:>4}{c['delta']:>+9.3%}{c['ppl']:>12.4f}"
              f"{c['pct']:>+10.3f}%{amp:>19.3f}")

    print("\n=== CONTROL 3: fine interpolation, midpoints of [0.0,0.5] ===",
          flush=True)
    fine = []
    for t in (0.05, 0.15, 0.25, 0.35, 0.45):
        lv = check(f"t={t}", normalise(
            [(1 - t) * a + t * b for a, b in zip(LLOYD, KL)]))
        p = measure(f"interp t={t:.2f}", lv)
        fine.append({"t": t, "ppl": p})
    log["fine_interp"] = fine
    json.dump(log, open(OUT, "w"), indent=1)

    coarse = {0.0: 22.9166, 0.1: 23.7232, 0.2: 22.2948, 0.3: 22.7628,
              0.4: 21.5832, 0.5: 22.0202}
    print(f"\n  {'t':>6}{'ppl':>11}   (* = newly measured midpoint)")
    allpts = sorted([(k, v, "") for k, v in coarse.items()]
                    + [(f["t"], f["ppl"], " *") for f in fine])
    for t, p, mark in allpts:
        print(f"  {t:>6.2f}{p:>11.4f}{mark}")
    d = np.diff([p for _, p, _ in allpts])
    print(f"\n  sign changes along the refined path: "
          f"{int((np.sign(d[:-1]) != np.sign(d[1:])).sum())} of {len(d)-1}")
    print(f"  refined step range: {d.min():+.4f} .. {d.max():+.4f} ppl")
    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
