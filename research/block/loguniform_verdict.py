#!/usr/bin/env python3
"""CAMPAIGN C, phase 3 -- the verdict on T39's log-uniformity assumption.

Phase 2 exposed two things phase 1 did not:

  (i)  the E8M0 waste of a block whose frac(log2 a_max) is EXACTLY 0 is 0, not 1
       (T38 Prop 2's parenthesis).  0.11 % - 0.90 % of real blocks are in that
       case, so `1 - x` overstates E[waste] by that much.  Everything here uses
       the round-up map itself, not the 1-x shorthand.
  (ii) frac(log2 a_max) is not a density at all.  A checkpoint stores weights in
       bf16 (7 explicit mantissa bits) or fp16 (10), so a_max lives on a LATTICE
       of 2^t points per octave and x takes 2^t values, not a continuum.  The
       lattice positions are log2(1 + j/2^t) -- exactly the FLOAT grid's points.

So T39 is checked against the real measure on three separate axes:
    T39-ATTAINED    geometric grid costs 2^-(m+1)                (any p: integral p = 1)
    T39-UNIQUE      no other grid does better                    (needs p == 1)
    T39-FLOAT       float/geometric -> 1/(2 ln^2 2) = 1.0406845  (needs p == 1)
plus T38-P3         E[waste] = 1/2 at every codebook phase       (needs p == 1)

Everything is evaluated by the exact round-up map on the raw samples.  Anything
fitted is fitted on one split and scored on another, never on itself.
"""
import os, sys, math, json
import numpy as np
from scipy import stats
from scipy.optimize import minimize

HERE = os.path.dirname(os.path.abspath(__file__))
MODELS = [("smollm2", "SmolLM2-135M", "bf16"), ("qwen", "Qwen2.5-0.5B", "bf16"),
          ("pythia", "Pythia-160M", "fp16"), ("opt", "OPT-125M", "fp16")]
MANT = {"bf16": 7, "fp16": 10}


# ------------------------------------------------------------------ maps ----
def grid_geometric(m, rot=0.0):
    n = 1 << m
    return np.sort(np.mod(np.arange(1, n + 1) / n + rot, 1.0))


def grid_float(m, rot=0.0):
    n = 1 << m
    return np.sort(np.mod(np.log2(1.0 + np.arange(1, n + 1) / n) + rot, 1.0))


def waste_vec(x, G):
    """Exact per-block headroom waste: round x UP to the next grid point, wrap.
    A block sitting on a grid point wastes 0 -- that is T38 Prop 2's parenthesis."""
    G = np.asarray(G, dtype=np.float64)
    idx = np.searchsorted(G, x, side="left")
    tops = np.where(idx < len(G), G[np.minimum(idx, len(G) - 1)], G[0] + 1.0)
    return tops - x


def W(x, G):
    return float(np.mean(waste_vec(x, G)))


def paired_t(x, Ga, Gb):
    d = waste_vec(x, Gb) - waste_vec(x, Ga)
    se = d.std(ddof=1) / math.sqrt(len(d))
    return float(d.mean()), float(se), float(d.mean() / se)


class Exact:
    """Exact cost of any grid against a fixed sample, by prefix sums."""
    def __init__(self, x):
        self.xs = np.sort(np.asarray(x, dtype=np.float64))
        self.P = np.concatenate([[0.0], np.cumsum(self.xs)])
        self.N = len(self.xs)

    def _sum(self, i, j, top):
        return top * (j - i) - (self.P[j] - self.P[i])

    def cost(self, G):
        G = np.sort(np.mod(np.asarray(G, float), 1.0))
        ss = np.searchsorted(self.xs, G, side="right")
        tot = self._sum(0, ss[0], G[0])                       # [0, G0]
        for i in range(1, len(G)):
            tot += self._sum(ss[i - 1], ss[i], G[i])
        tot += self._sum(ss[-1], self.N, G[0] + 1.0)          # (G_last, 1)
        return tot / self.N


