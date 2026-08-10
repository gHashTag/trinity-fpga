#!/usr/bin/env python3
"""Four families, one live network, one metric -- and a prediction made first.

GF and GF-T place the exponent/mantissa split by the golden ratio,
  E = round((N-1)/phi^2),
GF over bits and GF-T over positions with a ternary exponent. BNF and TNF place it
by the width rule: 1 + E + M = N with E sized for the range the workload actually
visits, BNF binary and TNF ternary.

The two axes have never been compared on model quality, only on synthetic error.
This closes that. The width rule is falsifiable here: it names a winner BEFORE the
perplexity is measured, from the measured binade span of the weights alone. If the
measured winner is a different member, the rule is wrong and we say so.

RULER CHECK: unquantised baseline must land in a plausible band or nothing counts.
"""
import os, sys, math
import numpy as np, torch
from transformers import AutoModelForCausalLM, AutoTokenizer
torch.set_grad_enabled(False)

W = ("/private/tmp/claude-501/-Users-ssdm4-Desktop-PROJECTS-CLAUDE/"
     "0e868af8-ab2d-4d00-be03-8fea94ba48e4/scratchpad/weights")
MODEL, SEQLEN = os.path.join(W, "smollm2"), 2048
PHI2 = ((1 + 5 ** 0.5) / 2) ** 2

def levels(N, E, radix):
    """Value set of +/-(1 + m/2^M) * 2^e over the whole exponent field.

    Positions say M = N-1-E. Binary fabric says the whole table must fit in
    2^(N-1) magnitudes. For radix 2 the two agree exactly; for radix 3 they do
    not, and the shortfall in M is the packing loss the no-free-range theorem
    predicts. Charging it here is what makes GF-T and TNF comparable to GF and
    BNF on the same silicon."""
    if E < 0: return None
    nexp = (3 ** E if radix == 3 else 2 ** E)
    cap = 1 << (N - 1)
    if nexp > cap or nexp > 4096: return None
    M = 0
    while nexp * (1 << (M + 1)) <= cap: M += 1
    if M < 1: return None
    half = nexp // 2
    out = {0.0}
    for e in range(-half, nexp - half):
        for m in range(1 << M):
            out.add((1 + m / (1 << M)) * (2.0 ** e))
    v = sorted(out)
    return np.array(v) / v[-1]

def quant(w, lv):
    lv_t = torch.tensor(lv, dtype=torch.float64)
    x = w.double()
    s = x.abs().amax().clamp(min=1e-30) / lv_t[-1]
    y = (x / s).abs()
    bnd = (lv_t[:-1] + lv_t[1:]) / 2
    return (torch.sign(x) * lv_t[torch.bucketize(y, bnd)] * s).to(w.dtype)

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

print("загружаю модель…", flush=True)
tok = AutoTokenizer.from_pretrained(MODEL)
model = AutoModelForCausalLM.from_pretrained(MODEL, dtype=torch.float32).eval()
ids = tok(load_wikitext(), return_tensors="pt").input_ids

NWIN = 40
base = perplexity(model, ids, NWIN)
print(f"\nЛИНЕЙКА: базовая перплексия = {base:.4f}", flush=True)
if not (10.0 < base < 60.0):
    print("ЛИНЕЙКА СЛОМАНА — останов."); sys.exit(1)

# --- the range the workload visits, measured before any format is chosen ------
spans = []
for _, m in target_modules(model):
    x = m.weight.detach().double().abs()
    x = x[x > 0]
    spans.append(float(torch.log2(x.amax() / torch.quantile(x, 0.001))))
span = float(np.median(spans))
need_bin = math.ceil(math.log2(max(span, 2)))
need_tri = math.ceil(math.log(max(span, 2), 3))
print(f"\n═══ ПРЕДСКАЗАНИЕ ДО ЗАМЕРА ═══")
print(f"   веса посещают {span:.1f} бинад (медиана по слоям, 0.1-й процентиль -> максимум)")
print(f"   правило ширины: BNF8 требует E={need_bin}, TNF8 требует Et={need_tri}")
print(f"   -> предсказанные победители: BNF8 E={need_bin} (M={8-1-need_bin}), "
      f"TNF8 Et={need_tri} (M={8-1-need_tri})", flush=True)

N = 8
gf_E = round((N - 1) / PHI2)
CAND = [(f"GF8    E={gf_E} (золотое сечение, двоичная)",  levels(N, gf_E, 2)),
        (f"GF-T8  Et={gf_E} (золотое сечение, тернарная)", levels(N, gf_E, 3))]
for E in range(1, 6):
    CAND.append((f"BNF8   E={E} (правило ширины)"
                 + ("  <- предсказан" if E == need_bin else ""), levels(N, E, 2)))
for Et in range(1, 5):
    CAND.append((f"TNF8   Et={Et} (правило ширины)"
                 + ("  <- предсказан" if Et == need_tri else ""), levels(N, Et, 3)))

orig = {n: m.weight.detach().clone() for n, m in target_modules(model)}
print(f"\n{'кандидат':44s} {'уровней':>8s} {'ppl':>9s} {'Δ к fp32':>10s}")
print(f"{'fp32 (эталон)':44s} {'—':>8s} {base:9.4f} {'1.000x':>10s}")
res = []
for name, lv in CAND:
    if lv is None: continue
    for n, m in target_modules(model):
        m.weight.copy_(quant(orig[n], lv))
    p = perplexity(model, ids, NWIN)
    res.append((name, p))
    print(f"{name:44s} {len(lv):8d} {p:9.4f} {p/base:9.3f}x", flush=True)
for n, m in target_modules(model):
    m.weight.copy_(orig[n])

for fam in ("BNF8", "TNF8"):
    rs = [r for r in res if r[0].startswith(fam)]
    if not rs: continue
    win = min(rs, key=lambda r: r[1])
    pred = [r for r in rs if "предсказан" in r[0]]
    hit = bool(pred) and pred[0][0] == win[0]
    print(f"\n{fam}: победил «{win[0].split('(')[0].strip()}» ppl {win[1]:.4f} -> "
          f"правило ширины {'ПОДТВЕРДИЛОСЬ' if hit else 'ОПРОВЕРГНУТО'}")
gf = min([r for r in res if r[0].startswith("GF")], key=lambda r: r[1])
th = min([r for r in res if r[0].startswith(("BNF", "TNF"))], key=lambda r: r[1])
print(f"\nОСЬ ЗОЛОТОГО СЕЧЕНИЯ лучший: {gf[0].split('(')[0].strip()}  ppl {gf[1]:.4f}")
print(f"ОСЬ ТЕОРЕМ        лучший: {th[0].split('(')[0].strip()}  ppl {th[1]:.4f}")
print(f"разрыв: {abs(1 - th[1]/gf[1])*100:.2f}% в пользу "
      f"{'теорем' if th[1] < gf[1] else 'золотого сечения'}")
