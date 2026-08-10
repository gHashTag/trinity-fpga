"""At EQUAL bits, does a scale with a mantissa still beat a geometric grid?

Yesterday's frontier concluded that a mantissa in the scale beats any geometric
grid. The comparison behind that sentence gave E4M3 eight bits and the phi grid
four. That is not a comparison, and the conclusion drawn from it is not safe.

There is also a reason to expect the opposite. Block scales are log-distributed;
the grid minimising the worst-case log error over a fixed range with N points is
uniform in log, i.e. purely geometric with ratio R^(1/N). A float scale
2^e (1+m/2^k) is piecewise linear between powers of two and therefore NOT
uniform in log -- it spends resolution unevenly across each binade.

So this sweeps geometric grids at 5..8 bits against E4M3 at 8, all at K=32.
"""
import os, sys, json, numpy as np, torch
from transformers import AutoModelForCausalLM, AutoTokenizer
W=("/private/tmp/claude-501/-Users-ssdm4-Desktop-PROJECTS-CLAUDE/"
   "0e868af8-ab2d-4d00-be03-8fea94ba48e4/scratchpad/weights")
TAG=sys.argv[1] if len(sys.argv)>1 else "smollm2"
MODEL=os.path.join(W,TAG); K,SEQLEN,NW=32,2048,40
torch.set_grad_enabled(False)
def e2m1():
    o={0.0}
    for e in range(4):
        for m in range(2): o.add((m/2.0) if e==0 else (1+m/2.0)*2.0**(e-1))
    return sorted(o)
LV=torch.tensor(e2m1(),dtype=torch.float64)
PHI=(1+5**0.5)/2

def geo(raw, nbits, span_binades=9.5):
    """Geometric grid: 2^nbits points spread uniformly in log over the range the
    scales actually occupy. This is the log-optimal grid at that width."""
    g = 2.0 ** (span_binades / (2**nbits - 1))
    k = torch.ceil(torch.log(raw)/np.log(g))
    lo = k.min(); k = torch.clamp(k-lo, 0, 2**nbits-1)+lo
    return torch.pow(g, k)
def phigeo(raw, nbits):
    k = torch.ceil(torch.log(raw)/np.log(PHI))
    lo = k.min(); k = torch.clamp(k-lo, 0, 2**nbits-1)+lo
    return torch.pow(PHI, k)
def e4m3(raw, mbits=3):
    e = torch.floor(torch.log2(raw)); frac = raw/torch.pow(2.0,e)
    q = torch.clamp(torch.ceil((frac-1.0)*(2**mbits))/(2**mbits), 0, 1)
    return torch.pow(2.0,e)*(1.0+q)
def quantise(w, fn):
    n=(w.shape[1]//K)*K
    if n==0: return w
    head=w[:,:n].reshape(-1,K).double()
    raw=(head.abs().amax(dim=1)/LV[-1]).clamp(min=1e-30)
    s=fn(raw).clamp(min=1e-30)
    y=(head/s[:,None]).abs(); bnd=(LV[:-1]+LV[1:])/2
    rec=torch.sign(head)*LV[torch.bucketize(y,bnd)]*s[:,None]
    out=w.clone(); out[:,:n]=rec.reshape(-1,n).to(w.dtype); return out
def ppl(m,ids):
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
CAND=[("geo  5 бит", 5, lambda r: geo(r,5)),
      ("geo  6 бит", 6, lambda r: geo(r,6)),
      ("geo  7 бит", 7, lambda r: geo(r,7)),
      ("geo  8 бит", 8, lambda r: geo(r,8)),
      ("phi  4 бита",4, lambda r: phigeo(r,4)),
      ("E4M3 7 бит", 7, lambda r: e4m3(r,3)),
      ("E4M3 8 бит", 8, lambda r: e4m3(r,3)),
      ("E5M2 7 бит", 7, lambda r: e4m3(r,2)),
     ]
base=ppl(fresh(),ids); print(f"  {TAG}: базовая fp32 = {base:.4f}\n",flush=True)
print(f"  {'схема':14} {'бит':>4} {'б/вес всего':>12} {'ppl':>9}",flush=True)
rows=[]
for nm,b,fn in CAND:
    m=fresh()
    for _,mod in m.named_modules():
        if isinstance(mod,torch.nn.Linear) and "lm_head" not in _:
            mod.weight.data=quantise(mod.weight.data,fn)
    p=ppl(m,ids); tot=4.0+b/K; rows.append((nm,b,tot,p))
    print(f"  {nm:14} {b:4} {tot:12.4f} {p:9.4f}",flush=True); del m
for b in (7,8):
    g=[r for r in rows if r[1]==b and r[0].startswith("geo")]
    e=[r for r in rows if r[1]==b and r[0].startswith("E4M3")]
    if g and e:
        print(f"\n  ПРИ {b} БИТАХ: геометрическая {g[0][3]:.4f}  против E4M3 {e[0][3]:.4f}"
              f"  -> {'ГЕОМЕТРИЧЕСКАЯ ЛУЧШЕ' if g[0][3]<e[0][3] else 'мантисса лучше'}")
json.dump({"tag":TAG,"baseline":base,"rows":rows},open(f"scale_equalbits_{TAG}.json","w"),indent=1)
