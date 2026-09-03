#!/usr/bin/env python3
"""ВАРИАНТ B (луп 29.07.2026b): замер РЕАЛЬНОГО model bits-per-token для оси-КОМПОЗИЦИИ
GF+A vs GF+A⊕intra-pocket на 29M-модели. [измерено — GPU] при запуске на поде.

Закрывает ГЛАВНУЮ незакрытую границу инварианта №26: SW-абляция selector_vs_intrapocket.py
доказала, что композиция ≥ каждой оси по MSE-метрике ВЫБОРА (0/20 нарушений), НО инвариант №18
предупреждает: SQNR/MSE слоя = СУРРОГАТ, который может НЕ окупаться по downstream model-BPB.
Здесь мы КВАНТУЕМ веса реальной модели тремя способами и меряем bits-per-token на независимом
val-потоке — честно проверяя, переносится ли SW-выигрыш композиции в потери модели.

Три конфигурации:
  (0) baseline FP32                          — верхняя планка (без квантования)
  (A) ось1: GF+A catalog-select              — построчный выбор кармана МЕЖДУ форматами φ-каталога
  (B) композиция: GF+A ∘ intra-pocket        — тот же catalog-select, НО если карман = minifloat,
      поверх — построчный (e,m)-refinement бит-разбиения ВНУТРИ семейства (dMX-стиль)

ГЛАВНЫЙ ВОПРОС: ΔBPT = BPT(композиция) − BPT(GF+A). Порог значимости Parameter Golf = 0.005 BPB
= 0.0195 BPT (коэф 3.9 байт/ток). Если ΔBPT ≤ −0.0195 — композиция ОКУПАЕТ +0.18 бит/эл оверхеда
downstream. Если |ΔBPT| < порога — SW-выигрыш композиции НЕ переносится в потери модели (SQNR был
суррогатом, инв.18), и оси остаются ОРТОГОНАЛЬНЫМИ, но композиция не даёт downstream-выигрыша при
данном бит-бюджете. Честно замеряем ОБА исхода — заявление о превосходстве НЕ делается ни в каком.

BINDING (правила честности):
  • Это НЕ реимплементация dMX (у них дифф. end-to-end поиск + STE-обучение). intra-pocket =
    СВОЯ SW-модель оси распределения бит внутри семейства, [SW proxy].
  • Композиция тратит +0.18 бит/эл на per-group заголовок кармана → сравнение НЕ бит-выровнено
    в пользу композиции; поэтому вывод «композиция ≥ GF+A downstream» можно делать ТОЛЬКО если
    ΔBPT проходит порог С УЧЁТОМ этого оверхеда. Иначе — оси ортогональны, не более.
  • bits-per-token — ПЕРВИЧНАЯ метрика (не требует токенайзера). BPB = BPT/3.9 [прокси-коэф],
    т.к. поток sp1024 не декодируется найденным 8192-BPE .model (vocab mismatch, инв.18).

Запуск на поде (env ПЕРЕД python, НЕ перед curl):
  curl -s https://raw.githubusercontent.com/gHashTag/trinity-fpga/main/webterm_composition_bpb.py -o /tmp/cb.py
  STEPS=3000 python3 /tmp/cb.py
"""
import os, sys, json, math, subprocess

