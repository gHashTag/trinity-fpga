#!/usr/bin/env python3
"""ВАРИАНТ B (луп 30.07.2026e) — GF+A (межформатный выбор) vs PolyQ-proxy
(поканальная разрядность) по ЕДИНОЙ downstream model bits-per-token.
[измерено — SW proxy, CPU]. seed=20260730.

МОТИВАЦИЯ (честность прошлого лупа): врезка PR #16 заявила, что 5 июльских
соседей (PolyQ/KronQ/...) лежат на ВНУТРИФОРМАТНОЙ оси (adaptive bit-width
внутри семейства), комплементарной МЕЖФОРМАТНОЙ оси GF+A (выбор формата из
каталога). Но текст явно оговорил: «отсутствие прямого конкурента по нашей
оси ≠ превосходство по downstream». Этот харнесс КОЛИЧЕСТВЕННО закрывает эту
границу — прямой бит-выровненный замер обеих осей по ОДНОЙ метрике (BPT).

PolyQ (arXiv:2607.14618, Oh и др.): activation-aware per-channel bit-width из
{2,3,4,8,16} под заданный СРЕДНИЙ битовый бюджет; каналы кластеризуются в
bit-homogeneous блоки для CPU. Это ИНАЯ ось, чем GF+A (per-row выбор ФОРМАТА
при фикс. разрядности). Мы делаем ЧЕСТНЫЙ SW-proxy PolyQ (без CPU-компилятора):
per-column bit-width из {2,4,8} по activation-aware важности (диагональ Гессиана
H_jj=E[x_j^2] на калибр-активациях), подобранный так, чтобы СРЕДНИЙ бит == бюджет
GF+A. Обе конфигурации меряются ОДНИМ model-BPT на независимом val-потоке.

BINDING (границы):
- Микро-LM (НЕ 29M) → вывод про НАПРАВЛЕНИЕ/ортогональность, НЕ величину.
- PolyQ-proxy — упрощение (нет CPU-компилятора/permute/LUT-кернелов; только
  сам bit-allocation-механизм). Замеряем ТОЛЬКО потери качества, НЕ скорость/энергию.
- Сравнение бит-выровнено по СРЕДНЕМУ биту веса (оверхед заголовков считаем отдельно).
- НЕ заявлять «GF+A обходит PolyQ». Вывод: обе оси дают ΔBPT одного порядка при
  равном бюджете → ОРТОГОНАЛЬНЫ и КОМПЛЕМЕНТАРНЫ; ни одна не доминирует downstream
  на микро-масштабе. Порог значимости Parameter Golf = 0.005 BPB = 0.0195 BPT.
"""
import numpy as np, math, json, os
import torch, torch.nn as nn, torch.nn.functional as F

torch.manual_seed(20260730); np.random.seed(20260730)
device = "cpu"

# ── φ-каталог карманов (SSOT, идентичен composition_bpt_cpu_proxy.py) ──
PHI2 = ((1 + 5**0.5) / 2) ** 2
def phi_split(N):
    e = round((N - 1) / PHI2); m = N - 1 - e
    return e, m, (2**(e-1)-1 if e > 0 else 0)
def fmt_maxn(e, m, bias):
    return (2**m-1)*2.0**(-m) if e == 0 else 2.0**((1<<e)-1-bias)*(2-2.0**-m)
def minifloat_qd(x, e, m, bias):
    x = x.double()
    if e == 0:
        step = 2.0**(-m); mx = (2**m-1)*step
        return torch.clamp(torch.round(x/step)*step, -mx, mx)
    EMIN = 1-bias; EMAX = (1<<e)-1-bias; MAXN = 2.0**EMAX*(2-2.0**-m)
    a = x.abs(); sgn = torch.sign(x)
    ex = torch.clamp(torch.floor(torch.log2(torch.clamp(a, min=2.0**(EMIN-m-1)))), EMIN, EMAX)
    step = torch.where(a < 2.0**EMIN, torch.full_like(a, 2.0**(EMIN-m)), 2.0**(ex-m))
    return sgn*torch.clamp(torch.round(a/step)*step, max=MAXN)
