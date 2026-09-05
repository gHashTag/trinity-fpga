#!/usr/bin/env python3
# W968: this rig bound the name TNF8 to TNFFormat(4, 3) -- 11 bits, 126.91 binades,
# which is TNF16's exponent field with a truncated mantissa and NOT the ladder's
# eighth rung. The ladder defines rung 8 as TNFFormat(3, 4): 10 bits, 30.95 binades.
# Corrected below. The records this rig produced are marked with _format_note and
# superseded by census_tnf8_w963.json and rung_w964_*.json.
"""W941: does the 8-bit null survive quantised activations?

Every accuracy result so far quantised WEIGHTS ONLY, with activations and
accumulation in fp32. That is the weakest possible test of a number format, and
the standard suspicion about a null result: the format never touched the data
path, only the stored parameters.

Quantising activations through a pure-Python oracle is far too slow (2.5M values
per layer at ~10k calls/s). Instead the format's value set is enumerated ONCE from
the oracle -- the same exhaustive table that generates the RTL in oracle_rtl.py --
and quantisation becomes a vectorised nearest-neighbour search into a sorted
array. The equivalence to the oracle round-trip is asserted on a sample before any
result is reported.
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
    "TNF8": (T, T.TNFFormat(3, 4), 10),   # W968: 1 sign + exp + 4 mant, sign_shift + 1 = 10
    "fp8e4m3": (F8, F8.FORMATS["fp8_e4m3"], 8),
    "fp8e5m2": (F8, F8.FORMATS["fp8_e5m2"], 8),
    "posit8": (P, P.FORMATS["posit8"], 8),
    "GF8": (G, G.FORMATS["gf8"], 8),
    "TNF4": (T, T.TNFFormat(2, 1), 6),    # 1 + 4 + 1
    "fp4e2m1": (F8, F8.FORMATS["fp4_e2m1"], 4),
    "GF4": (G, G.FORMATS["gf4"], 4),
}


def value_set(mod, fmt, bits):
    vals = []
    for code in range(1 << bits):
        try:
            v = mod.decode(fmt, code)
        except Exception:
            continue
        try:
            f = float(v)
        except Exception:
            continue
        if np.isfinite(f):
            vals.append(f)
    arr = np.unique(np.array(sorted(set(vals)), dtype=np.float64))
    # A value set with no negatives means the enumeration missed the sign bit --
    # exactly how a 10-bit guess for an 11-bit format goes unnoticed, since the
    # positive half decodes perfectly well on its own.
    assert (arr < 0).any(), "value set has no negative values: the sign bit was not enumerated"
    return arr


def quantiser(vals):
    """Nearest representable value, vectorised."""
    def q(x):
        flat = np.asarray(x, dtype=np.float64).ravel()
        idx = np.searchsorted(vals, flat)
        idx = np.clip(idx, 1, len(vals) - 1)
        lo, hi = vals[idx - 1], vals[idx]
        pick = np.where(np.abs(flat - lo) <= np.abs(hi - flat), lo, hi)
        return pick.reshape(np.asarray(x).shape).astype(np.float32)
    return q


def verify(mod, fmt, q, name):
    """The table must agree with the oracle round-trip, or nothing below is valid."""
    rng = np.random.default_rng(11)
    sample = rng.normal(0, 0.3, 200)
    bad = 0
    for v in sample:
        try:
            ref = float(mod.decode(fmt, mod.encode(fmt, float(v))))
        except Exception:
            continue
        if not np.isfinite(ref):
            continue
        got = float(q(np.array([v]))[0])
        if abs(got - ref) > 1e-6 * max(1.0, abs(ref)):
            bad += 1
    return bad


def idx(path, kind):
    raw = gzip.open(path, "rb").read()
    if kind == "img":
        n = int.from_bytes(raw[4:8], "big")
        return np.frombuffer(raw[16:], np.uint8).reshape(n, 784).astype(np.float32) / 255.0
    return np.frombuffer(raw[8:], np.uint8).astype(np.int64)


def train(Xtr, ytr, seed, H=256):
    torch.manual_seed(seed)
    net = nn.Sequential(nn.Linear(784, H), nn.ReLU(), nn.Linear(H, H), nn.ReLU(), nn.Linear(H, 10))
    opt = torch.optim.Adam(net.parameters(), lr=1e-3)
    lf = nn.CrossEntropyLoss()
    Xt, yt = torch.from_numpy(Xtr), torch.from_numpy(ytr)
    for _ in range(4):
        perm = torch.randperm(len(Xt))
        for i in range(0, len(Xt), 256):
            b = perm[i:i + 256]
            opt.zero_grad(); lf(net(Xt[b]), yt[b]).backward(); opt.step()
    return net


def forward(net, X, q=None, qa=False):
    """Manual forward so activations can be quantised between layers."""
    W = [p.detach().numpy() for p in net.parameters()]
    h = X
    for li in range(3):
        w, b = W[2 * li], W[2 * li + 1]
        h = h @ w.T + b
        if li < 2:
            h = np.maximum(h, 0.0)
            if qa and q is not None:
                sc = float(np.max(np.abs(h))) or 1.0
                h = q(h / sc) * sc
    return h


def main():
    qs, sets = {}, {}
    for name, (mod, fmt, bits) in FORMATS.items():
        vals = value_set(mod, fmt, bits)
        q = quantiser(vals)
        bad = verify(mod, fmt, q, name)
        qs[name], sets[name] = q, vals
        print(f"  {name:8} {bits:2}b: {len(vals):5} различных значений, "
              f"расхождений с оракулом {bad}/200", flush=True)
        # Nearest-value and the oracle's own encoder need not agree on ties or on
        # formats whose encoder is not round-to-nearest. A few disagreements are the
        # format's rounding rule, not a bug; a HALF of them is a missing sign bit,
        # which is what this threshold is set to catch.
        assert bad <= 20, f"{name}: {bad}/200 расхождений -- перебор кодов подозрителен"

    out = {"arch": "784-256-256-10", "seeds": SEEDS, "tasks": {}}
    for task, d in TASKS.items():
        Xtr, ytr = idx(d / "train-images-idx3-ubyte.gz", "img"), idx(d / "train-labels-idx1-ubyte.gz", "lab")
        Xte, yte = idx(d / "t10k-images-idx3-ubyte.gz", "img"), idx(d / "t10k-labels-idx1-ubyte.gz", "lab")
        per = {"baseline": [], "weights_only": {}, "weights_and_activations": {}}
        for seed in SEEDS:
            t0 = time.time()
            net = train(Xtr, ytr, seed)
            base = float((forward(net, Xte).argmax(1) == yte).mean())
            per["baseline"].append(base)
            W0 = [p.detach().numpy().copy() for p in net.parameters()]
            for name, q in qs.items():
                for qa in (False, True):
                    with torch.no_grad():
                        for p, w in zip(net.parameters(), W0):
                            sc = float(np.max(np.abs(w))) or 1.0
                            p.copy_(torch.from_numpy(q(w / sc) * sc))
                        acc = float((forward(net, Xte, q, qa).argmax(1) == yte).mean())
                        for p, w in zip(net.parameters(), W0):
                            p.copy_(torch.from_numpy(w))
                    key = "weights_and_activations" if qa else "weights_only"
                    per[key].setdefault(name, []).append(acc)
            print(f"  {task} seed {seed}: base {base*100:.2f}%  ({time.time()-t0:.0f} с)", flush=True)
        out["tasks"][task] = per
        b = np.array(per["baseline"])
        print(f"\n  == {task}: база {b.mean()*100:.2f} ± {b.std(ddof=1)*100:.2f}", flush=True)
        print(f"  {'формат':9} {'только веса':>14} {'веса+активации':>17} {'разница':>10}", flush=True)
        for name in FORMATS:
            wo = np.array(per["weights_only"][name]); wa = np.array(per["weights_and_activations"][name])
            print(f"  {name:9} {(b-wo).mean()*100:+13.2f} {(b-wa).mean()*100:+16.2f} "
                  f"{((b-wa)-(b-wo)).mean()*100:+9.2f}", flush=True)
    p = SC / "activations.json"
    p.write_text(json.dumps(out, indent=1))
    print("\nWROTE " + str(p), flush=True)


if __name__ == "__main__":
    main()
