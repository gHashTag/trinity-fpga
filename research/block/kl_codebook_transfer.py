#!/usr/bin/env python3
"""Does the KL-optimised eight-level codebook transfer off SmolLM2-135M?

`kl_optimal_codebook.py` fitted six interior magnitudes by coordinate descent on
SmolLM2-135M's own logits and reported -7.66 % perplexity against MXFP4 on that
same checkpoint. A codebook fitted to one checkpoint and judged on that same
checkpoint is an in-sample number. This runs the identical three codebooks,
through the identical quantiser, on a model the search never saw.

Nothing about the measurement path is reimplemented: `quant`, `perplexity`,
`target_modules` and `load_wikitext` are taken from `block_tnf.py` by executing
its source up to the driver marker. All three codebooks are normalised to a top
level of exactly 1.0, so every one of them gets the same alignment rule
s = 2^ceil(log2(a_max)) -- see MXFP4_SCALE_CONVENTION_2026-08-11.md, where
mixing conventions inverted which codebook won.

    MDIR=qwen NWIN=40 python3 kl_codebook_transfer.py
"""
import os
import sys
import time

import numpy as np
import torch

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "block_tnf.py")
MARKER = 'print("загружаю модель…", flush=True)'
_src = open(SRC, encoding="utf-8").read()
if MARKER not in _src:
    raise SystemExit("driver marker not found in block_tnf.py")
_ns = {}
exec(compile(_src.split(MARKER)[0], SRC, "exec"), _ns)

fp_levels = _ns["fp_levels"]
quant = _ns["quant"]
perplexity = _ns["perplexity"]
target_modules = _ns["target_modules"]
load_wikitext = _ns["load_wikitext"]
K, SEQLEN = _ns["K"], _ns["SEQLEN"]
W = os.path.dirname(_ns["MODEL"])

torch.set_grad_enabled(False)

NWIN = int(os.environ.get("NWIN", "40"))
OFFSET = int(os.environ.get("OFFSET", "0"))      # skip this many windows first
MDIR = os.environ.get("MDIR", "qwen")


def normalise(lv):
    v = sorted(float(x) for x in lv)
    return [x / v[-1] for x in v]


MXFP4 = normalise(fp_levels(2, 1))
LLOYD = normalise([0.0, 0.10334, 0.21079, 0.32491, 0.44963,
                   0.59031, 0.75635, 0.96567])
KLOPT = [0.0, 0.07701, 0.18828, 0.31396, 0.46561, 0.6113, 0.79074, 1.0]


def main():
    from transformers import AutoModelForCausalLM, AutoTokenizer
    path = os.path.join(W, MDIR)
    print(f"model dir = {path}", flush=True)
    tok = AutoTokenizer.from_pretrained(path)
    model = AutoModelForCausalLM.from_pretrained(path, dtype=torch.float32)
    model.eval()
    ids = tok(load_wikitext(), return_tensors="pt").input_ids
    flat = ids.reshape(-1)
    nwin_total = flat.numel() // SEQLEN
    win = flat[:nwin_total * SEQLEN].view(-1, SEQLEN)
    print(f"tokens={flat.numel()}  windows of {SEQLEN} available = {nwin_total}",
          flush=True)
    sub = win[OFFSET:OFFSET + NWIN].reshape(1, -1)   # perplexity() re-slices
    print(f"evaluating windows [{OFFSET}, {OFFSET + NWIN})", flush=True)

    lins = target_modules(model)
    print(f"{len(lins)} linear tensors quantised (lm_head excluded)", flush=True)
    orig = {n: m.weight.detach().clone() for n, m in lins}

    def apply(lv):
        for n, m in lins:
            m.weight.copy_(orig[n] if lv is None else quant(orig[n], lv))

    t0 = time.time()
    apply(None)
    base = perplexity(model, sub, NWIN)
    print(f"\nfp32 baseline = {base:.4f}   ({time.time() - t0:.0f}s)", flush=True)
    if not (3.0 < base < 60.0):
        print("baseline implausible -- refusing to compare.")
        return 1

    rows = {}
    for name, lv in (("MXFP4 (E2M1)", MXFP4),
                     ("Lloyd-Max (MSE opt)", LLOYD),
                     ("KL-optimised (SmolLM2-fitted)", KLOPT)):
        t0 = time.time()
        apply(lv)
        p = perplexity(model, sub, NWIN)
        rows[name] = p
        print(f"{name:<32} {p:>10.4f}   ({time.time() - t0:.0f}s)", flush=True)
    apply(None)

    mx = rows["MXFP4 (E2M1)"]
    print(f"\n  {'codebook':<32}{'ppl':>10}{'vs fp32':>10}{'vs MXFP4':>11}")
    print(f"  {'fp32':<32}{base:>10.4f}{'':>10}{'':>11}")
    for name in ("MXFP4 (E2M1)", "Lloyd-Max (MSE opt)",
                 "KL-optimised (SmolLM2-fitted)"):
        p = rows[name]
        print(f"  {name:<32}{p:>10.4f}{p - base:>+10.4f}"
              f"{100 * (p / mx - 1):>+10.2f}%")
    kl = rows["KL-optimised (SmolLM2-fitted)"]
    print(f"\nTRANSFER: {'HOLDS' if kl < mx else 'FAILS'} on {MDIR} "
          f"({100 * (kl / mx - 1):+.2f}% vs MXFP4)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
