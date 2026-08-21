#!/usr/bin/env python3
"""W951: redo the sweep under the computed scale, and OBSERVE saturation.

Two open items from W950, closed by one rig.

1. T799 says failures are saturation: the learned scale collapses until max|x|/s
   exceeds the top of the grid. That was INFERRED from logged scales -- the records
   never stored the tensor maxima, so agreement was 90.8 %, not a measurement. This
   logs max|x|/s divided by max(grid) per layer per epoch. A value above 1 IS
   saturation, observed.

2. The 40-run sweep used the learned scale everywhere -- the recipe W950 showed to
   be the cause of the failures. Until the three tasks are repeated under the
   computed scale, "TNF4 55/55" mostly describes our own defect.

SCALE_MODE=learned  : LSQ with the gradient factor, s initialised to max|x| (peak2one)
SCALE_MODE=computed : OCP-MX-style shared power-of-two per block, never learned
BLOCK=0 per-tensor, BLOCK=32 the OCP size.
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
TASK = os.environ.get("TASK", "mnist")
MODE = os.environ.get("SCALE_MODE", "computed")
BLOCK = int(os.environ.get("BLOCK", "0"))
TH = {"mnist": 60.0, "fashion": 60.0, "kmnist": 40.0}[TASK]
# W964: the ladder's eighth rung has a measured area (W963) and no measured accuracy.
# Every accuracy figure ever published for "TNF8" used TNFFormat(4, 3) -- 11 bits,
# 126.91 binades -- not the ladder's TNFFormat(3, 4) -- 10 bits, 30.95 binades. Both
# run here, with a float matched to the TRUE rung's width, so the substitution has an
# accuracy number as well as an area one.
_Fx = F8.FPxFormat
FMT = {"TNF8_true_10b": (T, T.TNFFormat(3, 4), 10),
       "TNF8_sub_11b": (T, T.TNFFormat(4, 3), 11),
       "fp10_e5m4": (F8, _Fx("fp10_e5m4", 5, 4, 15), 10)}
OUT = S / f"rung_w964_{TASK}_{MODE}_b{BLOCK}_{EPOCHS}ep.json"

SAT = {}          # layer -> max observed (max|x|/s)/gmax this epoch


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


def observe(tag, x, s, gmax):
    """Record (max|x|/s)/gmax. Above 1.0 means the tensor is clipped at the top."""
    with torch.no_grad():
        r = float(x.abs().max() / max(float(s), 1e-30) / gmax)
    if r > SAT.get(tag, 0.0):
        SAT[tag] = r


def mxq(x, g, gmax, block, tag):
    if block <= 0:
        m = x.abs().max().clamp(min=1e-30)
        s = torch.pow(2.0, torch.floor(torch.log2(m / gmax))).clamp(min=1e-30)
        observe(tag, x, s, gmax)
        q = snap(x / s, g) * s
        return x + (q - x).detach()
    shp = x.shape
    n = shp[-1]
    pad = (-n) % block
    xf = Fn.pad(x.reshape(-1, n), (0, pad)) if pad else x.reshape(-1, n)
    xb = xf.reshape(-1, block)
    m = xb.abs().amax(dim=1, keepdim=True).clamp(min=1e-30)
    s = torch.pow(2.0, torch.floor(torch.log2(m / gmax))).clamp(min=1e-30)
    with torch.no_grad():
        r = float((xb.abs() / s).max() / gmax)
    if r > SAT.get(tag, 0.0):
        SAT[tag] = r
    q = (snap(xb / s, g) * s).reshape(xf.shape)
    if pad:
        q = q[:, :n]
    return x + (q.reshape(shp) - x).detach()


class QLinear(nn.Linear):
    g = None
    gmax = 1.0

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.ws = nn.Parameter(torch.ones(1))
        self.as_ = nn.Parameter(torch.ones(1))
        self._init = False
        self.tag = ""

    def forward(self, x):
        if QLinear.g is None:
            return Fn.linear(x, self.weight, self.bias)
        if MODE == "computed":
            w = mxq(self.weight, QLinear.g, QLinear.gmax, BLOCK, self.tag + "w")
            x = mxq(x, QLinear.g, QLinear.gmax, BLOCK, self.tag + "a")
            return Fn.linear(x, w, self.bias)
        if not self._init:
            with torch.no_grad():
                self.ws.fill_(max(float(self.weight.abs().max()), 1e-8))
                self.as_.fill_(max(float(x.abs().max()), 1e-8) if x.numel() else 1.0)
            self._init = True
        sw = self.ws.abs().clamp(min=1e-8); sa = self.as_.abs().clamp(min=1e-8)
        observe(self.tag + "w", self.weight, sw, QLinear.gmax)
        observe(self.tag + "a", x, sa, QLinear.gmax)
        w = LSQ.apply(self.weight, sw, QLinear.g)
        x = LSQ.apply(x, sa, QLinear.g)
        return Fn.linear(x, w, self.bias)


def idx(p, kind):
    raw = gzip.open(p, "rb").read()
    if kind == "img":
        n = int.from_bytes(raw[4:8], "big")
        return np.frombuffer(raw[16:], np.uint8).reshape(n, 784).astype(np.float32) / 255.0
    return np.frombuffer(raw[8:], np.uint8).astype(np.int64)


def main():
    d = S / TASK
    Xt = torch.from_numpy(idx(d / "train-images-idx3-ubyte.gz", "img"))
    yt = torch.from_numpy(idx(d / "train-labels-idx1-ubyte.gz", "lab"))
    Xv = torch.from_numpy(idx(d / "t10k-images-idx3-ubyte.gz", "img"))
    yv = torch.from_numpy(idx(d / "t10k-labels-idx1-ubyte.gz", "lab"))
    assert len(Xt) == 60000 and len(Xv) == 10000, (len(Xt), len(Xv))
    grids = {k: grid(*v) for k, v in FMT.items()}
    out = {"task": TASK, "mode": MODE, "block": BLOCK, "epochs": EPOCHS,
           "seeds": SEEDS, "threshold": TH, "runs": {}}
    for name, g in grids.items():
        QLinear.g, QLinear.gmax = g, float(g.max())
        for seed in SEEDS:
            t0 = time.time()
            torch.manual_seed(seed)
            net = nn.Sequential(QLinear(784, 256), nn.ReLU(),
                                QLinear(256, 256), nn.ReLU(), QLinear(256, 10))
            for i, m in enumerate([m for m in net if isinstance(m, QLinear)]):
                m.tag = f"L{i+1}"
            opt = torch.optim.Adam(net.parameters(), lr=1e-3)
            lf = nn.CrossEntropyLoss()
            trace = []
            for ep in range(EPOCHS):
                SAT.clear()
                perm = torch.randperm(len(Xt))
                for i in range(0, len(Xt), 256):
                    b = perm[i:i + 256]
                    opt.zero_grad(); lf(net(Xt[b]), yt[b]).backward(); opt.step()
                with torch.no_grad():
                    acc = (net(Xv).argmax(1) == yv).float().mean().item() * 100
                trace.append({"epoch": ep + 1, "acc": round(acc, 2),
                              "sat": {k: round(v, 4) for k, v in sorted(SAT.items())}})
            out["runs"].setdefault(name, {})[str(seed)] = trace
            worst = max(max(t["sat"].values()) for t in trace)
            print(f"  {TASK:7} {MODE:8} b{BLOCK:<3} {name:8} сид {seed:8}: "
                  f"{trace[-1]['acc']:6.2f}%  насыщение x{worst:8.2f}  ({time.time()-t0:.0f} с)",
                  flush=True)
            try:
                OUT.write_text(json.dumps(out, indent=1))
            except OSError as e:
                print(f"  (запись не удалась: {e})", flush=True)
        f = sum(1 for tr in out["runs"][name].values() if tr[-1]["acc"] < TH)
        print(f"  -> {TASK} {MODE} b{BLOCK} {name}: отказов {f}/5", flush=True)
        QLinear.g = None
    print("WROTE " + str(OUT), flush=True)


if __name__ == "__main__":
    main()
