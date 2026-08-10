"""Is the win from phi, or merely from a finer scale grid?

Replacing the E8M0 power-of-two block scale with a phi-power scale improved
perplexity 5.1% at K=32 -- five times the entire element-codebook ceiling. The
obvious mechanism is granularity: rounding a block's scale UP to the next grid
point wastes range, and a finer grid wastes less.

If that is the whole story then sqrt(2) = 1.414, being FINER than phi = 1.618,
must win by more. If phi wins against a finer grid, granularity is not the whole
story. Either answer is worth having, and only one of them is about phi.

Also runs the second model, which is the step that has killed two explanations
tonight already.
"""
import os, sys, json, numpy as np, torch
from transformers import AutoModelForCausalLM, AutoTokenizer
W = ("/private/tmp/claude-501/-Users-ssdm4-Desktop-PROJECTS-CLAUDE/"
     "0e868af8-ab2d-4d00-be03-8fea94ba48e4/scratchpad/weights")
TAG = sys.argv[1] if len(sys.argv) > 1 else "smollm2"
MODEL = os.path.join(W, TAG); K, SEQLEN, NW = 32, 2048, 40
torch.set_grad_enabled(False)
def e2m1():
    out={0.0}
    for e in range(4):
        for m in range(2): out.add((m/2.0) if e==0 else (1+m/2.0)*2.0**(e-1))
    return sorted(out)
LV = torch.tensor(e2m1(), dtype=torch.float64)
GRIDS = {
 "2^k        (E8M0, MX spec)": 2.0,
 "phi^k      (1.6180)":        (1+5**0.5)/2,
 "sqrt2^k    (1.4142) FINER":  2.0**0.5,
 "2^(k/4)    (1.1892) FINER":  2.0**0.25,
 "plastic^k  (1.3247)":        1.324717957244746,
}
def quantise(w, g):
    n=(w.shape[1]//K)*K
    if n==0: return w
    head=w[:,:n].reshape(-1,K).double()
    raw=(head.abs().amax(dim=1)/LV[-1]).clamp(min=1e-30)
    s=torch.pow(g, torch.ceil(torch.log(raw)/np.log(g))).clamp(min=1e-30)
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
base=ppl(fresh(),ids); print(f"  {TAG}: базовая fp32 = {base:.4f}\n", flush=True)
rows=[]
for nm,g in GRIDS.items():
    m=fresh()
    for _,mod in m.named_modules():
        if isinstance(mod,torch.nn.Linear) and "lm_head" not in _:
            mod.weight.data=quantise(mod.weight.data,g)
    p=ppl(m,ids); rows.append((nm,g,p))
    # сколько бит нужно экспоненте, чтобы покрыть тот же диапазон, что 2^8
    bits=np.log2(256*np.log(2)/np.log(g))
    print(f"  {nm:28} шаг={g:.4f}  экспоненте нужно {bits:.1f} бит  ppl={p:8.4f}", flush=True)
    del m
b=min(rows,key=lambda t:t[2]); ref=[r for r in rows if r[0].startswith("2^k")][0]
print(f"\n  лучший: {b[0]} {b[2]:.4f}   против 2^k {ref[2]:.4f}  ({(ref[2]-b[2])/ref[2]*100:+.2f}%)")
json.dump({"tag":TAG,"baseline":base,"rows":rows}, open(f"scale_control_{TAG}.json","w"), indent=1)
