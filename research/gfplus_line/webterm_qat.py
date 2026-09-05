#!/usr/bin/env python3
"""Micro-QAT v3: train-шард для тренировки, val-шард для eval (дизъюнктность по построению),
3 сида, медиана, автокарантин аномальных сидов. Resumable (save после каждой ячейки).

Paste in Web Terminal:
  curl -s https://raw.githubusercontent.com/gHashTag/trinity-fpga/main/webterm_qat.py | python3
"""
import os, sys, json, math
import numpy as np

print("Installing deps...")
os.system("pip3 install --upgrade typing_extensions -q 2>&1 | tail -1")
os.system("pip3 uninstall -y torch torchvision torchaudio 2>/dev/null")
os.system("pip3 install torch --pre --index-url https://download.pytorch.org/whl/nightly/cu128 -q 2>&1 | tail -3")
os.system("pip3 install --upgrade typing_extensions -q 2>&1 | tail -1")
os.system("pip3 install sentencepiece huggingface-hub -q 2>&1 | tail -1")

import torch
import torch.nn as nn, torch.nn.functional as F
import sentencepiece as spm

GPU = torch.cuda.get_device_name(0)
print(f"GPU: {GPU} | PyTorch: {torch.__version__}")

os.chdir("/workspace")
if not os.path.exists("parameter-golf"):
    os.system("git clone --depth 1 https://github.com/openai/parameter-golf.git")
os.chdir("/workspace/parameter-golf")

device='cuda'; VOCAB=1024; D=512; NL=9; SEQ=1024; BATCH=48; STEPS=2000

# ═══ ДАННЫЕ: train-шард для тренировки, val-шард для eval ═══
# v2-БАГ: train и val резались из ОДНОГО val-шарда → seed=123 дал BPB 0.0184
# (в ~50x "лучше" SOTA челленджа ~1.06) = красный флаг дефекта сплита/данных.
DD='data/datasets/fineweb10B_sp1024'
TR=f'{DD}/fineweb_train_000000.bin'; VA=f'{DD}/fineweb_val_000000.bin'
if not (os.path.exists(TR) and os.path.exists(VA)):
    os.system("python3 data/cached_challenge_fineweb.py --variant sp1024 --train-shards 1 2>&1 | tail -2")
assert os.path.exists(TR), f"нет train-шарда {TR}"
assert os.path.exists(VA), f"нет val-шарда {VA}"
def load_tokens(path,n):
    """Чтение шарда с автопропуском nanogpt-заголовка (256 int32, magic 20240520).
    v3-БАГ: чтение файла с нуля без проверки заголовка → токены ≥VOCAB →
    device-assert 'gather index out of bounds' на eval (v2 случайно перепрыгивал срезом [8M:])."""
    a=np.memmap(path,dtype=np.uint16,mode='r')
    if len(a)>512 and int(np.frombuffer(np.array(a[:2]).tobytes(),dtype=np.int32)[0])==20240520:
        print(f"DATA {os.path.basename(path)}: nanogpt-заголовок обнаружен — пропускаю 512 uint16")
        a=a[512:]
    return torch.tensor(np.array(a[:n]).astype(np.int64))
train_t=load_tokens(TR,8_000_000)
val_t  =load_tokens(VA,2_000_000)

# ─── Диагностика данных (защита от утечки/деградации/OOB) ───
for nm,a in (("train(shard0)",train_t),("val(shard0)",val_t)):
    z=float((a==0).float().mean()); mx=int(a.max()); mn=int(a.min())
    print(f"DATA {nm}: len={len(a):,} zero_frac={z:.4f} uniq_frac={len(torch.unique(a))/VOCAB:.3f} min={mn} max={mx}")
    assert 0<=mn and mx<VOCAB, f"{nm}: токен {mx} ≥ VOCAB={VOCAB} — битый шард/неучтённый заголовок — СТОП"
    assert z<0.05, f"{nm}: {z:.1%} нулевых токенов — подозрение на padding/битый шард"
h_tr={hash(train_t[i:i+256].numpy().tobytes()) for i in range(0,len(train_t)-256,4096)}
h_va={hash(val_t[i:i+256].numpy().tobytes()) for i in range(0,len(val_t)-256,4096)}
ov=len(h_tr & h_va)
print(f"DATA overlap smoke-check (256-ток окна, шаг 4096): {ov} совпадений (ожидание 0)")
assert ov==0, "train/val пересекаются — СТОП"

sp=spm.SentencePieceProcessor(model_file='data/tokenizers/fineweb_1024_bpe.model')
bb=torch.zeros(VOCAB,dtype=torch.int16);hs=torch.zeros(VOCAB,dtype=torch.bool);ib=torch.zeros(VOCAB,dtype=torch.bool)
for t in range(VOCAB):
    d=sp.decode([t])
    if d: bb[t]=len(d.encode('utf-8'));hs[t]=d[0]==' '
    if sp.is_unknown(t)or sp.is_control(t)or sp.is_byte(t): ib[t]=True;bb[t]=0

