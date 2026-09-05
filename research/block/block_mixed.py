"""Do the two-segment ladders that win on squared error win on perplexity?

They win on squared error by a lot -- the best is 1.54x the Lloyd-Max bound
against MXFP4's 14.97x. That is a reason to measure, not a result: squared error
was tested as a predictor on this axis one iteration ago and failed, selecting
r*=1.3308 which measured 37.06 while a ladder it ranked worse measured 23.36.

So this measures perplexity, under the protocol the earlier block runs used, and
the squared-error table is treated as what it is: a way to choose which twelve
candidates to spend a perplexity run on.
"""
import os, json, numpy as np, torch
from transformers import AutoModelForCausalLM, AutoTokenizer
W = ("/private/tmp/claude-501/-Users-ssdm4-Desktop-PROJECTS-CLAUDE/"
     "0e868af8-ab2d-4d00-be03-8fea94ba48e4/scratchpad/weights")
MODEL = os.path.join(W, "smollm2"); K, SEQLEN, NW = 32, 2048, 40
torch.set_grad_enabled(False)
def e8m0(s): return torch.pow(2.0, torch.ceil(torch.log2(s.clamp(min=1e-30))))
def e2m1():
    out={0.0}
    for e in range(4):
        for m in range(2): out.add((m/2.0) if e==0 else (1+m/2.0)*2.0**(e-1))
    return sorted(out)
H = {"shift":2.0,"phi":1.618033989,"supergold":1.465571232,
     "plastic":1.324717957,"deg4":1.178724176}
def two_seg(rt, rb, nt, n=7):
    lv=[1.0]
    for _ in range(nt): lv.append(lv[-1]/rt)
    while len(lv) < n: lv.append(lv[-1]/rb)
    return sorted([0.0]+lv[:n])
def quantise(w, lv):
    lv_t = torch.tensor(sorted(lv), dtype=torch.float64)
    n=(w.shape[1]//K)*K
    if n==0: return w
    head = w[:,:n].reshape(-1,K).double()
    s = e8m0((head.abs().amax(dim=1)/lv_t[-1]).clamp(min=1e-30)).clamp(min=1e-30)
    y = (head/s[:,None]).abs(); bnd=(lv_t[:-1]+lv_t[1:])/2
    rec = torch.sign(head)*lv_t[torch.bucketize(y,bnd)]*s[:,None]
    out = w.clone(); out[:,:n]=rec.reshape(-1,n).to(w.dtype); return out
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
LLOYD = json.load(open("block_bound.json"))["lloyd"]
CAND = {
 "MXFP4 (E2M1) [контроль]": e2m1(),
 "Lloyd-Max [предел, не реализуем]": LLOYD,
 "supergold/plastic top4": two_seg(H["supergold"],H["plastic"],4),
 "supergold/plastic top3": two_seg(H["supergold"],H["plastic"],3),
 "supergold/deg4 top4":    two_seg(H["supergold"],H["deg4"],4),
 "phi/supergold top2":     two_seg(H["phi"],H["supergold"],2),
 "phi/plastic top2":       two_seg(H["phi"],H["plastic"],2),
 "shift/supergold top2":   two_seg(H["shift"],H["supergold"],2),
 "shift/phi top2":         two_seg(H["shift"],H["phi"],2),
 "shift/plastic top3":     two_seg(H["shift"],H["plastic"],3),
}
base = ppl(fresh(), ids); print(f"  базовая fp32 = {base:.4f}\n", flush=True)
rows=[]
for nm, lv in CAND.items():
    m=fresh()
    for _,mod in m.named_modules():
        if isinstance(mod,torch.nn.Linear) and "lm_head" not in _:
            mod.weight.data = quantise(mod.weight.data, lv)
    p=ppl(m,ids); rows.append((nm,p))
    print(f"  {nm:36} ppl={p:9.4f}", flush=True); del m
mx=[p for n,p in rows if n.startswith("MXFP4")][0]
best=min((r for r in rows if "предел" not in r[0]), key=lambda t:t[1])
print(f"\n  MXFP4          : {mx:.4f}")
print(f"  лучший реализуемый: {best[0]}  {best[1]:.4f}")
print(f"  ИТОГ: {'ПОБЕДА' if best[1] < mx else 'проигрыш'}  ({(mx-best[1])/mx*100:+.2f}%)")
json.dump({"baseline":base,"rows":rows}, open("block_mixed.json","w"), indent=1)
