#!/usr/bin/env python3
"""ВАРИАНТ B — CPU-ПРОКСИ downstream-BPT замер оси-композиции (луп 29.07.2026b).
[измерено — SW proxy, CPU]. seed=20260729. БЕЗ GPU: обучаем МИКРО-LM на игрушечном
последовательном потоке, затем квантуем Linear-веса тремя способами и меряем реальный
model bits-per-token на независимом val-потоке. Это ПРОКСИ полноразмерного пода-замера
(webterm_composition_bpb.py) — даёт первую честную downstream-цифру ДО прогона на поде.

Цель: частично закрыть главную границу инв.№26 — «композиция end-to-end downstream =
[открытая гипотеза]» — переведя её в [измерено — SW proxy, CPU] на микро-масштабе. Полный
GPU-замер на 29M-модели остаётся [ТРЕБУЕТ ДЕЙСТВИЯ ПОЛЬЗОВАТЕЛЯ] (пода в песочнице нет).

Три конфигурации: (0) FP32; (A) ось1 GF+A catalog-select; (B) композиция GF+A∘intra-pocket.
Порог значимости Parameter Golf = 0.005 BPB = 0.0195 BPT (коэф 3.9). Честно замеряем ΔBPT.

BINDING: микро-масштаб (не 29M) → цифры НЕ обобщаются на большие модели; вывод про НАПРАВЛЕНИЕ
эффекта, не про величину. Композиция тратит оверхед заголовка → сравнение НЕ бит-выровнено.
Превосходство оси НЕ заявляется — вывод про ортогональность/окупаемость downstream.
"""
import numpy as np, math, json, os
import torch, torch.nn as nn, torch.nn.functional as F

torch.manual_seed(20260729); np.random.seed(20260729)
device = "cpu"

# ── карманы φ-каталога (SSOT, идентичны webterm_composition_bpb.py) ──
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
def qd_mf(w, e, m, bias):
    x = w.double(); amax = x.abs().amax(-1, keepdim=True).clamp(min=1e-12)
    return minifloat_qd(x/(amax/fmt_maxn(e, m, bias)), e, m, bias)*(amax/fmt_maxn(e, m, bias))
def qd_int(w, bits):
    x = w.double(); amax = x.abs().amax(-1, keepdim=True).clamp(min=1e-12)
    return int_qd(x/amax, bits)*amax
def qd_lns(w, bits):
    x = w.double(); amax = x.abs().amax(-1, keepdim=True).clamp(min=1e-12)
    return lns_qd(x/amax, bits)*amax
def catalog(W, N):
    pe, pm, pb = phi_split(N)
    c = [qd_mf(W, pe, pm, pb)]
    if N-3 >= 1: c.append(qd_mf(W, 2, N-3, 1))
    c.append(qd_int(W, N)); c.append(qd_lns(W, N))
    return c[:4]
def _splits(N, e_max=8):
    return [(e, N-1-e, 2**(e-1)-1) for e in range(1, min(N, e_max+1)) if N-1-e >= 0]
def intra_best(W, N):
    qs = [qd_mf(W, e, m, b) for (e, m, b) in _splits(N)]
    errs = torch.stack([((W.double()-q)**2).sum(-1) for q in qs])
    ch = errs.argmin(0)
    return torch.stack(qs)[ch, torch.arange(W.shape[0])]
def q_axis1(W, N):
    c = catalog(W, N); qs = torch.stack(c)
    errs = torch.stack([((W.double()-q)**2).sum(-1) for q in c]); ch = errs.argmin(0)
    return qs[ch, torch.arange(W.shape[0])]
def q_comp(W, N):
    pool = catalog(W, N) + [intra_best(W, N)]; qs = torch.stack(pool)
    errs = torch.stack([((W.double()-q)**2).sum(-1) for q in pool]); ch = errs.argmin(0)
    return qs[ch, torch.arange(W.shape[0])]

