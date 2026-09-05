"""Does a phi-family ladder beat MXFP4 on the block axis?

The block axis was measured and lost, but what was measured there was TNF4 -- a
ternary-exponent float, which pays a packing remainder because 3^E never divides
2^k. A geometric ladder pays no such remainder: eight magnitudes are eight
magnitudes, exactly as E2M1 has eight.

And our own law makes a prediction here. Within a block of 32 the span is
1.89 binades median, not the 269x of a whole channel, and a small span moves the
optimum toward a FINER ratio. So the rung that should win on the block axis is
not phi -- it is further down the hierarchy.

Protocol identical to the earlier block measurement: K=32 along the contraction
axis, E8M0 shared scale (the MX spec's own), same model, same windows.
"""
import os, sys, json, numpy as np, torch
from transformers import AutoModelForCausalLM, AutoTokenizer
W = ("/private/tmp/claude-501/-Users-ssdm4-Desktop-PROJECTS-CLAUDE/"
     "0e868af8-ab2d-4d00-be03-8fea94ba48e4/scratchpad/weights")
MODEL = os.path.join(W, "smollm2")
K, SEQLEN, NW = 32, 2048, 40
torch.set_grad_enabled(False)

def e8m0(s):
    return torch.pow(2.0, torch.ceil(torch.log2(s.clamp(min=1e-30))))

def e2m1_levels():
    """OCP MXFP4 element: E2M1, no Inf/NaN reservation -- eight magnitudes."""
    out = {0.0}
    for e in range(4):
        for m in range(2):
            if e == 0: v = (m / 2.0) * 2.0 ** (-0)      # subnormal
            else:      v = (1 + m / 2.0) * 2.0 ** (e - 1)
            out.add(v)
    return sorted(out)

def ladder_levels(r, n_mag=7):
    """Zero plus n_mag magnitudes in geometric progression -- eight in total,
    matching E2M1's count exactly."""
    return sorted([0.0] + [r ** (-k) for k in range(n_mag)])

def quantise(w, lv):
    lv_t = torch.tensor(lv, dtype=torch.float64)
    orig = w.shape; n = (orig[1] // K) * K
    if n == 0: return w
    head = w[:, :n].reshape(-1, K).double()
    s = e8m0((head.abs().amax(dim=1) / lv_t[-1]).clamp(min=1e-30)).clamp(min=1e-30)
    y = (head / s[:, None]).abs()
    bnd = (lv_t[:-1] + lv_t[1:]) / 2
    rec = torch.sign(head) * lv_t[torch.bucketize(y, bnd)] * s[:, None]
    out = w.clone(); out[:, :n] = rec.reshape(-1, n).to(w.dtype)
    return out

def perplexity(m, ids):
    n = (ids.numel() // SEQLEN) * SEQLEN
    x = ids[:n].reshape(-1, SEQLEN)[:NW]
    nll = cnt = 0
    for i in range(x.shape[0]):
        c = x[i:i+1]; nll += m(c, labels=c).loss.double().item() * (SEQLEN-1); cnt += SEQLEN-1
    return float(np.exp(nll/cnt))

tok = AutoTokenizer.from_pretrained(MODEL)
import pyarrow.parquet as pq
text = "\n\n".join(pq.read_table(os.path.join(W,"wikitext2-test.parquet")).column("text").to_pylist())
ids = tok(text, return_tensors="pt").input_ids[0]
def fresh():
    m = AutoModelForCausalLM.from_pretrained(MODEL, dtype=torch.float32); m.eval(); return m

# ---- сначала закон: какое r оптимально ВНУТРИ БЛОКА -------------------------
m0 = fresh()
blocks = []
for nm, mod in m0.named_modules():
    if isinstance(mod, torch.nn.Linear) and "lm_head" not in nm:
        w = mod.weight.data.double(); n = (w.shape[1]//K)*K
        if n == 0: continue
        h = w[:, :n].reshape(-1, K).abs()
        s = h.amax(dim=1, keepdim=True).clamp_min(1e-12)
        v = (h/s).flatten()
        blocks.append(v[::max(1, v.numel()//60000)].numpy())
bx = np.concatenate(blocks).astype(np.float64); del blocks
def c2(r):
    u = np.linspace(0,1,20001); x = r**(-u)
    return float(np.mean((np.minimum(np.abs(x-1.0), np.abs(x-1.0/r))/x)**2))
def mse(x, r, nmag=7):
    t = r**(-(nmag-1))/2; b = x < t
    return (c2(r)*float((x[~b]**2).sum()) + float((x[b]**2).sum()))/x.size
grid = np.linspace(1.05, 2.4, 400)
rstar = float(grid[int(np.argmin([mse(bx, float(v)) for v in grid]))])
span = float(np.log2(1/np.quantile(bx, 0.01)))
print(f"  внутриблочных значений: {bx.size:,}", flush=True)
print(f"  размах внутри блока (до 1-го процентиля): {span:.2f} бинад", flush=True)
print(f"  ЗАКОН ГОВОРИТ: r* = {rstar:.4f}  при 8 величинах\n", flush=True)
del m0

CAND = {
    "MXFP4 (E2M1, 8 mag)":  e2m1_levels(),
    "phi     1.6180":       ladder_levels((1+5**0.5)/2),
    "supergold 1.4656":     ladder_levels(1.465571231876768),
    "plastic 1.3247":       ladder_levels(1.324717957244746),
    "deg4    1.1787":       ladder_levels(1.178724176),
    f"r* = {rstar:.4f}":    ladder_levels(rstar),
}
base = perplexity(fresh(), ids)
print(f"  базовая fp32 = {base:.4f}\n", flush=True)
rows = []
for nm, lv in CAND.items():
    m = fresh()
    for _, mod in m.named_modules():
        if isinstance(mod, torch.nn.Linear) and "lm_head" not in _:
            mod.weight.data = quantise(mod.weight.data, lv)
    p = perplexity(m, ids)
    sp = lv[-1]/min(v for v in lv if v > 0)
    rows.append((nm, len(lv), sp, p))
    print(f"  {nm:22} величин={len(lv)}  размах={sp:7.2f}x  ppl={p:9.4f}", flush=True)
    del m
json.dump({"baseline": base, "rstar": rstar, "block_span_binades": span,
           "rows": [{"name":a,"mags":b,"span":c,"ppl":d} for a,b,c,d in rows]},
          open("block_ladder.json","w"), indent=1)
best = min(rows, key=lambda t: t[3])
print(f"\n  ЛУЧШИЙ: {best[0]}  ppl={best[3]:.4f}")
mx = [r for r in rows if r[0].startswith("MXFP4")][0]
print(f"  MXFP4 : {mx[3]:.4f}   -> {'ПОБЕДА' if best[3] < mx[3] else 'проигрыш'}"
      f"  ({(mx[3]-best[3])/mx[3]*100:+.2f}%)")
