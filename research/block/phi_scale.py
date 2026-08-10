#!/usr/bin/env python3
"""The decisive test the phi alphabet has never been given: does snapping a
layer's scale to a power of phi cost anything?

BitNet b1.58 and every derivative store ternary weights plus a REAL per-layer
scale alpha = mean|W|.  Applying alpha is a genuine multiply, so the multiplier
the ternary weights removed comes straight back at the layer boundary.

Three scale grids, same ternary weights, same everything else:

  exact alpha   real number      needs a multiplier          (BitNet)
  alpha = 2^k   power of two     needs a shift               (free, coarse)
  alpha = phi^k power of phi     needs shift-and-add         (free, 1.44x finer)

The phi grid is denser than the power-of-two grid by log(2)/log(phi) = 1.44 at
the same cost class, and by Z[phi] closure it is applied exactly.  So the
prediction, made before measuring:

    ppl(exact)  <=  ppl(phi^k)  <  ppl(2^k)

and the gap phi-to-exact should be roughly half the gap two-to-exact.

Falsifiable: if phi^k does not beat 2^k, the density argument is wrong and the
alphabet's practical case rests on exactness alone.

RULER CHECK: the unquantised baseline must land in a plausible band first.
"""
import os, sys, math
import numpy as np, torch
from transformers import AutoModelForCausalLM, AutoTokenizer
torch.set_grad_enabled(False)

W = ("/private/tmp/claude-501/-Users-ssdm4-Desktop-PROJECTS-CLAUDE/"
     "0e868af8-ab2d-4d00-be03-8fea94ba48e4/scratchpad/weights")
MODEL, SEQLEN, NWIN = os.path.join(W, "smollm2"), 2048, 40
PHI = (1 + 5 ** 0.5) / 2

def target_modules(model):
    return [(n, m) for n, m in model.named_modules()
            if isinstance(m, torch.nn.Linear) and "lm_head" not in n]

def load_wikitext():
    import pyarrow.parquet as pq
    t = pq.read_table(os.path.join(W, "wikitext2-test.parquet"))
    return "\n\n".join(t.column("text").to_pylist())

def perplexity(model, ids, limit=None):
    flat = ids.reshape(-1)
    n = (flat.numel() // SEQLEN) * SEQLEN
    x = flat[:n].view(-1, SEQLEN)
    if limit: x = x[:limit]
    nll = cnt = 0.0
    for i in range(x.shape[0]):
        c = x[i:i + 1]
        nll += model(c, labels=c).loss.double().item() * (SEQLEN - 1)
        cnt += SEQLEN - 1
    return float(np.exp(nll / cnt))

def ternarise(w, grid):
    """BitNet absmean ternarisation, with the layer scale snapped to `grid`."""
    x = w.double()
    alpha = x.abs().mean().item()
    if alpha <= 0: return w
    if grid == "pow2":
        alpha = 2.0 ** round(math.log(alpha, 2))
    elif grid == "phi":
        alpha = PHI ** round(math.log(alpha, PHI))
    q = torch.clamp(torch.round(x / alpha), -1, 1)
    return (q * alpha).to(w.dtype)

print("загружаю модель…", flush=True)
tok = AutoTokenizer.from_pretrained(MODEL)
model = AutoModelForCausalLM.from_pretrained(MODEL, dtype=torch.float32).eval()
ids = tok(load_wikitext(), return_tensors="pt").input_ids
base = perplexity(model, ids, NWIN)
print(f"\nЛИНЕЙКА: базовая перплексия = {base:.4f}", flush=True)
if not (10.0 < base < 60.0):
    print("ЛИНЕЙКА СЛОМАНА — останов."); sys.exit(1)

print(f"""
ПРЕДСКАЗАНИЕ ДО ЗАМЕРА
   сетка phi плотнее сетки степеней двойки в log(2)/log(phi) = {math.log(2)/math.log(PHI):.3f} раза
   при той же цене: сдвиг-сложение против сдвига.
   ожидаем  ppl(точное alpha) <= ppl(phi^k) < ppl(2^k),
   и разрыв phi-к-точному примерно вдвое меньше разрыва 2-к-точному.
""", flush=True)

orig = {n: m.weight.detach().clone() for n, m in target_modules(model)}
res = {}
print(f"{'масштаб слоя':34s} {'цена в железе':22s} {'ppl':>9s} {'Δ к fp32':>10s}")
print(f"{'fp32, без тернаризации':34s} {'—':22s} {base:9.4f} {'1.000x':>10s}")
for grid, label, cost in (("exact", "alpha = mean|W| (BitNet)", "УМНОЖИТЕЛЬ"),
                          ("phi",   "alpha = phi^k (наш)",       "сдвиг+сложение"),
                          ("pow2",  "alpha = 2^k",               "сдвиг")):
    for n, m in target_modules(model):
        m.weight.copy_(ternarise(orig[n], grid))
    p = perplexity(model, ids, NWIN)
    res[grid] = p
    print(f"{label:34s} {cost:22s} {p:9.4f} {p/base:9.3f}x", flush=True)
for n, m in target_modules(model):
    m.weight.copy_(orig[n])

gap_phi = res["phi"] - res["exact"]
gap_p2 = res["pow2"] - res["exact"]
print(f"\nразрыв phi к точному : {gap_phi:+.4f}")
print(f"разрыв 2^k к точному : {gap_p2:+.4f}")
if gap_p2 > 0:
    print(f"отношение разрывов   : {gap_phi/gap_p2:.3f}  (предсказано ~0.5)")
print()
if res["phi"] < res["pow2"]:
    print(f"ВЕРДИКТ: phi^k БЬЁТ 2^k на {(1-res['phi']/res['pow2'])*100:.2f}% — "
          f"аргумент о плотности сетки подтверждён.")
    print(f"   И это при том, что phi^k применяется ТОЧНО (замыкание Z[phi]),")
    print(f"   тогда как умножение на вещественное alpha требует умножителя.")
else:
    print(f"ВЕРДИКТ: phi^k НЕ бьёт 2^k ({res['phi']:.4f} против {res['pow2']:.4f}).")
    print(f"   Аргумент о плотности сетки ОПРОВЕРГНУТ; практическая опора")
    print(f"   алфавита остаётся только на точности, а не на разрешении масштаба.")
