#!/usr/bin/env python3
"""Is Lloyd-Max the ceiling for perplexity, or only for squared error?

`BLOCK_AXIS_CLOSED_2026-08-10.md` closes the block axis on this argument:

> Lloyd-Max on the within-block distribution gives the eight-level codebook that
> minimises squared error. […] It is the ceiling.
> **No eight-level element format will take the block axis from MXFP4, because
> the best possible one does not.**

The measurement behind it is sound — Lloyd-Max reaches 22.2976 perplexity against
MXFP4's 22.4998, a 0.9 % edge, and is not implementable. But the *argument* has a
gap, and the same document supplies the evidence for it:

> Squared error and perplexity are nearly unrelated here. […] The correlation is
> not weak. It points the wrong way.

Lloyd-Max is the ceiling **for squared error**. If the two objectives disagree —
and `METRIC_DISAGREEMENT_2026-08-11.md` shows they disagree by sign under
rotation — then the squared-error optimum has no claim to being the perplexity
optimum, and "the best possible one" is unearned. A codebook optimised against
the objective that actually decides could sit above it.

This searches for one. Eight magnitudes, the first pinned at zero and the last at
one (the quantiser normalises by the top level, so only the six interior points
are free), optimised by coordinate descent against KL(fp32 ‖ quantised) — the
quantity perplexity is made of, and far cheaper to evaluate than a 40-window
perplexity.

Instrument check, run before any search: MXFP4 and Lloyd-Max must reproduce the
published 22.4998 and 22.2976 at 40 windows. If they do not, this script is not
measuring what that document measured and nothing below it means anything.

Outcome, either way, is worth having:
  - a codebook beating both on perplexity  -> the ceiling claim is wrong and the
    axis is not closed by that argument
  - no such codebook after a real search   -> the claim survives a test it had
    not been given, which is stronger than the argument it rests on now

    NWIN=40 EVALS=120 python3 kl_optimal_codebook.py
"""
import os
import sys

import numpy as np
import torch
import torch.nn.functional as F

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "block_tnf.py")
MARKER = 'print("загружаю модель…", flush=True)'
_src = open(SRC, encoding="utf-8").read()
if MARKER not in _src:
    raise SystemExit("kl_optimal_codebook: driver marker not found in block_tnf.py")
_ns = {}
exec(compile(_src.split(MARKER)[0], SRC, "exec"), _ns)

fp_levels = _ns["fp_levels"]
q_e8m0_t = _ns["q_e8m0_t"]
quant = _ns["quant"]
perplexity = _ns["perplexity"]
target_modules = _ns["target_modules"]
load_wikitext = _ns["load_wikitext"]
MODEL, K, SEQLEN = _ns["MODEL"], _ns["K"], _ns["SEQLEN"]

torch.set_grad_enabled(False)

NWIN = int(os.environ.get("NWIN", "40"))     # perplexity windows, as published
KLWIN = int(os.environ.get("KLWIN", "2"))    # windows used inside the search
EVALS = int(os.environ.get("EVALS", "120"))

MXFP4 = sorted(fp_levels(2, 1))
LLOYD = [0.0, 0.10334, 0.21079, 0.32491, 0.44963, 0.59031, 0.75635, 0.96567]
PUBLISHED = {"MXFP4": 22.4998, "Lloyd-Max": 22.2976, "fp32": 14.4874}


def normalise(lv):
    v = sorted(float(x) for x in lv)
    return [x / v[-1] for x in v]


