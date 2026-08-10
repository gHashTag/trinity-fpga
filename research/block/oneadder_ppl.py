"""Does the one-adder family deliver on a network, as scale and as element?

T38 says r^d = r + 1 costs one addition at every degree and its roots approach
2^(1/d). Silicon agrees: a fivefold refinement costs 51% more LUTs and no
frequency. The arithmetic and the fabric are settled; the network is not.

Two questions:
  * as a BLOCK SCALE, does a multiply-free ratio within 0.06% of the optimum
    measure like the optimum? If so the lower frontier is ours without a
    multiplier.
  * as an ELEMENT ladder, where the earlier sweep only had degrees 1-3.
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

def root(d, k=1):
    """real root >1 of r^d = r^k + 1"""
    c=[0.0]*(d+1); c[0]=1.0; c[d-k]-=1.0; c[d]-=1.0
    return max(z.real for z in np.roots(c) if abs(z.imag)<1e-9 and z.real>1)

R5  = root(5,3)        # 1.236506  -- 0.06% от оптимума при 5 битах
R6  = root(6,1)        # 1.134724
R6b = root(6,4)        # ближе к оптимуму 6 бит
R8  = root(8,1)        # 1.096982
PHI = (1+5**0.5)/2
OPT5 = 2.0**(9.5/31); OPT6 = 2.0**(9.5/63)

def grid(raw, g, nbits):
    k=torch.ceil(torch.log(raw)/np.log(g))
    lo=k.min(); k=torch.clamp(k-lo,0,2**nbits-1)+lo
    return torch.pow(g,k)
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
CAND=[
 ("phi          r^2=r+1   4b", PHI, 4),
 ("оптимум 5б   (умножитель)", OPT5, 5),
 ("MF r^5=r^3+1  0.06% от опт 5b", R5, 5),
 ("оптимум 6б   (умножитель)", OPT6, 6),
 ("MF r^6=r^4+1  6b", R6b, 6),
 ("MF r^8=r+1    6b", R8, 6),
]
base=ppl(fresh(),ids); print(f"  {TAG}: базовая fp32 = {base:.4f}\n",flush=True)
print(f"  {'масштаб':32} {'r':>10} {'бит':>4} {'б/вес':>8} {'ppl':>9}",flush=True)
rows=[]
for nm,g,b in CAND:
    m=fresh()
    for _,mod in m.named_modules():
        if isinstance(mod,torch.nn.Linear) and "lm_head" not in _:
            mod.weight.data=quantise(mod.weight.data, lambda r,g=g,b=b: grid(r,g,b))
    p=ppl(m,ids); rows.append((nm,g,b,4.0+b/K,p))
    print(f"  {nm:32} {g:10.6f} {b:4} {4.0+b/K:8.4f} {p:9.4f}",flush=True); del m
for a,bb in ((1,2),(3,4)):
    if len(rows)>bb:
        d=(rows[bb][4]-rows[a][4])/rows[a][4]*100
        print(f"\n  multiply-free против оптимума ({rows[a][2]}б): "
              f"{rows[bb][4]:.4f} против {rows[a][4]:.4f}  ({d:+.2f}%)")
json.dump({"tag":TAG,"baseline":base,"rows":rows},open(f"oneadder_ppl_{TAG}.json","w"),indent=1)
