#!/usr/bin/env python3
# W968: this rig bound the name TNF8 to TNFFormat(4, 3) -- 11 bits, 126.91 binades,
# which is TNF16's exponent field with a truncated mantissa and NOT the ladder's
# eighth rung. The ladder defines rung 8 as TNFFormat(3, 4): 10 bits, 30.95 binades.
# Corrected below. The records this rig produced are marked with _format_note and
# superseded by census_tnf8_w963.json and rung_w964_*.json.
"""W943: does the 4-bit result hold on a convolutional network?

Every accuracy claim in this project comes from MLPs. Convolutions change both the
weight distribution (fan-in per filter is small, so per-tensor scaling behaves
differently) and the sensitivity to dynamic range, and the LUT-DNN literature never
settles for one architecture. This runs the identical PTQ protocol on a small CNN.
"""
import gzip, json, pathlib, sys, time
import numpy as np
import torch
import torch.nn as nn

import os as _envos
SC = pathlib.Path(_envos.environ.get("T27_WORK") or pathlib.Path(__file__).resolve().parent)
sys.path.insert(0, _envos.environ.get("T27_CONFORMANCE") or str(SC / "oracles"))
import tnf_ref as T, gf_ref as G, posit_ref as P, fp8_ref as F8

SEEDS = [20260820, 7, 1337, 424242, 99991]
TASKS = {"mnist": SC / "mnist", "fashion": SC / "fashion"}
FORMATS = {
    "TNF4": (T, T.TNFFormat(2, 1), 6),
    "fp4e2m1": (F8, F8.FORMATS["fp4_e2m1"], 4),
    "GF4": (G, G.FORMATS["gf4"], 4),
    "TNF8": (T, T.TNFFormat(3, 4), 10),
    "fp8e4m3": (F8, F8.FORMATS["fp8_e4m3"], 8),
    "posit8": (P, P.FORMATS["posit8"], 8),
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
    arr = np.unique(np.array(sorted(set(vals)), dtype=np.float64))
    assert (arr < 0).any(), "value set has no negatives"
    return arr


def quantiser(vals):
    def q(x):
        flat = np.asarray(x, dtype=np.float64).ravel()
        i = np.clip(np.searchsorted(vals, flat), 1, len(vals) - 1)
        lo, hi = vals[i - 1], vals[i]
        return np.where(np.abs(flat - lo) <= np.abs(hi - flat), lo, hi).reshape(
            np.asarray(x).shape).astype(np.float32)
    return q


def idx(path, kind):
    raw = gzip.open(path, "rb").read()
    if kind == "img":
        n = int.from_bytes(raw[4:8], "big")
        return np.frombuffer(raw[16:], np.uint8).reshape(n, 1, 28, 28).astype(np.float32) / 255.0
    return np.frombuffer(raw[8:], np.uint8).astype(np.int64)


def make(seed):
    torch.manual_seed(seed)
    return nn.Sequential(
        nn.Conv2d(1, 16, 3, padding=1), nn.ReLU(), nn.MaxPool2d(2),
        nn.Conv2d(16, 32, 3, padding=1), nn.ReLU(), nn.MaxPool2d(2),
        nn.Flatten(), nn.Linear(32 * 7 * 7, 10))


def main():
    qs = {k: quantiser(value_set(*v)) for k, v in FORMATS.items()}
    out = {"arch": "conv16-conv32-fc10", "seeds": SEEDS,
           "quantisation": "weights-only PTQ, per-tensor max scale, activations fp32", "tasks": {}}
    for task, d in TASKS.items():
        Xtr, ytr = idx(d / "train-images-idx3-ubyte.gz", "img"), idx(d / "train-labels-idx1-ubyte.gz", "lab")
        Xte, yte = idx(d / "t10k-images-idx3-ubyte.gz", "img"), idx(d / "t10k-labels-idx1-ubyte.gz", "lab")
        Xv, yv = torch.from_numpy(Xte), torch.from_numpy(yte)
        per = {"baseline": [], "formats": {}}
        for seed in SEEDS:
            t0 = time.time()
            net = make(seed)
            opt = torch.optim.Adam(net.parameters(), lr=1e-3)
            lf = nn.CrossEntropyLoss()
            Xt, yt = torch.from_numpy(Xtr), torch.from_numpy(ytr)
            for _ in range(2):
                perm = torch.randperm(len(Xt))
                for i in range(0, len(Xt), 256):
                    b = perm[i:i + 256]
                    opt.zero_grad(); lf(net(Xt[b]), yt[b]).backward(); opt.step()
            with torch.no_grad():
                base = (net(Xv).argmax(1) == yv).float().mean().item()
            per["baseline"].append(base)
            W0 = [p.detach().numpy().copy() for p in net.parameters()]
            for name, q in qs.items():
                with torch.no_grad():
                    for p, w in zip(net.parameters(), W0):
                        s = float(np.max(np.abs(w))) or 1.0
                        p.copy_(torch.from_numpy(q(w / s) * s))
                    acc = (net(Xv).argmax(1) == yv).float().mean().item()
                    for p, w in zip(net.parameters(), W0):
                        p.copy_(torch.from_numpy(w))
                per["formats"].setdefault(name, []).append(acc)
            print(f"  {task} seed {seed}: base {base*100:.2f}%  ({time.time()-t0:.0f} с)", flush=True)
        out["tasks"][task] = per
        b = np.array(per["baseline"])
        print(f"\n  == {task} (CNN): база {b.mean()*100:.2f} ± {b.std(ddof=1)*100:.2f}", flush=True)
        for name in FORMATS:
            a = np.array(per["formats"][name])
            print(f"   {name:9} {a.mean()*100:6.2f} ± {a.std(ddof=1)*100:5.2f}   "
                  f"падение {(b-a).mean()*100:+7.2f} ± {(b-a).std(ddof=1)*100:5.2f} п.п.", flush=True)
    p = SC / "conv.json"
    p.write_text(json.dumps(out, indent=1))
    print("\nWROTE " + str(p), flush=True)


if __name__ == "__main__":
    main()
