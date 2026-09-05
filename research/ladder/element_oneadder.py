"""The one-adder family as an ELEMENT ladder, not just as a block scale.

The ladder law was measured over degrees 1-3 only: shift, phi, supergolden,
plastic. T38 then showed that r^d = r + 1 costs one addition at every degree, so
degrees 5 and 8 are as cheap to apply as phi is. The law says the optimal rung
falls as the budget rises; the family now reaches much further down.
"""
import os, sys, json, numpy as np, torch
from transformers import AutoModelForCausalLM, AutoTokenizer
W=("/private/tmp/claude-501/-Users-ssdm4-Desktop-PROJECTS-CLAUDE/"
   "0e868af8-ab2d-4d00-be03-8fea94ba48e4/scratchpad/weights")
TAG=sys.argv[1] if len(sys.argv)>1 else "smollm2"
MODEL=os.path.join(W,TAG); SEQLEN,WINDOWS=2048,12
torch.set_grad_enabled(False)
def root(d,k=1):
    c=[0.0]*(d+1); c[0]=1.0; c[d-k]-=1.0; c[d]-=1.0
    return max(z.real for z in np.roots(c) if abs(z.imag)<1e-9 and z.real>1)
RAT={
 "shift        2.0000  d1 0 add": 2.0,
 "phi          1.6180  d2 1 add": (1+5**0.5)/2,
 "plastic      1.3247  d3 1 add": root(3,1),
 "r^4=r+1      1.2207  d4 1 add": root(4,1),
 "r^5=r^3+1    1.2365  d5 1 add": root(5,3),
 "r^6=r+1      1.1347  d6 1 add": root(6,1),
 "r^8=r+1      1.0970  d8 1 add": root(8,1),
}
def codebook(r,bits):
    n=(2**bits-1)//2
    return np.array([0.0]+[r**(-k) for k in range(n)]+[-r**(-k) for k in range(n)])
def quantise_(w,cb):
    o=w.data.to(torch.float64)
    s=o.abs().amax(dim=1,keepdim=True).clamp_min(1e-12)
    x=(o/s).cpu().numpy()
    idx=np.abs(x[...,None]-cb[None,None,:]).argmin(axis=-1)
    w.data=torch.from_numpy(cb[idx]).to(torch.float64).mul_(s).to(w.dtype)
def ppl(m,ids):
    n=(ids.numel()//SEQLEN)*SEQLEN; x=ids[:n].reshape(-1,SEQLEN)[:WINDOWS]
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
base=ppl(fresh(),ids); print(f"  {TAG}: базовая fp32 = {base:.4f}\n",flush=True)
rows=[]
for bits in (4,5,6):
    print(f"  ─── {bits} бит ───",flush=True)
    for nm,r in RAT.items():
        m=fresh(); cb=codebook(r,bits)
        for n_,mod in m.named_modules():
            if isinstance(mod,torch.nn.Linear) and "lm_head" not in n_:
                quantise_(mod.weight,cb)
        p=ppl(m,ids); span=r**((2**bits-1)//2-1)
        rows.append((bits,nm,r,span,p))
        print(f"    {nm:32} охват={span:8.1f}x  ppl={p:10.4f}",flush=True); del m
    best=min([x for x in rows if x[0]==bits],key=lambda t:t[4])
    print(f"    ЛУЧШАЯ: {best[1]}  {best[4]:.4f}",flush=True)
json.dump({"tag":TAG,"baseline":base,"rows":rows},open(f"element_oneadder_{TAG}.json","w"),indent=1)
