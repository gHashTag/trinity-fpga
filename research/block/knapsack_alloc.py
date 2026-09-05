#!/usr/bin/env python3
"""The knapsack solution is not top-N -- it is top-2. Testing that prediction.

Under the measured bit-width curves (demotion costs 3.49x D4, promotion saves 0.660x D4), a
swap pays iff D_promoted/D_demoted > 5.29. Walking the greedy swaps:

    swap 1: demote b5  (0.0097) -> promote b29 (0.4070)  ratio 41.96  net +0.2348  TAKE
    swap 2: demote b9  (0.0256) -> promote b20 (0.1742)  ratio  6.80  net +0.0256  TAKE
    swap 3: demote b7  (0.0358) -> promote b18 (0.1507)  ratio  4.21  net -0.0255  STOP

Only TWO swaps clear the bar. That is precisely why promote-10/demote-10 failed: it forced eight
swaps that were known losers. The optimal constant-width allocation is 2 demoted, 2 promoted,
everything else at 4 bits -- average still exactly 4.000.

PRE-REGISTERED PREDICTION: -0.2604 perplexity against uniform 4-bit, at identical average width.
If it holds, this is the first constant-width mixed-precision win in the programme, and the
earlier failure was an allocation error rather than a property of the model.

The 4-swap arm is included as the falsifier: the model says swaps 3 and 4 are losers, so 4-swap
should be WORSE than 2-swap. If 4-swap is better, the greedy criterion is wrong.
"""
import os, sys
import numpy as np, torch
sys.path.insert(0, "/Users/ssdm4/Desktop/PROJECTS/CLAUDE/trinity-fpga/research/block")
from bitwidth_scaling import CB, BASE, lins, layer_index, quantise, ids, model, SEQLEN

D = np.array([0.0952,0.0973,0.1083,0.0695,0.0401,0.0097,0.0572,0.0358,0.0383,0.0256,0.0469,
 0.0960,0.0706,0.0691,0.0993,0.0661,0.0812,0.1113,0.1507,0.1237,0.1742,0.0614,0.0762,0.1165,
 0.0579,0.0563,0.1160,0.0774,0.1311,0.4070])
NL, LO, HI = 30, 6, 18
asc = np.argsort(D); desc = asc[::-1]

def ppl():
    n=(ids.numel()//SEQLEN)*SEQLEN; x=ids[:n].view(-1,SEQLEN)[LO:HI]
    return float(np.exp(sum(model(x[i:i+1],labels=x[i:i+1]).loss.double().item()
                            for i in range(x.shape[0]))/x.shape[0]))
def run(bits):
    for n,m in lins:
        m.weight.copy_(quantise(BASE[n].double(),
            torch.tensor(CB[bits[layer_index(n)]],dtype=torch.float64)).to(m.weight.dtype))
    p=ppl()
    for n,m in lins: m.weight.copy_(BASE[n])
    return p

p0=ppl(); p4=run(np.full(NL,4))
print(f"\nRULER CHECK -- fp32 {p0:.4f} (windows {LO}-{HI-1})")
print(f"  uniform 4-bit  {p4:.4f}  ({p4-p0:+.4f})\n")
print(f"  {'allocation':<34}{'avg bits':>10}{'ppl':>10}{'vs uniform 4-bit':>19}")
for ns in (1, 2, 3, 4, 10):
    bits=np.full(NL,4)
    bits[asc[:ns]]=3; bits[desc[:ns]]=5
    p=run(bits)
    tag = "  <- model optimum" if ns==2 else ("  <- model says loser" if ns>2 else "")
    print(f"  {f'{ns} swap(s): demote {ns}, promote {ns}':<34}{bits.mean():>10.3f}{p:>10.4f}"
          f"{p-p4:>+19.4f}{tag}")
print("\n  model predicted 2-swap = -0.2604 vs uniform 4-bit, and 3+ swaps to get worse.")
