#!/usr/bin/env python3
"""GPU Format Benchmark — ALL formats including GF8 and ternary"""
import os, sys, json

# Step 1: ALWAYS install typing_extensions + correct PyTorch FIRST
print("Installing deps...")
os.system("pip3 install --upgrade typing_extensions -q 2>&1 | tail -1")
os.system("pip3 uninstall -y torch torchvision torchaudio 2>/dev/null")
os.system("pip3 install torch --pre --index-url https://download.pytorch.org/whl/nightly/cu128 -q 2>&1 | tail -3")
os.system("pip3 install --upgrade typing_extensions -q 2>&1 | tail -1")
os.system("pip3 install sentencepiece huggingface-hub -q 2>&1 | tail -1")

# Step 2: NOW import torch (fresh process not needed — packages are installed)
import torch
x = torch.randn(100,100).cuda()
test = (x@x).sum().item()
GPU = torch.cuda.get_device_name(0)
print(f"GPU: {GPU} | PyTorch: {torch.__version__} | test={test:.1f}")

# Setup
os.chdir("/workspace")
if not os.path.exists("parameter-golf"):
    os.system("git clone --depth 1 https://github.com/openai/parameter-golf.git")
os.chdir("/workspace/parameter-golf")
if not os.path.exists("data/datasets/fineweb10B_sp1024/fineweb_val_000000.bin"):
    os.system("python3 data/cached_challenge_fineweb.py --variant sp1024 --train-shards 1 2>&1 | tail -2")

import torch.nn as nn, torch.nn.functional as F
import numpy as np, math
import sentencepiece as spm

device = 'cuda'
VOCAB=1024; D=512; NL=9; SEQ=1024; BATCH=48; STEPS=3000

val = np.memmap('data/datasets/fineweb10B_sp1024/fineweb_val_000000.bin', dtype=np.uint16, mode='r')
train = torch.tensor(val[:8000000].astype(np.int64))
val_t = torch.tensor(val[8000000:].astype(np.int64))

sp = spm.SentencePieceProcessor(model_file='data/tokenizers/fineweb_1024_bpe.model')
bb = torch.zeros(VOCAB, dtype=torch.int16); hs = torch.zeros(VOCAB, dtype=torch.bool); ib = torch.zeros(VOCAB, dtype=torch.bool)
for t in range(VOCAB):
    d = sp.decode([t])
    if d: bb[t] = len(d.encode('utf-8')); hs[t] = d[0]==' '
    if sp.is_unknown(t) or sp.is_control(t) or sp.is_byte(t): ib[t]=True; bb[t]=0

class M(nn.Module):
    def __init__(s):
        super().__init__()
        s.e=nn.Embedding(VOCAB,D);s.p=nn.Embedding(SEQ,D)
        s.l=nn.ModuleList([nn.TransformerEncoderLayer(d_model=D,nhead=8,dim_feedforward=D*4,dropout=0.1,batch_first=True,activation='gelu',norm_first=True) for _ in range(NL)])
        s.f=nn.LayerNorm(D);s.h=nn.Linear(D,VOCAB,bias=False);s.h.weight=s.e.weight
    def forward(s,x):
        h=s.e(x)+s.p(torch.arange(x.size(1),device=x.device))
        for b in s.l:h=b(h)
        return s.h(s.f(h))

def q_gf(E,Mm):
    B=(1<<(E-1))-1;EM=(1<<E)-1;MV=2.**(1-B-Mm);ms=float(1<<Mm)
    def f(t):
        sg=torch.sign(t);a=torch.abs(t).clamp(min=MV);e=torch.floor(torch.log2(a));ff=a/(2.**e);ef=torch.clamp(e+B,1,EM-1)
        r=sg*(1+torch.round((ff-1)*ms)/ms)*(2.**(ef-B));return torch.where(torch.abs(t)<MV,torch.zeros_like(r),r)
    return f

def q_fp8_direct():
    def f(t): return t.to(torch.float8_e4m3fn).to(t.dtype)
    return f

def q_fp8_scaled():
    MX=448.0
    def f(t):
        if t.dim()<2: return t.to(torch.float8_e4m3fn).to(t.dtype)
        sc=(t.abs().amax(dim=-1,keepdim=True)/MX).clamp(min=1e-12)
        return (t/sc).to(torch.float8_e4m3fn).to(t.dtype)*sc
    return f

def q_gf8_direct():
    return q_gf(3,4)

def q_gf8_scaled():
    E,BIAS,Mm=3,3,4
    MX=(2.0**((1<<E)-1-BIAS))*(2.0-2.0**(-Mm))
    def f(t):
        if t.dim()<2: return q_gf(3,4)(t)
        sc=(t.abs().amax(dim=-1,keepdim=True)/MX).clamp(min=1e-12)
        ws=t/sc
        sg=torch.sign(ws);a=torch.abs(ws).clamp(min=2.0**(1-BIAS-Mm))
        e=torch.floor(torch.log2(a));ef=torch.clamp(e+BIAS,1,(1<<E)-1)
        ff=a/(2.**e)
        ms=float(1<<Mm)
        r=sg*(1+torch.round((ff-1)*ms)/ms)*(2.**(ef-BIAS))
        return torch.clamp(r,-MX,MX)*sc
    return f

def q_int(bits):
    lv=(1<<(bits-1))-1
    def f(t):
        mx=t.abs().max();return torch.round(t/(mx/lv)).clamp(-lv-1,lv)*(mx/lv) if mx>0 else t
    return f

