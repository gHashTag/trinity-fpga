"""How far is MXFP4 from the best possible eight-level codebook?

Two attacks on the block axis have lost to E2M1. Before designing a third, the
question worth answering is whether there is anything to win: if E2M1 sits close
to the optimal eight-magnitude codebook for this distribution, the axis is
closed and no format will take it. If there is a gap, the gap is the budget for
a third attempt.

Lloyd-Max on the within-block distribution gives the optimum for squared error.
It is not multiply-free and not implementable as a ladder -- it is a bound, and
a bound is what is being asked for.

The two-segment sweep is the constructive part: E2M1's ratios run 2, 1.5, 1.33,
1.5, 1.33, 1.5, so it spends fine steps at the top and coarse at the bottom. A
ladder with one ratio at the top and another below can do the same, and both
ratios can be drawn from the multiply-free hierarchy.
"""
import os, json, itertools, numpy as np, torch
from transformers import AutoModelForCausalLM, AutoTokenizer
W = ("/private/tmp/claude-501/-Users-ssdm4-Desktop-PROJECTS-CLAUDE/"
     "0e868af8-ab2d-4d00-be03-8fea94ba48e4/scratchpad/weights")
MODEL = os.path.join(W, "smollm2")
K, SEQLEN, NW = 32, 2048, 40
torch.set_grad_enabled(False)

def e8m0(s): return torch.pow(2.0, torch.ceil(torch.log2(s.clamp(min=1e-30))))
def e2m1():
    out={0.0}
    for e in range(4):
        for m in range(2):
            out.add((m/2.0) if e==0 else (1+m/2.0)*2.0**(e-1))
    return sorted(out)

m0 = AutoModelForCausalLM.from_pretrained(MODEL, dtype=torch.float32); m0.eval()
lin = [(nm,mod) for nm,mod in m0.named_modules()
       if isinstance(mod, torch.nn.Linear) and "lm_head" not in nm]
bl=[]
for nm,mod in lin:
    w = mod.weight.data.double(); n=(w.shape[1]//K)*K
    if n==0: continue
    h = w[:,:n].reshape(-1,K).abs()
    v = (h/h.amax(dim=1,keepdim=True).clamp_min(1e-12)).flatten()
    bl.append(v[::max(1,v.numel()//80000)].numpy())
x = np.concatenate(bl).astype(np.float64); del bl
print(f"  внутриблочных значений: {x.size:,}", flush=True)

def q_err(lv, x):
    lv = np.asarray(sorted(lv)); b=(lv[:-1]+lv[1:])/2
    return float(np.mean((lv[np.searchsorted(b,x)]-x)**2))

# --- Ллойд-Макс: оптимальные 8 уровней (0 закреплён, как у всех кандидатов) ---
lv = np.array(sorted(set([0.0] + list(np.quantile(x, np.linspace(0.2,1.0,7))))))
for it in range(200):
    b = (lv[:-1]+lv[1:])/2
    idx = np.searchsorted(b, x)
    new = lv.copy()
    for k in range(len(lv)):
        s = x[idx==k]
        if s.size: new[k] = s.mean()
    new[0] = 0.0                      # ноль обязателен: разрежённость бесплатна
    if np.allclose(new, lv, atol=1e-12): break
    lv = np.sort(new)
LLOYD = lv
print(f"  Ллойд-Макс сошёлся за {it+1} итераций", flush=True)
print(f"    уровни: {[round(v,4) for v in LLOYD]}", flush=True)

# --- двухсегментные лестницы из иерархии ---
HIER = {"shift":2.0, "phi":1.618033989, "supergold":1.465571232,
        "plastic":1.324717957, "deg4":1.178724176}
def two_seg(r_top, r_bot, n_top, n_mag=7):
    """n_top steps at ratio r_top from 1 downward, the rest at r_bot."""
    lv=[1.0]
    for _ in range(n_top): lv.append(lv[-1]/r_top)
    while len(lv) < n_mag: lv.append(lv[-1]/r_bot)
    return sorted([0.0]+lv[:n_mag])

cands = {"MXFP4 (E2M1)": e2m1(), "Lloyd-Max bound": list(LLOYD)}
for (na,ra),(nb,rb) in itertools.product(HIER.items(), repeat=2):
    if ra <= rb: continue                       # верх должен быть ТОНЬШЕ низа
    for nt in (2,3,4):
        cands[f"{na[:4]}/{nb[:4]} top{nt}"] = two_seg(ra, rb, nt)
errs = {k: q_err(v, x) for k, v in cands.items()}
best = sorted(errs.items(), key=lambda kv: kv[1])
print(f"\n  ошибка квантования на внутриблочном распределении:")
mx = errs["MXFP4 (E2M1)"]; lb = errs["Lloyd-Max bound"]
print(f"    {'Ллойд-Макс (предел)':32} {lb:.6e}   1.00x")
print(f"    {'MXFP4 (E2M1)':32} {mx:.6e}   {mx/lb:.2f}x предела")
print(f"\n  лучшие двухсегментные из иерархии:")
for k,v in best:
    if k in ("MXFP4 (E2M1)","Lloyd-Max bound"): continue
    print(f"    {k:32} {v:.6e}   {v/lb:.2f}x предела   "
          f"{'ЛУЧШЕ MXFP4' if v < mx else ''}")
    if v > mx*1.6: break
json.dump({"lloyd": list(LLOYD), "err": errs}, open("block_bound.json","w"), indent=1)
