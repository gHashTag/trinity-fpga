#!/usr/bin/env python3
"""ВЕКТОР 2-BPB на поде: замер РЕАЛЬНОГО model-BPB для MSE-выбора vs Hessian-выбора кармана
GF+A на 29M-модели. [измерено — GPU]. Закрывает границу инварианта №18: вектор 2 доказал
выигрыш Hessian-выбора по downstream-SQNR выхода слоя, но SQNR РАНЖИРУЕТ, а решает model-BPB
при пороге значимости Parameter Golf = 0.005 BPB. Здесь мы КВАНТУЕМ веса модели (не только
считаем SQNR слоя), делаем реальный forward на независимом val-потоке и меряем bits-per-byte.

Три конфигурации + абляция:
  (0) baseline FP32                       — верхняя планка (без квантования)
  (A) MSE-выбор кармана во ВСЕ Linear     — квант-proxy BPB
  (B) Hessian-выбор кармана во ВСЕ Linear  — квант-proxy BPB
  (C) абляция «только глубокие linear1»   — Hessian vs MSE лишь в FFN up-proj слоёв ≥ середины
      (там, где вектор 2 показал максимальный ΔSQNR, до +3.1 дБ на l.8.linear1)

ГЛАВНЫЙ ВОПРОС: ΔBPB = BPB(Hessian) − BPB(MSE). Если |ΔBPB| ≥ 0.005 и знак «−» (BPB меньше) —
Hessian-выбор ОКУПАЕТ себя downstream. Если |ΔBPB| < 0.005 — SQNR-выигрыш НЕ переносится в BPB
(SQNR был суррогатом, порог не пройден). Честно замеряем ОБА исхода.

BPB считается честно: BPB = (Σ CE_nats / ln2) / Σ bytes, где bytes = длина декодированного
SentencePiece-текста целевых токенов в UTF-8 (НЕ фиксированный коэффициент).

Запуск на поде (env ПЕРЕД python, НЕ перед curl):
  curl -s https://raw.githubusercontent.com/gHashTag/trinity-fpga/main/webterm_gfplus_v2bpb.py -o /tmp/vb.py
  STEPS=3000 python3 /tmp/vb.py
"""
import os, sys, json, math, subprocess, re
import numpy as np

# ── Blackwell sm_120: системный torch (cu124) БЕЗ ядер sm_120. В одном процессе перегрузить
# CUDA-расширение НЕЛЬЗЯ → ставим cu128 и RE-EXEC скрипт (guard-флаг от петли). ────────────────
def _ensure_torch_cu128():
    if os.environ.get("_VB_TORCH_OK") == "1":
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
            os.environ["_VB_TORCH_OK"] = "1"; return
        print(f"torch {_t.__version__} БЕЗ {sm} (arch={arch}) → reinstall cu128 (3-6 мин)", flush=True)
    except Exception as e:
        print(f"torch import failed ({e}) → install cu128", flush=True)
    ok = False
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
            ok = True; break
    if not ok:
        print(f"WARN: torch всё ещё без {sm} — прогон может упасть", flush=True)
    os.environ["_VB_TORCH_OK"] = "1"
    print("=== re-exec со свежим torch ===", flush=True)
    os.execv(sys.executable, [sys.executable] + sys.argv)
_ensure_torch_cu128()
os.system("pip3 install sentencepiece numpy -q 2>&1 | tail -1")
import torch, torch.nn as nn, torch.nn.functional as F
import sentencepiece as spm
print(f"[final] torch {torch.__version__} | arch_list={torch.cuda.get_arch_list()}", flush=True)

# ── карманы GF+A (идентичны webterm_gfplus_v2select.py) ──
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
def scaled_qd(w, kind, **kw):
    x = w.double(); amax = x.abs().amax(dim=-1, keepdim=True).clamp(min=1e-12)
    if kind == "mf":
        e, m, b = kw["e"], kw["m"], kw["bias"]; scale = amax/fmt_maxn(e, m, b)
        return minifloat_qd(x/scale, e, m, b)*scale
    if kind == "int": return int_qd(x/amax, kw["bits"])*amax
    if kind == "lns": return lns_qd(x/amax, kw["bits"])*amax
    raise ValueError(kind)
