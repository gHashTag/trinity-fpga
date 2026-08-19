#!/usr/bin/env python3
"""W937: how much of the accuracy result is the sampling prior?

Every accuracy regenerator in the paper draws `_rng.integers(-38, 39)` -- uniform
over 77 binades. That is precisely the prior under which a flat-precision fixed
field must beat a tapered format, because a taper spends its precision near
|e| = 0 by construction. The word "prior" never appears in the manuscript in a
statistical sense, and the applicability section separately finds that real
transformer tensors fall outside that window.

This re-runs the SAME oracles and the SAME round-trip error over five priors and
reports how the ranking moves. No new format code: the oracles are the shipped
conformance references, imported unchanged.
"""
import json, sys, pathlib
import numpy as np

A = pathlib.Path("/private/tmp/claude-501/-Users-playom-t27--claude-worktrees-igla-fpga-improvements-3f5e1a/"
                 "eeed4a0e-20e8-40f4-aa16-1ecfee4ad92d/scratchpad/upstream-wt/research/arxiv_tnf")
sys.path.insert(0, str(A.parent.parent / "conformance"))
sys.path.insert(0, str(A))

import tnf_ref as T, gf_ref as G, takum_ref as K, posit_ref as P, bf16_ref as B, lns_ref as L

_tnf = T.TNFFormat(4, 11)
_gf16 = G.FORMATS["gf16"]
_tk = K.TakumFormat("takum16", 16)
_po = P.FORMATS["posit16"]
_bf = B.FORMATS["bfloat16"]
_ln = L.FORMATS["lns16"]


def _num(x):
    if x is None:
        return None
    try:
        f = float(x)
    except Exception:
        return None
    return f if np.isfinite(f) else None


def rt(mod, fmt, v):
    try:
        return _num(mod.decode(fmt, mod.encode(fmt, v)))
    except Exception:
        return None


def d_b16(v):
    x = np.float16(v)
    return float(x) if np.isfinite(x) else None


CODECS = {
    "TNF16": lambda v: rt(T, _tnf, v),
    "GF16": lambda v: rt(G, _gf16, v),
    "takum16": lambda v: rt(K, _tk, v),
    "posit16": lambda v: rt(P, _po, v),
    "bfloat16": lambda v: rt(B, _bf, v),
    "binary16": d_b16,
    "LNS16": lambda v: rt(L, _ln, v),
}

N = 6000
SEED = 20260809


def priors():
    """Five magnitude priors. The first is the paper's."""
    r = np.random.default_rng(SEED)
    pub = [float(s) * float(m) * 2.0 ** int(e) for s, m, e in
           zip(r.choice([-1, 1], N), r.uniform(1, 2, N), r.integers(-38, 39, N))]

    r = np.random.default_rng(SEED)
    normal = list(r.normal(0.0, 1.0, N))

    # A trained layer after standard init: sigma ~ 1/sqrt(fan_in), fan_in = 512.
    r = np.random.default_rng(SEED)
    he = list(r.normal(0.0, (2.0 / 512) ** 0.5, N))

    # Heavy-tailed weights: Student-t, df=3, the shape reported for attention matrices.
    r = np.random.default_rng(SEED)
    heavy = list(r.standard_t(3, N) * 0.05)

    # Log-uniform over a REALISTIC dynamic range: |e| in [0, 8] rather than [0, 38].
    r = np.random.default_rng(SEED)
    narrow = [float(s) * float(m) * 2.0 ** int(e) for s, m, e in
              zip(r.choice([-1, 1], N), r.uniform(1, 2, N), r.integers(-8, 9, N))]

    return {"published_uniform_77_binades": pub,
            "standard_normal": normal,
            "he_init_fan_in_512": he,
            "student_t_df3_scaled": heavy,
            "log_uniform_17_binades": narrow}


def rel_errors(vals, fn):
    out = []
    miss = 0
    for v in vals:
        if v == 0.0:
            continue
        d = fn(v)
        if d is None:
            miss += 1
            continue
        out.append(abs(d - v) / abs(v))
    return np.array(out), miss


def main():
    res = {}
    for pname, vals in priors().items():
        arr = np.array([abs(v) for v in vals if v != 0])
        res[pname] = {"_workload": {"n": len(vals),
                                    "median_abs": float(np.median(arr)),
                                    "p01_abs": float(np.quantile(arr, 0.01)),
                                    "p99_abs": float(np.quantile(arr, 0.99))},
                      "formats": {}}
        for fname, fn in CODECS.items():
            e, miss = rel_errors(vals, fn)
            if len(e) == 0:
                res[pname]["formats"][fname] = {"status": "no-values"}
                continue
            res[pname]["formats"][fname] = {
                "median_rel_err": float(np.median(e)),
                "mean_rel_err": float(np.mean(e)),
                "p99_rel_err": float(np.quantile(e, 0.99)),
                "unrepresentable": miss,
                "n": int(len(e))}
        order = sorted((v["median_rel_err"], k) for k, v in res[pname]["formats"].items()
                       if "median_rel_err" in v)
        res[pname]["ranking_by_median_rel_err"] = [k for _, k in order]
        print(f"\n{pname}  (median |v| = {res[pname]['_workload']['median_abs']:.3g})")
        for err, k in order:
            f = res[pname]["formats"][k]
            print(f"   {k:10} median {err:.3e}   mean {f['mean_rel_err']:.3e}   "
                  f"p99 {f['p99_rel_err']:.3e}   miss {f['unrepresentable']}")
    out = pathlib.Path("/private/tmp/claude-501/-Users-playom-t27--claude-worktrees-igla-fpga-improvements-3f5e1a/"
                       "eeed4a0e-20e8-40f4-aa16-1ecfee4ad92d/scratchpad/prior_sensitivity.json")
    out.write_text(json.dumps(res, indent=1))
    print("\nWROTE", out)


if __name__ == "__main__":
    main()