class Model(nn.Module):
    def __init__(s):
        super().__init__()
        s.e=nn.Embedding(VOCAB,D);s.p=nn.Embedding(SEQ,D)
        s.l=nn.ModuleList([nn.TransformerEncoderLayer(d_model=D,nhead=8,dim_feedforward=D*4,dropout=0.1,batch_first=True,activation='gelu',norm_first=True)for _ in range(NL)])
        s.f=nn.LayerNorm(D);s.h=nn.Linear(D,VOCAB,bias=False);s.h.weight=s.e.weight
    def forward(s,x):
        h=s.e(x)+s.p(torch.arange(x.size(1),device=x.device))
        for b in s.l:h=b(h)
        return s.h(s.f(h))

def ste_fp8s():
    MX=448.0
    def f(w):
        if w.dim()<2:return w
        sc=(w.detach().abs().amax(dim=-1,keepdim=True)/MX).clamp(min=1e-12)
        sim=(w/sc).to(torch.float8_e4m3fn).to(w.dtype)*sc
        return (sim-w).detach()+w
    return f

def ste_gf8s():
    MX=31.0;B=3;EM=7;MV=2.0**(1-3-4);ms=16.0
    def f(w):
        if w.dim()<2:return w
        sc=(w.detach().abs().amax(dim=-1,keepdim=True)/MX).clamp(min=1e-12)
        ws=w/sc;sg=torch.sign(ws);a=torch.abs(ws).clamp(min=MV)
        e=torch.floor(torch.log2(a));ff=a/(2.**e);ef=torch.clamp(e+B,1,EM-1)
        sim=sg*(1+torch.round((ff-1)*ms)/ms)*(2.**(ef-B))
        sim=torch.where(torch.abs(ws)<MV,torch.zeros_like(sim),sim)
        sim=torch.clamp(sim,-MX,MX)*sc
        return (sim-w).detach()+w
    return f

def ste_e2m5s():
    E,BIAS,Mm=2,1,5;MX=(2.0**((1<<E)-1-BIAS))*(2.0-2.0**(-Mm));B=1;EM=3;MV=2.0**(1-1-5);ms=32.0
    def f(w):
        if w.dim()<2:return w
        sc=(w.detach().abs().amax(dim=-1,keepdim=True)/MX).clamp(min=1e-12)
        ws=w/sc;sg=torch.sign(ws);a=torch.abs(ws).clamp(min=MV)
        e=torch.floor(torch.log2(a));ff=a/(2.**e);ef=torch.clamp(e+B,1,EM-1)
        sim=sg*(1+torch.round((ff-1)*ms)/ms)*(2.**(ef-B))
        sim=torch.where(torch.abs(ws)<MV,torch.zeros_like(sim),sim)
        sim=torch.clamp(sim,-MX,MX)*sc
        return (sim-w).detach()+w
    return f

def eval_bpb(m):
    m.eval();ls=0.;tk=0;by=0
    with torch.no_grad():
        for i in range(0,len(val_t)-SEQ-1,SEQ*4):
            xc=val_t[i:i+SEQ];yc=val_t[i+1:i+SEQ+1]
            if xc.size(0)<SEQ:continue
            x=xc.unsqueeze(0).to(device);y=yc.unsqueeze(0).to(device)
            lg=m(x).reshape(-1,VOCAB);yt=y.reshape(-1)
            ls+=F.cross_entropy(lg,yt,reduction='sum').item();tk+=SEQ
            # байт-статистика на CPU (дешево; убирает GPU-gather из зоны риска)
            tb=int(bb[yc].sum())+int((hs[yc]&~ib[xc]).sum());by+=max(tb,1)
    m.train();return ls/tk/math.log(2)*tk/by

def run_cell(arm_name, qat_fn, seed):
    """Одна ячейка (плечо, сид) → (bpb, final_train_loss)."""
    torch.manual_seed(seed)
    model=Model().to(device)
    opt=torch.optim.AdamW(model.parameters(),lr=0.003,weight_decay=0.1,betas=(0.95,0.95))
    fl=float('nan')
    for step in range(STEPS+1):
        idx=torch.randint(0,len(train_t)-SEQ-1,(BATCH,))
        x=torch.stack([train_t[i:i+SEQ]for i in idx]).to(device)
        y=torch.stack([train_t[i+1:i+SEQ+1]for i in idx]).to(device)
        if qat_fn:
            saved={n:p.data.clone()for n,p in model.named_parameters()if p.dim()>=2}
            for n,p in model.named_parameters():
                if p.dim()>=2:p.data=qat_fn(p.data)
        loss=F.cross_entropy(model(x).reshape(-1,VOCAB),y.reshape(-1))
        opt.zero_grad();loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(),1.0)
        if qat_fn:
            for n,p in model.named_parameters():
                if n in saved:p.data=saved[n]
        opt.step()
        fl=loss.item()
        if step%500==0:
            print(f"    step={step}/{STEPS} loss={fl:.3f}",flush=True)
    return eval_bpb(model), fl

