"""The scale-cost frontier: perplexity against bits per weight.

Comparing scale formats in pairs hides the thing that decides them. A scale is
one value per K weights, so its cost is scale_bits/K bits per weight, and the
three deployed choices sit at very different costs:

    MXFP4   E8M0, 8 bits / 32  = 0.250 b/w
    ours    phi^k, 4 bits / 32 = 0.125 b/w
    NVFP4   E4M3, 8 bits / 16  = 0.500 b/w   (+ a per-tensor FP32)

NVFP4 beats MXFP4 by spending four times what we spend. The question is not
whether a finer grid helps -- it does -- but where each choice sits on the
frontier of perplexity against total bits. That is one plot and it settles the
whole axis.

The element is E2M1 throughout, so only the scale varies.
"""
import os, sys, json, numpy as np, torch
from transformers import AutoModelForCausalLM, AutoTokenizer
W = ("/private/tmp/claude-501/-Users-ssdm4-Desktop-PROJECTS-CLAUDE/"
     "0e868af8-ab2d-4d00-be03-8fea94ba48e4/scratchpad/weights")
TAG = sys.argv[1] if len(sys.argv) > 1 else "smollm2"
MODEL = os.path.join(W, TAG); SEQLEN, NW = 2048, 40
PHI = (1+5**0.5)/2
torch.set_grad_enabled(False)
def e2m1():
    o={0.0}
    for e in range(4):
        for m in range(2): o.add((m/2.0) if e==0 else (1+m/2.0)*2.0**(e-1))
    return sorted(o)
LV = torch.tensor(e2m1(), dtype=torch.float64)

def grid_pow(raw, g, nbits):
    """Scale on a geometric grid of ratio g, exponent field nbits wide.
    The field is finite: exponents are clamped, which is what a real format does."""
    k = torch.ceil(torch.log(raw)/np.log(g))
    lo = k.min()
    k = torch.clamp(k - lo, 0, 2**nbits - 1) + lo
    return torch.pow(g, k)

def grid_float(raw, ebits, mbits):
    """A float scale: 2^e * (1 + m/2^mbits) -- E4M3 when (4,3), as NVFP4 uses."""
    e = torch.floor(torch.log2(raw))
    frac = raw / torch.pow(2.0, e)                    # in [1,2)
    q = torch.ceil((frac - 1.0) * (2**mbits)) / (2**mbits)
    q = torch.clamp(q, 0, 1)
    return torch.pow(2.0, e) * (1.0 + q)

def quantise(w, K, scale_fn):
    n=(w.shape[1]//K)*K
    if n==0: return w
    head=w[:,:n].reshape(-1,K).double()
    raw=(head.abs().amax(dim=1)/LV[-1]).clamp(min=1e-30)
    s=scale_fn(raw).clamp(min=1e-30)
    y=(head/s[:,None]).abs(); bnd=(LV[:-1]+LV[1:])/2
    rec=torch.sign(head)*LV[torch.bucketize(y,bnd)]*s[:,None]
    out=w.clone(); out[:,:n]=rec.reshape(-1,n).to(w.dtype); return out

def ppl(m, ids):
    n=(ids.numel()//SEQLEN)*SEQLEN; x=ids[:n].reshape(-1,SEQLEN)[:NW]
    nll=cnt=0
    for i in range(x.shape[0]):
        c=x[i:i+1]; nll+=m(c,labels=c).loss.double().item()*(SEQLEN-1); cnt+=SEQLEN-1
    return float(np.exp(nll/cnt))

tok=AutoTokenizer.from_pretrained(MODEL)
import pyarrow.parquet as pq
text="\n\n".join(pq.read_table(os.path.join(W,"wikitext2-test.parquet")).column("text").to_pylist())
ids=tok(text,return_tensors="pt").input_ids[0]
def fresh():
    m=AutoModelForCausalLM.from_pretrained(MODEL,dtype=torch.float32); m.eval(); return m

CAND = [
 ("MXFP4   E8M0 2^k  8b/32", 32, 8, lambda r: grid_pow(r, 2.0, 8)),
 ("2^k               4b/32", 32, 4, lambda r: grid_pow(r, 2.0, 4)),
 ("phi^k             4b/32", 32, 4, lambda r: grid_pow(r, PHI, 4)),
 ("phi^k             5b/32", 32, 5, lambda r: grid_pow(r, PHI, 5)),
 ("phi^k             4b/64", 64, 4, lambda r: grid_pow(r, PHI, 4)),
 ("phi^k             4b/16", 16, 4, lambda r: grid_pow(r, PHI, 4)),
 ("NVFP4-like E4M3   8b/16", 16, 8, lambda r: grid_float(r, 4, 3)),
 ("E4M3              8b/32", 32, 8, lambda r: grid_float(r, 4, 3)),
]
base=ppl(fresh(),ids); print(f"  {TAG}: базовая fp32 = {base:.4f}\n", flush=True)
print(f"  {'схема':26} {'бит/вес масштаба':>17} {'всего бит/вес':>14} {'ppl':>9}", flush=True)
rows=[]
for nm,K,sb,fn in CAND:
    m=fresh()
    for _,mod in m.named_modules():
        if isinstance(mod,torch.nn.Linear) and "lm_head" not in _:
            mod.weight.data=quantise(mod.weight.data,K,fn)
    p=ppl(m,ids); sbw=sb/K; tot=4.0+sbw
    rows.append((nm,K,sb,sbw,tot,p))
    print(f"  {nm:26} {sbw:17.4f} {tot:14.4f} {p:9.4f}", flush=True); del m
print("\n  ГРАНИЦА ПАРЕТО (дешевле И лучше одновременно):")
for nm,K,sb,sbw,tot,p in sorted(rows,key=lambda r:r[4]):
    dom=[o for o in rows if o[4]<=tot and o[5]<p and o[0]!=nm]
    if not dom: print(f"    {nm:26} {tot:.4f} б/вес  ppl={p:.4f}")
json.dump({"tag":TAG,"baseline":base,"rows":rows}, open(f"scale_frontier_{TAG}.json","w"), indent=1)
