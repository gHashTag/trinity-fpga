#!/usr/bin/env python3
"""Combined: Train model + run GF+ adaptive format benchmark"""
import os, sys, json, math
import numpy as np

# Install deps
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

# Setup data
os.chdir("/workspace")
if not os.path.exists("parameter-golf"):
    os.system("git clone --depth 1 https://github.com/openai/parameter-golf.git")
os.chdir("/workspace/parameter-golf")
if not os.path.exists("data/datasets/fineweb10B_sp1024/fineweb_val_000000.bin"):
    os.system("python3 data/cached_challenge_fineweb.py --variant sp1024 --train-shards 1 2>&1 | tail -2")

# ═══ GF+ quantizer (inline from colleague's code) ═══
PHI2 = ((1 + 5**0.5) / 2) ** 2

def phi_split(N):
    e = round((N - 1) / PHI2); m = N - 1 - e
    bias = 2 ** (e - 1) - 1 if e > 0 else 0
    return e, m, bias

def minifloat_qd(x, e, m, bias):
    x = x.double()
    if e == 0:
        step = 2.0 ** (-m); mx = (2**m - 1) * step
        return torch.clamp(torch.round(x / step) * step, -mx, mx)
    EMIN = 1 - bias; EMAX = (1 << e) - 1 - bias
    MAXN = 2.0**EMAX * (2 - 2.0**-m)
    a = x.abs(); sgn = torch.sign(x)
    ex = torch.floor(torch.log2(torch.clamp(a, min=2.0 ** (EMIN - m - 1))))
    ex = torch.clamp(ex, min=EMIN, max=EMAX)
    step = torch.where(a < 2.0**EMIN, torch.full_like(a, 2.0 ** (EMIN - m)), 2.0 ** (ex - m))
    q = torch.round(a / step) * step; q = torch.clamp(q, max=MAXN)
    return sgn * q

def fmt_maxn(e, m, bias):
    """Max representable magnitude of the minifloat format."""
    if e == 0:
        return (2**m - 1) * 2.0 ** (-m)
    return 2.0 ** ((1 << e) - 1 - bias) * (2 - 2.0 ** -m)

def int_qd(x, bits):
    L = 2 ** (bits - 1) - 1
    return torch.round(torch.clamp(x, -1.0, 1.0) * L) / L

NF4_LEVELS = torch.tensor([-1.0,-0.6962,-0.5251,-0.3949,-0.2844,-0.1848,-0.0911,0.0,
    0.0796,0.1609,0.2461,0.3379,0.4407,0.5626,0.7230,1.0])

def nf4_qd(x):
    lv = NF4_LEVELS.to(x.dtype)
    idx = torch.argmin((x.unsqueeze(-1) - lv).abs(), dim=-1)
    return lv[idx]

def scaled_qd(w, kind, **kw):
    """Per-row absmax -> FULL-SCALE of the format -> quant -> dequant.
    v2 fix: floats are scaled so row absmax lands on the format's MAXN
    (not on 1.0) — otherwise the exponent range idles and every float
    pocket is unfairly crushed into the denormal region."""
    x = w.double()
    flat = x.dim() < 2
    if flat: x = x.view(1, -1)
    amax = x.abs().amax(dim=-1, keepdim=True).clamp(min=1e-12)
    if kind == "mf":
        e, m, b = kw["e"], kw["m"], kw["bias"]
        scale = amax / fmt_maxn(e, m, b)
        q = minifloat_qd(x / scale, e, m, b) * scale
    elif kind == "int":
        q = int_qd(x / amax, kw["bits"]) * amax
    elif kind == "nf4":
        q = nf4_qd(x / amax) * amax
    else:
        raise ValueError(kind)
    if flat: q = q.view(-1)
    return q.view(w.shape)

def get_pockets(N):
    """Return list of (name, kind, kwargs) for width N."""
    e_phi, m_phi, b_phi = phi_split(N)
    pockets = [(f"phi_e{e_phi}m{m_phi}", "mf", dict(e=e_phi, m=m_phi, bias=b_phi))]
    for e_test in range(max(0, e_phi-2), e_phi+3):
        m_test = N - 1 - e_test
        if m_test < 1 or e_test < 0: continue
        b_test = 2**(e_test-1)-1 if e_test > 0 else 0
        name = f"e{e_test}m{m_test}"
        if name not in [p[0] for p in pockets]:
            pockets.append((name, "mf", dict(e=e_test, m=m_test, bias=b_test)))
    pockets.append((f"int{N}", "int", dict(bits=N)))
    if N == 4:
        pockets.append(("nf4", "nf4", {}))
    return pockets

def adaptive_qd(w, pockets):
    """Per-row: pick pocket with lowest per-row MEAN squared error.
    v2 fix: selection metric == report metric (MSE). Selecting on amax
    (L-inf) while reporting MSE broke the 'adaptive >= best pocket'
    invariant. Each pocket applies its own full-scale factor."""
    x = w if w.dim() >= 2 else w.view(1, -1)
    best_mse = None; best_q = None; best_idx = None
    for k, (name, kind, kw) in enumerate(pockets):
        q = scaled_qd(x, kind, **kw)
        mse = ((q - x.double()) ** 2).mean(dim=-1)
        if best_mse is None:
            best_mse = mse; best_q = q
            best_idx = torch.zeros(x.size(0), dtype=torch.long)
        else:
            imp = mse < best_mse
            best_mse = torch.where(imp, mse, best_mse)
            best_q = torch.where(imp.unsqueeze(-1), q, best_q)
            best_idx = torch.where(imp, torch.full_like(best_idx, k), best_idx)
    names = [pockets[i][0] for i in best_idx.tolist()]
    return best_q.view(w.shape), names