# ── Blackwell sm_120: при необходимости переставить torch cu128 и RE-EXEC (guard от петли) ──
def _ensure_torch_cu128():
    if os.environ.get("_CB_TORCH_OK") == "1":
        return
    def _sm_needed():
        rc = subprocess.run(["nvidia-smi", "--query-gpu=compute_cap", "--format=csv,noheader"],
                            capture_output=True, text=True)
        caps = [c.strip() for c in rc.stdout.splitlines() if c.strip()]
        return "sm_" + caps[0].replace(".", "") if caps else None
    sm = _sm_needed()
    try:
        import torch as _t
        arch = _t.cuda.get_arch_list() if _t.cuda.is_available() else []
        if sm is None or sm in arch:
            print(f"torch {_t.__version__} arch={arch} → {sm} OK", flush=True)
            os.environ["_CB_TORCH_OK"] = "1"; return
        print(f"torch {_t.__version__} БЕЗ {sm} (arch={arch}) → reinstall cu128 (3-6 мин)", flush=True)
    except Exception as e:
        print(f"torch import failed ({e}) → install cu128", flush=True)
    for idx in ("https://download.pytorch.org/whl/cu128",
                "https://download.pytorch.org/whl/nightly/cu128"):
        print(f"pip install -U torch --index-url {idx} ...", flush=True)
        subprocess.run([sys.executable, "-m", "pip", "install", "-q", "-U", "--no-cache-dir",
                        "torch", "--index-url", idx])
        chk = subprocess.run([sys.executable, "-c",
            "import torch;print(torch.__version__);print(torch.cuda.get_arch_list())"],
            capture_output=True, text=True)
        print(chk.stdout.strip()[-200:] + chk.stderr.strip()[-200:], flush=True)
        if sm is None or sm in chk.stdout:
            break
    os.environ["_CB_TORCH_OK"] = "1"
    print("=== re-exec со свежим torch ===", flush=True)
    os.execv(sys.executable, [sys.executable] + sys.argv)
_ensure_torch_cu128()
os.system("pip3 install sentencepiece numpy -q 2>&1 | tail -1")
import numpy as np
import torch, torch.nn as nn, torch.nn.functional as F
print(f"[final] torch {torch.__version__} | cuda={torch.cuda.is_available()}", flush=True)

# ─────────────────── карманы φ-каталога (идентичны SSOT gfplus_a) ───────────────────
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
def scaled_qd_mf(w, e, m, bias):
    x = w.double(); amax = x.abs().amax(dim=-1, keepdim=True).clamp(min=1e-12)
    scale = amax/fmt_maxn(e, m, bias)
    return minifloat_qd(x/scale, e, m, bias)*scale
def scaled_qd_int(w, bits):
    x = w.double(); amax = x.abs().amax(dim=-1, keepdim=True).clamp(min=1e-12)
    return int_qd(x/amax, bits)*amax
def scaled_qd_lns(w, bits):
    x = w.double(); amax = x.abs().amax(dim=-1, keepdim=True).clamp(min=1e-12)
    return lns_qd(x/amax, bits)*amax

# ── ось1: катал��г карманов GF+A (между форматами) ──
def catalog_candidates(W, N):
    """Список (имя, q[R,C], is_minifloat, (e,m,bias)) карманов φ-каталога."""
    pe, pm, pb = phi_split(N)
    cands = [(f"phi_e{pe}m{pm}", scaled_qd_mf(W, pe, pm, pb), True, (pe, pm, pb))]
    if N-3 >= 1:
        cands.append((f"e2m{N-3}", scaled_qd_mf(W, 2, N-3, 1), True, (2, N-3, 1)))
    cands.append((f"int{N}", scaled_qd_int(W, N), False, None))
    cands.append((f"lns{N}", scaled_qd_lns(W, N), False, None))
    return cands[:4]

# ── ось2: intra-pocket (e,m)-refinement ВНУТРИ семейства minifloat (dMX-стиль) ──
def _valid_splits(N, e_max=8):
    out = []
    for e in range(1, min(N, e_max + 1)):
        m = N - 1 - e
        if m >= 0:
            out.append((e, m, 2**(e-1)-1))
    return out
def intra_pocket_best(W, N):
    """Для КАЖДОЙ строки — лучший (e,m)-сплит minifloat по построчной MSE (ось распределения бит)."""
    splits = _valid_splits(N)
    qs = [scaled_qd_mf(W, e, m, b) for (e, m, b) in splits]           # список [R,C]
    errs = torch.stack([((W.double()-q)**2).sum(-1) for q in qs])     # [S,R]
    ch = errs.argmin(0)                                              # [R]
    return torch.stack(qs)[ch, torch.arange(W.shape[0], device=W.device)]

def quant_axis1(W, N):
    """ось1 GF+A: построчный выбор ЛУЧШЕГО кармана каталога по MSE."""
    cands = catalog_candidates(W, N)
    qs = torch.stack([q for _, q, _, _ in cands])                     # [P,R,C]
    errs = torch.stack([((W.double()-q)**2).sum(-1) for _, q, _, _ in cands])  # [P,R]
    ch = errs.argmin(0)
    return qs[ch, torch.arange(W.shape[0], device=W.device)]