def main():
    print("loading model…", flush=True)
    from transformers import AutoModelForCausalLM, AutoTokenizer
    tok = AutoTokenizer.from_pretrained(MODEL)
    model = AutoModelForCausalLM.from_pretrained(MODEL, dtype=torch.float32)
    model.eval()
    ids = tok(load_wikitext(), return_tensors="pt").input_ids
    lins = target_modules(model)
    orig = {n: m.weight.detach().clone() for n, m in lins}

    flat = ids.reshape(-1)
    win = flat[:(flat.numel() // SEQLEN) * SEQLEN].view(-1, SEQLEN)

    def apply(lv):
        if lv is None:
            for n, m in lins:
                m.weight.copy_(orig[n])
            return
        for n, m in lins:
            m.weight.copy_(quant(orig[n], lv))

    # reference logits for KL, from the untouched model
    apply(None)
    ref = torch.cat([model(win[i:i + 1]).logits.double() for i in range(KLWIN)])
    logp_ref = F.log_softmax(ref, dim=-1)
    p_ref = logp_ref.exp()

    def kl_of(lv):
        apply(lv)
        L = torch.cat([model(win[i:i + 1]).logits.double() for i in range(KLWIN)])
        return float((p_ref * (logp_ref - F.log_softmax(L, dim=-1))).sum(-1).mean())

    # ---- instrument: reproduce the published table ------------------------
    apply(None)
    base = perplexity(model, ids, NWIN)
    print(f"\nRULER  fp32 baseline = {base:.4f} (published {PUBLISHED['fp32']})")
    checks = []
    for name, lv in (("MXFP4", MXFP4), ("Lloyd-Max", LLOYD)):
        apply(lv)
        p = perplexity(model, ids, NWIN)
        ok = abs(p - PUBLISHED[name]) < 0.02
        checks.append(ok)
        print(f"RULER  {name:<10} = {p:.4f} (published {PUBLISHED[name]})  "
              f"{'ok' if ok else 'MISMATCH'}")
    if not all(checks) or abs(base - PUBLISHED["fp32"]) > 0.02:
        print("\nRULER BROKEN — this run does not reproduce the published table. Stop.")
        return 1

    # ---- search ------------------------------------------------------------
    best = None
    for seed_name, seed in (("MXFP4", MXFP4), ("Lloyd-Max", LLOYD)):
        lv = normalise(seed)
        cur = kl_of(lv)
        print(f"\nsearching from {seed_name}: KL {cur:.6f}", flush=True)
        evals = 0
        step = 0.06
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
                    if evals >= EVALS:
                        break
                if evals >= EVALS:
                    break
            if not improved:
                step /= 2
        print(f"  {evals} evaluations, KL {cur:.6f}")
        if best is None or cur < best[0]:
            best = (cur, lv, seed_name)

    kl_best, lv_best, origin = best
    print(f"\nbest by KL came from {origin}: {[round(x, 5) for x in lv_best]}")

    # ---- judge it on the axis the document used ----------------------------
    print(f"\n  {'codebook':<22} {'perplexity':>12} {'vs MXFP4':>10}")
    rows = {}
    for name, lv in (("MXFP4 (E2M1)", MXFP4), ("Lloyd-Max (MSE opt)", LLOYD),
                     ("KL-optimised", lv_best)):
        apply(lv)
        p = perplexity(model, ids, NWIN)
        rows[name] = p
        print(f"  {name:<22} {p:>12.4f} {100 * (p / rows['MXFP4 (E2M1)'] - 1):>+9.2f}%")

    mx, ll, kl = rows["MXFP4 (E2M1)"], rows["Lloyd-Max (MSE opt)"], rows["KL-optimised"]
    print()
    if kl < ll and kl < mx:
        print("RESULT: a codebook optimised against KL beats BOTH the deployed format")
        print("        and the squared-error optimum. Lloyd-Max was never the ceiling")
        print("        for this axis, and the closing argument in BLOCK_AXIS_CLOSED")
        print("        does not support its conclusion as written.")
    elif kl < mx:
        print("RESULT: beats MXFP4 but not Lloyd-Max. The ceiling claim survives in")
        print("        substance even though its argument was about the wrong metric.")
    else:
        print("RESULT: no improvement on MXFP4 from optimising the objective that")
        print("        decides. The conclusion now rests on a test it had not been")
        print("        given, which is a stronger footing than the one it had.")
    print(f"\nSCOPE: one model, eight magnitudes, {KLWIN}-window KL as the search "
          f"signal and {NWIN}-window perplexity as the judge. Coordinate descent "
          "is not a global search; a negative result bounds what this search "
          "found, not what exists.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