def q_sq(bits,a=0.5):
    lv=(1<<(bits-1))-1
    def f(t):
        if t.dim()<2:return q_int(bits)(t)
        cm=t.abs().amax(dim=0,keepdim=True).clamp(min=1e-8);rm=t.abs().amax(dim=1,keepdim=True).clamp(min=1e-8)
        sc=(cm.pow(a)*rm.pow(1-a)).clamp(min=1e-8);sm=t/sc;mx=sm.abs().max()
        return torch.round(sm/(mx/lv)).clamp(-lv-1,lv)*(mx/lv)*sc if mx>0 else t
    return f

def q_ternary():
    def f(t):
        if t.dim()<2: return q_int(2)(t)
        sc=t.abs().mean(dim=-1,keepdim=True);th=0.7*sc
        r=torch.zeros_like(t);r[t>th]=1;r[t<-th]=-1;return r*sc
    return f

def ev(m,qf=None):
    m.eval()
    if qf:
        o={n:p.data.clone()for n,p in m.named_parameters()if p.dim()>=2}
        for n,p in m.named_parameters():
            if p.dim()>=2:p.data=qf(p.data)
    ls=0.;tk=0;by=0
    bl=bb.to(device);hp=hs.to(device);ip=ib.to(device)
    with torch.no_grad():
        for i in range(0,len(val_t)-SEQ-1,SEQ*4):
            x=val_t[i:i+SEQ].unsqueeze(0).to(device);y=val_t[i+1:i+SEQ+1].unsqueeze(0).to(device)
            if x.size(1)<SEQ:continue
            lg=m(x).reshape(-1,VOCAB);yt=y.reshape(-1)
            ls+=F.cross_entropy(lg,yt,reduction='sum').item();tk+=SEQ
            pv=x.reshape(-1);tb=bl[yt].sum().item();tb+=(hp[yt]&~ip[pv]).int().sum().item();by+=max(tb,1)
    if qf:
        for n,p in m.named_parameters():
            if n in o:p.data=o[n]
    m.train()
    return ls/tk/math.log(2)*tk/by

print(f"\nTraining {NL}L d={D} {STEPS} steps...")
torch.manual_seed(42);model=M().to(device)
op=torch.optim.AdamW(model.parameters(),lr=0.003,weight_decay=0.1,betas=(0.95,0.95))
for s in range(STEPS+1):
    idx=torch.randint(0,len(train)-SEQ-1,(BATCH,))
    x=torch.stack([train[i:i+SEQ]for i in idx]).to(device)
    y=torch.stack([train[i+1:i+SEQ+1]for i in idx]).to(device)
    loss=F.cross_entropy(model(x).reshape(-1,VOCAB),y.reshape(-1))
    op.zero_grad();loss.backward()
    torch.nn.utils.clip_grad_norm_(model.parameters(),1.0);op.step()
    if s%500==0:
        bpb=ev(model);print(f"  {s}/{STEPS}: loss={loss.item():.4f} bpb={bpb:.4f}",flush=True)

# Save model checkpoint for GF+ benchmark
torch.save(model.state_dict(), '/workspace/model_checkpoint.pt')
print("Checkpoint saved: /workspace/model_checkpoint.pt")

b=ev(model);P=sum(p.numel()for p in model.parameters())
print(f"\n{'='*70}")
print(f"COMPLETE FORMAT LEADERBOARD — {GPU}")
print(f"Model:{NL}L d={D} seq={SEQ}|{P:,}params|{STEPS}steps|FineWeb PTQ-proxy BPB")
print(f"{'='*70}")
print(f"\n{'Format':<16}{'Family':<8}{'bpe':>5}{'BPB':>9}{'Delta':>9}{'Status'}")
print("-"*60)
print(f"{'FP32':<16}{'FP':<8}{32:>5}{b:>9.4f}{'—':>9}master")
R={'FP32':b}
for nm,qf,w,fam in[
    ('FP16 E5M10',q_gf(5,10),16,'FP'),
    ('BF16 E8M7',q_gf(8,7),16,'FP'),
    ('GF14+ E5M8',q_gf(5,8),14,'GF'),
    ('GF16+ E6M9',q_gf(6,9),16,'GF'),
    ('GF20 E7M12',q_gf(7,12),20,'GF'),
    ('FP8 E4M3',q_fp8_direct(),8,'FP8'),
    ('FP8+S E4M3',q_fp8_scaled(),8,'FP8'),
    ('GF8 E3M4',q_gf8_direct(),8,'GF8'),
    ('GF8+S E3M4',q_gf8_scaled(),8,'GF8'),
    ('INT8',q_int(8),8,'INT'),
    ('INT7',q_int(7),7,'INT'),
    ('INT6',q_int(6),6,'INT'),
    ('SQ-INT7',q_sq(7),7,'SQ'),
    ('SQ-INT6',q_sq(6),6,'SQ'),
    ('Ternary',q_ternary(),1.58,'TRI'),
]:
    r=ev(model,qf);dl=r-b;R[nm]=r
    st='lossless'if abs(dl)<0.001 else('good'if abs(dl)<0.01 else('noisy'if abs(dl)<0.05 else'BAD'))
    star=' ★'if'GF8'in nm or'SQ'in nm else''
    print(f'{nm:<16}{fam:<8}{w:>5.1f}{r:>9.4f}{dl:>+9.4f} {st}{star}')

json.dump(R,open('/workspace/full_leaderboard.json','w'),indent=2)
print(f"\nSaved. DONE")
