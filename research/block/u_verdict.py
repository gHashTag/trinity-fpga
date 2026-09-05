"""Read the u-surface measurements and answer the one question: is u* a function of
(block size K, element format), or of the model?

Consumes
    u_surface_<tag>*.json     ARM P, perplexity (the only judge)
    u_theory_weights.json     ARM W, squared error on the real weights, no forward pass
    u_theory_synth.json       ARM S, squared error on i.i.d. synthetic blocks, no model at all

Prints
    1. the measured u* surface, with the discrete argmin, a parabolic refinement, and the
       u-interval inside which perplexity stays within TOL of its minimum (a minimum you cannot
       locate is not a minimum);
    2. the three-way spread decomposition -- how far u* moves when you change the model, versus
       when you change K, versus when you change the element format;
    3. whether the derived arms predict the measured one.
"""
import glob
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
TOL = 0.05          # ppl units: the basin is every u whose ppl is within TOL of the cell minimum


def load_ppl():
    rows = []
    for p in sorted(glob.glob(os.path.join(HERE, "u_surface_*.json"))):
        if p.endswith("_gate.json"):
            continue
        with open(p) as fh:
            d = json.load(fh)
        rows += d["rows"]
    return rows


def parabolic(us, ys):
    i = int(np.argmin(ys))
    if i in (0, len(ys) - 1):
        return us[i], "edge"
    d = ys[i - 1] - 2 * ys[i] + ys[i + 1]
    if d <= 0:
        return us[i], "flat"
    return float(us[i] - 0.5 * (us[i + 1] - us[i]) * (ys[i + 1] - ys[i - 1]) / d), "interp"


def cells(rows):
    out = {}
    for r in rows:
        out.setdefault((r["model"], r["K"], r["fmt"], r["nw"]), []).append(r)
    for k in out:
        out[k].sort(key=lambda r: r["u"])
    return out


def main():
    rows = load_ppl()
    if not rows:
        print("no u_surface_*.json found -- nothing to report")
        return
    cs = cells(rows)

    print("\n=== 1. MEASURED u* SURFACE (perplexity) ===")
    print(f"{'model':<9}{'K':>5}{'fmt':>6}{'nw':>4}{'u grid':>34}{'argmin':>8}{'u*(par)':>9}"
          f"{'how':>8}{'ppl*':>10}{'basin(+' + str(TOL) + ')':>18}", flush=True)
    star = {}
    for (mdl, K, fmt, nw), rs in sorted(cs.items()):
        us = [r["u"] for r in rs]
        ys = [r["ppl"] for r in rs]
        up, how = parabolic(us, ys)
        lo = min(ys) + TOL
        inb = [u for u, y in zip(us, ys) if y <= lo]
        star[(mdl, K, fmt, nw)] = dict(argmin=us[int(np.argmin(ys))], upar=up, how=how,
                                       best=min(ys), basin=(min(inb), max(inb)), us=us, ys=ys)
        print(f"{mdl:<9}{K:>5}{fmt:>6}{nw:>4}{str(us):>34}{us[int(np.argmin(ys))]:8.3f}"
              f"{up:9.4f}{how:>8}{min(ys):10.4f}"
              f"{f'[{min(inb):.3f},{max(inb):.3f}]':>18}", flush=True)

    print("\n=== 2. SPREAD DECOMPOSITION of u* ===")
    print("  The perplexity curve is a shallow basin followed by a cliff, not a parabola, so a")
    print("  point estimate carries a systematic bias of up to half a grid step.  That bias is")
    print("  the same in every cell, so DIFFERENCES survive it; the decomposition is therefore")
    print("  run twice, once on the parabolic estimate and once on the raw discrete argmin, and")
    print("  only conclusions that agree between the two are reported.")
    for est in ("upar", "argmin"):
        print(f"\n  --- estimator: {est} ---")
        _decompose({k: dict(v, upar=v[est]) for k, v in star.items()})
    _predict(star)


