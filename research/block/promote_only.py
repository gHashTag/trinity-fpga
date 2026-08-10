#!/usr/bin/env python3
"""Promote-only allocation: the version the asymmetry says should work.

bitwidth_scaling.py measured demotion costing 4.49x and promotion saving only 2.94x -- a 1.53x
asymmetry, so any constant-width swap starts behind. Corrected break-even for a swap:

    gain  = (1 - 1/2.94) * D_promoted = 0.660 * D_promoted
    loss  = (4.49 - 1)   * D_demoted  = 3.49  * D_demoted
    pays iff D_promoted / D_demoted > 5.29     (was 4.00 under the classical rule)

n=10 ratio 3.58 < 5.29 -> should not pay (it didn't). n=6 ratio 5.62 is marginally above 5.29,
and lost 0.280 -- consistent with sitting on the boundary within measurement error.

So the honest move is to stop demoting. Promote the sensitive layers to 5 bits and leave the rest
at 4. That costs 0.333 bits/element, so the fair question is EFFICIENCY: what share of the full
4->5 bit improvement does it buy for a third of the bits? Above 33% means the profile is paying
for itself; at or below 33% it is no better than spending the bits uniformly.

Controls: the same promotion by MSE rank, and by a fixed arbitrary set. If those do as well, the
sensitivity profile contributed nothing.
"""
import os, re, sys
import numpy as np, torch
from transformers import AutoModelForCausalLM, AutoTokenizer
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bitwidth_scaling import CB, BASE, lins, layer_index, quantise, ppl, p0, model

DPPL = np.array([0.0952,0.0973,0.1083,0.0695,0.0401,0.0097,0.0572,0.0358,0.0383,0.0256,0.0469,
 0.0960,0.0706,0.0691,0.0993,0.0661,0.0812,0.1113,0.1507,0.1237,0.1742,0.0614,0.0762,0.1165,
 0.0579,0.0563,0.1160,0.0774,0.1311,0.4070])
MSE_L = np.array([1438.1943,1335.6018,1292.0653,1306.3311,1288.1378,1265.5231,1302.6299,1273.9641,
 1284.8257,1322.5296,1346.4854,1344.9005,1325.1743,1318.0615,1283.0718,1292.2842,1339.4485,
 1299.7285,1253.3065,1329.1526,1307.0804,1315.7523,1355.9736,1421.8265,1403.1751,1420.1261,
 1432.8625,1397.1226,1432.9144,1342.9496])
NL = 30

def run(bits):
    for n, m in lins:
        m.weight.copy_(quantise(BASE[n].double(),
                       torch.tensor(CB[bits[layer_index(n)]], dtype=torch.float64)
                       ).to(m.weight.dtype))
    p = ppl()
    for n, m in lins: m.weight.copy_(BASE[n])
    return p

print(f"\nRULER CHECK -- fp32 baseline {p0:.4f}")
p4 = run(np.full(NL, 4)); p5 = run(np.full(NL, 5))
d4, d5 = p4 - p0, p5 - p0
print(f"\n  uniform 4-bit  {p4:.4f}  (+{d4:.4f})")
print(f"  uniform 5-bit  {p5:.4f}  (+{d5:.4f})")
print(f"  full 4->5 improvement: {d4-d5:.4f} perplexity for 1.000 bit/element\n")
print(f"  {'promote 10 blocks to 5 bits by':<34}{'avg bits':>9}{'ppl':>10}{'vs fp32':>9}{'share of 4->5 gain':>20}")
for label, key in (("SENSITIVITY", DPPL), ("MSE  [control]", MSE_L),
                   ("first 10 blocks  [control]", -np.arange(NL, dtype=float))):
    bits = np.full(NL, 4); bits[np.argsort(key)[-10:]] = 5
    p = run(bits)
    share = (d4 - (p - p0)) / (d4 - d5) * 100
    print(f"  {label:<34}{bits.mean():>9.3f}{p:>10.4f}{p-p0:>+9.4f}{share:>19.1f}%")
print("\n  bit share spent: 33.3%.  Above that = the profile pays for itself.")
