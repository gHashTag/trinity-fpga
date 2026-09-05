#!/usr/bin/env python3
"""W944: does the residual 4-bit advantage survive a real QAT recipe?

W943 closed the PTQ gap 44x with the weakest possible QAT: straight-through, a
per-tensor max scale, no learning of the scale itself. A residual of +0.19 pp
(MNIST) and +0.89 (Fashion) remained, and the obvious objection is that the
residual is the recipe's, not the format's.

This adds the two things a real recipe has:
  * a LEARNED scale, trained by the LSQ gradient d(out)/ds = q(w/s) - w/s
    (straight-through on the round, product rule on the outer multiply), and
  * 4-BIT ACTIVATIONS, because that is where a real 4-bit deployment lives and
    every accuracy result here so far kept activations in fp32.

Three configurations, two formats (GF4 is bit-identical to fp4 e2m1 on every seed
of every previous run, so it is dropped), five seeds, two tasks.
"""
import gzip, json, pathlib, sys, time
import numpy as np
import torch
import torch.nn as nn

SC = pathlib.Path("/private/tmp/claude-501/-Users-playom-t27--claude-worktrees-igla-fpga-improvements-3f5e1a/"
                  "eeed4a0e-20e8-40f4-aa16-1ecfee4ad92d/scratchpad")
sys.path.insert(0, str(SC / "upstream-wt/conformance"))
import tnf_ref as T, fp8_ref as F8

SEEDS = [20260820, 7, 1337, 424242, 99991]
TASKS = {"mnist": SC / "mnist", "fashion": SC / "fashion"}
# W945: TNF4 is physically SIX bits (57 grid values); comparing it against a
# 4-bit fp4 grid (15 values) is a width mismatch, and on sparse activations that
# mismatch -- not the number system -- is what collapsed MNIST. The fair peers at
# six bits are fp6_e2m3 and fp6_e3m2, both shipped by the same oracle.
FORMATS = {"TNF4": (T, T.TNFFormat(2, 1), 6),
           "fp6e2m3": (F8, F8.FORMATS["fp6_e2m3"], 6),
           "fp6e3m2": (F8, F8.FORMATS["fp6_e3m2"], 6),
           "fp4e2m1": (F8, F8.FORMATS["fp4_e2m1"], 4)}
EPOCHS = 3


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
    assert (arr < 0).any(), "value set has no negatives"
    return torch.from_numpy(arr)


def snap(x, vals):
    i = torch.bucketize(x, vals).clamp(1, len(vals) - 1)
    lo, hi = vals[i - 1], vals[i]
    return torch.where((x - lo).abs() <= (hi - x).abs(), lo, hi)


class LSQ(torch.autograd.Function):
    """out = snap(x/s) * s, with the LSQ gradient for s."""
    @staticmethod
    def forward(ctx, x, s, vals):
        xs = x / s
        q = snap(xs, vals)
        ctx.save_for_backward(xs, q)
        return q * s

    @staticmethod
    def backward(ctx, g):
        xs, q = ctx.saved_tensors
        return g, (g * (q - xs)).sum().reshape(1), None


class QLinear(nn.Linear):
    vals = None
    act_vals = None

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
                self.ws.fill_(float(self.weight.abs().max().clamp(min=1e-8)))
                self.as_.fill_(float(x.abs().max().clamp(min=1e-8)) if x.numel() else 1.0)
            self._init = True
        w = LSQ.apply(self.weight, self.ws.abs().clamp(min=1e-8), QLinear.vals)
        if QLinear.act_vals is not None:
            x = LSQ.apply(x, self.as_.abs().clamp(min=1e-8), QLinear.act_vals)
        return nn.functional.linear(x, w, self.bias)


def idx(path, kind):
    raw = gzip.open(path, "rb").read()
    if kind == "img":
        n = int.from_bytes(raw[4:8], "big")
        return np.frombuffer(raw[16:], np.uint8).reshape(n, 784).astype(np.float32) / 255.0
    return np.frombuffer(raw[8:], np.uint8).astype(np.int64)


def run(Xtr, ytr, Xv, yv, seed, vals, act_vals):
    QLinear.vals, QLinear.act_vals = vals, act_vals
    torch.manual_seed(seed)
    net = nn.Sequential(QLinear(784, 256), nn.ReLU(), QLinear(256, 256), nn.ReLU(), QLinear(256, 10))
    opt = torch.optim.Adam(net.parameters(), lr=1e-3)
    lf = nn.CrossEntropyLoss()
    Xt, yt = torch.from_numpy(Xtr), torch.from_numpy(ytr)
    for _ in range(EPOCHS):
        perm = torch.randperm(len(Xt))
        for i in range(0, len(Xt), 256):
            b = perm[i:i + 256]
            opt.zero_grad(); lf(net(Xt[b]), yt[b]).backward(); opt.step()
    with torch.no_grad():
        acc = (net(Xv).argmax(1) == yv).float().mean().item()
    QLinear.vals = QLinear.act_vals = None
    return acc


def main():
    sets = {k: value_set(*v) for k, v in FORMATS.items()}
    out = {"arch": "784-256-256-10", "seeds": SEEDS, "epochs": EPOCHS,
           "configs": ["fp32", "qat_learned_scale", "qat_learned_scale_act4"], "tasks": {}}
    for task, d in TASKS.items():
        Xtr, ytr = idx(d / "train-images-idx3-ubyte.gz", "img"), idx(d / "train-labels-idx1-ubyte.gz", "lab")
        Xte, yte = idx(d / "t10k-images-idx3-ubyte.gz", "img"), idx(d / "t10k-labels-idx1-ubyte.gz", "lab")
        Xv, yv = torch.from_numpy(Xte), torch.from_numpy(yte)
        per = {"fp32": [], "w4": {}, "w4a4": {}}
        for seed in SEEDS:
            t0 = time.time()
            per["fp32"].append(run(Xtr, ytr, Xv, yv, seed, None, None))
            for name, vals in sets.items():
                per["w4"].setdefault(name, []).append(run(Xtr, ytr, Xv, yv, seed, vals, None))
                per["w4a4"].setdefault(name, []).append(run(Xtr, ytr, Xv, yv, seed, vals, vals))
            print(f"  {task} seed {seed}: {time.time()-t0:.0f} с", flush=True)
        out["tasks"][task] = per
        b = np.array(per["fp32"])
        print(f"\n  == {task}: fp32 {b.mean()*100:.2f} ± {b.std(ddof=1)*100:.2f}", flush=True)
        for key, lab in (("w4", "веса 4б"), ("w4a4", "веса+акт 4б")):
            for name in FORMATS:
                a = np.array(per[key][name])
                print(f"   {lab:12} {name:9} {a.mean()*100:6.2f} ± {a.std(ddof=1)*100:4.2f}  "
                      f"падение {(b-a).mean()*100:+6.2f}", flush=True)
            t = np.array(per[key]["TNF4"])
            for opp in ("fp6e2m3", "fp6e3m2", "fp4e2m1"):
                f = np.array(per[key][opp]); dd = (t - f) * 100
                se = dd.std(ddof=1) / np.sqrt(len(dd))
                print(f"   {lab:12} ПАРНО TNF4−{opp}: {dd.mean():+7.2f} ± {se:5.2f} п.п., "
                      f"t={dd.mean()/se if se else float('inf'):6.1f}, {int((dd>0).sum())}/5", flush=True)
    p = SC / "lsq6.json"
    p.write_text(json.dumps(out, indent=1))
    print("\nWROTE " + str(p), flush=True)


if __name__ == "__main__":
    main()
