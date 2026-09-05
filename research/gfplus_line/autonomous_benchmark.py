#!/usr/bin/env python3
"""
Autonomous GPU benchmark — runs on RunPod, pushes results to GitHub.

Usage (in RunPod Web Terminal or dockerArgs):
  curl -s https://raw.githubusercontent.com/gHashTag/trinity-fpga/main/autonomous_benchmark.py | python3

This script:
1. Installs PyTorch (cu128 for Blackwell, cu124 for H100)
2. Trains a model on FineWeb
3. Evaluates ALL formats with official BPB
4. Pushes results to GitHub as a Gist
"""
import subprocess, sys, os, json, platform

def sh(cmd):
    return os.system(cmd)

# Detect GPU and install correct PyTorch
import torch
if not torch.cuda.is_available():
    print("Installing PyTorch...")
    sh("pip3 install torch --pre --index-url https://download.pytorch.org/whl/nightly/cu128 -q")
    import importlib; importlib.reload(torch)

try:
    x = torch.randn(10,10).cuda()
    assert (x@x).sum() != 0
    GPU = torch.cuda.get_device_name(0)
    print(f"GPU: {GPU} | PyTorch: {torch.__version__}")
except:
    print("Installing cu128...")
    sh("pip3 uninstall -y torch torchvision torchaudio 2>/dev/null")
    sh("pip3 install torch --pre --index-url https://download.pytorch.org/whl/nightly/cu128 -q 2>&1 | tail -3")
    import importlib; importlib.reload(torch)
    GPU = torch.cuda.get_device_name(0)
    print(f"GPU: {GPU} | PyTorch: {torch.__version__}")

sh("pip3 install sentencepiece huggingface-hub -q 2>&1 | tail -1")

# Setup
os.chdir("/workspace")
if not os.path.exists("parameter-golf"):
    sh("git clone --depth 1 https://github.com/openai/parameter-golf.git")
os.chdir("/workspace/parameter-golf")
if not os.path.exists("data/datasets/fineweb10B_sp1024/fineweb_val_000000.bin"):
    sh("python3 data/cached_challenge_fineweb.py --variant sp1024 --train-shards 1 2>&1 | tail -2")

# Import everything
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

def qg(E,Mm):
    B=(1<<(E-1))-1;EM=(1<<E)-1;MV=2.**(1-B-Mm);ms=float(1<<Mm)
    def f(t):
        sg=torch.sign(t);a=torch.abs(t).clamp(min=MV);e=torch.floor(torch.log2(a));ff=a/(2.**e);ef=torch.clamp(e+B,1,EM-1)
        r=sg*(1+torch.round((ff-1)*ms)/ms)*(2.**(ef-B));return torch.where(torch.abs(t)<MV,torch.zeros_like(r),r)
    return f
def qi(b):
    lv=(1<<(b-1))-1
    def f(t):
        mx=t.abs().max();return torch.round(t/(mx/lv)).clamp(-lv-1,lv)*(mx/lv) if mx>0 else t
    return f
def qs(b,a=0.5):
    lv=(1<<(b-1))-1
    def f(t):
        if t.dim()<2:return qi(b)(t)
        cm=t.abs().amax(dim=0,keepdim=True).clamp(min=1e-8);rm=t.abs().amax(dim=1,keepdim=True).clamp(min=1e-8)
        sc=(cm.pow(a)*rm.pow(1-a)).clamp(min=1e-8);sm=t/sc;mx=sm.abs().max()
        return torch.round(sm/(mx/lv)).clamp(-lv-1,lv)*(mx/lv)*sc if mx>0 else t
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

print(f"\nTraining {NL}L d={D} {STEPS} steps on {GPU}...")
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

b=ev(model);P=sum(p.numel()for p in model.parameters())
print(f"\n{'='*65}")
print(f"FORMAT LEADERBOARD — {GPU}")
print(f"Model:{NL}L d={D} seq={SEQ}|{P:,}params|{STEPS}steps|FineWeb")
print(f"{'='*65}")
print(f"\n{'Format':<12}{'Fam':<5}{'bpe':>4}{'BPB':>9}{'Delta':>9}{'Status'}")
print("-"*55)
print(f"{'FP32':<12}{'FP':<5}{32:>4}{b:>9.4f}{'—':>9}master")
R={'FP32':b,'meta':{'gpu':GPU,'model':f'{NL}L d={D}','params':P,'steps':STEPS}}
for nm,qf,w,fam in[
    ('FP16',qg(5,10),16,'FP'),('BF16',qg(8,7),16,'FP'),
    ('GF14+',qg(5,8),14,'GF'),('GF16+',qg(6,9),16,'GF'),('GF20',qg(7,12),20,'GF'),('GF24',qg(9,14),24,'GF'),
    ('INT8',qi(8),8,'INT'),('INT7',qi(7),7,'INT'),('INT6',qi(6),6,'INT'),
    ('SQ-INT7',qs(7),7,'SQ'),('SQ-INT6',qs(6),6,'SQ'),
]:
    r=ev(model,qf);dl=r-b;R[nm]=r
    st='lossless'if abs(dl)<0.001 else('good'if abs(dl)<0.01 else'noisy')
    star=' ★'if'SQ'in nm else''
    print(f'{nm:<12}{fam:<5}{w:>4}{r:>9.4f}{dl:>+9.4f} {st}{star}')

# PUSH RESULTS TO GITHUB (autonomous reporting)
print("\n=== Pushing results to GitHub ===")
results_json = json.dumps(R, indent=2)
sh(f'''cd /workspace && git clone https://ghashtag:{os.environ.get("GH_TOKEN","")}@github.com/gHashTag/trinity-fpga.git repo 2>/dev/null || true''')
os.makedirs("/workspace/repo/data", exist_ok=True)
with open("/workspace/repo/data/gpu_benchmark_results.json","w") as f:
    f.write(results_json)
sh("cd /workspace/repo && git add data/gpu_benchmark_results.json && git commit -m 'auto: GPU benchmark results' && git push 2>&1 | tail -2")
print("\nDONE — results pushed to GitHub")
