#!/usr/bin/env python3
"""W949: the mechanism was computed in a convention the experiment never used.

Every stability run in this project initialised the quantiser scale as s = max|x|,
so the tensor peak lands on grid value 1.0. The PUBLISHED mechanism -- "the narrow
grids zero everything below 1.67 % (e2m3) or 0.22 % (e3m2) of the tensor peak" --
is min/max of each grid, i.e. it assumes the peak lands on the grid's MAXIMUM,
which is the standard max-rule. The two differ enormously, because the grids have
maxima of 3072 (TNF4), 28 (e3m2) and 7.5 (e2m3).

Under what the rig actually did, TNF4 zeroes everything below 12.5 % of the peak
against e3m2's 6.25 %, and its usable alphabet shrinks from 57 values to 7 while
e3m2 keeps 12. TNF4 is HANDICAPPED under its own experiment and still trained 40/40.

So scale initialisation was never matched across formats, and the mismatch is
format-dependent by up to 400x. This runs both conventions, changing nothing else.

  peak2one : s = max|x|                 -- what every previous run did
  peak2max : s = max|x| / max(grid)     -- the standard max rule, matched
"""
import gzip, json, os, pathlib, sys, time
import numpy as np
import torch
import torch.nn as nn

S = pathlib.Path(os.environ.get("T27_WORK") or pathlib.Path(__file__).resolve().parent)
sys.path.insert(0, os.environ.get("T27_CONFORMANCE") or str(S / "oracles"))
import tnf_ref as T, fp8_ref as F8

SEEDS = [20260820, 7, 1337, 424242, 99991]
EPOCHS = int(os.environ.get("EPOCHS", "3"))
FMT = {"TNF4": (T, T.TNFFormat(2, 1), 6),
       "fp6e2m3": (F8, F8.FORMATS["fp6_e2m3"], 6),
       "fp6e3m2": (F8, F8.FORMATS["fp6_e3m2"], 6)}
OUT = S / f"scaleconv_w949_{EPOCHS}ep.json"


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


def snap(x, vals):
    i = torch.bucketize(x, vals).clamp(1, len(vals) - 1)
    lo, hi = vals[i - 1], vals[i]
    return torch.where((x - lo).abs() <= (hi - x).abs(), lo, hi)


class LSQ(torch.autograd.Function):
    @staticmethod
    def forward(ctx, x, s, vals):
        xs = x / s
        q = snap(xs, vals)
        ctx.save_for_backward(xs, q)
        ctx.g = 1.0 / max((x.numel() * max(float(vals.abs().max()), 1.0)) ** 0.5, 1.0)
        return q * s

    @staticmethod
    def backward(ctx, g):
        xs, q = ctx.saved_tensors
        return g, (g * (q - xs)).sum().reshape(1) * ctx.g, None


class QLinear(nn.Linear):
    vals = None
    denom = 1.0          # 1.0 => peak lands on grid 1.0; max(grid) => standard rule

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.ws = nn.Parameter(torch.ones(1))
        self.as_ = nn.Parameter(torch.ones(1))
        self._init = False

    def forward(self, x):
        if QLinear.vals is None:
            return nn.functional.linear(x, self.weight, self.bias)
        if not self._init:
            with torch.no_grad():
                d = QLinear.denom
                self.ws.fill_(max(float(self.weight.abs().max()) / d, 1e-8))
                self.as_.fill_(max(float(x.abs().max()) / d, 1e-8) if x.numel() else 1.0)
            self._init = True
        w = LSQ.apply(self.weight, self.ws.abs().clamp(min=1e-8), QLinear.vals)
        x = LSQ.apply(x, self.as_.abs().clamp(min=1e-8), QLinear.vals)
        return nn.functional.linear(x, w, self.bias)


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
    grids = {k: grid(*v) for k, v in FMT.items()}
    out = {"task": "mnist", "epochs": EPOCHS, "seeds": SEEDS,
           "note": "peak2one is the legacy convention used by every prior run",
           "grid_max": {k: float(g.max()) for k, g in grids.items()}, "runs": {}}
    for conv in ("peak2one", "peak2max"):
        for name, g in grids.items():
            QLinear.vals = g
            QLinear.denom = 1.0 if conv == "peak2one" else float(g.max())
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
                print(f"  {conv:9} {name:8} сид {seed:8}: {a:6.2f}%  ({time.time()-t0:.0f} с)", flush=True)
            out["runs"].setdefault(conv, {})[name] = accs
            fails = sum(1 for a in accs if a < 60.0)
            print(f"  -> {conv} {name}: отказов {fails}/5, среднее {np.mean(accs):.2f}", flush=True)
            OUT.write_text(json.dumps(out, indent=1))   # incremental: survives a kill
            QLinear.vals = None
    print("WROTE " + str(OUT), flush=True)


if __name__ == "__main__":
    main()
