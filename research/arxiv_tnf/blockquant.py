#!/usr/bin/env python3
"""W950: the experiment that can kill this project's surviving claim.

W949 measured, on enumerated grids alone, that a shared scale per 32 elements
removes most of the dynamic range a format has to span -- and that at that block
size TNF4's relative RMS error is 3.46x WORSE than fp6 e2m3's. If the stability
advantage came from range, block scaling should erase it: fp6 e2m3 should stop
failing.

No training run in this project had ever used a block scale. This one does, in the
OCP microscaling style rather than ours:

  * block of 32 elements along the feature axis, weights AND activations;
  * shared scale is a POWER OF TWO computed per block per forward pass, not learned
    -- s = 2^floor(log2(max|block| / max(grid))), which is what MX specifies;
  * straight-through estimator; no LSQ, because there is no scale parameter left.

Control arm: the same rig with the block spanning the whole tensor, which isolates
the block size as the only variable.
"""
import gzip, json, os, pathlib, sys, time
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as Fn

S = pathlib.Path(os.environ.get("T27_WORK") or pathlib.Path(__file__).resolve().parent)
sys.path.insert(0, os.environ.get("T27_CONFORMANCE") or str(S / "oracles"))
import tnf_ref as T, fp8_ref as F8

SEEDS = [20260820, 7, 1337, 424242, 99991]
EPOCHS = int(os.environ.get("EPOCHS", "3"))
BLOCKS = [int(b) for b in os.environ.get("BLOCKS", "32,0").split(",")]  # 0 = per-tensor
FMT = {"TNF4": (T, T.TNFFormat(2, 1), 6),
       "fp6e2m3": (F8, F8.FORMATS["fp6_e2m3"], 6),
       "fp6e3m2": (F8, F8.FORMATS["fp6_e3m2"], 6)}
OUT = S / f"blockquant_w950_{EPOCHS}ep.json"


def grid(mod, fmt, bits):
    v = []
    for c in range(1 << bits):
        try:
            x = float(mod.decode(fmt, c))
        except Exception:
            continue
        if np.isfinite(x):
            v.append(x)
    a = np.unique(np.array(sorted(set(v)), dtype=np.float32))
    assert (a < 0).any()
    return torch.from_numpy(a)


def snap(x, g):
    i = torch.bucketize(x, g).clamp(1, len(g) - 1)
    lo, hi = g[i - 1], g[i]
    return torch.where((x - lo).abs() <= (hi - x).abs(), lo, hi)


def mxq(x, g, gmax, block):
    """MX-style: shared power-of-two scale per block, straight-through."""
    if block <= 0:
        m = x.abs().max().clamp(min=1e-30)
        s = torch.pow(2.0, torch.floor(torch.log2(m / gmax))).clamp(min=1e-30)
        q = snap(x / s, g) * s
        return x + (q - x).detach()
    shp = x.shape
    n = shp[-1]
    pad = (-n) % block
    xf = Fn.pad(x.reshape(-1, n), (0, pad)) if pad else x.reshape(-1, n)
    xb = xf.reshape(-1, block)
    m = xb.abs().amax(dim=1, keepdim=True).clamp(min=1e-30)
    s = torch.pow(2.0, torch.floor(torch.log2(m / gmax))).clamp(min=1e-30)
    q = snap(xb / s, g) * s
    q = q.reshape(xf.shape)
    if pad:
        q = q[:, :n]
    q = q.reshape(shp)
    return x + (q - x).detach()


class QLinear(nn.Linear):
    g = None
    gmax = 1.0
    block = 32

    def forward(self, x):
        if QLinear.g is None:
            return Fn.linear(x, self.weight, self.bias)
        w = mxq(self.weight, QLinear.g, QLinear.gmax, QLinear.block)
        x = mxq(x, QLinear.g, QLinear.gmax, QLinear.block)
        return Fn.linear(x, w, self.bias)


def idx(p, kind):
    raw = gzip.open(p, "rb").read()
    if kind == "img":
        n = int.from_bytes(raw[4:8], "big")
        return np.frombuffer(raw[16:], np.uint8).reshape(n, 784).astype(np.float32) / 255.0
    return np.frombuffer(raw[8:], np.uint8).astype(np.int64)


def main():
    d = S / "mnist"
    Xt = torch.from_numpy(idx(d / "train-images-idx3-ubyte.gz", "img"))
    yt = torch.from_numpy(idx(d / "train-labels-idx1-ubyte.gz", "lab"))
    Xv = torch.from_numpy(idx(d / "t10k-images-idx3-ubyte.gz", "img"))
    yv = torch.from_numpy(idx(d / "t10k-labels-idx1-ubyte.gz", "lab"))
    assert len(Xt) == 60000 and len(Xv) == 10000, (len(Xt), len(Xv))
    grids = {k: grid(*v) for k, v in FMT.items()}
    out = {"task": "mnist", "epochs": EPOCHS, "seeds": SEEDS, "blocks": BLOCKS,
           "scheme": "OCP-MX-style: shared power-of-two scale per block, STE, not learned",
           "runs": {}}
    for block in BLOCKS:
        key = "per_tensor" if block <= 0 else f"block{block}"
        for name, g in grids.items():
            QLinear.g, QLinear.gmax, QLinear.block = g, float(g.max()), block
            accs = []
            for seed in SEEDS:
                t0 = time.time()
                torch.manual_seed(seed)
                net = nn.Sequential(QLinear(784, 256), nn.ReLU(),
                                    QLinear(256, 256), nn.ReLU(), QLinear(256, 10))
                opt = torch.optim.Adam(net.parameters(), lr=1e-3)
                lf = nn.CrossEntropyLoss()
                for _ in range(EPOCHS):
                    perm = torch.randperm(len(Xt))
                    for i in range(0, len(Xt), 256):
                        b = perm[i:i + 256]
                        opt.zero_grad(); lf(net(Xt[b]), yt[b]).backward(); opt.step()
                with torch.no_grad():
                    a = (net(Xv).argmax(1) == yv).float().mean().item() * 100
                accs.append(round(a, 2))
                print(f"  {key:10} {name:8} сид {seed:8}: {a:6.2f}%  ({time.time()-t0:.0f} с)", flush=True)
            out["runs"].setdefault(key, {})[name] = accs
            print(f"  -> {key} {name}: отказов {sum(1 for a in accs if a < 60.0)}/5, "
                  f"среднее {np.mean(accs):.2f}", flush=True)
            # W950: the first run of this rig died of ENOSPC on its own progress
            # write, throwing away five completed runs. A checkpoint that can kill
            # the experiment is worse than no checkpoint -- the console log is a
            # record too, and it is what the results are reconstructed from here.
            try:
                OUT.write_text(json.dumps(out, indent=1))
            except OSError as e:
                print(f"  (запись записи не удалась: {e}; лог остаётся записью)", flush=True)
            QLinear.g = None
    print("WROTE " + str(OUT), flush=True)


if __name__ == "__main__":
    main()