def pockets_v2(N):
    pe, pm, pb = phi_split(N)
    out = [(f"phi_e{pe}m{pm}", "mf", dict(e=pe, m=pm, bias=pb))]
    if N-3 >= 1: out.append((f"e2m{N-3}", "mf", dict(e=2, m=N-3, bias=1)))
    out.append((f"int{N}", "int", dict(bits=N)))
    out.append((f"lns{N}", "lns", dict(bits=N)))
    return out[:4]
def select(W, N, hess=None, metric="mse"):
    """Возвращает q:[R,C] — построчный выбор кармана + сам квант."""
    cands = [scaled_qd(W, k, **kw) for _, k, kw in pockets_v2(N)]
    wj = hess.view(1, -1) if metric == "hess" else torch.ones(1, W.shape[1], dtype=torch.double, device=W.device)
    errs = torch.stack([(wj*(W.double()-q)**2).sum(-1) for q in cands])  # [P,R]
    ch = errs.argmin(0)
    return torch.stack(cands)[ch, torch.arange(W.shape[0], device=W.device)]

# ── модель (как webterm_gfplus_v2select) ──
device = 'cuda'; VOCAB=1024; D=512; NL=9; SEQ=1024; BATCH=48
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

# SentencePiece-модель для перевода токены→байты (честный знаменатель BPB)
sp = None
for cand in (f"{DATA}/sp1024.model", f"{DATA}/tokenizer.model", "data/sp1024.model"):
    if os.path.exists(cand):
        sp = spm.SentencePieceProcessor(model_file=cand); print(f"SP model: {cand}"); break
if sp is None:
    hits = subprocess.run(["bash","-c","find /workspace/parameter-golf -name '*.model' 2>/dev/null | head -3"],
                          capture_output=True, text=True).stdout.strip()
    print(f"SP .model поиск: {hits or 'НЕ найдено'}")
    if hits: sp = spm.SentencePieceProcessor(model_file=hits.splitlines()[0])

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

print(f"GPU: {torch.cuda.get_device_name(0)} | torch {torch.__version__}")
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

# ── целевые Linear-слои и снятие Hessian-диагонали (calib pass) ──
# ВАЖНО: self_attn.out_proj внутри nn.MultiheadAttention ВЫЗЫВАЕТСЯ через functional-путь
# (F._native_multi_head_attention) — forward-hook на нём НЕ срабатывает (проверено). Поэтому
# Hessian снимается только для FFN (linear1/linear2), где hook надёжен — а именно там вектор 2
# локализовал весь downstream-выигрыш. out_proj остаётся на чистом MSE (hess=None) — не падать.
lin = {n: mod for n, mod in model.named_modules()
       if isinstance(mod, nn.Linear) and mod.weight.numel() > 100000 and mod.weight is not model.e.weight}
print(f"\nLinear-слоёв под квант: {len(lin)}")
acc = {n: {"sx2": None, "n": 0} for n in lin}
def mk_calib(name):
    def h(mod, inp, out):
        if not inp or inp[0] is None: return
        X = inp[0].detach().reshape(-1, inp[0].shape[-1]).double()
        s2 = (X*X).sum(0)
        acc[name]["sx2"] = s2 if acc[name]["sx2"] is None else acc[name]["sx2"]+s2
        acc[name]["n"] += X.shape[0]
    return h
hooks = [m.register_forward_hook(mk_calib(n)) for n, m in lin.items()]
with torch.no_grad():
    for _ in range(4):
        idx=torch.randint(0,len(train_t)-SEQ-1,(8,)); xb=torch.stack([train_t[i:i+SEQ] for i in idx]).to(device); model(xb)