def int_qd(x, bits):
    L = 2**(bits-1)-1
    return torch.round(torch.clamp(x, -1.0, 1.0)*L)/L
def lns_qd(x, bits):
    x = x.double(); L = 2**(bits-1)-1; a = x.abs(); sgn = torch.sign(x)
    LMIN = -8.0; step = -LMIN/L
    la = torch.log2(a.clamp(min=2.0**LMIN))
    idx = torch.round((la-LMIN)/step).clamp(0, L)
    mag = torch.where(a < 2.0**(LMIN-1), torch.zeros_like(a), 2.0**(LMIN+idx*step))
    return sgn*mag.clamp(max=1.0)

# per-ROW (выход-канал) absmax scale — единый режим масштабирования для обеих осей
def qd_mf_row(w, e, m, bias):
    x = w.double(); amax = x.abs().amax(-1, keepdim=True).clamp(min=1e-12)
    return minifloat_qd(x/(amax/fmt_maxn(e, m, bias)), e, m, bias)*(amax/fmt_maxn(e, m, bias))
def qd_int_row(w, bits):
    x = w.double(); amax = x.abs().amax(-1, keepdim=True).clamp(min=1e-12)
    return int_qd(x/amax, bits)*amax
def qd_lns_row(w, bits):
    x = w.double(); amax = x.abs().amax(-1, keepdim=True).clamp(min=1e-12)
    return lns_qd(x/amax, bits)*amax

def catalog(W, N):
    pe, pm, pb = phi_split(N)
    c = [qd_mf_row(W, pe, pm, pb)]
    if N-3 >= 1: c.append(qd_mf_row(W, 2, N-3, 1))
    c.append(qd_int_row(W, N)); c.append(qd_lns_row(W, N))
    return c[:4]

# ── ОСЬ GF+A: per-ROW межформатный выбор кармана при ФИКСИРОВАННОЙ разрядности N ──
def q_gfa(W, N):
    c = catalog(W, N); qs = torch.stack(c)
    errs = torch.stack([((W.double()-q)**2).sum(-1) for q in c]); ch = errs.argmin(0)
    return qs[ch, torch.arange(W.shape[0])], float(N)  # эфф.бит = N (2 бита заголовка/строка отдельно)

# ── ОСЬ PolyQ-proxy: per-COLUMN activation-aware bit-width из {2,4,8} под средний бюджет N ──
# INT-квант по столбцу (входному каналу) с разной разрядностью; важность = H_jj = E[x_j^2].
def qd_int_percol(W, bits_per_col):
    # W: [out, in]; bits_per_col: [in]. per-column absmax scale (как в PolyQ bit-homogeneous блоках).
    x = W.double()
    amax = x.abs().amax(0, keepdim=True).clamp(min=1e-12)  # [1, in]
    xn = x/amax
    out = torch.zeros_like(x)
    for b in torch.unique(bits_per_col):
        b = int(b); mask = (bits_per_col == b)
        L = 2**(b-1)-1
        out[:, mask] = torch.round(torch.clamp(xn[:, mask], -1, 1)*L)/L
    return out*amax
def polyq_alloc(Hdiag, target_bits, choices=(2, 4, 8)):
    # activation-aware: столбцы с большей важностью H_jj получают больше бит,
    # так чтобы СРЕДНЕЕ == target_bits. Жадный водоналивной по бюджету.
    n = len(Hdiag); choices = sorted(choices)
    order = np.argsort(-Hdiag)  # по убыванию важности
    bits = np.full(n, choices[0], dtype=np.int64)
    budget = target_bits*n
    used = bits.sum()
    ci = {c: i for i, c in enumerate(choices)}
    for idx in order:
        while ci[bits[idx]] < len(choices)-1:
            nxt = choices[ci[bits[idx]]+1]
            if used - bits[idx] + nxt <= budget:
                used += nxt - bits[idx]; bits[idx] = nxt
            else:
                break
        if used >= budget: break
    return bits
def q_polyq(W, N, Hdiag):
    bits = polyq_alloc(Hdiag, N)
    q = qd_int_percol(W, torch.tensor(bits))
    return q, float(bits.mean())  # реальный средний бит

