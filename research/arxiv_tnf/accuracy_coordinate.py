#!/usr/bin/env python3
"""W938: give the area figure an accuracy coordinate, and measure the real prior.

Every LUT-domain competitor prices area against a named accuracy on a named
dataset. This project has none: `top-1`, `ImageNet`, `CIFAR`, `MNIST` return zero
hits across the manuscript's 7,858 lines. So a reviewer cannot tell whether
28 LUT/weight is good.

This trains a small MLP on MNIST, then quantises its trained weights through the
SAME shipped conformance oracles used by the paper's accuracy tables, and reports
test accuracy per format. It also extracts the empirical magnitude distribution of
the trained tensors, which is the decisive prior W937 could only bound.
"""
import gzip, json, pathlib, sys, time
import numpy as np
import torch
import torch.nn as nn

SC = pathlib.Path("/private/tmp/claude-501/-Users-playom-t27--claude-worktrees-igla-fpga-improvements-3f5e1a/"
                  "eeed4a0e-20e8-40f4-aa16-1ecfee4ad92d/scratchpad")
sys.path.insert(0, str(SC / "upstream-wt/conformance"))
import tnf_ref as T, gf_ref as G, takum_ref as K, posit_ref as P, bf16_ref as B, fp8_ref as F8

WIDTH = int(sys.argv[1]) if len(sys.argv) > 1 else 16
_tnf = T.TNFFormat(4, 11)
_gf16 = G.FORMATS["gf16"]
_tk = K.TakumFormat("takum16", 16)
_po = P.FORMATS["posit16"]
_bf = B.FORMATS["bfloat16"]
# The 8-bit rungs: this is where the field actually fights, and where a 16-bit
# comparison found no task-level difference at all.
_tnf8 = T.TNFFormat(4, 3)
_po8 = P.FORMATS["posit8"]
_gf8 = G.FORMATS["gf8"]
_e4m3 = F8.FORMATS["fp8_e4m3"]
_e5m2 = F8.FORMATS["fp8_e5m2"]
_fp4 = F8.FORMATS["fp4_e2m1"]
_gf4 = G.FORMATS["gf4"]
_tnf4 = T.TNFFormat(2, 1)


def idx(path, kind):
    with gzip.open(path, "rb") as f:
        raw = f.read()
    if kind == "img":
        n, r, c = int.from_bytes(raw[4:8], "big"), int.from_bytes(raw[8:12], "big"), int.from_bytes(raw[12:16], "big")
        return np.frombuffer(raw[16:], np.uint8).reshape(n, r * c).astype(np.float32) / 255.0
    n = int.from_bytes(raw[4:8], "big")
    return np.frombuffer(raw[8:], np.uint8).astype(np.int64)


def rt(mod, fmt):
    def f(v):
        try:
            x = mod.decode(fmt, mod.encode(fmt, float(v)))
            x = float(x)
            return x if np.isfinite(x) else 0.0
        except Exception:
            return 0.0
    return f


CODECS16 = {
    "TNF16": rt(T, _tnf),
    "GF16": rt(G, _gf16),
    "takum16": rt(K, _tk),
    "posit16": rt(P, _po),
    "bfloat16": rt(B, _bf),
    "binary16": lambda v: float(np.float16(v)),
}
CODECS8 = {
    "TNF8 (E_t=4,M=3)": rt(T, _tnf8),
    "GF8": rt(G, _gf8),
    "posit8": rt(P, _po8),
    "fp8 e4m3": rt(F8, _e4m3),
    "fp8 e5m2": rt(F8, _e5m2),
}
CODECS4 = {
    "TNF4 (E_t=2,M=1)": rt(T, _tnf4),
    "GF4": rt(G, _gf4),
    "fp4 e2m1": rt(F8, _fp4),
}
CODECS = {16: CODECS16, 8: CODECS8, 4: CODECS4}[WIDTH]


