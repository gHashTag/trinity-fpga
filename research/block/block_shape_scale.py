"""Two unexplored parts of the block axis: the block's shape, and the scale.

The 0.9% ceiling was measured at K=32 along the contraction axis with an E8M0
scale, which is the MX specification's choice and not a law. Two things were
never varied:

  * the SHAPE. A different K changes the within-block distribution, and the
    ceiling was computed from that distribution.
  * the SCALE. E8M0 is a bare power of two, one per 32 elements, so its cost is
    amortised 32-fold -- which is exactly the regime where a finer scale grid is
    affordable. phi^k halves the scale-grid step against 2^k at the same
    exponent width, and phi^k is what this work's datapath applies natively.

Both are cheap to test and the first decides whether the second is worth doing.
"""
import os, json, numpy as np, torch
from transformers import AutoModelForCausalLM, AutoTokenizer
W = ("/private/tmp/claude-501/-Users-ssdm4-Desktop-PROJECTS-CLAUDE/"
     "0e868af8-ab2d-4d00-be03-8fea94ba48e4/scratchpad/weights")
MODEL = os.path.join(W, "smollm2"); SEQLEN, NW = 2048, 40
PHI = (1 + 5 ** 0.5) / 2
torch.set_grad_enabled(False)

def e2m1():
    out = {0.0}
    for e in range(4):
        for m in range(2): out.add((m/2.0) if e == 0 else (1+m/2.0)*2.0**(e-1))
    return sorted(out)
LV = torch.tensor(e2m1(), dtype=torch.float64)

def scale_pow2(s):  return torch.pow(2.0, torch.ceil(torch.log2(s.clamp(min=1e-30))))
def scale_phi(s):   return torch.pow(PHI, torch.ceil(torch.log(s.clamp(min=1e-30))/np.log(PHI)))

def quantise(w, K, scale_fn):
    n = (w.shape[1]//K)*K
    if n == 0: return w
    head = w[:, :n].reshape(-1, K).double()
    s = scale_fn((head.abs().amax(dim=1)/LV[-1]).clamp(min=1e-30)).clamp(min=1e-30)
    y = (head/s[:, None]).abs(); bnd = (LV[:-1]+LV[1:])/2
    rec = torch.sign(head)*LV[torch.bucketize(y, bnd)]*s[:, None]
    out = w.clone(); out[:, :n] = rec.reshape(-1, n).to(w.dtype); return out

def ppl(m, ids):
    n = (ids.numel()//SEQLEN)*SEQLEN; x = ids[:n].reshape(-1, SEQLEN)[:NW]
    nll = cnt = 0
    for i in range(x.shape[0]):
        c = x[i:i+1]; nll += m(c, labels=c).loss.double().item()*(SEQLEN-1); cnt += SEQLEN-1
    return float(np.exp(nll/cnt))

def lloyd_bound(x, n_lv=8, iters=200):
    lv = np.array(sorted(set([0.0]+list(np.quantile(x, np.linspace(0.2, 1.0, n_lv-1))))))
    for _ in range(iters):
        b = (lv[:-1]+lv[1:])/2; idx = np.searchsorted(b, x); new = lv.copy()
        for k in range(len(lv)):
            s = x[idx == k]
            if s.size: new[k] = s.mean()
        new[0] = 0.0
        if np.allclose(new, lv, atol=1e-12): break
        lv = np.sort(new)
    b = (lv[:-1]+lv[1:])/2
    return float(np.mean((lv[np.searchsorted(b, x)]-x)**2)), lv

tok = AutoTokenizer.from_pretrained(MODEL)
import pyarrow.parquet as pq
text = "\n\n".join(pq.read_table(os.path.join(W,"wikitext2-test.parquet")).column("text").to_pylist())
ids = tok(text, return_tensors="pt").input_ids[0]
def fresh():
    m = AutoModelForCausalLM.from_pretrained(MODEL, dtype=torch.float32); m.eval(); return m

base = ppl(fresh(), ids); print(f"  базовая fp32 = {base:.4f}\n", flush=True)
m0 = fresh()
lin = [(nm, mod) for nm, mod in m0.named_modules()
       if isinstance(mod, torch.nn.Linear) and "lm_head" not in nm]

print(f"  {'K':>5} {'кв.ошибка E2M1':>16} {'предел Ллойда':>14} {'x предела':>10} "
      f"{'ppl 2^k':>9} {'ppl phi^k':>10}", flush=True)
rows = []
for K in (8, 16, 32, 64, 128):
    # распределение внутри блока данной формы
    bl = []
    for nm, mod in lin:
        w = mod.weight.data.double(); n = (w.shape[1]//K)*K
        if n == 0: continue
        h = w[:, :n].reshape(-1, K).abs()
        v = (h/h.amax(dim=1, keepdim=True).clamp_min(1e-12)).flatten()
        bl.append(v[::max(1, v.numel()//40000)].numpy())
    x = np.concatenate(bl).astype(np.float64)
    lb, _ = lloyd_bound(x)
    lvn = LV.numpy(); bnd = (lvn[:-1]+lvn[1:])/2
    e_mx = float(np.mean((lvn[np.searchsorted(bnd, x)]-x)**2))
    res = {}
    for tagn, fn in (("2^k", scale_pow2), ("phi^k", scale_phi)):
        m = fresh()
        for nm, mod in m.named_modules():
            if isinstance(mod, torch.nn.Linear) and "lm_head" not in nm:
                mod.weight.data = quantise(mod.weight.data, K, fn)
        res[tagn] = ppl(m, ids); del m
    rows.append((K, e_mx, lb, e_mx/lb, res["2^k"], res["phi^k"]))
    print(f"  {K:5} {e_mx:16.4e} {lb:14.4e} {e_mx/lb:10.2f} "
          f"{res['2^k']:9.4f} {res['phi^k']:10.4f}"
          + ("   <-- phi ЛУЧШЕ" if res["phi^k"] < res["2^k"] else ""), flush=True)
json.dump({"baseline": base, "rows": rows}, open("block_shape_scale.json","w"), indent=1)