# ═══ Train model ═══
device = 'cuda'
VOCAB=1024; D=512; NL=9; SEQ=1024; BATCH=48; STEPS=3000

val = np.memmap('data/datasets/fineweb10B_sp1024/fineweb_val_000000.bin', dtype=np.uint16, mode='r')
train_t = torch.tensor(val[:8000000].astype(np.int64))
val_t = torch.tensor(val[8000000:].astype(np.int64))

sp = spm.SentencePieceProcessor(model_file='data/tokenizers/fineweb_1024_bpe.model')
bb = torch.zeros(VOCAB, dtype=torch.int16); hs = torch.zeros(VOCAB, dtype=torch.bool); ib = torch.zeros(VOCAB, dtype=torch.bool)
for t in range(VOCAB):
    d = sp.decode([t])
    if d: bb[t] = len(d.encode('utf-8')); hs[t] = d[0]==' '
    if sp.is_unknown(t) or sp.is_control(t) or sp.is_byte(t): ib[t]=True; bb[t]=0

class Model(nn.Module):
    def __init__(s):
        super().__init__()
        s.e=nn.Embedding(VOCAB,D);s.p=nn.Embedding(SEQ,D)
        s.l=nn.ModuleList([nn.TransformerEncoderLayer(d_model=D,nhead=8,dim_feedforward=D*4,dropout=0.1,batch_first=True,activation='gelu',norm_first=True) for _ in range(NL)])
        s.f=nn.LayerNorm(D);s.h=nn.Linear(D,VOCAB,bias=False);s.h.weight=s.e.weight
    def forward(s,x):
        h=s.e(x)+s.p(torch.arange(x.size(1),device=x.device))
        for b in s.l:h=b(h)
        return s.h(s.f(h))

print(f"\nTraining {NL}L d={D} {STEPS} steps...")
torch.manual_seed(42);model=Model().to(device)
op=torch.optim.AdamW(model.parameters(),lr=0.003,weight_decay=0.1,betas=(0.95,0.95))
for s in range(STEPS+1):
    idx=torch.randint(0,len(train_t)-SEQ-1,(BATCH,))
    x=torch.stack([train_t[i:i+SEQ]for i in idx]).to(device)
    y=torch.stack([train_t[i+1:i+SEQ+1]for i in idx]).to(device)
    loss=F.cross_entropy(model(x).reshape(-1,VOCAB),y.reshape(-1))
    op.zero_grad();loss.backward()
    torch.nn.utils.clip_grad_norm_(model.parameters(),1.0);op.step()
    if s%1000==0: print(f"  {s}/{STEPS}: loss={loss.item():.4f}",flush=True)

try:
    torch.save(model.state_dict(), '/workspace/model_checkpoint.pt')
    print("checkpoint saved -> /workspace/model_checkpoint.pt")
except Exception as ex:
    print(f"checkpoint save skipped: {ex}")

# ═══ GF+ benchmark on REAL model weights ═══
print(f"\n{'='*65}")
print(f"GF+ ADAPTIVE FORMAT BENCHMARK ON REAL WEIGHTS")
print(f"Model: {NL}L d={D} | {sum(p.numel()for p in model.parameters()):,} params")
print(f"{'='*65}")

weights = {n: p.data.float().cpu() for n, p in model.named_parameters() if p.dim() >= 2 and p.numel() > 1000}

for width in [4, 6, 8]:
    pockets = get_pockets(width)
    print(f"\n--- {width}-bit ---")
    print(f"{'Format':<16}{'SQNR(dB)':>10}{'MSE':>12}")
    print("-"*40)
    
    # v2 fix: ONE aggregation for everybody — global sums (as GF+A below),
    # not avg-of-per-tensor SQNRs for pockets vs global for adaptive.
    all_sqnr = {}
    for name, kind, kw in pockets:
        tm = 0.0; ts = 0.0
        for wname, w in weights.items():
            q = scaled_qd(w, kind, **kw)
            tm += ((q - w.double())**2).sum().item()
            ts += (w.double()**2).sum().item()
        sqnr = 10 * math.log10(ts / max(tm, 1e-30))
        all_sqnr[name] = sqnr
        print(f"{name:<16}{sqnr:>10.2f}{tm/max(ts,1e-30):>12.2e}")
    
    # GF+A adaptive
    total_mse_a = 0; total_sig = 0
    pocket_counts = {p[0]: 0 for p in pockets}
    for wname, w in weights.items():
        q, names = adaptive_qd(w, pockets)
        total_mse_a += ((q - w.double())**2).sum().item()
        total_sig += (w.double()**2).sum().item()
        for n in names: pocket_counts[n] = pocket_counts.get(n, 0) + 1
    
    sqnr_a = 10 * math.log10(total_sig / max(total_mse_a, 1e-30))
    print(f"{'GF+A adaptive':<16}{sqnr_a:>10.2f}{'':>12} ★")
    print(f"  Pocket distribution: {dict(sorted(pocket_counts.items(), key=lambda x:-x[1])[:4])}")
    
    best_single = max(all_sqnr, key=all_sqnr.get)
    delta = sqnr_a - all_sqnr[best_single]
    print(f"  GF+A vs best single ({best_single}): {'+' if delta>=0 else ''}{delta:.2f} dB")

print(f"\nDONE")