def main():
    M = SC / "mnist"
    Xtr, ytr = idx(M / "train-images-idx3-ubyte.gz", "img"), idx(M / "train-labels-idx1-ubyte.gz", "lab")
    Xte, yte = idx(M / "t10k-images-idx3-ubyte.gz", "img"), idx(M / "t10k-labels-idx1-ubyte.gz", "lab")
    print(f"  MNIST: train {Xtr.shape}, test {Xte.shape}", flush=True)

    torch.manual_seed(20260820)
    net = nn.Sequential(nn.Linear(784, 32), nn.ReLU(), nn.Linear(32, 10))
    opt = torch.optim.Adam(net.parameters(), lr=1e-3)
    lossf = nn.CrossEntropyLoss()
    Xt, yt = torch.from_numpy(Xtr), torch.from_numpy(ytr)
    for ep in range(4):
        perm = torch.randperm(len(Xt))
        for i in range(0, len(Xt), 256):
            b = perm[i:i + 256]
            opt.zero_grad(); loss = lossf(net(Xt[b]), yt[b]); loss.backward(); opt.step()
        print(f"  эпоха {ep + 1}: loss {loss.item():.4f}", flush=True)

    Xv, yv = torch.from_numpy(Xte), torch.from_numpy(yte)
    with torch.no_grad():
        base = (net(Xv).argmax(1) == yv).float().mean().item()
    print(f"  базовая точность fp32: {base * 100:.2f}%", flush=True)

    W = [p.detach().numpy().copy() for p in net.parameters()]
    flat = np.concatenate([w.ravel() for w in W])
    nz = np.abs(flat[flat != 0])
    emp = {"n_params": int(flat.size),
           "median_abs": float(np.median(nz)), "p01_abs": float(np.quantile(nz, 0.01)),
           "p99_abs": float(np.quantile(nz, 0.99)),
           "log2_span_p01_p99": float(np.log2(np.quantile(nz, 0.99) / np.quantile(nz, 0.01))),
           "binades_covered": float(np.log2(nz.max() / nz.min()))}
    print(f"  эмпирический приор: медиана |w| = {emp['median_abs']:.4g}, "
          f"p01..p99 охватывают {emp['log2_span_p01_p99']:.1f} бинад "
          f"(полный размах {emp['binades_covered']:.1f})", flush=True)

    t0 = time.time()
    for _ in range(300):
        next(iter(CODECS.values()))(0.0137)
    rate = 300 / (time.time() - t0)
    print(f"  скорость оракула ~{rate:.0f} вызовов/с; параметров {flat.size}", flush=True)

    # SCALED is the deployment-realistic path: every real sub-8-bit weight format
    # carries a per-tensor scale, and without one a 4-bit format simply cannot
    # reach a weight of magnitude 0.05 -- it underflows to zero and the result
    # measures dynamic range rather than the number system.
    SCALED = len(sys.argv) > 2 and sys.argv[2] == "scaled"
    res = {"baseline_fp32_accuracy": base, "empirical_prior": emp,
           "per_tensor_scale": SCALED, "formats": {}}
    for name, fn in CODECS.items():
        t0 = time.time()
        qs = []
        for w in W:
            if SCALED:
                sc = float(np.max(np.abs(w))) or 1.0
                q = np.array([fn(v) for v in (w.ravel() / sc)], dtype=np.float32).reshape(w.shape) * sc
            else:
                q = np.array([fn(v) for v in w.ravel()], dtype=np.float32).reshape(w.shape)
            qs.append(q)
        with torch.no_grad():
            for p, q in zip(net.parameters(), qs):
                p.copy_(torch.from_numpy(q))
            acc = (net(Xv).argmax(1) == yv).float().mean().item()
            for p, w in zip(net.parameters(), W):
                p.copy_(torch.from_numpy(w))
        qf = np.concatenate([q.ravel() for q in qs])
        m = flat != 0
        rel = np.abs(qf[m] - flat[m]) / np.abs(flat[m])
        res["formats"][name] = {"top1": acc, "drop_pp": (base - acc) * 100,
                                "median_rel_err_on_real_weights": float(np.median(rel)),
                                "zeroed": int((qf == 0).sum() - (flat == 0).sum()),
                                "seconds": round(time.time() - t0, 1)}
        print(f"  {name:10} top-1 {acc*100:6.2f}%  падение {(base-acc)*100:+5.2f} п.п.  "
              f"медианная отн. ошибка {np.median(rel):.3e}  ({time.time()-t0:.0f} с)", flush=True)

    out = SC / (f"accuracy_coordinate_{WIDTH}" + ("_scaled" if SCALED else "") + ".json")
    out.write_text(json.dumps(res, indent=1))
    print("WROTE " + str(out), flush=True)


if __name__ == "__main__":
    main()