def _decompose(star):
    for nw in sorted({k[3] for k in star}):
        sub = {k: v for k, v in star.items() if k[3] == nw}
        if not sub:
            continue
        print(f"  nw={nw}")
        # model axis
        d = {}
        for (mdl, K, fmt, _), v in sub.items():
            d.setdefault((K, fmt), {})[mdl] = v["upar"]
        pair = [(k, vv) for k, vv in d.items() if len(vv) > 1]
        if pair:
            sp = [max(vv.values()) - min(vv.values()) for _, vv in pair]
            print(f"    change the MODEL, hold (K,fmt):  n={len(pair)} cells, "
                  f"mean |spread| {np.mean(sp):.4f}, max {max(sp):.4f}")
            for k, vv in sorted(pair):
                print(f"        K={k[0]:<4}{k[1]:<6} " +
                      "  ".join(f"{m}={x:.4f}" for m, x in sorted(vv.items())) +
                      f"   spread {max(vv.values()) - min(vv.values()):+.4f}")
        # K axis
        d = {}
        for (mdl, K, fmt, _), v in sub.items():
            d.setdefault((mdl, fmt), {})[K] = v["upar"]
        pair = [(k, vv) for k, vv in d.items() if len(vv) > 1]
        if pair:
            sp = [max(vv.values()) - min(vv.values()) for _, vv in pair]
            print(f"    change K, hold (model,fmt):      n={len(pair)} cells, "
                  f"mean |spread| {np.mean(sp):.4f}, max {max(sp):.4f}")
            for k, vv in sorted(pair):
                print(f"        {k[0]:<9}{k[1]:<6} " +
                      "  ".join(f"K{kk}={x:.4f}" for kk, x in sorted(vv.items())) +
                      f"   spread {max(vv.values()) - min(vv.values()):+.4f}")
        # format axis
        d = {}
        for (mdl, K, fmt, _), v in sub.items():
            d.setdefault((mdl, K), {})[fmt] = v["upar"]
        pair = [(k, vv) for k, vv in d.items() if len(vv) > 1]
        if pair:
            sp = [max(vv.values()) - min(vv.values()) for _, vv in pair]
            print(f"    change the FORMAT, hold (model,K): n={len(pair)} cells, "
                  f"mean |spread| {np.mean(sp):.4f}, max {max(sp):.4f}")
            for k, vv in sorted(pair):
                print(f"        {k[0]:<9}K={k[1]:<4} " +
                      "  ".join(f"{f}={x:.4f}" for f, x in sorted(vv.items())) +
                      f"   spread {max(vv.values()) - min(vv.values()):+.4f}")

def _predict(star):
    print("\n=== 3. DO THE DERIVED ARMS PREDICT THE MEASURED ONE? ===")
    try:
        wt = json.load(open(os.path.join(HERE, "u_theory_weights.json")))
        sy = json.load(open(os.path.join(HERE, "u_theory_synth.json")))
    except FileNotFoundError:
        print("  (u_theory_*.json missing)")
        return
    wmap = {(r["model"], r["K"], r["fmt"]): r["ustar"] for r in wt}
    smap = {(r["dist"], r["K"], r["fmt"]): r["ustar"] for r in sy}
    print(f"{'model':<9}{'K':>5}{'fmt':>6}{'nw':>4}{'u*_ppl':>9}{'u*_sse(weights)':>17}"
          f"{'u*_sse(gauss)':>15}{'ppl-sse':>10}{'ppl-gauss':>11}", flush=True)
    d1, d2 = [], []
    for (mdl, K, fmt, nw), v in sorted(star.items()):
        a, b = wmap.get((mdl, K, fmt)), smap.get(("gauss", K, fmt))
        if a is None or b is None:
            continue
        d1.append(v["upar"] - a)
        d2.append(v["upar"] - b)
        print(f"{mdl:<9}{K:>5}{fmt:>6}{nw:>4}{v['upar']:9.4f}{a:17.4f}{b:15.4f}"
              f"{v['upar'] - a:10.4f}{v['upar'] - b:11.4f}", flush=True)
    if d1:
        print(f"  u*_ppl - u*_sse(real weights): mean {np.mean(d1):+.4f}  "
              f"sd {np.std(d1):.4f}  max|.| {max(abs(x) for x in d1):.4f}  n={len(d1)}")
        print(f"  u*_ppl - u*_sse(iid gaussian): mean {np.mean(d2):+.4f}  "
              f"sd {np.std(d2):.4f}  max|.| {max(abs(x) for x in d2):.4f}  n={len(d2)}")


if __name__ == "__main__":
    TOL = float(sys.argv[1]) if len(sys.argv) > 1 else TOL
    main()
