"""Is u* a property of (K, element format), or of the model?  Verdict from rows already on disk.

Three questions, each with its own statistic and its own denominator:

  Q1  LOCATION.  Does the argmin u* move with K and with the element format, and is it the same
      across the two models?  Reported on the COMMON 5-point grid {0,.125,.25,.375,.5} so that
      cells measured at different resolution are not compared unfairly, plus the finer grids
      where they exist, marked.

  Q2  AMPLITUDE.  How much does the alignment matter at all?  A = (max-min)/min over the common
      grid.  This is the quantity the mechanism predicts, and it is what a practitioner cares
      about: how much is on the table.

  Q3  MECHANISM.  u moves the scale in whole factors of 2, and u_interior_invariance.py shows the
      reconstruction is then EXACTLY invariant except at three sites -- top clamp, bottom flush,
      and (for a float with subnormals) the subnormal resolution step.  So A should track the
      weight mass sitting at those sites.  That mass is already recorded per cell as
      el_clamp + el_zero.  Correlating them is a test the data can fail.
"""
import glob
import json
import math
import os

HERE = os.path.dirname(os.path.abspath(__file__))
KS = (16, 32, 64, 128)
FMTS = ("INT4", "E2M1", "E3M0")            # ordered by dynamic range, narrow -> wide
BINADES = {"E2M1": 3.585, "E3M0": 6.000, "INT4": 2.807}
COMMON = (0.0, 0.125, 0.25, 0.375, 0.5)


def load(nw=4):
    cells = {}
    for p in sorted(glob.glob(os.path.join(HERE, "u_surface_*.json"))):
        d = json.load(open(p))
        if "rows" not in d or d.get("nw") != nw or d.get("tie") != "even":
            continue
        for r in d["rows"]:
            cells.setdefault((r["model"], r["K"], r["fmt"]), {})[round(r["u"], 6)] = r
    return cells


def spearman(x, y):
    def rank(v):
        s = sorted(range(len(v)), key=lambda i: v[i])
        r = [0.0] * len(v)
        for pos, i in enumerate(s):
            r[i] = pos
        return r
    rx, ry = rank(x), rank(y)
    n = len(x)
    mx, my = sum(rx) / n, sum(ry) / n
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    den = math.sqrt(sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry))
    return num / den if den else float("nan")


