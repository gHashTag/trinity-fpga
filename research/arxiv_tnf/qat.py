#!/usr/bin/env python3
"""W943: does the 4-bit advantage survive quantisation-aware training?

Every accuracy result here is post-training quantisation without retraining -- the
weakest setting for the weaker format. The standing objection is that QAT closes
the gap: a network trained through the quantiser learns weights that live on the
grid, and a coarse grid stops being a handicap.

Straight-through estimator: quantise in the forward pass through the format's own
value set (enumerated from the shipped oracle), pass gradients unchanged. Per-tensor
max scale, recomputed each step. Same five seeds, same two tasks, same architecture
as the PTQ runs, so the two are directly comparable.
"""
import gzip, json, pathlib, sys, time
import numpy as np
import torch
import torch.nn as nn

import os as _envos
SC = pathlib.Path(_envos.environ.get("T27_WORK") or pathlib.Path(__file__).resolve().parent)
sys.path.insert(0, _envos.environ.get("T27_CONFORMANCE") or str(SC / "oracles"))
import tnf_ref as T, gf_ref as G, fp8_ref as F8

SEEDS = [20260820, 7, 1337, 424242, 99991]
TASKS = {"mnist": SC / "mnist", "fashion": SC / "fashion"}
FORMATS = {
    "TNF4": (T, T.TNFFormat(2, 1), 6),
    "fp4e2m1": (F8, F8.FORMATS["fp4_e2m1"], 4),
    "GF4": (G, G.FORMATS["gf4"], 4),
}


def value_set(mod, fmt, bits):
    vals = []
    for code in range(1 << bits):
        try:
            v = float(mod.decode(fmt, code))
        except Exception:
            continue
        if np.isfinite(v):
            vals.append(v)
    arr = np.unique(np.array(sorted(set(vals)), dtype=np.float32))
    assert (arr < 0).any(), "value set has no negatives: the sign bit was not enumerated"
    return torch.from_numpy(arr)


class QuantSTE(torch.autograd.Function):
    @staticmethod
    def forward(ctx, x, vals):
        idx = torch.bucketize(x.detach(), vals).clamp(1, len(vals) - 1)
        lo, hi = vals[idx - 1], vals[idx]
        return torch.where((x - lo).abs() <= (hi - x).abs(), lo, hi)

    @staticmethod
    def backward(ctx, g):
        return g, None


class QLinear(nn.Linear):
    """Linear whose weights are quantised in the forward pass, per-tensor scaled."""
    vals = None

    def forward(self, x):
        w = self.weight
        if QLinear.vals is None:
            return nn.functional.linear(x, w, self.bias)
        s = w.detach().abs().max().clamp(min=1e-12)
        wq = QuantSTE.apply(w / s, QLinear.vals) * s
        return nn.functional.linear(x, wq, self.bias)


def idx(path, kind):
    raw = gzip.open(path, "rb").read()
    if kind == "img":
        n = int.from_bytes(raw[4:8], "big")
        return np.frombuffer(raw[16:], np.uint8).reshape(n, 784).astype(np.float32) / 255.0
    return np.frombuffer(raw[8:], np.uint8).astype(np.int64)


def net_of(seed, H=256):
    torch.manual_seed(seed)
    return nn.Sequential(QLinear(784, H), nn.ReLU(), QLinear(H, H), nn.ReLU(), QLinear(H, 10))


def run(Xtr, ytr, Xv, yv, seed, vals):
    QLinear.vals = vals
    net = net_of(seed)
    opt = torch.optim.Adam(net.parameters(), lr=1e-3)
    lf = nn.CrossEntropyLoss()
    Xt, yt = torch.from_numpy(Xtr), torch.from_numpy(ytr)
    for _ in range(4):
        perm = torch.randperm(len(Xt))
        for i in range(0, len(Xt), 256):
            b = perm[i:i + 256]
            opt.zero_grad(); lf(net(Xt[b]), yt[b]).backward(); opt.step()
    with torch.no_grad():
        acc = (net(Xv).argmax(1) == yv).float().mean().item()
    QLinear.vals = None
    return acc


def main():
    sets = {k: value_set(*v) for k, v in FORMATS.items()}
    for k, v in sets.items():
        print(f"  {k:8}: {len(v)} значений в сетке", flush=True)
    out = {"arch": "784-256-256-10", "seeds": SEEDS, "method": "QAT, straight-through, per-tensor max scale",
           "epochs": 4, "tasks": {}}
    for task, d in TASKS.items():
        Xtr, ytr = idx(d / "train-images-idx3-ubyte.gz", "img"), idx(d / "train-labels-idx1-ubyte.gz", "lab")
        Xte, yte = idx(d / "t10k-images-idx3-ubyte.gz", "img"), idx(d / "t10k-labels-idx1-ubyte.gz", "lab")
        Xv, yv = torch.from_numpy(Xte), torch.from_numpy(yte)
        per = {"fp32": [], "qat": {}}
        for seed in SEEDS:
            t0 = time.time()
            per["fp32"].append(run(Xtr, ytr, Xv, yv, seed, None))
            for name, vals in sets.items():
                per["qat"].setdefault(name, []).append(run(Xtr, ytr, Xv, yv, seed, vals))
            print(f"  {task} seed {seed}: {time.time()-t0:.0f} с", flush=True)
        out["tasks"][task] = per
        b = np.array(per["fp32"])
        print(f"\n  == {task}: fp32 {b.mean()*100:.2f} ± {b.std(ddof=1)*100:.2f}", flush=True)
        for name in FORMATS:
            a = np.array(per["qat"][name])
            print(f"   {name:9} QAT {a.mean()*100:6.2f} ± {a.std(ddof=1)*100:4.2f}   "
                  f"падение {(b-a).mean()*100:+6.2f} ± {(b-a).std(ddof=1)*100:4.2f} п.п.", flush=True)
    p = SC / "qat.json"
    p.write_text(json.dumps(out, indent=1))
    print("\nWROTE " + str(p), flush=True)


if __name__ == "__main__":
    main()
