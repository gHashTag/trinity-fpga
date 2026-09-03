#!/usr/bin/env python3
"""ВЕКТОР 2 на поде: downstream-aware выбор кармана GF+A на РЕАЛЬНОЙ 29M-модели.
[измерено — GPU]. Обучает (или грузит чекпоинт) transformer, снимает ВХОДНЫЕ активации
каждого Linear через forward-hooks на калибр-батче, считает диагональ Гессиана H_jj=E[x_j^2],
затем СРАВНИВАЕТ два выбора кармана (MSE весов vs Hessian-взвеш.) по ОДНОЙ downstream-метрике:
SQNR выхода слоя Y=xW^T на НЕЗАВИСИМОМ val-батче (holdout — без утечки калибровки).

Запуск на поде (env ПЕРЕД python, НЕ перед curl):
  curl -s https://raw.githubusercontent.com/gHashTag/trinity-fpga/main/webterm_gfplus_v2select.py -o /tmp/v2.py
  STEPS=3000 python3 /tmp/v2.py
"""
import os, sys, json, math, subprocess
import numpy as np

# ── Blackwell sm_120: системный torch (cu124) БЕЗ ядер sm_120. Надолом в одном процессе
# НЕЛЬЗЯ (скомпилированное CUDA-расширение не перезагружается) → ставим cu128 и RE-EXEC скрипт.
def _ensure_torch_cu128():
    if os.environ.get("_V2_TORCH_OK") == "1":
        return  # уже после re-exec со свежим torch
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
            os.environ["_V2_TORCH_OK"] = "1"; return
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
    # RE-EXEC: свежий интерпретатор подхватит новый torch чисто
    os.environ["_V2_TORCH_OK"] = "1"
    print("=== re-exec со свежим torch ===", flush=True)
    os.execv(sys.executable, [sys.executable] + sys.argv)
_ensure_torch_cu128()
os.system("pip3 install sentencepiece numpy -q 2>&1 | tail -1")
import torch, torch.nn as nn, torch.nn.functional as F
import sentencepiece as spm
print(f"[final] torch {torch.__version__} | arch_list={torch.cuda.get_arch_list()}", flush=True)

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
    """W:[R,C]. hess:[C] или None. Возвращает q:[R,C]."""
    cands = [scaled_qd(W, k, **kw) for _, k, kw in pockets_v2(N)]
    wj = hess.view(1, -1) if metric == "hess" else torch.ones(1, W.shape[1], dtype=torch.double, device=W.device)
    errs = torch.stack([(wj*(W.double()-q)**2).sum(-1) for q in cands])  # [P,R]
    ch = errs.argmin(0)
    return torch.stack(cands)[ch, torch.arange(W.shape[0], device=W.device)]

def out_sqnr(W, Wq, X):
    Y = X.double() @ W.double().T; Yq = X.double() @ Wq.double().T
    return float(10*torch.log10((Y**2).mean()/((Y-Yq)**2).mean().clamp(min=1e-30)))

# ── модель (как webterm_gfplus) ──
device = 'cuda'; VOCAB=1024; D=512; NL=9; SEQ=1024; BATCH=48
STEPS = int(os.environ.get("STEPS", 3000))
os.chdir("/workspace")
if not os.path.exists("parameter-golf"):
    os.system("git clone --depth 1 https://github.com/openai/parameter-golf.git")
os.chdir("/workspace/parameter-golf")
if not os.path.exists("data/datasets/fineweb10B_sp1024/fineweb_val_000000.bin"):
    os.system("python3 data/cached_challenge_fineweb.py --variant sp1024 --train-shards 1 2>&1 | tail -2")
val = np.memmap('data/datasets/fineweb10B_sp1024/fineweb_val_000000.bin', dtype=np.uint16, mode='r')
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

# ── снятие ВХОДНЫХ активаций Linear через hooks (calib + val, holdout) ──
lin = {n: mod for n, mod in model.named_modules() if isinstance(mod, nn.Linear) and mod.weight.numel() > 100000 and mod.weight is not model.e.weight}
print(f"\nLinear-слоёв для замера: {len(lin)}")
acc = {n: {"sумx2": None, "n": 0} for n in lin}
val_acts = {}
def mk_hook(name, store):
    def h(mod, inp, out):
        X = inp[0].detach().reshape(-1, inp[0].shape[-1]).double()  # [tokens, C_in]
        if store == "calib":
            s2 = (X*X).sum(0)
            if acc[name]["sумx2"] is None: acc[name]["sумx2"] = s2
            else: acc[name]["sумx2"] += s2
            acc[name]["n"] += X.shape[0]
        else:
            if name not in val_acts: val_acts[name] = X[:4096].cpu()  # holdout выборка
    return h

# calib pass
hooks = [m.register_forward_hook(mk_hook(n, "calib")) for n, m in lin.items()]
with torch.no_grad():
    for _ in range(4):
        idx=torch.randint(0,len(train_t)-SEQ-1,(8,)); xb=torch.stack([train_t[i:i+SEQ] for i in idx]).to(device); model(xb)
for h in hooks: h.remove()
# val pass (независимый)
hooks = [m.register_forward_hook(mk_hook(n, "val")) for n, m in lin.items()]
with torch.no_grad():
    idx=torch.randint(0,len(val_t)-SEQ-1,(8,)); xb=torch.stack([val_t[i:i+SEQ] for i in idx]).to(device); model(xb)
for h in hooks: h.remove()

# ── сравнение MSE vs Hessian по downstream-SQNR на VAL ──
print(f"\n{'='*70}\nВЕКТОР 2: MSE-выбор vs Hessian-выбор (downstream SQNR выхода, VAL holdout)\n{'='*70}")
report = {}
for N in (4, 6, 8):
    print(f"\n--- {N}-bit --- (порог значимости 0.005 BPB ~ доли дБ)")
    print(f"{'layer':<28}{'SQNR_mse':>10}{'SQNR_hess':>11}{'ΔSQNR':>8}")
    report[str(N)] = {}
    deltas = []
    for n, m in lin.items():
        if n not in val_acts: continue
        W = m.weight.data.double(); C = W.shape[1]
        hess = (acc[n]["sумx2"] / max(acc[n]["n"], 1)).double()
        Xv = val_acts[n].to(device)
        q_mse = select(W, N, metric="mse"); q_h = select(W, N, hess=hess, metric="hess")
        s_mse = out_sqnr(W, q_mse, Xv); s_h = out_sqnr(W, q_h, Xv)
        deltas.append(s_h - s_mse)
        report[str(N)][n] = dict(sqnr_mse=s_mse, sqnr_hess=s_h, dsqnr=s_h-s_mse)
        short = n[-26:]
        print(f"{short:<28}{s_mse:>10.3f}{s_h:>11.3f}{s_h-s_mse:>+8.3f}")
    if deltas:
        arr = np.array(deltas)
        print(f"  Σ: среднее ΔSQNR {arr.mean():+.3f} дБ | медиана {np.median(arr):+.3f} | "
              f"{int((arr>0).sum())} лучше/{int((arr<0).sum())} хуже/{int((arr==0).sum())} равно")
        report[str(N)]["_summary"] = dict(mean=float(arr.mean()), median=float(np.median(arr)),
                                          better=int((arr>0).sum()), worse=int((arr<0).sum()))
json.dump(report, open("/workspace/v2select_results.json", "w"), indent=2)
print("\nsaved /workspace/v2select_results.json")