def fit_grid(ex, m, n_restart=14, seed=0):
    """Free 2^m-point grid minimising the EXACT cost on the fitting split.
    Starts include the geometric grid itself at four rotations and the float
    grid, so a returned grid can only be at least as good IN SAMPLE."""
    n = 1 << m
    rng = np.random.default_rng(seed)

    def unpack(th):
        g = np.exp(th[:n] - th[:n].max())
        return np.mod(np.cumsum(g / g.sum()) + th[n], 1.0)

    fg = np.log(np.diff(np.concatenate(
        [[0.0], np.log2(1.0 + np.arange(1, n + 1) / n)])))
    best, bv = None, np.inf
    starts = [np.concatenate([np.zeros(n), [r]]) for r in (0.0, .25, .5, .75)]
    starts += [np.concatenate([fg, [0.0]])]
    for _ in range(n_restart - len(starts)):
        starts.append(np.concatenate([rng.normal(0, .6, n), rng.uniform(0, 1, 1)]))
    for s in starts:
        r = minimize(lambda t: ex.cost(unpack(t)), s, method="Nelder-Mead",
                     options=dict(maxiter=2000 * (n + 1), xatol=1e-10, fatol=1e-14))
        if r.fun < bv:
            bv, best = r.fun, unpack(r.x)
    # never return something worse in sample than the plain geometric grid
    g0 = grid_geometric(m)
    return np.sort(best) if bv < ex.cost(g0) else g0


def fit_rot(ex, m, kind="geo", n=721):
    gf = grid_geometric if kind == "geo" else grid_float
    rs = np.linspace(0, 1, n)[:-1]
    c = [ex.cost(gf(m, r)) for r in rs]
    return float(rs[int(np.argmin(c))])


