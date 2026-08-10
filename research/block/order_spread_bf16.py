"""Addendum to order_spread.py: does the summation-order spread depend on precision?

order_spread.py answers the question at float32 accumulation. If the answer there is
"the spread is negligible", the obvious follow-up is whether that is a property of the
problem or of the accumulator. Both checkpoints are bf16-origin and bf16 inference is
the deployment default, so bf16 is the honest second point -- and it is the precision at
which an exact ternary datapath would actually be competing.

Same construction as order_spread.py: identical phi^k-quantised weights in every arm,
only the contraction order differs.
"""
import os
import sys
import json
import time

import numpy as np
import torch
import torch.nn.functional as F
from transformers import AutoModelForCausalLM, AutoTokenizer

WDIR = ("/private/tmp/claude-501/-Users-ssdm4-Desktop-PROJECTS-CLAUDE/"
        "0e868af8-ab2d-4d00-be03-8fea94ba48e4/scratchpad/weights")
TAG = "smollm2"
NW = int(sys.argv[1]) if len(sys.argv) > 1 else 40
DT = {"bf16": torch.bfloat16, "fp32": torch.float32}[sys.argv[2] if len(sys.argv) > 2 else "bf16"]
MODEL = os.path.join(WDIR, TAG)
K, SEQLEN = 32, 2048
PHI = (1 + 5 ** 0.5) / 2
LOGPHI = np.log(PHI)
torch.set_grad_enabled(False)
torch.set_num_threads(8)
PHIL = torch.tensor([0.0] + [PHI ** (-k) for k in range(6, -1, -1)], dtype=torch.float64)


def quant_phi(w):
    n = (w.shape[1] // K) * K
    b = w[:, :n].reshape(-1, K).double()
    amax = b.abs().amax(dim=1).clamp(min=1e-300)
    s = torch.pow(PHI, torch.ceil(torch.log(amax) / LOGPHI - 1e-9))
    a = (b / s[:, None]).abs()
    rec = torch.sign(b) * PHIL[torch.bucketize(a, (PHIL[:-1] + PHIL[1:]) / 2)] * s[:, None]
    out = w.clone()
    out[:, :n] = rec.reshape(-1, n)
    return out


def fail(m):
    print(f"\n  SELF-TEST FAILED: {m}\n  No numbers reported.")
    sys.exit(1)


# self-tests, in the working dtype
print(f"  self-tests (dtype {DT})")
g = torch.Generator().manual_seed(11)
# exact-integer bitwise test sized so every partial sum is exact in THIS dtype
mant = 8 if DT is torch.bfloat16 else 24
lim, n_ = (2, 16) if DT is torch.bfloat16 else (8, 256)
xi = torch.randint(-lim, lim + 1, (13, n_), generator=g).to(DT)
wi = torch.randint(-lim, lim + 1, (17, n_), generator=g).to(DT)
p = torch.randperm(n_, generator=g)
y0, y1 = F.linear(xi, wi), F.linear(xi[:, p], wi[:, p])
if float(y0.abs().max()) >= 2 ** mant:
    fail(f"integer self-test exceeded exact range of {DT} ({float(y0.abs().max())} >= 2^{mant})")
if not torch.equal(y0, y1):
    fail(f"permutation changes an EXACT integer contraction in {DT}")
print(f"    permuted == natural BITWISE on exact integer data in {DT} "
      f"(max |y| = {float(y0.abs().max()):.0f} < 2^{mant})  OK")
xf = torch.randn(64, 576, generator=g).to(DT)
wf = torch.randn(1536, 576, generator=g).to(DT)
pp = torch.randperm(576, generator=g)
z0, z1 = F.linear(xf, wf), F.linear(xf[:, pp], wf[:, pp])
if torch.equal(z0, z1):
    fail(f"permutation does not move a {DT} contraction at all")
print(f"    one GEMM moves by {float((z0-z1).abs().max()/z0.abs().mean()):.2e} of a typical "
      f"output in {DT}  OK\n")

tok = AutoTokenizer.from_pretrained(MODEL)
import pyarrow.parquet as pq
_t = "\n\n".join(pq.read_table(os.path.join(WDIR, "wikitext2-test.parquet"))
                 .column("text").to_pylist())
_ids = tok(_t, return_tensors="pt").input_ids[0]
_n = (_ids.numel() // SEQLEN) * SEQLEN
X = _ids[:_n].reshape(-1, SEQLEN)[:NW]


def fresh():
    m = AutoModelForCausalLM.from_pretrained(MODEL, dtype=DT)
    m.eval()
    return m


def targets(m):
    return [(nm, mod) for nm, mod in m.named_modules()
            if isinstance(mod, torch.nn.Linear) and "lm_head" not in nm and "embed_out" not in nm]


_m0 = AutoModelForCausalLM.from_pretrained(MODEL, dtype=torch.float32)
QC = {nm: quant_phi(mod.weight.data.double()).to(DT) for nm, mod in targets(_m0)}
del _m0
print(f"  {TAG}, {NW} windows, dtype {DT}, {len(QC)} linear layers permuted")


def run(kind, seed):
    m = fresh()
    for nm, mod in targets(m):
        mod.weight.data = QC[nm].clone()
    if kind != "none":
        for i, (nm, mod) in enumerate(targets(m)):
            d = mod.in_features
            q = (torch.arange(d) if kind == "id" else
                 torch.arange(d - 1, -1, -1) if kind == "rev" else
                 torch.randperm(d, generator=torch.Generator().manual_seed(seed * 100003 + i)))
            mod.weight.data = mod.weight.data[:, q].contiguous()
            mod.register_forward_pre_hook(lambda _m, a, _q=q: (a[0][..., _q],) + a[1:])
    tot = 0.0
    for i in range(X.shape[0]):
        c = X[i:i + 1]
        tot += m(c, labels=c).loss.double().item()
    del m
    return float(np.exp(tot / X.shape[0]))


res = {}
for label, kind, seed in (("natural", "none", 0), ("identity", "id", 0), ("reverse", "rev", 0),
                          ("rand1", "rand", 1), ("rand2", "rand", 2), ("rand3", "rand", 3)):
    t0 = time.time()
    res[label] = run(kind, seed)
    print(f"    {label:9} ppl = {res[label]:12.6f}   ({time.time()-t0:.0f}s)", flush=True)
rep = run("none", 0)
print(f"    {'repeat':9} ppl = {rep:12.6f}   noise floor = {abs(rep-res['natural']):.2e}"
      f"{' (bitwise identical)' if rep == res['natural'] else ' (NOT identical!)'}")
v = list(res.values())
print(f"\n  dtype {DT}: natural {res['natural']:.6f}  spread {max(v)-min(v):.6f}  "
      f"sd {np.std(v, ddof=1):.6f}")
json.dump({"tag": TAG, "dtype": str(DT), "windows": int(X.shape[0]), "runs": res,
           "repeat": rep, "spread": max(v) - min(v), "sd": float(np.std(v, ddof=1))},
          open("/Users/ssdm4/Desktop/PROJECTS/CLAUDE/trinity-fpga/research/block/"
               f"order_spread_{TAG}_{str(DT).split('.')[-1]}.json", "w"), indent=1)