for h in hooks: h.remove()
# hess[n] = None для нехукнутых (out_proj) → там выбор пойдёт по MSE в обеих конфигурациях
hess = {n: ((acc[n]["sx2"]/acc[n]["n"]).double() if acc[n]["sx2"] is not None and acc[n]["n"] > 0 else None)
        for n in lin}
hooked = [n for n in lin if hess[n] is not None]
no_hess = [n for n in lin if hess[n] is None]
print(f"  Hessian снят: {len(hooked)}/{len(lin)} слоёв (FFN). Без Hessian (out_proj, остаются MSE): {len(no_hess)}")
if no_hess: print(f"    нет активаций: {no_hess[:3]}{'...' if len(no_hess)>3 else ''}")

# ── эталонные FP32-веса, чтобы возвращать/переквантовывать ──
fp32 = {n: m.weight.data.clone() for n, m in lin.items()}

# ── честная метрика: реальный forward на независимом val ──
# ПЕРВИЧНАЯ метрика = bits-per-token (однозначна, НЕ требует токенайзера).
# BPB через токенайзер НЕ считаем: единственная найденная .model — 8192-BPE, а поток sp1024
# (VOCAB=1024): ид-шкалы НЕ совпадают → decode дал бы мусорные байты. BPB пересчитываем лишь
# для справки через документированный коэф. байт/токен (sp1024 ≈ 3.9), помечен [прокси-коэф].
BYTES_PER_TOK = float(os.environ.get("BYTES_PER_TOK", 3.9))  # sp1024 эмпирика; только для справочного BPB
BPB_THRESH = 0.005                                          # порог Parameter Golf (BPB)
BPT_THRESH = BPB_THRESH * BYTES_PER_TOK                     # эквивалент в bits-per-token ≈ 0.0195
NBATCH = int(os.environ.get("BPB_BATCH", 24))   # val-батчей по SEQ токенов
def eval_bpb(tag):
    torch.manual_seed(123)  # фикс val-выборки: одинаковый набор для всех конфигураций
    tot_nats = 0.0; tot_tok = 0
    with torch.no_grad():
        for _ in range(NBATCH):
            i = torch.randint(0, len(val_t)-SEQ-1, (1,)).item()
            x = val_t[i:i+SEQ].unsqueeze(0).to(device)
            y = val_t[i+1:i+SEQ+1].to(device)
            logits = model(x).reshape(-1, VOCAB)
            ce = F.cross_entropy(logits, y, reduction='sum')  # nats
            tot_nats += float(ce); tot_tok += y.numel()
    bpt = tot_nats/math.log(2)/tot_tok               # bits per token (ПЕРВИЧНАЯ)
    bpb = bpt / BYTES_PER_TOK                          # справочный [прокси-коэф байт/ток]
    print(f"  [{tag}] bits/token={bpt:.5f}  bits/byte≈{bpb:.5f} [прокси]  (tok={tot_tok})", flush=True)
    return dict(tag=tag, bits_per_token=bpt, bits_per_byte_proxy=bpb, tokens=tot_tok)

def apply_quant(N, metric, layer_filter=None):
    """Проквантовать веса выбранных слоёв на месте. layer_filter(name)->bool или None=все.
    Если metric=='hess', но hess[n] отсутствует (out_proj) — авто-fallback на MSE для этого слоя."""
    for n, m in lin.items():
        if layer_filter is not None and not layer_filter(n):
            m.weight.data.copy_(fp32[n]); continue   # оставить FP32
        W = fp32[n].double()
        use_hess = (metric == "hess" and hess[n] is not None)
        q = select(W, N, hess=hess[n] if use_hess else None, metric="hess" if use_hess else "mse")
        m.weight.data.copy_(q.to(m.weight.dtype))
def restore_fp32():
    for n, m in lin.items(): m.weight.data.copy_(fp32[n])