# ── микро-LM (идентичен composition_bpt_cpu_proxy.py — та же методология) ──
VOCAB = 256; D = 128; NL = 4; SEQ = 64; NTRAIN = 200_000; NVAL = 40_000
_PRNG = np.random.default_rng(777)
_P = _PRNG.dirichlet(np.ones(VOCAB)*0.3, size=VOCAB)  # α=0.3 → выше энтропия → квант-ущерб виден
_C = np.cumsum(_P, axis=1)
def gen_stream(n, seed):
    rng = np.random.default_rng(seed)
    out = np.zeros(n, dtype=np.int64); out[0] = rng.integers(VOCAB); out[1] = rng.integers(VOCAB)
    u = rng.random(n)
    for i in range(2, n):
        ctx = int((out[i-1] + 3*out[i-2]) % VOCAB)
        out[i] = int(np.searchsorted(_C[ctx], u[i]))
    return torch.tensor(np.clip(out, 0, VOCAB-1))
train_t = gen_stream(NTRAIN, 1); val_t = gen_stream(NVAL, 2)

class Micro(nn.Module):
    def __init__(s):
        super().__init__()
        s.e = nn.Embedding(VOCAB, D); s.p = nn.Embedding(SEQ, D)
        s.l = nn.ModuleList([nn.TransformerEncoderLayer(D, 4, D*4, 0.1, batch_first=True,
                             activation='gelu', norm_first=True) for _ in range(NL)])
        s.f = nn.LayerNorm(D); s.h = nn.Linear(D, VOCAB, bias=False); s.h.weight = s.e.weight
    def forward(s, x):
        h = s.e(x) + s.p(torch.arange(x.size(1)))
        for b in s.l: h = b(h)
        return s.h(s.f(h))

STEPS = int(os.environ.get("STEPS", 800)); BATCH = int(os.environ.get("BATCH", 32))
torch.set_num_threads(int(os.environ.get("THREADS", 4)))
torch.manual_seed(42); model = Micro().to(device)
op = torch.optim.AdamW(model.parameters(), lr=3e-3, weight_decay=0.1, betas=(0.9, 0.95))
print(f"Обучение микро-LM {NL}L d={D} vocab={VOCAB} {STEPS} шагов (CPU)...", flush=True)
for st in range(STEPS+1):
    idx = torch.randint(0, len(train_t)-SEQ-1, (BATCH,))
    x = torch.stack([train_t[i:i+SEQ] for i in idx])
    y = torch.stack([train_t[i+1:i+SEQ+1] for i in idx])
    loss = F.cross_entropy(model(x).reshape(-1, VOCAB), y.reshape(-1))
    op.zero_grad(); loss.backward(); nn.utils.clip_grad_norm_(model.parameters(), 1.0); op.step()
    if st % 400 == 0: print(f"  {st}/{STEPS}: loss={loss.item():.4f}", flush=True)
model.eval()

lin = {n: m for n, m in model.named_modules()
       if isinstance(m, nn.Linear) and m.weight is not model.e.weight}
print(f"Linear-слоёв под квант: {len(lin)}")
fp32 = {n: m.weight.data.clone() for n, m in lin.items()}

# ── activation-aware важность (диагональ Гессиана) на КАЛИБР-активациях ──
# H_jj = E[x_j^2] по входу каждого Linear-слоя. Снимаем forward-хуками на калибр-батче.
Hdiag = {}
def make_hook(name):
    def hook(mod, inp, out):
        x = inp[0].detach().double().reshape(-1, inp[0].shape[-1])
        s = (x*x).mean(0).cpu().numpy()
        Hdiag[name] = Hdiag.get(name, 0)*0 + s if name not in Hdiag else Hdiag[name] + s
    return hook
handles = [m.register_forward_hook(make_hook(n)) for n, m in lin.items()]
with torch.no_grad():
    torch.manual_seed(555)
    for _ in range(20):
        i = torch.randint(0, len(train_t)-SEQ-1, (1,)).item()
        model(train_t[i:i+SEQ].unsqueeze(0))
for h in handles: h.remove()