def quant_composition(W, N):
    """композиция ось1∘ось2: построчный argmin-union КАТАЛОГА и intra-pocket-refined minifloat.
    Демонстрирует, что композиция ≥ каждой оси по MSE — здесь мы КВАНТУЕМ модель этим выбором."""
    cands = catalog_candidates(W, N)
    q_intra = intra_pocket_best(W, N)                                 # [R,C] лучший intra-сплит
    pool = [q for _, q, _, _ in cands] + [q_intra]
    qs = torch.stack(pool)                                            # [P+1,R,C]
    errs = torch.stack([((W.double()-q)**2).sum(-1) for q in pool])   # [P+1,R]
    ch = errs.argmin(0)
    return qs[ch, torch.arange(W.shape[0], device=W.device)]

# ─────────────────── модель (как webterm_gfplus_v2bpb) ───────────────────
device = 'cuda' if torch.cuda.is_available() else 'cpu'
VOCAB=1024; D=512; NL=9; SEQ=1024; BATCH=48
STEPS = int(os.environ.get("STEPS", 3000))
os.chdir("/workspace")
if not os.path.exists("parameter-golf"):
    os.system("git clone --depth 1 https://github.com/openai/parameter-golf.git")
os.chdir("/workspace/parameter-golf")
DATA = "data/datasets/fineweb10B_sp1024"
if not os.path.exists(f"{DATA}/fineweb_val_000000.bin"):
    os.system("python3 data/cached_challenge_fineweb.py --variant sp1024 --train-shards 1 2>&1 | tail -2")
val = np.memmap(f'{DATA}/fineweb_val_000000.bin', dtype=np.uint16, mode='r')
train_t = torch.tensor(val[:8000000].astype(np.int64)); val_t = torch.tensor(val[8000000:].astype(np.int64))

class Model(nn.Module):
    def __init__(s):
        super().__init__()
        s.e=nn.Embedding(VOCAB,D); s.p=nn.Embedding(SEQ,D)
        s.l=nn.ModuleList([nn.TransformerEncoderLayer(d_model=D,nhead=8,dim_feedforward=D*4,dropout=0.1,batch_first=True,activation='gelu',norm_first=True) for _ in range(NL)])
        s.f=nn.LayerNorm(D); s.h=nn.Linear(D,VOCAB,bias=False); s.h.weight=s.e.weight
    def forward(s,x):
        h=s.e(x)+s.p(torch.arange(x.size(1),device=x.device))
        for b in s.l: h=b(h)
        return s.h(s.f(h))

print(f"device={device} | torch {torch.__version__}")
print(f"Training {NL}L d={D} {STEPS} steps...")
torch.manual_seed(42); model=Model().to(device)
op=torch.optim.AdamW(model.parameters(),lr=0.003,weight_decay=0.1,betas=(0.95,0.95))
for s in range(STEPS+1):
    idx=torch.randint(0,len(train_t)-SEQ-1,(BATCH,))
    x=torch.stack([train_t[i:i+SEQ] for i in idx]).to(device)
    y=torch.stack([train_t[i+1:i+SEQ+1] for i in idx]).to(device)
    loss=F.cross_entropy(model(x).reshape(-1,VOCAB),y.reshape(-1))
    op.zero_grad(); loss.backward(); torch.nn.utils.clip_grad_norm_(model.parameters(),1.0); op.step()
    if s%1000==0: print(f"  {s}/{STEPS}: loss={loss.item():.4f}", flush=True)
model.eval()

lin = {n: mod for n, mod in model.named_modules()
       if isinstance(mod, nn.Linear) and mod.weight.numel() > 100000 and mod.weight is not model.e.weight}
print(f"\nLinear-слоёв под квант: {len(lin)}")
fp32 = {n: m.weight.data.clone() for n, m in lin.items()}