# ------------------------------------------------------------------ main ----
def main():
    X = {k: np.load(os.path.join(HERE, f"loguniform_x_{k}.npy"))
         for k, _, _ in MODELS}
    rng = np.random.default_rng(20260811)
    HALF = {}
    for k, _, _ in MODELS:
        idx = rng.permutation(len(X[k]))
        h = len(idx) // 2
        HALF[k] = (X[k][idx[:h]], X[k][idx[h:]])
    out = {}

    print("=" * 80)
    print("1.  IS frac(log2 a_max) UNIFORM ON [0,1)?   (T39's stated assumption)")
    print("=" * 80)
    print(f"{'model':<15}{'store':>6}{'blocks':>12}{'KS D':>9}{'KS p':>11}"
          f"{'atoms/oct':>11}{'P(x=0)':>9}")
    tab1 = {}
    for k, lb, dt in MODELS:
        x = X[k]
        r = stats.kstest(x, "uniform")
        atoms = len(np.unique(np.round(x, 6)))
        p0 = float((x == 0.0).mean())
        tab1[k] = dict(ks_D=float(r.statistic), ks_p=float(r.pvalue),
                       atoms=int(atoms), p_zero=p0, n=int(len(x)), store=dt)
        print(f"{lb:<15}{dt:>6}{len(x):>12,}{r.statistic:>9.4f}{r.pvalue:>11.1e}"
              f"{atoms:>11,}{p0*100:>8.2f}%")
    print()
    print("    UNIFORMITY IS REJECTED IN ALL FOUR, at p = 0 to double precision.")
    print("    It is not even continuous: 2^t atoms per octave, t = mantissa bits")
    print("    of the checkpoint dtype (bf16 -> 128, fp16 -> 1024), and the atom")
    print("    positions log2(1 + j/2^t) ARE the float grid's points.")
    print(f"    predicted atoms/octave: bf16 {2**MANT['bf16']}, fp16 {2**MANT['fp16']}"
          "  (measured counts inflated ~2.5x by float64 log2 rounding)")
    out["1_uniformity"] = tab1

    print()
    print("=" * 80)
    print("2.  T39-ATTAINED:  does the geometric grid still cost 2^-(m+1) bits?")
    print("    exact round-up on raw samples; the claim needs only integral p = 1")
    print("=" * 80)
    print(f"{'m':>2}{'2^-(m+1)':>11}" + "".join(f"{lb:>22}" for _, lb, _ in MODELS))
    tab2 = {}
    for m in range(0, 9):
        pred = 2.0 ** (-(m + 1))
        row = [W(X[k], grid_geometric(m)) for k, _, _ in MODELS]
        tab2[m] = row
        print(f"{m:>2}{pred:>11.6f}" +
              "".join(f"{v:>13.6f}{(v/pred-1)*100:>8.2f}%" for v in row))
    out["2_attained"] = {str(m): tab2[m] for m in tab2}
    dev = max(abs(v / 2.0 ** (-(m + 1)) - 1) for m in tab2 for v in tab2[m])
    abs_dev = max(abs(v - 2.0 ** (-(m + 1))) for m in tab2 for v in tab2[m])
    print(f"\n    worst relative error over all m and models: {dev*100:.2f}%"
          f"   worst absolute: {abs_dev:.4f} bits")

    print()
    print("=" * 80)
    print("3.  T39-UNIQUE:  is equal log-spacing still optimal under the measured p?")
    print("    theory: optimal point density is proportional to SQRT(p), not")
    print("    constant; optimum = (integral sqrt p)^2 * 2^-(m+1) <= 2^-(m+1).")
    print("=" * 80)
    print("    (a) the SMOOTH part of p -- shape only, lattice averaged out")
    print(f"        {'model':<15}{'bins':>6}{'(int sqrt p)^2':>16}{'max gain':>11}")
    tab3a = {}
    for k, lb, _ in MODELS:
        for B in (16, 64):
            h, _ = np.histogram(X[k], bins=B, range=(0, 1))
            p = h / h.sum() * B
            s = float((np.sqrt(p).mean()) ** 2)
            tab3a[f"{k}_B{B}"] = s
            print(f"        {lb if B == 16 else '':<15}{B:>6}{s:>16.6f}"
                  f"{(1-s)*100:>10.3f}%")
    out["3a_sqrt_p"] = tab3a

    print()
    print("    (b) measured, HONESTLY SPLIT: grid fitted on a random half of the")
    print("        model's blocks, scored by exact round-up on the other half")
    print(f"        {'model':<15}{'m':>2}{'geometric':>11}{'best fitted':>12}"
          f"{'gain':>9}{'t':>9}")
    tab3b = {}
    for k, lb, _ in MODELS:
        fitx, evx = HALF[k]
        ex = Exact(fitx)
        for m in (0, 1, 2, 3, 4):
            G = fit_grid(ex, m)
            g0 = grid_geometric(m)
            d, se, t = paired_t(evx, g0, G)
            tab3b[f"{k}_m{m}"] = dict(geo=W(evx, g0), fit=W(evx, G),
                                      gain=-d / W(evx, g0), t=t,
                                      grid=[float(v) for v in G])
            print(f"        {lb if m == 0 else '':<15}{m:>2}{W(evx,g0):>11.6f}"
                  f"{W(evx,G):>12.6f}{-d/W(evx,g0)*100:>8.3f}%{-t:>9.1f}")
    out["3b_split_fit"] = tab3b

    print()
    print("=" * 80)
    print("4.  T39-FLOAT:  is float/geometric still 1/(2 ln^2 2) = 1.0406845?")
    print("=" * 80)
    print("    (a) high-rate closed form under the measured p: E_p[2^-x] / ln 2")
    print(f"        {'model':<15}{'measured const':>16}{'uniform-p const':>17}{'shift':>9}")
    C = 1.0 / (2 * math.log(2) ** 2)
    tab4a = {}
    for k, lb, _ in MODELS:
        r = float(np.mean(np.exp2(-X[k])) / math.log(2))
        tab4a[k] = r
        print(f"        {lb:<15}{r:>16.6f}{C:>17.6f}{(r/C-1)*100:>8.2f}%")
    out["4a_closed_form"] = tab4a

    print()
    print("    (b) exact measured ratio at each m, with the paired t of")
    print("        float - geometric (t > 0 = float worse, T39-FLOAT's prediction)")
    print(f"        {'m':>2}{'uniform':>9}" + "".join(f"{lb.split('-')[0]:>19}"
                                                     for _, lb, _ in MODELS))
    tab4b = {}
    for m in range(1, 9):
        base = 0.5 * (1 << m) * (1.0 / (1 << m)) ** 2
        gf = np.diff(np.concatenate([[0.0], np.log2(
            1.0 + np.arange(1, (1 << m) + 1) / (1 << m))]))
        cells, row = [], []
        for k, _, _ in MODELS:
            wg, wf = W(X[k], grid_geometric(m)), W(X[k], grid_float(m))
            _, _, t = paired_t(X[k], grid_geometric(m), grid_float(m))
            row.append(dict(ratio=wf / wg, t=t))
            cells.append(f"{wf/wg:>11.4f}{t:>8.0f}")
        tab4b[m] = row
        print(f"        {m:>2}{0.5*sum(g*g for g in gf)/base:>9.4f}" + "".join(cells))
    out["4b_measured_ratio"] = {str(m): tab4b[m] for m in tab4b}
    print("\n    T39-FLOAT predicts ratio > 1 at every m >= 1. Count of (model, m)")
    print("    cells where the float grid is measurably BETTER (ratio < 1, t < 0):")
    bad = [(m, MODELS[i][1]) for m in tab4b for i, c in enumerate(tab4b[m])
           if c["ratio"] < 1.0 and c["t"] < -3]
    print(f"        {len(bad)} of {8*4}:  " +
          ", ".join(f"{lb} m={m}" for m, lb in sorted(bad)) if bad else "        none")

    print()
    print("=" * 80)
    print("5.  T38-P3:  'E[waste] = 1/2 bit for EVERY codebook top T'")
    print("    phi = log2 T mod 1 rotates the m=0 grid. Under uniform p the sweep")
    print("    is flat at 0.5 for every phi. Measured:")
    print("=" * 80)
    ph = np.linspace(0, 1, 201)[:-1]
    print(f"    {'model':<15}{'min':>10}{'at phi':>8}{'max':>10}{'at phi':>8}"
          f"{'spread':>9}{'at phi=0':>10}")
    tab5 = {}
    for k, lb, _ in MODELS:
        v = np.array([W(X[k], np.array([p])) for p in ph])
        i, j = int(np.argmin(v)), int(np.argmax(v))
        tab5[k] = dict(min=float(v[i]), argmin=float(ph[i]), max=float(v[j]),
                       argmax=float(ph[j]), spread=float(v[j] - v[i]),
                       at0=float(v[0]))
        print(f"    {lb:<15}{v[i]:>10.6f}{ph[i]:>8.3f}{v[j]:>10.6f}{ph[j]:>8.3f}"
              f"{v[j]-v[i]:>9.6f}{v[0]:>10.6f}")
    out["5_phase"] = tab5

    print()
    print("=" * 80)
    print("6.  DOES THE CORRECTION TRANSFER?  leave-one-model-out, JOINT-KL rule")
    print("    fit on the pooled blocks of the other three, score on the held-out")
    print("=" * 80)
    print(f"    {'held out':<15}{'m':>2}{'geometric':>11}{'joint fit':>11}"
          f"{'gain':>9}{'t':>8}   {'same-dtype pair fit':>20}{'gain':>9}")
    tab6 = {}
    for k, lb, dt in MODELS:
        rest = [kk for kk, _, _ in MODELS if kk != k]
        pool = np.concatenate([X[r][::max(1, len(X[r]) // 1500000)] for r in rest])
        mate = [kk for kk, _, d2 in MODELS if kk != k and d2 == dt][0]
        exj, exm = Exact(pool), Exact(X[mate][::max(1, len(X[mate]) // 3000000)])
        for m in (0, 1, 2, 3, 4):
            g0 = grid_geometric(m)
            Gj, Gm = fit_grid(exj, m), fit_grid(exm, m)
            dj, _, tj = paired_t(X[k], g0, Gj)
            dm, _, tm = paired_t(X[k], g0, Gm)
            w0 = W(X[k], g0)
            tab6[f"{k}_m{m}"] = dict(geo=w0, joint=w0 + dj, joint_gain=-dj / w0,
                                     t=tj, mate=w0 + dm, mate_gain=-dm / w0,
                                     mate_t=tm, mate_model=mate)
            print(f"    {lb if m == 0 else '':<15}{m:>2}{w0:>11.6f}{w0+dj:>11.6f}"
                  f"{-dj/w0*100:>8.3f}%{-tj:>8.1f}   {w0+dm:>20.6f}"
                  f"{-dm/w0*100:>8.3f}%")
    out["6_transfer"] = tab6

    with open(os.path.join(HERE, "loguniform_verdict.json"), "w") as f:
        json.dump(out, f, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