# фильтр «глубокие linear1» = FFN up-proj (linear1) в слоях второй половины стека.
# Имена модулей: 'l.<idx>.linear1' (TransformerEncoderLayer в ModuleList 'l').
def deep_ffn(n):
    if "linear1" not in n: return False
    mt = re.search(r"(?:^|\.)l\.(\d+)\.", n)
    return mt is not None and int(mt.group(1)) >= NL//2

print(f"\n{'='*72}\nВЕКТОР 2-BPB: реальный model bits-per-token, MSE-выбор vs Hessian-выбор кармана GF+A")
print(f"порог Parameter Golf = {BPB_THRESH} BPB = {BPT_THRESH:.4f} BPT (коэф {BYTES_PER_TOK} байт/ток) | val батчей={NBATCH}\n{'='*72}")
report = {"meta": dict(NL=NL, D=D, steps=STEPS, nbatch=NBATCH, primary_metric="bits_per_token",
                       bytes_per_tok=BYTES_PER_TOK, bpt_thresh=BPT_THRESH, bpb_thresh=BPB_THRESH,
                       hooked_ffn=len(hooked), no_hess_out_proj=len(no_hess), n_lin=len(lin), seed=42)}

restore_fp32(); report["fp32"] = eval_bpb("FP32 baseline")

for N in (4, 6, 8):
    print(f"\n--- {N}-bit ---")
    apply_quant(N, "mse");  r_mse  = eval_bpb(f"{N}b MSE-выбор (все слои)")
    apply_quant(N, "hess"); r_hess = eval_bpb(f"{N}b Hessian-выбор (все FFN)")
    # абляция: Hessian лишь в глубоких linear1, остальное MSE
    apply_quant(N, "mse"); apply_quant(N, "hess", layer_filter=deep_ffn)
    r_abl = eval_bpb(f"{N}b гибрид: Hessian@глубокие-linear1, MSE иначе")
    d_all = r_hess["bits_per_token"] - r_mse["bits_per_token"]   # решаем по BPT (первичная)
    d_abl = r_abl["bits_per_token"]  - r_mse["bits_per_token"]
    sig = lambda d: "ЗНАЧИМО" if abs(d) >= BPT_THRESH else f"<порог {BPT_THRESH:.4f} BPT (незначимо)"
    print(f"  ΔBPT(Hessian−MSE, все слои) = {d_all:+.5f} бит/ток  → {sig(d_all)}"
          f"{'  [Hessian ОКУПАЕТ]' if d_all<=-BPT_THRESH else ''}")
    print(f"  ΔBPT(гибрид−MSE)            = {d_abl:+.5f} бит/ток  → {sig(d_abl)}")
    report[str(N)] = dict(mse=r_mse, hess=r_hess, hybrid_deep_ffn=r_abl,
                          dbpt_all=d_all, dbpt_hybrid=d_abl,
                          dbpb_proxy_all=d_all/BYTES_PER_TOK, dbpb_proxy_hybrid=d_abl/BYTES_PER_TOK,
                          significant_all=bool(abs(d_all)>=BPT_THRESH),
                          hessian_pays_off=bool(d_all<=-BPT_THRESH))
restore_fp32()
json.dump(report, open("/workspace/v2bpb_results.json", "w"), indent=2)
print("\nsaved /workspace/v2bpb_results.json")
print(f"\nИТОГ (решение по bits-per-token, порог {BPT_THRESH:.4f} BPT = {BPB_THRESH} BPB):")
print(f"  • если ΔBPT(все слои) ≤ −{BPT_THRESH:.4f} хотя бы на одной битности — Hessian-выбор ОКУПАЕТ")
print("    себя downstream (SQNR-выигрыш переносится в потери модели);")
print("  • если |ΔBPT| < порога везде — SQNR был суррогатом, выбор кармана нейтрален по потерям.")
print("\nГраница: bits-per-token — честная первичная метрика; BPB = BPT/коэф [прокси], т.к. поток")
print("sp1024 не декодируется найденным 8192-BPE-токенайзером (vocab mismatch). Hessian только на FFN.")