BYTES_PER_TOK = float(os.environ.get("BYTES_PER_TOK", 3.9))
BPB_THRESH = 0.005
BPT_THRESH = BPB_THRESH * BYTES_PER_TOK   # ≈ 0.0195
NBATCH = int(os.environ.get("BPB_BATCH", 24))
def eval_bpt(tag):
    torch.manual_seed(123)
    tot_nats = 0.0; tot_tok = 0
    with torch.no_grad():
        for _ in range(NBATCH):
            i = torch.randint(0, len(val_t)-SEQ-1, (1,)).item()
            x = val_t[i:i+SEQ].unsqueeze(0).to(device)
            y = val_t[i+1:i+SEQ+1].to(device)
            ce = F.cross_entropy(model(x).reshape(-1, VOCAB), y, reduction='sum')
            tot_nats += float(ce); tot_tok += y.numel()
    bpt = tot_nats/math.log(2)/tot_tok
    print(f"  [{tag}] bits/token={bpt:.5f}  bits/byte≈{bpt/BYTES_PER_TOK:.5f} [прокси]  (tok={tot_tok})", flush=True)
    return dict(tag=tag, bits_per_token=bpt, bits_per_byte_proxy=bpt/BYTES_PER_TOK, tokens=tot_tok)

def apply_quant(N, fn):
    for n, m in lin.items():
        q = fn(fp32[n].double(), N)
        m.weight.data.copy_(q.to(m.weight.dtype))
def restore_fp32():
    for n, m in lin.items(): m.weight.data.copy_(fp32[n])

print(f"\n{'='*74}\nВАРИАНТ B: model bits-per-token — ось1 GF+A vs КОМПОЗИЦИЯ (GF+A∘intra-pocket)")
print(f"порог Parameter Golf = {BPB_THRESH} BPB = {BPT_THRESH:.4f} BPT | val батчей={NBATCH}\n{'='*74}")
report = {"meta": dict(NL=NL, D=D, steps=STEPS, nbatch=NBATCH, primary_metric="bits_per_token",
                       bytes_per_tok=BYTES_PER_TOK, bpt_thresh=BPT_THRESH, bpb_thresh=BPB_THRESH,
                       n_lin=len(lin), seed=42, note="composition overhead +0.18 bit/elem не вычтен из BPT — "
                       "если композиция не проходит порог, она НЕ окупается downstream")}

restore_fp32(); report["fp32"] = eval_bpt("FP32 baseline")
for N in (4, 6, 8):
    print(f"\n--- {N}-bit ---")
    apply_quant(N, quant_axis1);       r_a1 = eval_bpt(f"{N}b ось1 GF+A catalog-select")
    apply_quant(N, quant_composition); r_cp = eval_bpt(f"{N}b композиция GF+A∘intra-pocket")
    d = r_cp["bits_per_token"] - r_a1["bits_per_token"]
    sig = "ЗНАЧИМО (композиция ОКУПАЕТ downstream)" if d <= -BPT_THRESH else \
          (f"<порог {BPT_THRESH:.4f} BPT (незначимо — оси ортогональны, downstream-выигрыша НЕТ)")
    print(f"  ΔBPT(композиция − ось1) = {d:+.5f} бит/ток  → {sig}")
    report[str(N)] = dict(axis1=r_a1, composition=r_cp, dbpt=d,
                          dbpb_proxy=d/BYTES_PER_TOK,
                          significant=bool(abs(d) >= BPT_THRESH),
                          composition_pays_off=bool(d <= -BPT_THRESH))
restore_fp32()
json.dump(report, open("/workspace/composition_bpb_results.json", "w"), indent=2)
print("\nsaved /workspace/composition_bpb_results.json")
print(f"\nИТОГ (решение по bits-per-token, порог {BPT_THRESH:.4f} BPT):")
print("  • ΔBPT ≤ −порога хотя бы на одной битности → композиция окупает +0.18 бит/эл оверхеда;")
print("  • |ΔBPT| < порога везде → SW-выигрыш композиции (0/20 по MSE) НЕ переносится в потери")
print("    модели (SQNR/MSE слоя = суррогат, инв.18) — оси ортогональны, но не downstream-лучше.")
print("  Ни в каком исходе превосходство оси НЕ заявляется.")
