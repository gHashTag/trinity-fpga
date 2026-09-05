#!/usr/bin/env python3
"""CAMPAIGN C, phase 2 -- redo T39's arithmetic under the MEASURED density.

Phase 1 (loguniform_test.py) rejected uniformity of x = frac(log2 a_max) in all
four models. This phase asks what that does to T39.

General statement (no uniformity assumed).  A scale grid is a set of 2^m points
on the circle R/Z of log-magnitude.  A block at position x is rounded UP to the
next grid point t, wasting t - x bits.  So

    E[waste](G) = sum_i integral over gap i of (top_i - x) p(x) dx.

Under p == 1 this is (1/2) sum g_i^2 and T39 follows.  Under general p, the
high-rate calculus gives, for a grid whose point density is lambda(x),

    E[waste] = (1/2) integral p(x)/lambda(x) dx,     subject to integral lambda = n

minimised by lambda proportional to SQRT(p) -- not by lambda constant -- at

    E[waste]_opt = (1/(2n)) * (integral sqrt(p))^2   <=   1/(2n)

with equality iff p is constant (Cauchy-Schwarz).  So:

  * the GEOMETRIC grid (lambda constant) still costs 1/(2n) = 2^-(m+1) for ANY p,
    because integral p = 1 -- T39's attained value survives verbatim;
  * but it is no longer OPTIMAL: the sqrt(p) grid is better by the factor
    (integral sqrt p)^2 < 1.  T39's uniqueness claim is FALSE off the uniform p.
  * the float penalty becomes E_p[2^-x]/ln2, which equals 1/(2 ln^2 2) only at
    p == 1.

All four statements are checked here against the measured samples: exact
empirical evaluation (searchsorted round-up on the raw x), never a model.

Protocol for anything fitted: grids are fitted on a SMOOTHED (Fourier) density
and then evaluated on the RAW samples, and the exploitability question is asked
leave-one-model-out, the same way JOINT-KL was.
"""
import os, sys, math, json
import numpy as np
from scipy.optimize import minimize

HERE = os.path.dirname(os.path.abspath(__file__))
MODELS = [("smollm2", "SmolLM2-135M"), ("qwen", "Qwen2.5-0.5B"),
          ("pythia", "Pythia-160M"), ("opt", "OPT-125M")]
NH = 12          # harmonics kept in the smoothed density used for FITTING only
MFINE = 400000   # quadrature resolution for the smoothed density


# ---------------------------------------------------------------- grids -----
def grid_geometric(m, rot=0.0):
    n = 1 << m
    return np.sort(np.mod(np.arange(1, n + 1) / n + rot, 1.0))


def grid_float(m, rot=0.0):
    """Scales 2^e (1 + j/2^m): equal in the MANTISSA, so log-positions
    log2(1 + j/2^m).  The point at j=0 is the octave boundary, position 0 == 1."""
    n = 1 << m
    pts = np.log2(1.0 + np.arange(1, n + 1) / n)   # j=1..n ; j=n gives 1.0
    return np.sort(np.mod(pts + rot, 1.0))


def emp_waste_vec(x, G):
    """EXACT per-block waste of grid G on the raw samples x. Round up, wrap."""
    G = np.asarray(G, dtype=np.float64)
    idx = np.searchsorted(G, x, side="left")
    tops = np.where(idx < len(G), G[np.minimum(idx, len(G) - 1)], G[0] + 1.0)
    return tops - x


def emp_waste(x, G):
    return float(np.mean(emp_waste_vec(x, G)))


def paired(x, Ga, Gb):
    """mean(a), mean(b), and the PAIRED standard error of mean(b)-mean(a)."""
    a, b = emp_waste_vec(x, Ga), emp_waste_vec(x, Gb)
    d = b - a
    return float(a.mean()), float(b.mean()), float(d.std(ddof=1) / math.sqrt(len(d)))


# ------------------------------------------------- smoothed density ---------
def fourier(x, nh=NH):
    k = np.arange(1, nh + 1)
    a = np.array([2.0 * np.mean(np.cos(2 * np.pi * kk * x)) for kk in k])
    b = np.array([2.0 * np.mean(np.sin(2 * np.pi * kk * x)) for kk in k])
    return a, b


def dens_on(u, ab):
    a, b = ab
    k = np.arange(1, len(a) + 1)[:, None]
    return 1.0 + (a[:, None] * np.cos(2 * np.pi * k * u[None, :])
                  + b[:, None] * np.sin(2 * np.pi * k * u[None, :])).sum(0)


