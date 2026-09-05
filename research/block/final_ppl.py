#!/usr/bin/env python3
"""The decisive test for the one surviving codebook design: DP-16 with a pinned zero.

It beats both NF4 and a correct E2M1 on MSE. MSE ordering has already been shown to invert
relative to perplexity, so that proves nothing on its own. This measures perplexity.

If it loses here too, the codebook axis is closed on the metric that matters and the honest
conclusion is that no p_eff-derived codebook beats the incumbents.
"""
import os, sys
import numpy as np, torch
from transformers import AutoModelForCausalLM, AutoTokenizer

W = ("/private/tmp/claude-501/-Users-ssdm4-Desktop-PROJECTS-CLAUDE/"
     "0e868af8-ab2d-4d00-be03-8fea94ba48e4/scratchpad/weights")
MODEL, K, SEQLEN = os.path.join(W, "smollm2"), 32, 2048
NW = int(os.environ.get("NW", "12"))
torch.set_grad_enabled(False)

MAGS = [0.0, 0.5, 1.0, 1.5, 2.0, 3.0, 4.0, 6.0]
E2M1 = np.array(sorted(set([-v/6 for v in MAGS] + [v/6 for v in MAGS])))
NF4 = np.array([-1.0,-0.6961928009986877,-0.5250730514526367,-0.39491748809814453,
 -0.28444138169288635,-0.18477343022823334,-0.09105003625154495,0.0,0.07958029955625534,
 0.16093020141124725,0.24611230194568634,0.33791524171829224,0.44070982933044434,
 0.5626170039176941,0.7229568362236023,1.0])
DP16Z = np.array([-1.0000,-0.7805,-0.6094,-0.4645,-0.3361,-0.2183,-0.1066,0.0000,
 0.0944,0.1901,0.2908,0.3987,0.5162,0.6491,0.8053,1.0000])
DP16 = np.array([-1.000,-0.792,-0.628,-0.488,-0.364,-0.252,-0.148,-0.048,
 0.051,0.152,0.256,0.367,0.489,0.628,0.792,1.000])

def quantise(w, lv):
    n = (w.shape[1]//K)*K
    if n == 0: return w
    b = w[:, :n].reshape(-1, K).double()
    s = b.abs().amax(1).clamp(min=1e-30)
    idx = torch.bucketize(b/s[:,None], (lv[:-1]+lv[1:])/2).clamp(0, len(lv)-1)
    out = w.clone(); out[:, :n] = (lv[idx]*s[:,None]).reshape(-1, n).to(w.dtype); return out

tok = AutoTokenizer.from_pretrained(MODEL)
model = AutoModelForCausalLM.from_pretrained(MODEL, dtype=torch.float32).eval()
import pyarrow.parquet as pq
text = "\n\n".join(pq.read_table(os.path.join(W,"wikitext2-test.parquet")).column("text").to_pylist())
ids = tok(text, return_tensors="pt").input_ids[0]
lins = [(n,m) for n,m in model.named_modules() if isinstance(m, torch.nn.Linear) and "lm_head" not in n]
base = {n: m.weight.detach().clone() for n,m in lins}

def ppl():
    n = (ids.numel()//SEQLEN)*SEQLEN
    x = ids[:n].view(-1, SEQLEN)[:NW]
    return float(np.exp(sum(model(x[i:i+1], labels=x[i:i+1]).loss.double().item()
                            for i in range(x.shape[0]))/x.shape[0]))

p0 = ppl()
print(f"RULER CHECK -- fp32 baseline {p0:.3f} ({NW} windows)")
if not (5.0 < p0 < 60.0): sys.exit("baseline implausible")
print(f"\n  {'codebook':<28}{'has 0':>7}{'vals':>6}{'perplexity':>12}{'vs fp32':>10}")
for name, lv in (("E2M1 (correct)", E2M1), ("NF4 (real)", NF4),
                 ("DP-16 (no zero)", DP16), ("DP-16 + zero  [NEW]", DP16Z)):
    lvt = torch.tensor(lv, dtype=torch.float64)
    for n,m in lins: m.weight.copy_(quantise(base[n].double(), lvt).to(m.weight.dtype))
    p = ppl()
    hz = "yes" if np.min(np.abs(lv)) < 1e-12 else "NO"
    print(f"  {name:<28}{hz:>7}{len(set(np.round(lv,9))):>6}{p:>12.3f}{p-p0:>+10.3f}")
for n,m in lins: m.weight.copy_(base[n])
