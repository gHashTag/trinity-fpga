#!/usr/bin/env python3
"""Real trained activations, not Gaussians pushed through an activation function.

Every measurement in this directory so far used x ~ N(0,1) fed to SiLU/GELU. That
assumes the input distribution rather than observing it, and it cannot produce the
per-channel outliers that training creates and that dominate 4-bit quantisation.

This trains a small SwiGLU transformer on a structured task and captures the
tensors an inference engine would actually quantise.
"""
import math

import torch
import torch.nn as nn

torch.manual_seed(20260809)
D, H, L, V, T = 128, 4, 3, 256, 64


class SwiGLU(nn.Module):
    def __init__(self, d, hidden):
        super().__init__()
        self.w1 = nn.Linear(d, hidden, bias=False)
        self.w3 = nn.Linear(d, hidden, bias=False)
        self.w2 = nn.Linear(hidden, d, bias=False)

    def forward(self, x):
        self.gate = torch.nn.functional.silu(self.w1(x))   # captured: post-SiLU
        self.hidden = self.gate * self.w3(x)               # captured: SwiGLU output
        return self.w2(self.hidden)


class Block(nn.Module):
    def __init__(self):
        super().__init__()
        self.n1, self.n2 = nn.LayerNorm(D), nn.LayerNorm(D)
        self.att = nn.MultiheadAttention(D, H, batch_first=True)
        self.mlp = SwiGLU(D, 4 * D)

    def forward(self, x):
        self.ln1 = self.n1(x)                              # captured: attn input
        a, _ = self.att(self.ln1, self.ln1, self.ln1, need_weights=False)
        x = x + a
        self.ln2 = self.n2(x)                              # captured: mlp input
        return x + self.mlp(self.ln2)


class Model(nn.Module):
    def __init__(self):
        super().__init__()
        self.emb = nn.Embedding(V, D)
        self.blocks = nn.ModuleList(Block() for _ in range(L))
        self.head = nn.Linear(D, V, bias=False)

    def forward(self, idx):
        x = self.emb(idx)
        for b in self.blocks:
            x = b(x)
        return self.head(x)


def batch(n=32):
    """Structured task: predict a shifted, modular-mixed sequence. Not language,
    but it forces the model to learn channel structure rather than memorise noise."""
    idx = torch.randint(0, V, (n, T))
    tgt = (idx * 7 + 13) % V
    return idx, tgt


def train(steps=400):
    m = Model()
    opt = torch.optim.AdamW(m.parameters(), lr=3e-3)
    lossf = nn.CrossEntropyLoss()
    for i in range(steps):
        idx, tgt = batch()
        loss = lossf(m(idx).reshape(-1, V), tgt.reshape(-1))
        opt.zero_grad()
        loss.backward()
        opt.step()
    return m, loss.item()


def capture(m):
    """One forward pass; return the tensors an engine quantises, by name."""
    with torch.no_grad():
        m(batch(16)[0])
    out = {}
    for i, b in enumerate(m.blocks):
        out[f"L{i}.attn_input(postLN)"] = b.ln1.flatten().tolist()
        out[f"L{i}.mlp_input(postLN)"] = b.ln2.flatten().tolist()
        out[f"L{i}.silu_gate"] = b.mlp.gate.flatten().tolist()
        out[f"L{i}.swiglu_hidden"] = b.mlp.hidden.flatten().tolist()
        out[f"L{i}.w2.weight"] = b.mlp.w2.weight.flatten().tolist()
    return out


if __name__ == "__main__":
    m, loss = train()
    print(f"обучено, финальный loss = {loss:.4f}  (случайный уровень = {math.log(V):.4f})")
    acts = capture(m)
    print(f"\n{'тензор':26s}{'значений':>10s}{'доля<0':>9s}{'энергия<0':>11s}{'выброс канала':>15s}")
    for name, v in acts.items():
        if not name.startswith(("L0", "L2")):
            continue
        n = len(v)
        fr = sum(1 for x in v if x < 0) / n
        en = sum(x * x for x in v if x < 0) / max(1e-30, sum(x * x for x in v))
        srt = sorted(abs(x) for x in v)
        ratio = srt[-1] / max(1e-30, srt[len(srt) // 2])
        print(f"{name:26s}{n:10d}{fr:8.1%}{en:11.1%}{ratio:14.0f}x")