class Smooth:
    """Piecewise quadrature of a smoothed density; cost of any grid in closed
    form from cumulative sums, so the fit sees a smooth objective."""
    def __init__(self, ab, M=MFINE):
        u = (np.arange(M) + 0.5) / M
        p = np.clip(dens_on(u, ab), 1e-9, None)
        w = p / M
        w = w / w.sum()
        self.u, self.M = u, M
        self.W = np.concatenate([[0.0], np.cumsum(w)])
        self.X = np.concatenate([[0.0], np.cumsum(w * u)])
        self.p = p

    def _seg(self, a, b):
        """integral_a^b (b - x) p(x) dx with 0 <= a <= b <= 1."""
        ia = int(np.searchsorted(self.u, a))
        ib = int(np.searchsorted(self.u, b))
        return b * (self.W[ib] - self.W[ia]) - (self.X[ib] - self.X[ia])

    def cost(self, G):
        G = np.sort(np.mod(np.asarray(G, float), 1.0))
        tot = 0.0
        for i in range(len(G)):
            hi = G[i]
            lo = G[i - 1] if i > 0 else None
            if lo is None:                       # wrapping gap (G[-1], G[0]+1]
                tot += self._seg(0.0, G[0])
                tot += (G[0] + 1.0) * (self.W[-1] - self.W[
                    int(np.searchsorted(self.u, G[-1]))]) - (
                    self.X[-1] - self.X[int(np.searchsorted(self.u, G[-1]))])
            else:
                tot += self._seg(lo, hi)
        return tot

    def sqrt_int(self):
        """(integral sqrt(p))^2 -- the asymptotic optimal/geometric ratio."""
        return float((np.sqrt(self.p).sum() / self.M) ** 2)


def fit_grid(sm, m, n_restart=14, seed=0):
    """Minimise the SMOOTHED cost over all 2^m-point grids (gaps + rotation)."""
    n = 1 << m
    rng = np.random.default_rng(seed)

    def unpack(th):
        g = np.exp(th[:n] - th[:n].max())
        g = g / g.sum()
        return np.mod(np.cumsum(g) + th[n], 1.0)

    def obj(th):
        return sm.cost(unpack(th))

    best, bestv = None, np.inf
    starts = [np.concatenate([np.zeros(n), [0.0]])]
    for _ in range(n_restart - 1):
        starts.append(np.concatenate([rng.normal(0, 0.6, n), rng.uniform(0, 1, 1)]))
    for s in starts:
        r = minimize(obj, s, method="Nelder-Mead",
                     options=dict(maxiter=4000 * (n + 1), xatol=1e-9, fatol=1e-13))
        if r.fun < bestv:
            bestv, best = r.fun, unpack(r.x)
    return np.sort(best), bestv