def main():
    cells = load(4)
    models = sorted({k[0] for k in cells})
    print(f"\n{'=' * 100}")
    print(f"u* SURFACE VERDICT   nw=4 windows x 2048 tok = 8,192 tokens, ties=even, g=2, "
          f"weight-only")
    print(f"cells: {len(cells)} of 24   models: {models}")
    print(f"{'=' * 100}")

    # ---------------------------------------------------------------- Q2/Q3 first: amplitude
    print(f"\nQ2/Q3  AMPLITUDE AND MECHANISM   (common grid {COMMON}, 5 points per cell)")
    print(f"       A        = (max ppl - min ppl) / min ppl over the common grid")
    print(f"       end-mass = el_clamp + el_zero at u=0, i.e. the fraction of the model's weights"
          f" sitting at a u-sensitive site")
    print(f"       G_left   = ppl(u=0)/ppl(u*) - 1, the BOTTOM site alone: what leaving the "
          f"no-clamp alignment buys")
    print(f"\n       {'model':<9}{'fmt':<6}{'K':>5}{'binades':>9}{'end-mass@0':>12}"
          f"{'A':>9}{'u* (common)':>13}{'ppl min':>10}{'ppl max':>10}{'G_left':>9}")
    rows = []
    for model in models:
        for fmt in FMTS:
            for K in KS:
                c = cells.get((model, K, fmt))
                if not c:
                    continue
                have = [u for u in COMMON if u in c]
                if len(have) < len(COMMON):
                    print(f"       {model:<9}{fmt:<6}{K:>5}   incomplete common grid: {have}")
                    continue
                ps = [c[u]["ppl"] for u in have]
                lo, hi = min(ps), max(ps)
                A = (hi - lo) / lo
                ustar = have[ps.index(lo)]
                # u=0 IS the no-clamp alignment, so el_clamp is 0 there by construction and
                # end-mass@0 is exactly the bottom site: weights flushed to zero.
                end0 = c[0.0]["el_clamp"] + c[0.0]["el_zero"]
                # G_left isolates the BOTTOM site: what moving off the no-clamp alignment buys.
                gl = c[0.0]["ppl"] / lo - 1.0
                rows.append(dict(model=model, fmt=fmt, K=K, A=A, end0=end0, ustar=ustar,
                                 lo=lo, hi=hi, bin=BINADES[fmt], gl=gl,
                                 elz0=c[0.0]["el_zero"], elc0=c[0.0]["el_clamp"]))
                print(f"       {model:<9}{fmt:<6}{K:>5}{BINADES[fmt]:>9.3f}{end0:>11.2f}%"
                      f"{A:>8.1%}{ustar:>13.3f}{lo:>10.4f}{hi:>10.4f}{gl:>9.1%}")

    print(f"\n       ordering test, per model: is A(INT4) > A(E2M1) > A(E3M0) at every K?")
    ok = tot = 0
    for model in models:
        for K in KS:
            a = {r["fmt"]: r["A"] for r in rows if r["model"] == model and r["K"] == K}
            if len(a) == 3:
                tot += 1
                good = a["INT4"] > a["E2M1"] > a["E3M0"]
                ok += good
                print(f"         {model:<9}K={K:<4} INT4 {a['INT4']:6.1%}  E2M1 {a['E2M1']:6.1%}"
                      f"  E3M0 {a['E3M0']:6.1%}   {'HOLDS' if good else 'FAILS'}")
    print(f"       -> format ordering holds in {ok} of {tot} (model, K) cells")

    print(f"\n       monotone in K?  A should grow with K (a wider block spreads its elements "
          f"further below its own maximum)")
    for model in models:
        for fmt in FMTS:
            a = [(K, r["A"]) for K in KS for r in rows
                 if r["model"] == model and r["K"] == K and r["fmt"] == fmt]
            if len(a) == 4:
                mono = all(a[i][1] <= a[i + 1][1] for i in range(3))
                print(f"         {model:<9}{fmt:<6}" + "  ".join(f"K{K}:{v:6.1%}" for K, v in a)
                      + f"   {'MONOTONE' if mono else 'not monotone'}")

    print(f"\n       monotone in K for G_left (the site the end-mass actually measures)?")
    nmono = ntot = 0
    for model in models:
        for fmt in FMTS:
            a = [(K, r["gl"]) for K in KS for r in rows
                 if r["model"] == model and r["K"] == K and r["fmt"] == fmt]
            if len(a) == 4:
                ntot += 1
                mono = all(a[i][1] <= a[i + 1][1] for i in range(3))
                nmono += mono
                print(f"         {model:<9}{fmt:<6}" + "  ".join(f"K{K}:{v:6.1%}" for K, v in a)
                      + f"   {'MONOTONE' if mono else 'not monotone'}")
    print(f"       -> G_left monotone in K in {nmono} of {ntot} (model, format) series")

    print(f"\n       Q3: rank correlation with end-mass@0 (denominator = cells)")
    for label, key in (("A     ", "A"), ("G_left", "gl")):
        print(f"         {label} all {len(rows):2d} cells: "
              f"rho = {spearman([r['end0'] for r in rows], [r[key] for r in rows]):+.4f}"
              + "".join(f"   {m}({sum(1 for r in rows if r['model'] == m)}): "
                        f"{spearman([r['end0'] for r in rows if r['model'] == m], [r[key] for r in rows if r['model'] == m]):+.4f}"
                        for m in models))
    print(f"\n       within ONE format (8 cells = 4 K x 2 models) -- the sharp test, because "
          f"format is held fixed:")
    for fmt in FMTS:
        sub = [r for r in rows if r["fmt"] == fmt]
        print(f"         {fmt:<6} {len(sub)} cells: rho(end-mass, A) = "
              f"{spearman([r['end0'] for r in sub], [r['A'] for r in sub]):+.4f}   "
              f"rho(end-mass, G_left) = "
              f"{spearman([r['end0'] for r in sub], [r['gl'] for r in sub]):+.4f}")

    # ---------------------------------------------------------------- Q1 location
    print(f"\n\nQ1  LOCATION of u*  -- how much of its variation is (K, fmt), how much is model?")
    print(f"       common-grid argmin (resolution 0.125), per (K, fmt), both models")
    print(f"       {'fmt':<6}{'K':>5}" + "".join(f"{m:>12}" for m in models)
          + f"{'|difference|':>14}")
    diffs, byK, byfmt = [], {}, {}
    for fmt in FMTS:
        for K in KS:
            v = {}
            for m in models:
                r = [x for x in rows if x["model"] == m and x["K"] == K and x["fmt"] == fmt]
                if r:
                    v[m] = r[0]["ustar"]
            if len(v) == 2:
                d = abs(v[models[0]] - v[models[1]])
                diffs.append(d)
                print(f"       {fmt:<6}{K:>5}" + "".join(f"{v[m]:>12.3f}" for m in models)
                      + f"{d:>14.3f}")
                byK.setdefault(K, []).extend(v.values())
                byfmt.setdefault(fmt, []).extend(v.values())
    if diffs:
        print(f"\n       spread BETWEEN MODELS at fixed (K, fmt): mean |diff| = "
              f"{sum(diffs) / len(diffs):.4f} over {len(diffs)} (K,fmt) pairs, "
              f"max {max(diffs):.3f}, grid step 0.125")
        allu = [r["ustar"] for r in rows]
        print(f"       spread ACROSS K at fixed (model,fmt): "
              + ", ".join(f"{m}/{f}: {max(z) - min(z):.3f}" for m in models for f in FMTS
                          for z in [[r['ustar'] for r in rows
                                     if r['model'] == m and r['fmt'] == f]] if len(z) == 4))
        print(f"       total spread of u* over all {len(allu)} cells: "
              f"{min(allu):.3f} .. {max(allu):.3f}")

    json.dump(rows, open(os.path.join(HERE, "u_surface_verdict.json"), "w"), indent=1)
    print(f"\n       rows written to u_surface_verdict.json")


if __name__ == "__main__":
    main()
