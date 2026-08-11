#!/usr/bin/env python3
"""Zoom on MXFP4 level 1 below the 1% scale, where the sweep found a sharp bump.

Measured so far, moving level 1 = 0.083333 DOWN from MXFP4 (21.9397):
    -0.10% -> 22.0592   -0.25% -> 22.0527   -0.50% -> 21.9531
    -1.00% -> 21.9956   -2.00% -> 21.8994   -5.00% -> 21.8522
i.e. up, up, down, up, down, down -- a turn at every scale sampled. Either the
response really does oscillate below 1%, or the sampling is aliasing a smooth
curve. This fills in the gaps to tell those apart, and re-measures two points
1/50th apart (-0.100% and -0.102%) as a locality check: on a continuous
function those must agree closely, whatever the curve is doing at 0.1%.

Level 1 is the level the KL search moved furthest (-28%), so the shape of this
response is load-bearing for how much that search's result should be trusted.
"""
import json
import math
import os
import sys
import time

if os.environ.get("CAMPC_DETACH") == "1" and os.fork() > 0:
    os._exit(0)
if os.environ.get("CAMPC_DETACH") == "1":
    os.setsid()
    sys.stdout.flush()

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
OUT = os.path.join(HERE, f"campaignC_level1_zoom_{MDIR}.json")

v = sorted(fp_levels(2, 1))
MXFP4 = [x / v[-1] for x in v]
MXFP4[-1] = 1.0
assert abs(MXFP4[-1] - 1.0) < 1e-12          # T38: headroom phase phi = 0

KNOWN = {0.0: 21.93966176, -0.001: 22.0592, -0.0025: 22.0527, -0.005: 21.9531,
         -0.01: 21.9956, -0.02: 21.8994, -0.05: 21.8522}
NEW = [-0.0002, -0.0005, -0.00102, -0.0015, -0.0035, -0.0075, -0.015, -0.03]


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
    got = {}

    def measure(d):
        lv = list(MXFP4)
        lv[1] = MXFP4[1] * (1 + d)
        assert lv[0] < lv[1] < lv[2] and abs(lv[-1] - 1.0) < 1e-12
        t0 = time.time()
        for n, m in lins:
            m.weight.copy_(quant(orig[n], lv))
        p = perplexity(model, win[:NWIN].reshape(1, -1), NWIN)
        for n, m in lins:
            m.weight.copy_(orig[n])
        got[d] = p
        json.dump({"level": 1, "base": MXFP4[1], "known": KNOWN,
                   "measured": {str(k): v for k, v in got.items()}},
                  open(OUT, "w"), indent=1)
        print(f"  level1 {d:+.5%}  L={lv[1]:.8f}  ppl {p:.4f}  "
              f"({100*(p/KNOWN[0.0]-1):+.3f}%)   ({time.time()-t0:.0f}s)",
              flush=True)
        return p

    print("=== zoom on level 1 below the 1% scale ===", flush=True)
    for dd in NEW:
        measure(dd)

    allp = dict(KNOWN)
    allp.update(got)
    print("\n=== the response of level 1, all points, least negative first ===")
    print(f"{'delta':>10}{'L':>12}{'ppl':>11}{'vs MXFP4':>11}")
    for dd in sorted(allp, reverse=True):
        print(f"{dd:>+10.5%}{MXFP4[1]*(1+dd):>12.8f}{allp[dd]:>11.4f}"
              f"{100*(allp[dd]/KNOWN[0.0]-1):>+10.3f}%")
    seq = [allp[k] for k in sorted(allp, reverse=True)]
    turns = sum(1 for i in range(1, len(seq) - 1)
                if (seq[i] - seq[i - 1]) * (seq[i + 1] - seq[i]) < 0)
    print(f"\ndirection changes across {len(seq)} points: {turns}")
    a, b = allp[-0.001], allp[-0.00102]
    print(f"locality check: -0.100% -> {a:.4f}   -0.102% -> {b:.4f}   "
          f"|diff| {abs(a-b):.4f} ppl ({100*abs(a-b)/a:.3f}%)")
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