def main():
    X = {k: np.load(os.path.join(HERE, f"loguniform_x_{k}.npy")) for k, _ in MODELS}
    AB = {k: fourier(X[k]) for k, _ in MODELS}
    SM = {k: Smooth(AB[k]) for k, _ in MODELS}
    out = {}

    print("=" * 78)
    print("A.  T39's ATTAINED VALUE:  is the geometric grid still 2^-(m+1) bits?")
    print("    exact empirical E[waste], raw samples, geometric grid anchored at 0")
    print("=" * 78)
    print(f"{'m':>2} {'2^-(m+1)':>10} " + " ".join(f"{lb.split('-')[0]:>12}" for _, lb in MODELS))
    tabA = {}
    for m in range(0, 9):
        pred = 2.0 ** (-(m + 1))
        row = [emp_waste(X[k], grid_geometric(m)) for k, _ in MODELS]
        tabA[m] = row
        print(f"{m:>2} {pred:>10.6f} " + " ".join(f"{v:>12.6f}" for v in row))
    out["A_geometric_vs_pred"] = {str(m): tabA[m] for m in tabA}

    print()
    print("    relative error of the 2^-(m+1) prediction, per model")
    print(f"{'m':>2} " + " ".join(f"{lb:>14}" for _, lb in MODELS))
    for m in range(0, 9):
        pred = 2.0 ** (-(m + 1))
        print(f"{m:>2} " + " ".join(f"{(v/pred-1)*100:>13.2f}%" for v in tabA[m]))

    print()
    print("=" * 78)
    print("B.  THE FLOAT PENALTY:  is float/geometric still 1/(2 ln^2 2) = 1.0406845?")
    print("    exact empirical ratio, both grids anchored at the octave boundary")
    print("=" * 78)
    print(f"{'m':>2} {'uniform-p':>10} " + " ".join(f"{lb:>14}" for _, lb in MODELS))
    tabB = {}
    for m in range(1, 9):
        base = 0.5 * sum(g * g for g in [1.0 / (1 << m)] * (1 << m))
        fl = 0.5 * sum(g * g for g in np.diff(np.concatenate(
            [[0.0], np.log2(1.0 + np.arange(1, (1 << m) + 1) / (1 << m))])))
        row = []
        for k, _ in MODELS:
            wg = emp_waste(X[k], grid_geometric(m))
            wf = emp_waste(X[k], grid_float(m))
            row.append(wf / wg)
        tabB[m] = row
        print(f"{m:>2} {fl/base:>10.6f} " + " ".join(f"{v:>14.6f}" for v in row))
    out["B_float_over_geometric"] = {str(m): tabB[m] for m in tabB}

    print()
    print("    closed form under measured p:  ratio -> E_p[2^-x] / ln2")
    print(f"    {'model':<16}{'E_p[2^-x]/ln2':>15}{'uniform 1/(2ln^2 2)':>22}{'shift':>9}")
    C = 1.0 / (2 * math.log(2) ** 2)
    predB = {}
    for k, lb in MODELS:
        r = float(np.mean(np.power(2.0, -X[k])) / math.log(2))
        predB[k] = r
        print(f"    {lb:<16}{r:>15.6f}{C:>22.6f}{(r/C-1)*100:>8.2f}%")
    out["B_closed_form"] = predB

    print()
    print("=" * 78)
    print("C.  T39's UNIQUENESS:  does a NON-uniform grid beat the geometric one?")
    print("    asymptotic prediction: optimal/geometric -> (integral sqrt p)^2 <= 1")
    print("=" * 78)
    print(f"    {'model':<16}{'(int sqrt p)^2':>16}{'max gain':>11}")
    sq = {}
    for k, lb in MODELS:
        s = SM[k].sqrt_int()
        sq[k] = s
        print(f"    {lb:<16}{s:>16.6f}{(1-s)*100:>10.3f}%")
    out["C_sqrt_int"] = sq

    print()
    print("    measured, in sample: grid fitted on the model's own smoothed p,")
    print("    then evaluated exactly on that model's raw samples")
    print(f"    {'model':<16}{'m':>3}{'geometric':>12}{'fitted':>12}{'gain':>9}")
    tabC = {}
    for k, lb in MODELS:
        for m in (0, 1, 2, 3):
            G, _ = fit_grid(SM[k], m)
            wg = emp_waste(X[k], grid_geometric(m))
            wf = emp_waste(X[k], G)
            tabC[f"{k}_m{m}"] = dict(geo=wg, fit=wf, gain=1 - wf / wg,
                                     grid=[float(v) for v in G])
            print(f"    {lb:<16}{m:>3}{wg:>12.6f}{wf:>12.6f}{(1-wf/wg)*100:>8.3f}%")
    out["C_in_sample"] = tabC

    print()
    print("=" * 78)
    print("D.  IS THE VIOLATION EXPLOITABLE?  leave-one-model-out, the JOINT-KL rule")
    print("    fit the grid on the pooled smoothed p of three models, evaluate")
    print("    exactly on the raw samples of the held-out fourth")
    print("=" * 78)
    print(f"    {'held out':<16}{'m':>3}{'geometric':>12}{'joint fit':>12}{'gain':>9}"
          f"{'t (paired)':>12}")
    tabD = {}
    for k, lb in MODELS:
        rest = [kk for kk, _ in MODELS if kk != k]
        pooled = np.concatenate([X[r][::max(1, len(X[r]) // 2000000)] for r in rest])
        smp = Smooth(fourier(pooled))
        for m in (0, 1, 2, 3):
            G, _ = fit_grid(smp, m)
            wg, wf, se = paired(X[k], grid_geometric(m), G)
            t = (wf - wg) / se if se > 0 else 0.0
            tabD[f"{k}_m{m}"] = dict(geo=wg, fit=wf, gain=1 - wf / wg, se=se, t=t)
            print(f"    {lb:<16}{m:>3}{wg:>12.6f}{wf:>12.6f}{(1-wf/wg)*100:>8.3f}%"
                  f"{t:>12.1f}")
    out["D_leave_one_out"] = tabD

    print()
    print("=" * 78)
    print("E.  T38 Proposition 3:  'E[waste] = 1/2 for EVERY codebook top T'")
    print("    m=0 phase sweep on raw samples. phi = log2 T mod 1.")
    print("=" * 78)
    ph = np.linspace(0, 1, 41)[:-1]
    print(f"    {'model':<16}{'min over phi':>14}{'at phi':>9}{'max':>10}"
          f"{'at phi':>9}{'spread':>9}")
    tabE = {}
    for k, lb in MODELS:
        vals = np.array([emp_waste(X[k], np.array([p if p > 0 else 1.0]))
                         for p in ph])
        i, j = int(np.argmin(vals)), int(np.argmax(vals))
        tabE[k] = dict(phi=list(map(float, ph)), waste=list(map(float, vals)))
        print(f"    {lb:<16}{vals[i]:>14.6f}{ph[i]:>9.3f}{vals[j]:>10.6f}"
              f"{ph[j]:>9.3f}{vals[j]-vals[i]:>9.6f}")
    out["E_phase_sweep"] = tabE
    print("    (T38 P3 predicts a flat 0.5 at every phi; spread would be 0)")
    print()
    print("    phase of the codebooks T38 tabulates:")
    for nm, T in (("E2M1 as published", 6.0), ("Lloyd-Max as published", 0.96567),
                  ("normalised T=1", 1.0)):
        phi = math.log2(T) % 1.0
        row = " ".join(f"{emp_waste(X[k], np.array([phi if phi > 0 else 1.0])):.4f}"
                       for k, _ in MODELS)
        print(f"      {nm:<24} phi={phi:.4f}   E[waste] = {row}")

    with open(os.path.join(HERE, "loguniform_theory.json"), "w") as f:
        json.dump(out, f, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
