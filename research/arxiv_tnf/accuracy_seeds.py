#!/usr/bin/env python3
# W968: this rig bound the name TNF8 to TNFFormat(4, 3) -- 11 bits, 126.91 binades,
# which is TNF16's exponent field with a truncated mantissa and NOT the ladder's
# eighth rung. The ladder defines rung 8 as TNFFormat(3, 4): 10 bits, 30.95 binades.
# Corrected below. The records this rig produced are marked with _format_note and
# superseded by census_tnf8_w963.json and rung_w964_*.json.
"""W939: make the 4-bit result admissible -- five seeds, two tasks, error bars.

W938 produced one seed on one split, and the LUT-DNN literature does not accept
that: NeuraLUT reports 10-seed ablations, LUTNet plots min/mean/max over five,
SparseLUT retrains every baseline. The binomial floor on a 10,000-image test set
at p ~ 0.93 is 0.248 pp, so only the 4-bit separation (5.49 pp) ever cleared it --
and it cleared it on a single draw.

This runs five seeds on MNIST and on Fashion-MNIST (same shape, materially harder),
reports mean +- sample std across seeds, and states which differences survive.
"""
import gzip, json, pathlib, sys, time
import numpy as np
import torch
import torch.nn as nn

SC = pathlib.Path("/private/tmp/claude-501/-Users-playom-t27--claude-worktrees-igla-fpga-improvements-3f5e1a/"
                  "eeed4a0e-20e8-40f4-aa16-1ecfee4ad92d/scratchpad")
sys.path.insert(0, str(SC / "upstream-wt/conformance"))
import tnf_ref as T, gf_ref as G, takum_ref as K, posit_ref as P, bf16_ref as B, fp8_ref as F8

SEEDS = [20260820, 7, 1337, 424242, 99991]
TASKS = {"mnist": SC / "mnist", "fashion": SC / "fashion"}


def rt(mod, fmt):
    def f(v):
        try:
            x = float(mod.decode(fmt, mod.encode(fmt, float(v))))
            return x if np.isfinite(x) else 0.0
        except Exception:
            return 0.0
    return f


BANKS = {
    16: {"TNF16": rt(T, T.TNFFormat(4, 11)), "GF16": rt(G, G.FORMATS["gf16"]),
         "takum16": rt(K, K.TakumFormat("takum16", 16)), "posit16": rt(P, P.FORMATS["posit16"]),
         "bfloat16": rt(B, B.FORMATS["bfloat16"]), "binary16": lambda v: float(np.float16(v))},
    8: {"TNF8": rt(T, T.TNFFormat(3, 4)), "GF8": rt(G, G.FORMATS["gf8"]),
        "posit8": rt(P, P.FORMATS["posit8"]), "fp8e4m3": rt(F8, F8.FORMATS["fp8_e4m3"]),
        "fp8e5m2": rt(F8, F8.FORMATS["fp8_e5m2"])},
    4: {"TNF4": rt(T, T.TNFFormat(2, 1)), "GF4": rt(G, G.FORMATS["gf4"]),
        "fp4e2m1": rt(F8, F8.FORMATS["fp4_e2m1"])},
}


def idx(path, kind):
    raw = gzip.open(path, "rb").read()
    if kind == "img":
        n = int.from_bytes(raw[4:8], "big")
        return np.frombuffer(raw[16:], np.uint8).reshape(n, 784).astype(np.float32) / 255.0
    return np.frombuffer(raw[8:], np.uint8).astype(np.int64)


def train(Xtr, ytr, seed):
    torch.manual_seed(seed)
    H = int(__import__("os").environ.get("HID", "32"))
    net = nn.Sequential(nn.Linear(784, H), nn.ReLU(), nn.Linear(H, H), nn.ReLU(), nn.Linear(H, 10)) if H > 32 else nn.Sequential(nn.Linear(784, H), nn.ReLU(), nn.Linear(H, 10))
    opt = torch.optim.Adam(net.parameters(), lr=1e-3)
    lf = nn.CrossEntropyLoss()
    Xt, yt = torch.from_numpy(Xtr), torch.from_numpy(ytr)
    for _ in range(4):
        perm = torch.randperm(len(Xt))
        for i in range(0, len(Xt), 256):
            b = perm[i:i + 256]
            opt.zero_grad(); lf(net(Xt[b]), yt[b]).backward(); opt.step()
    return net


def main():
    out = {"seeds": SEEDS, "epochs": 4, "arch": __import__("os").environ.get("ARCH", "784-32-10"),
           "quantisation": "weights-only PTQ with per-tensor max scale; activations fp32",
           "test_set_size": 10000, "tasks": {}}
    for task, d in TASKS.items():
        Xtr, ytr = idx(d / "train-images-idx3-ubyte.gz", "img"), idx(d / "train-labels-idx1-ubyte.gz", "lab")
        Xte, yte = idx(d / "t10k-images-idx3-ubyte.gz", "img"), idx(d / "t10k-labels-idx1-ubyte.gz", "lab")
        Xv, yv = torch.from_numpy(Xte), torch.from_numpy(yte)
        per = {"baseline": [], "formats": {}}
        for seed in SEEDS:
            t0 = time.time()
            net = train(Xtr, ytr, seed)
            with torch.no_grad():
                base = (net(Xv).argmax(1) == yv).float().mean().item()
            per["baseline"].append(base)
            W = [p.detach().numpy().copy() for p in net.parameters()]
            for width, bank in ({4: BANKS[4], 8: BANKS[8]} if __import__("os").environ.get("HID","32") != "32" else BANKS).items():
                for name, fn in bank.items():
                    key = f"{width}b/{name}"
                    qs = []
                    for w in W:
                        sc = float(np.max(np.abs(w))) or 1.0
                        qs.append(np.array([fn(v) for v in (w.ravel() / sc)], dtype=np.float32).reshape(w.shape) * sc)
                    with torch.no_grad():
                        for p, q in zip(net.parameters(), qs):
                            p.copy_(torch.from_numpy(q))
                        acc = (net(Xv).argmax(1) == yv).float().mean().item()
                        for p, w in zip(net.parameters(), W):
                            p.copy_(torch.from_numpy(w))
                    per["formats"].setdefault(key, []).append(acc)
            print(f"  {task} seed {seed}: base {base*100:.2f}%  ({time.time()-t0:.0f} с)", flush=True)
        out["tasks"][task] = per
        b = np.array(per["baseline"])
        print(f"\n  == {task}: база {b.mean()*100:.2f} +- {b.std(ddof=1)*100:.2f} п.п. (5 сидов)", flush=True)
        for key, v in sorted(per["formats"].items()):
            a = np.array(v)
            drop = (b - a) * 100
            print(f"   {key:14} {a.mean()*100:6.2f} +- {a.std(ddof=1)*100:4.2f}   "
                  f"падение {drop.mean():+6.2f} +- {drop.std(ddof=1):4.2f} п.п.", flush=True)
    p = SC / ("accuracy_seeds" + __import__("os").environ.get("TAG","") + ".json")
    p.write_text(json.dumps(out, indent=1))
    print("\nWROTE " + str(p), flush=True)


if __name__ == "__main__":
    main()
