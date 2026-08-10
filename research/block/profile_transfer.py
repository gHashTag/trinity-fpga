#!/usr/bin/env python3
"""Does a sensitivity profile measured on ONE model allocate bits well on ANOTHER?

This is the question that separates a method from a curiosity. If the profile must be measured
per model, promote-only allocation needs a calibration pass per deployment. If a profile from a
small model transfers, it is a fixed rule.

Qwen's own profile (24 blocks) replicates SmolLM2's structure qualitatively: MSE-damage
correlation r=+0.139 (SmolLM2 +0.128), largest-MSE block is again nearly the least damaging,
the FINAL block is the most damaging in both, MLP (down/up) dominates by total damage, and
v_proj again shows the extreme signature -- the LOWEST MSE of any projection type (11.74) with
the third HIGHEST damage (0.2743).

Four allocations on Qwen, all at 4.333 bits/element (promote 8 of 24 blocks to 5 bits):

    OWN         Qwen's own measured profile           -- the ceiling for this method
    TRANSFER    SmolLM2's profile, interpolated from 30 positions onto 24 by relative depth
    MSE         allocate by per-layer MSE             -- control
    LAST-N      promote the final 8 blocks            -- the trivial depth heuristic

LAST-N matters: if simply promoting the deepest blocks does as well as a measured profile, then
no profiling is needed at all and the whole sensitivity apparatus is unnecessary.
"""
import os, re, sys
import numpy as np, torch
sys.path.insert(0, "/Users/ssdm4/Desktop/PROJECTS/CLAUDE/trinity-fpga/research/block")
from transformers import AutoModelForCausalLM, AutoTokenizer

W = ("/private/tmp/claude-501/-Users-ssdm4-Desktop-PROJECTS-CLAUDE/"
     "0e868af8-ab2d-4d00-be03-8fea94ba48e4/scratchpad/weights")
K, SEQLEN, NBIN = 32, 2048, 800
torch.set_grad_enabled(False)
from bitwidth_scaling import dp_pinned, quantise

SMOL = np.array([0.0952,0.0973,0.1083,0.0695,0.0401,0.0097,0.0572,0.0358,0.0383,0.0256,0.0469,
 0.0960,0.0706,0.0691,0.0993,0.0661,0.0812,0.1113,0.1507,0.1237,0.1742,0.0614,0.0762,0.1165,
 0.0579,0.0563,0.1160,0.0774,0.1311,0.4070])
QWEN = np.array([0.0805,0.0266,0.1006,0.0901,0.0538,0.0429,0.0731,0.0399,0.0456,0.0548,0.0498,
 0.0635,0.0448,0.0674,0.0510,0.0619,0.0933,0.0811,0.0452,0.0623,0.1068,0.0990,0.1183,0.2187])
QMSE = np.array([102.6337,62.7949,62.5382,59.6237,61.1121,61.7206,61.2348,60.9100,63.1468,
 58.3867,58.9751,55.5034,58.5153,58.5300,59.5923,61.3145,63.0638,61.7509,62.4228,63.9112,
 65.9136,67.4416,66.2654,62.1705])
NL, NPROM = 24, 8
TRANSFER = np.interp(np.linspace(0, 1, NL), np.linspace(0, 1, len(SMOL)), SMOL)
print(f"  Spearman(own, transferred) = "
      f"{np.corrcoef(np.argsort(np.argsort(QWEN)), np.argsort(np.argsort(TRANSFER)))[0,1]:+.3f}")

def layer_index(nm):
    m = re.search(r"layers?\.(\d+)\.", nm)
    return int(m.group(1)) if m else -1

MODEL = os.path.join(W, "qwen")
tok = AutoTokenizer.from_pretrained(MODEL)
model = AutoModelForCausalLM.from_pretrained(MODEL, dtype=torch.float32).eval()
import pyarrow.parquet as pq
text = "\n\n".join(pq.read_table(os.path.join(W,"wikitext2-test.parquet")).column("text").to_pylist())
ids = tok(text, return_tensors="pt").input_ids[0]
lins = [(n,m) for n,m in model.named_modules()
        if isinstance(m, torch.nn.Linear) and "lm_head" not in n]
BASE = {n: m.weight.detach().clone() for n,m in lins}
hist = np.zeros(NBIN)
for n,m in lins:
    w = BASE[n].double(); nn_=(w.shape[1]//K)*K
    if nn_==0: continue
    b=w[:,:nn_].reshape(-1,K); a=b.abs().amax(1); ok=a>0
    hist += np.histogram((b[ok]/a[ok][:,None]).reshape(-1).numpy(),bins=NBIN,range=(-1,1))[0]
dens = hist/(hist.sum()*(2.0/NBIN))
CB = {b: dp_pinned(dens, 1<<b) for b in (4,5)}

LO, HI = 4, 14
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

p0=ppl(); p4=run(np.full(NL,4)); p5=run(np.full(NL,5)); d4,d5=p4-p0,p5-p0
print(f"\nRULER CHECK -- Qwen fp32 {p0:.4f} (windows {LO}-{HI-1})")
print(f"  uniform 4-bit +{d4:.4f}   uniform 5-bit +{d5:.4f}   full gain {d4-d5:.4f}\n")
print(f"  {'promote 8 of 24 to 5 bits by':<34}{'vs fp32':>10}{'share of gain':>16}")
for label,key in (("OWN profile (Qwen)",QWEN),("TRANSFER (SmolLM2 profile)",TRANSFER),
                  ("MSE  [control]",QMSE),("LAST-8 blocks  [control]",np.arange(NL,dtype=float))):
    bits=np.full(NL,4); bits[np.argsort(key)[-NPROM:]]=5
    p=run(bits)
    print(f"  {label:<34}{p-p0:>+10.4f}{(d4-(p-p0))/(d4-d5)*100:>15.1f}%")
print(f"\n  bit share spent: {(NPROM*5+(NL-NPROM)*4)/NL/5*100:.1f}% of the 5-bit budget"
      f"  (avg {(NPROM*5+(NL-NPROM)*4)/NL:.3f} bits)")
print("  33.3% = break-even; above it the ordering is paying for itself.")
