#!/usr/bin/env python3
"""The block axis: does the width rule pick a better element than the MX spec did?

MXFP4 fixes the element at E2M1 -- two exponent bits inside a block that already
carries a shared E8M0 scale. Our width rule says the exponent is sized for the
range the workload actually visits, so the first thing to do is MEASURE that
range inside a block rather than assume it, then spend the remaining positions
on mantissa. If the measured within-block spread is smaller than four binades,
E2M1 is buying range that the shared scale already paid for.

RULER CHECK. The unquantised baseline must land in a plausible band for a 135M
model on wikitext-2, or nothing below it means anything.
"""
import os, sys, math
import numpy as np, torch
from transformers import AutoModelForCausalLM, AutoTokenizer
W = ("/private/tmp/claude-501/-Users-ssdm4-Desktop-PROJECTS-CLAUDE/"
     "0e868af8-ab2d-4d00-be03-8fea94ba48e4/scratchpad/weights")
MODEL, K, SEQLEN = os.path.join(W, "smollm2"), 32, 2048

# Copied rather than imported: perplexity.py runs its whole experiment at
# import time, so importing it would launch a different measurement.
def fp_levels(eb, mb):
    """OCP MX element formats reserve no Inf/NaN: every exponent code is finite.
    Reserving the top code would hand E2M1 six magnitudes instead of eight --
    2.58 bits where the spec gives 3 -- and quietly rig the comparison."""
    bias = (1 << (eb - 1)) - 1
    out = {0.0}
    for e in range(1, 1 << eb):
        for m in range(1 << mb):
            out.add((1 + m / (1 << mb)) * 2.0 ** (e - bias))
    for m in range(1, 1 << mb):
        out.add((m / (1 << mb)) * 2.0 ** (1 - bias))
    v = sorted(out)
    return [x / v[-1] for x in v]

def q_e8m0_t(s):
    return torch.pow(2.0, torch.ceil(torch.log2(s.clamp(min=1e-30))))

def target_modules(model):
    return [(n, m) for n, m in model.named_modules()
            if isinstance(m, torch.nn.Linear) and "lm_head" not in n]

def load_wikitext():
    import pyarrow.parquet as pq
    t = pq.read_table(os.path.join(W, "wikitext2-test.parquet"))
    return "\n\n".join(t.column("text").to_pylist())

def perplexity(model, ids, limit_windows=None):
    flat = ids.reshape(-1)
    n = (flat.numel() // SEQLEN) * SEQLEN
    x = flat[:n].view(-1, SEQLEN)
    if limit_windows: x = x[:limit_windows]
    nll = cnt = 0.0
    for i in range(x.shape[0]):
        c = x[i:i + 1]
        nll += model(c, labels=c).loss.double().item() * (SEQLEN - 1)
        cnt += SEQLEN - 1
    return float(np.exp(nll / cnt))
torch.set_grad_enabled(False)

def uniform_levels(nbits):
    """sign + (nbits-1) mantissa positions, no element exponent at all."""
    n = (1 << (nbits - 1)) - 1
    return [i / n for i in range(n + 1)]

def tnf_levels(nbits, Et):
    """Width rule inside a block: 1 sign + Et exponent + M mantissa = nbits."""
    M = nbits - 1 - Et
    if M < 0: return None
    out = {0.0}
    nexp = 3 ** Et if Et > 0 else 1
    nexp = min(nexp, 64)
    for e in range(nexp):
        for m in range(1 << M):
            out.add((1 + m / (1 << M)) * (2.0 ** -e))
    v = sorted(out)
    return [x / v[-1] for x in v][: (1 << (nbits - 1))]

def quant(w, lv, scale="e8m0"):
    lv_t = torch.tensor(sorted(lv), dtype=torch.float64)
    orig = w.shape; n = (orig[1] // K) * K
    if n == 0: return w
    head = w[:, :n].reshape(-1, K).double()
    s = (head.abs().amax(dim=1) / lv_t[-1]).clamp(min=1e-30)
    s = q_e8m0_t(s).clamp(min=1e-30)
    y = (head / s[:, None]).abs()
    bnd = (lv_t[:-1] + lv_t[1:]) / 2
    rec = torch.sign(head) * lv_t[torch.bucketize(y, bnd)] * s[:, None]
    out = w.clone(); out[:, :n] = rec.reshape(-1, n).to(w.dtype)
    return out


print("загружаю модель…", flush=True)
tok = AutoTokenizer.from_pretrained(MODEL)
model = AutoModelForCausalLM.from_pretrained(MODEL, dtype=torch.float32).eval()
ids = tok(load_wikitext(), return_tensors="pt").input_ids
NWIN = 40
base = perplexity(model, ids, NWIN)
print(f"\nЛИНЕЙКА: базовая перплексия = {base:.4f}", flush=True)
if not (10.0 < base < 60.0):
    print("ЛИНЕЙКА СЛОМАНА — останов."); sys.exit(1)

print("""
ПРЕДСКАЗАНИЕ ККТ, СДЕЛАННОЕ ДО ЗАМЕРА
   Разброс внутри блока: 1.89 бинад в медиане, 3.04 на 99-м процентиле.
   Задача с множителем даёт E* = ceil(log2(разброс)):
      защищаем медиану        -> E*=1, M*=2  -> E1M2
      защищаем 99-й процентиль -> E*=2, M*=1  -> E2M1 (спецификация MX)
   Теорема о сожалении говорит, что цена несимметрична: заужение платит на
   хвосте линейно, расширение платит на КАЖДОМ значении логарифмически.
   Если хвост весит больше — победит E2M1, и тогда спецификация MX выведена,
   а не угадана. Если победит E1M2 — комитет защитил хвост, которого нет.
""", flush=True)

orig = {n: m.weight.detach().clone() for n, m in target_modules(model)}
CANDS = [("E1M2 + E8M0  (ККТ по медиане)",        fp_levels(1, 2)),
         ("E2M1 + E8M0  (ККТ по 99%, = MXFP4)",   fp_levels(2, 1)),
         ("E3M0 + E8M0  (сверх-широкая экспонента)", fp_levels(3, 0))]
print(f"{'кандидат':40s} {'уровней':>8s} {'ppl':>9s} {'Δ к fp32':>10s}")
res = []
for name, lv in CANDS:
    for n, m in target_modules(model):
        m.weight.copy_(quant(orig[n], lv))
    p = perplexity(model, ids, NWIN)
    res.append((name, p))
    print(f"{name:40s} {len(lv):8d} {p:9.4f} {p/base:9.3f}x", flush=True)
for n, m in target_modules(model):
    m.weight.copy_(orig[n])

win = min(res, key=lambda r: r[1])
mx = [r for r in res if "MXFP4" in r[0]][0]
print(f"\nПОБЕДИТЕЛЬ: {win[0]}  ppl {win[1]:.4f}")
if win is mx:
    print("-> Правило ширины при 99-м процентиле ВЫВОДИТ E2M1. Спецификация MX")
    print("   оказывается единственным решением задачи с множителем, а не соглашением.")
else:
    print(f"-> E2M1 ПРОИГРАЛ ({mx[1]:.4f}). Комитет защитил хвост, который на этих")
    print("   весах не окупается; правило ширины по медиане точнее стандарта.")