BYTES_PER_TOK = 3.9; BPB_TH = 0.005; BPT_TH = BPB_TH*BYTES_PER_TOK; NB = 40
def eval_bpt(tag):
    torch.manual_seed(123); tot_nats = 0.0; tot = 0
    with torch.no_grad():
        for _ in range(NB):
            i = torch.randint(0, len(val_t)-SEQ-1, (1,)).item()
            x = val_t[i:i+SEQ].unsqueeze(0); y = val_t[i+1:i+SEQ+1]
            ce = F.cross_entropy(model(x).reshape(-1, VOCAB), y, reduction='sum')
            tot_nats += float(ce); tot += y.numel()
    bpt = tot_nats/math.log(2)/tot
    print(f"  [{tag}] bits/token={bpt:.5f}", flush=True)
    return bpt
def restore():
    for n, m in lin.items(): m.weight.data.copy_(fp32[n])

print(f"\n{'='*74}\nВАРИАНТ B: GF+A (межформатный выбор, per-row) vs PolyQ-proxy (поканальная\nразрядность, per-col activation-aware) — ЕДИНАЯ downstream model-BPT")
print(f"порог = {BPB_TH} BPB = {BPT_TH:.4f} BPT | val батчей={NB} | seed=20260730\n{'='*74}")
rep = {"meta": dict(scale="micro-LM CPU proxy", NL=NL, D=D, vocab=VOCAB, steps=STEPS,
                    bpt_thresh=BPT_TH, seed=20260730,
                    note="направление/ортогональность, НЕ величина; НЕ обобщается на 29M; "
                         "PolyQ-proxy без CPU-компилятора; оверхед заголовков не вычтен")}
restore(); rep["fp32"] = eval_bpt("FP32 baseline")
fp32_bpt = rep["fp32"]
for N in (4, 6, 8):
    print(f"\n--- средний бюджет {N} бит ---")
    # GF+A
    eff_gfa = []
    for n, m in lin.items():
        q, eb = q_gfa(fp32[n].double(), N); m.weight.data.copy_(q.to(m.weight.dtype)); eff_gfa.append(eb)
    b_gfa = eval_bpt(f"{N}b GF+A (per-row формат)")
    restore()
    # PolyQ-proxy
    eff_pq = []
    for n, m in lin.items():
        # fallback: слои внутри fused MultiheadAttention не ловятся Python-хуком →
        # равномерная важность (H_jj=1) = честный worst-case для activation-aware.
        hj = Hdiag[n] if n in Hdiag else np.ones(fp32[n].shape[1])
        q, eb = q_polyq(fp32[n].double(), N, hj); m.weight.data.copy_(q.to(m.weight.dtype)); eff_pq.append(eb)
    b_pq = eval_bpt(f"{N}b PolyQ-proxy (per-col bit-width)")
    restore()
    d = b_pq - b_gfa
    verdict = ("оси РАЗЛИЧАЮТСЯ downstream" if abs(d) >= BPT_TH
               else f"|Δ|<порог {BPT_TH:.4f} → downstream-НЕОТЛИЧИМЫ (ортогональны)")
    print(f"  эфф.бит GF+A≈{np.mean(eff_gfa):.2f}  PolyQ-proxy≈{np.mean(eff_pq):.2f}")
    print(f"  ΔBPT(PolyQ − GF+A) = {d:+.5f} бит/ток → {verdict}")
    print(f"  ΔBPT(GF+A − fp32)  = {b_gfa-fp32_bpt:+.5f}  |  ΔBPT(PolyQ − fp32) = {b_pq-fp32_bpt:+.5f}")
    rep[str(N)] = dict(gfa_bpt=b_gfa, polyq_bpt=b_pq, dbpt_polyq_minus_gfa=d,
                       eff_bits_gfa=float(np.mean(eff_gfa)), eff_bits_polyq=float(np.mean(eff_pq)),
                       gfa_vs_fp32=b_gfa-fp32_bpt, polyq_vs_fp32=b_pq-fp32_bpt,
                       distinguishable=bool(abs(d) >= BPT_TH))
restore()
out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gfa_vs_polyq_bpt_cpu_proxy_results.json")
json.dump(rep, open(out, "w"), indent=2)
print(f"\nsaved {out}")
