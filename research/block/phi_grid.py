#!/usr/bin/env python3
"""Does snapping a layer scale to a power of phi cost less than snapping to a
power of two?  Measured on the quantity the question is actually about.

A first attempt asked this through perplexity and measured nothing: post-hoc
ternarisation destroys a model that was not trained for it, so ALL arms --
including BitNet's exact alpha -- landed at ppl ~2e7 against a baseline of
14.49.  Three arms inside a destroyed regime are not a comparison.  Recorded as
defect #13 rather than reported as a refutation.

The question is per-layer and self-contained: given ternary weights, how well
does a scale drawn from a grid approximate the best possible scale?  That is a
reconstruction error, and it is exact arithmetic on real weights.

Grids, all at the same weight cost of 2 bits per element:
    exact   alpha* minimising ||W - alpha*Q||   needs a multiplier
    phi^k   spacing log2(phi) = 0.694 octave    shift-and-add, exact in Z[phi]
    2^k     spacing 1 octave                    shift

Prediction, before measuring: the phi grid is denser by log(2)/log(phi) = 1.44,
so its excess error over exact should be near half the power-of-two grid's.
"""
import os, math, sys
import numpy as np, torch
from safetensors import safe_open
torch.set_grad_enabled(False)
W = ("/private/tmp/claude-501/-Users-ssdm4-Desktop-PROJECTS-CLAUDE/"
     "0e868af8-ab2d-4d00-be03-8fea94ba48e4/scratchpad/weights")
PHI = (1 + 5 ** 0.5) / 2

def best_alpha(x, q):
    """alpha minimising ||x - alpha*q||_2 for fixed ternary q: a least squares."""
    d = float((q * q).sum())
    return float((x * q).sum()) / d if d > 0 else 0.0

def err(x, q, a):
    return float(torch.linalg.vector_norm(x - a * q) / torch.linalg.vector_norm(x))

f = safe_open(os.path.join(W, "smollm2", "model.safetensors"), framework="pt")
keys = [k for k in f.keys() if k.endswith(".weight") and "layers." in k
        and any(t in k for t in ("q_proj", "k_proj", "v_proj", "o_proj",
                                 "gate_proj", "up_proj", "down_proj"))]
print(f"слоёв: {len(keys)}\n")
print("ЛИНЕЙКА: у точного alpha ошибка обязана быть НАИМЕНЬШЕЙ из трёх по построению")
print("         (это решение задачи наименьших квадратов). Если нет — прибор врёт.\n")

rows = []
for k in keys:
    x = f.get_tensor(k).double()
    thr = 0.7 * x.abs().mean()
    q = torch.sign(x) * (x.abs() > thr)          # BitNet-style ternary support
    a_ex = best_alpha(x, q)
    if a_ex <= 0: continue
    a_phi = PHI ** round(math.log(a_ex, PHI))
    a_p2 = 2.0 ** round(math.log(a_ex, 2))
    rows.append((err(x, q, a_ex), err(x, q, a_phi), err(x, q, a_p2)))

E = np.array(rows)
ex, ph, p2 = E[:, 0], E[:, 1], E[:, 2]
if not (np.all(ex <= ph + 1e-12) and np.all(ex <= p2 + 1e-12)):
    print("ЛИНЕЙКА СЛОМАНА: точное alpha не наименьшее. Останов."); sys.exit(1)
print("линейка в норме\n")

print(f"{'сетка масштаба':28s} {'цена':18s} {'ошибка сред.':>13s} {'избыток над точным':>20s}")
print(f"{'exact alpha* (BitNet)':28s} {'УМНОЖИТЕЛЬ':18s} {ex.mean():13.6f} {0.0:19.4f}%")
for nm, cost, e in (("phi^k (наш)", "сдвиг+сложение", ph), ("2^k", "сдвиг", p2)):
    print(f"{nm:28s} {cost:18s} {e.mean():13.6f} {100*(e.mean()/ex.mean()-1):19.4f}%")

xs_phi = 100 * (ph / ex - 1); xs_p2 = 100 * (p2 / ex - 1)
print(f"\nизбыток по слоям, медиана:  phi {np.median(xs_phi):.4f}%   2^k {np.median(xs_p2):.4f}%")
print(f"слоёв, где phi лучше 2^k :  {int((ph < p2).sum())} из {len(ph)}")
r = xs_phi.mean() / xs_p2.mean() if xs_p2.mean() > 0 else float('nan')
print(f"отношение избытков       :  {r:.3f}   (предсказано ~0.5 по плотности сетки)")
print()
if ph.mean() < p2.mean():
    print(f"ВЕРДИКТ: сетка phi БЬЁТ сетку степеней двойки. Избыток над недостижимым")
    print(f"   точным alpha меньше в {xs_p2.mean()/max(xs_phi.mean(),1e-12):.2f} раза, при той же")
    print(f"   цене класса 'без умножителя' — и применяется ТОЧНО по замыканию Z[phi].")
else:
    print(f"ВЕРДИКТ: сетка phi НЕ бьёт степени двойки. Аргумент о плотности опровергнут.")