def sane(bpb, fl):
    """Санити-гейт: для 29M/2000 шагов валидный BPB ~2.6-3.2; SOTA челленджа ~1.06.
    BPB<1.5 или train loss<2.0 = физически неправдоподобно → [ANOMALY], карантин."""
    return (1.5 < bpb < 6.0) and (fl > 2.0)

# ═══ 4 плеча x 3 сида, resumable + чанки через env ═══
# АНТИ-ЗАВИСАНИЕ: гонять по частям, напр.
#   QAT_ARMS=FP32 curl ... | python3        → только FP32 (3 ячейки)
#   QAT_ARMS=FP8S,GF8S curl ... | python3    → два плеча
#   QAT_SEEDS=42 curl ... | python3          → только сид 42 по всем плечам
# Результаты копятся в qat_v3_results.json; итоговая таблица — по всему накопленному.
ALL_ARMS=[("FP32",None),("FP8S",ste_fp8s()),("GF8S",ste_gf8s()),("E2M5S",ste_e2m5s())]
SEEDS=[42,123,777]
_af=os.environ.get("QAT_ARMS");_sf=os.environ.get("QAT_SEEDS")
ARMS=[a for a in ALL_ARMS if (not _af or a[0] in _af.split(","))]
run_seeds=[s for s in SEEDS if (not _sf or str(s) in _sf.split(","))]
RES='/workspace/qat_v3_results.json'
results=json.load(open(RES)) if os.path.exists(RES) else {}
todo=[(a[0],s) for a in ARMS for s in run_seeds if f"{a[0]}/s{s}" not in results]
print(f"\nПЛАН: в этом запуске плечи={[a[0] for a in ARMS]} сиды={run_seeds}")
print(f"      уже готово {len(results)}/12 ячеек; осталось считать {len(todo)}: {todo}\n",flush=True)

for arm_name,qat_fn in ARMS:
    for seed in run_seeds:
        key=f"{arm_name}/s{seed}"
        if key in results:
            print(f"[skip] {key} = {results[key]['bpb']:.4f} (уже посчитано)");continue
        print(f"\n=== {key} ===",flush=True)
        bpb,fl=run_cell(arm_name,qat_fn,seed)
        ok=sane(bpb,fl)
        results[key]={"bpb":bpb,"final_train_loss":fl,"valid":ok}
        tag="" if ok else "  <<< [ANOMALY — карантин, в медиану не идёт]"
        print(f"  → BPB={bpb:.4f} train_loss={fl:.3f}{tag}")
        json.dump(results,open(RES,'w'),indent=2)
        torch.cuda.empty_cache()

# ═══ Итог: медиана валидных сидов, аномалии перечислены явно ═══
import statistics
# Итог ВСЕГДА по всем 4 плечам из накопленного JSON (не только по этому чанку)
print(f"\n{'='*60}\nQAT v3 RESULTS ({STEPS} steps, seeds={SEEDS}, train-shard/val-shard)\nнакоплено {len(results)}/12 ячеек\n{'='*60}")
med={}
for arm_name,_ in ALL_ARMS:
    vals=[results[f'{arm_name}/s{s}']['bpb'] for s in SEEDS if f'{arm_name}/s{s}' in results and results[f'{arm_name}/s{s}']['valid']]
    bad=[s for s in SEEDS if f'{arm_name}/s{s}' in results and not results[f'{arm_name}/s{s}']['valid']]
    med[arm_name]=statistics.median(vals) if vals else float('nan')
    print(f"{arm_name:<8} median={med[arm_name]:.4f} n_valid={len(vals)}/{len(SEEDS)}"
          +(f" ANOMALY seeds={bad}" if bad else ""))
fp32=med.get("FP32",float('nan'))
print(f"\n{'Arm':<8}{'medBPB':>9}{'Δ vs FP32':>11}   (порог значимости 0.005)")
print("-"*40)
for arm_name,_ in ALL_ARMS:
    d=med[arm_name]-fp32
    print(f"{arm_name:<8}{med[arm_name]:>9.4f}{d:>+11.4f}"+("  <порог" if abs(d)<0.005 else ""))
remaining=[(a[0],s) for a in ALL_ARMS for s in SEEDS if f"{a[0]}/s{s}" not in results]
print(f"\nОСТАЛОСЬ ячеек: {len(remaining)} {remaining if remaining else '— ВСЁ ГОТОВО'}")
print("DONE")