# ── игрушечный последовательный поток: Markov-ish с дальней зависимостью (не тривиальный) ──
VOCAB = 256; D = 128; NL = 4; SEQ = 64; NTRAIN = 200_000; NVAL = 40_000
# ОБЩАЯ переходная матрица для train И val (одно распределение — иначе val нерепрезентативен).
_PRNG = np.random.default_rng(777)
_P = _PRNG.dirichlet(np.ones(VOCAB)*0.05, size=VOCAB)   # α=0.05 → высокая, но НЕ нулевая энтропия
_C = np.cumsum(_P, axis=1)
def gen_stream(n, seed):
    # марковская цепь порядка 2, единая _P для train/val, только seed старта/шума разный.
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

STEPS = int(os.environ.get("STEPS", 800)); BATCH = 32
torch.manual_seed(42); model = Micro().to(device)
op = torch.optim.AdamW(model.parameters(), lr=3e-3, weight_decay=0.1, betas=(0.9, 0.95))
print(f"Обучение микро-LM {NL}L d={D} vocab={VOCAB} {STEPS} шагов (CPU)...", flush=True)
for st in range(STEPS+1):
    idx = torch.randint(0, len(train_t)-SEQ-1, (BATCH,))
    x = torch.stack([train_t[i:i+SEQ] for i in idx])
    y = torch.stack([train_t[i+1:i+SEQ+1] for i in idx])
    loss = F.cross_entropy(model(x).reshape(-1, VOCAB), y.reshape(-1))
    op.zero_grad(); loss.backward(); nn.utils.clip_grad_norm_(model.parameters(), 1.0); op.step()
    if st % 500 == 0: print(f"  {st}/{STEPS}: loss={loss.item():.4f}", flush=True)
model.eval()

lin = {n: m for n, m in model.named_modules()
       if isinstance(m, nn.Linear) and m.weight is not model.e.weight}
print(f"Linear-слоёв под квант: {len(lin)}  (имена: {list(lin)[:4]}...)")
fp32 = {n: m.weight.data.clone() for n, m in lin.items()}

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
    print(f"  [{tag}] bits/token={bpt:.5f}  (tok={tot})", flush=True)
    return dict(tag=tag, bits_per_token=bpt)
def apply_q(N, fn):
    for n, m in lin.items(): m.weight.data.copy_(fn(fp32[n].double(), N).to(m.weight.dtype))
def restore():
    for n, m in lin.items(): m.weight.data.copy_(fp32[n])

print(f"\n{'='*72}\nВАРИАНТ B CPU-ПРОКСИ: model bits-per-token — ось1 GF+A vs композиция")
print(f"порог = {BPB_TH} BPB = {BPT_TH:.4f} BPT | val батчей={NB}\n{'='*72}")
rep = {"meta": dict(scale="micro-LM CPU proxy", NL=NL, D=D, vocab=VOCAB, steps=STEPS,
                    bpt_thresh=BPT_TH, seed=20260729,
                    note="направление эффекта, НЕ величина; НЕ обобщается на 29M; оверхед не вычтен")}
restore(); rep["fp32"] = eval_bpt("FP32 baseline")
for N in (4, 6, 8):
    print(f"\n--- {N}-bit ---")
    apply_q(N, q_axis1); r1 = eval_bpt(f"{N}b ось1 GF+A")
    apply_q(N, q_comp);  rc = eval_bpt(f"{N}b композиция GF+A∘intra")
    d = rc["bits_per_token"] - r1["bits_per_token"]
    sig = "ЗНАЧИМО (окупает downstream)" if d <= -BPT_TH else f"<порог {BPT_TH:.4f} BPT (незначимо)"
    print(f"  ΔBPT(композиция − ось1) = {d:+.5f} бит/ток → {sig}")
    rep[str(N)] = dict(axis1=r1, composition=rc, dbpt=d,
                       significant=bool(abs(d) >= BPT_TH),
                       composition_pays_off=bool(d <= -BPT_TH))
restore()
out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "composition_bpt_cpu_proxy_results.json")
json.dump(rep, open(out, "w"), indent=2)
print(f"\nsaved {out}")
