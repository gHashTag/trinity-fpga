#!/usr/bin/env python3
"""Sanity gate for the GPTQ implementation before it is used as a baseline.

The first GPTQ run produced a result that cannot be right:

    RTN  uniform 4-bit   +2.6386
    GPTQ uniform 4-bit   +3.0570      <- GPTQ WORSE than round-to-nearest
    RTN  uniform 5-bit   +0.6796
    GPTQ uniform 5-bit   +0.6445      <- GPTQ better here

GPTQ beating RTN at 4 bits is the entire reason GPTQ exists. An implementation that loses to RTN
is not a GPTQ baseline, so no conclusion may be drawn from a comparison against it -- including
the flattering one (promote-only captured 60.4% of the gain under that broken baseline, versus
54.1% under RTN; that number is not evidence of anything).

Most likely cause: too little calibration data. The Hessian is d_in x d_in with d_in up to 1536,
and the first run used 4 sequences x 2048 tokens = 8192 samples -- about 5x the dimension.
Reference GPTQ uses 128 sequences. An ill-conditioned H makes the error compensation amplify
noise instead of cancelling it, which would hurt most at low precision, exactly as observed.

This runs the gate alone, at several calibration sizes: does GPTQ 4-bit beat RTN 4-bit? Only if
it does is the baseline usable.
"""
import os, sys
import numpy as np, torch
sys.path.insert(0, "/Users/ssdm4/Desktop/PROJECTS/CLAUDE/trinity-fpga/research/block")
from gptq_baseline import (CB, BASE, lins, layer_index, rtn_layer, gptq_layer,
                           WINS, model, NL, ppl, restore, p0)

LO, HI = 6, 18

def gptq_all(bits, ncal, cal_start=18):
    restore()
    CAL = WINS[cal_start:cal_start + ncal]
    for bi in range(NL):
        names = [n for n, _ in lins if layer_index(n) == bi]
        Hs, cnt, hooks = {}, {}, []
        def mk(nm):
            def h(mod, inp, out):
                x = inp[0].detach().double().reshape(-1, inp[0].shape[-1])
                Hs[nm] = Hs.get(nm, 0) + 2.0 * (x.T @ x)
                cnt[nm] = cnt.get(nm, 0) + x.shape[0]
            return h
        for n, m in lins:
            if n in names: hooks.append(m.register_forward_hook(mk(n)))
        for i in range(CAL.shape[0]): model(CAL[i:i+1])
        for h in hooks: h.remove()
        for n, m in lins:
            if n in names and n in Hs:
                m.weight.copy_(gptq_layer(BASE[n], Hs[n]/max(cnt[n],1),
                                          CB[bits[layer_index(n)]]).to(m.weight.dtype))

U4 = np.full(NL, 4)
for n, m in lins:
    m.weight.copy_(rtn_layer(BASE[n].double(), CB[4]).to(m.weight.dtype))
rtn4 = ppl(); restore()
print(f"\nGATE -- fp32 {p0:.4f}   RTN 4-bit {rtn4:.4f} ({rtn4-p0:+.4f})\n")
print(f"  {'calibration':<22}{'GPTQ 4-bit':>12}{'vs fp32':>10}{'vs RTN 4-bit':>15}  gate")
for ncal in (4, 12, 32):
    gptq_all(U4, ncal)
    p = ppl(); restore()
    ok = "PASS" if p < rtn4 else "FAIL"
    print(f"  {f'{ncal} seq ({ncal*2048} tok)':<22}{p:>12.4f}{p-p0:>+10.4f}{p-rtn4:>+15.4f}  {ok}")
print("\n  A GPTQ implementation that loses to RTN at 4 bits cannot serve as a baseline.")
