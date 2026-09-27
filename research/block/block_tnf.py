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
    """Width rule says 1 + Et + M = nbits in POSITIONS. Binary fabric addresses
    only 2^(nbits-1) magnitudes, so the realisable format obeys
        3^Et * 2^M <= 2^(nbits-1)
    and the gap between the two accountings IS the packing loss -- the no-free-
    range theorem, concretely. Sizing M from the position count alone and then
    truncating the sorted table put the top level at 0.25 instead of 1.0 and
    produced a 100x perplexity artefact against our own format."""
    cap = 1 << (nbits - 1)
    nexp = 3 ** Et
    if nexp > cap: return None
    M = 0
    while nexp * (1 << (M + 1)) <= cap: M += 1
    out = {0.0}
    for e in range(nexp):
        for m in range(1 << M):
            out.add((1 + m / (1 << M)) * (2.0 ** -e))
    v = sorted(out)
    return [x / v[-1] for x in v]

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
model = AutoModelForCausalLM.from_pretrained(MODEL, dtype=torch.float32)
model.eval()
ids = tok(load_wikitext(), return_tensors="pt").input_ids

NWIN = 40
base = perplexity(model, ids, NWIN)
print(f"\nЛИНЕЙКА: базовая перплексия без квантования = {base:.4f}", flush=True)
if not (10.0 < base < 60.0):
    print("ЛИНЕЙКА СЛОМАНА — базовая перплексия вне правдоподобной полосы. Останов.")
    sys.exit(1)
print("линейка в норме\n", flush=True)

# ---- measure the within-block range the workload actually visits -----------
spread = []
for _, m in target_modules(model):
    w = m.weight.detach().double(); n = (w.shape[1] // K) * K
    if n == 0: continue
    b = w[:, :n].reshape(-1, K)
    a = b.abs().amax(dim=1); ok = a > 0
    y = (b[ok].abs() / a[ok][:, None]).clamp(min=1e-30)
    # binades between the block max and the median element of the block
    spread.append(torch.log2(y.median(dim=1).values.clamp(min=1e-30)).neg().numpy())
sp = np.concatenate(spread)
print("═══ ЧТО БЛОК РЕАЛЬНО ПОСЕЩАЕТ ═══")
for q in (50, 90, 99, 99.9):
    print(f"   {q:5.1f}-й процентиль разброса: {np.percentile(sp, q):6.2f} бинад")
need = math.ceil(np.percentile(sp, 99))
print(f"   -> экспоненте элемента хватает {need} бинад на 99% блоков")
print(f"   -> E2M1 у MXFP4 даёт 4 бинады; правило ширины просит "
      f"Et_bin={max(0,math.ceil(math.log2(max(need,1))))}\n", flush=True)

orig = {n: m.weight.detach().clone() for n, m in target_modules(model)}
CANDS = [
    ("MXFP4  E2M1 + E8M0 (эталон отрасли)", fp_levels(2, 1)),
    ("int4   равномерный + E8M0",            uniform_levels(4)),
    ("TNF4   Et=1 (упакован)",               tnf_levels(4, 1)),
    ("TNF4   Et=2 (упакован)",               tnf_levels(4, 2)),
    ("MXFP6  E2M3 + E8M0",                   fp_levels(2, 3)),
    ("TNF6   Et=1 (упакован)",               tnf_levels(6, 1)),
    ("TNF6   Et=2 (упакован)",               tnf_levels(6, 2)),
]
print(f"{'кандидат':38s} {'уровней':>8s} {'ppl':>9s} {'Δ к fp32':>10s}")
print(f"{'fp32 (эталон)':38s} {'—':>8s} {base:9.4f} {'1.000x':>10s}")
res = []
for name, lv in CANDS:
    if lv is None: continue
    for n, m in target_modules(model):
        m.weight.copy_(quant(orig[n], lv))
    p = perplexity(model, ids, NWIN)
    res.append((name, len(lv), p))
    print(f"{name:38s} {len(lv):8d} {p:9.4f} {p/base:9.3f}x", flush=True)
for n, m in target_modules(model):
    m.weight.copy_(orig[n])

mx = [r for r in res if r[0].startswith("MXFP4")][0]
best4 = min([r for r in res if "4" in r[0].split()[0]], key=lambda r: r[2])
print(f"\nВЕРДИКТ на 4 битах: лучший = {best4[0].strip()}  ppl {best4[2]:.4f}")
print(f"   против MXFP4 {mx[2]:.4f} -> {'ПОБЕДА' if best4[2] < mx[2] else 'ПОРАЖЕНИЕ'}"
      f" на {abs(1-best4[2]/mx[2])*100:.2f}%")
