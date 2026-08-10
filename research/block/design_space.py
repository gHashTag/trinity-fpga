#!/usr/bin/env python3
"""Using the finite-N formula to DESIGN a codebook, not merely to rank existing ones.

Everything so far measured formats other people invented. The formula's real payoff is that
it identifies the OPTIMAL codebook in closed form, and that optimum turns out to depend on
the block size -- which no published 4-bit format accounts for.

DERIVATION.

Work in the max-normalised domain. Set the top level t_max = 1 (without loss of generality:
if the optimiser returned a top level l < 1, the scale s = a/l reproduces the maximum just
the same, so pinning it is a reparametrisation, not a constraint). For a block of K iid
samples of density p with block maximum a, the scale is s = a and the normalised values are
y = x/a. Conditional on a, a non-maximal element has density

    p(y | a) = a * p(a*y) / (2F(a) - 1),        |y| <= 1

and a itself has the maximum density f_a(a) = K * 2p(a) * (2F(a)-1)^(K-1). Marginalising:

    p_eff(y) = INTEGRAL_0^inf  f_a(a) * a * p(a*y) / (2F(a)-1)  da .        (*)

THEOREM (optimal block-scaled codebook). The N-level codebook minimising block-scaled MSE
is the Lloyd-Max quantizer of p_eff with its top level pinned at 1. Since f_a depends on K,
p_eff depends on K, and therefore SO DOES THE OPTIMAL CODEBOOK.

COROLLARY (why NF4 is the wrong shape here). NF4 places levels at quantiles of the
UNCONDITIONAL Normal. Under block-max scaling the quantizer never sees that density -- it
sees p_eff, which is the Normal conditioned on lying below the block maximum and rescaled
by it. p_eff is strictly flatter: dividing by a spreads small-a blocks out over the whole
[-1,1] range. So a codebook tuned to the unconditional Normal over-concentrates levels near
zero. The size of the effect is what this script measures.

The claim is falsifiable in the obvious way: derive the codebook from theory alone, then
measure it against the incumbents on data it never saw. If it does not win, the theorem is
wrong.
"""
import math
import random

random.seed(20260809)

NBIN = 3000          # resolution of p_eff on [0, 1]
NA = 1200            # resolution of the outer integral over the block maximum


# ---------------------------------------------------------------- densities
def gaussian():
    return (lambda x: math.exp(-x * x / 2) / math.sqrt(2 * math.pi),
            lambda a: math.erf(a / math.sqrt(2)),
            6.0)


def laplace():
    return (lambda x: 0.5 * math.exp(-abs(x)),
            lambda a: 1 - math.exp(-a),
            14.0)


def student_t3():
    nu = 3.0
    c = math.gamma((nu + 1) / 2) / (math.sqrt(nu * math.pi) * math.gamma(nu / 2))
    pdf = lambda x: c * (1 + x * x / nu) ** (-(nu + 1) / 2)
    def cdf_abs(a):                      # numeric, symmetric
        n, h, s = 400, a / 400, 0.0
        for i in range(n):
            s += pdf((i + 0.5) * h) * h
        return 2 * s
    return pdf, cdf_abs, 30.0


DISTS = {"gaussian": gaussian(), "laplace": laplace(), "student-t3": student_t3()}


# ---------------------------------------------------------------- p_eff
def p_eff(dist, K):
    """Effective density seen by the quantizer, on the half-line [0,1]. Returns (vals, dy)."""
    pdf, cdf_abs, a_hi = dist
    dy = 1.0 / NBIN
    vals = [0.0] * NBIN
    da = a_hi / NA
    for ia in range(1, NA + 1):
        a = ia * da
        Fa = cdf_abs(a)
        if Fa <= 1e-15:
            continue
        f_a = K * (2 * pdf(a)) * (Fa ** (K - 1))
        if f_a <= 0:
            continue
        w = f_a * da * a / Fa
        for iy in range(NBIN):
            y = (iy + 0.5) * dy
            vals[iy] += w * 2 * pdf(a * y)       # factor 2: folded to |y|
    s = sum(vals) * dy
    return [v / s for v in vals], dy


# ---------------------------------------------------------------- Lloyd-Max
def lloyd(vals, dy, nlev, pin_top=True, iters=200):
    """Lloyd-Max on a discretised density over [0,1]. Level 0 is pinned at 0 (sign symmetry)."""
    lv = [i / (nlev - 1) for i in range(nlev)]
    for _ in range(iters):
        bnd = [(lv[i] + lv[i + 1]) / 2 for i in range(nlev - 1)]
        num = [0.0] * nlev
        den = [0.0] * nlev
        j = 0
        for iy in range(NBIN):
            y = (iy + 0.5) * dy
            while j < nlev - 1 and y > bnd[j]:
                j += 1
            w = vals[iy] * dy
            num[j] += w * y
            den[j] += w
        new = [num[i] / den[i] if den[i] > 0 else lv[i] for i in range(nlev)]
        new[0] = 0.0
        if pin_top:
            new[-1] = 1.0
        new = sorted(new)
        if max(abs(new[i] - lv[i]) for i in range(nlev)) < 1e-12:
            lv = new
            break
        lv = new
    return lv


# ---------------------------------------------------------------- incumbents
def fp_levels(eb, mb):
    """Element magnitudes INCLUDING SUBNORMALS.

    The original version emitted only normal numbers, which cost E2M1 its 0.5 level -- 7
    magnitudes instead of 8. That single missing level made the reference format measure 37%
    worse than it is, and accounted for essentially the whole advantage this programme
    claimed. Subnormals are m/2^mb * 2^(1-bias) for m = 1 .. 2^mb - 1.
    """
    bias = (1 << (eb - 1)) - 1
    out = {0.0}
    for m in range(1, 1 << mb):
        out.add((m / (1 << mb)) * 2.0 ** (1 - bias))
    for e in range(1 - bias, (1 << eb) - bias):
        for m in range(1 << mb):
            out.add((1 + m / (1 << mb)) * 2.0 ** e)
    lv = sorted(out)
    return [v / max(lv) for v in lv]


def nf4_style(dist):
    """The NF4 PRINCIPLE -- levels at quantiles of the UNCONDITIONAL density.

    This is our own construction of that principle for a symmetric 8-magnitude codebook, not
    the published QLoRA table (which is asymmetric, 16 values, and tuned to N(0,1)); quoting
    numbers from memory would be a guess. What is being tested is the principle: place levels
    by unconditional quantiles rather than by the conditional density (*).
    """
    pdf, cdf_abs, a_hi = dist
    n, h = 20000, a_hi / 20000
    xs, cum, c = [], [], 0.0
    for i in range(n):
        x = (i + 0.5) * h
        c += 2 * pdf(x) * h
        xs.append(x)
        cum.append(c)
    def quant(q):
        for i, v in enumerate(cum):
            if v >= q * cum[-1]:
                return xs[i]
        return xs[-1]
    lv = [0.0] + [quant((i + 0.5) / 8) for i in range(1, 8)]
    return [v / max(lv) for v in lv]


# ---------------------------------------------------------------- evaluation
def q(y, lv):
    s = -1.0 if y < 0 else 1.0
    a = abs(y)
    lo, hi = 0, len(lv) - 1
    while lo < hi:                       # nearest level, binary search
        mid = (lo + hi) // 2
        if lv[mid] < a:
            lo = mid + 1
        else:
            hi = mid
    cands = [lv[max(0, lo - 1)], lv[lo]]
    return s * min(cands, key=lambda L: abs(L - a))


def sample(name, n):
    if name == "gaussian":
        return [random.gauss(0, 1) for _ in range(n)]
    if name == "laplace":
        return [random.expovariate(1.0) * (1 if random.random() < .5 else -1) for _ in range(n)]
    out = []
    for _ in range(n):                   # Student-t3 via normal / sqrt(chi2/nu)
        z = random.gauss(0, 1)
        g = sum(random.gauss(0, 1) ** 2 for _ in range(3))
        out.append(z / math.sqrt(g / 3))
    return out


def measured(lv, data, K):
    tot, nb = 0.0, 0
    top = max(lv)
    for i in range(0, len(data) - K, K):
        blk = data[i:i + K]
        amax = max(abs(v) for v in blk)
        if amax == 0:
            continue
        s = amax / top
        tot += sum((s * q(v / s, lv) - v) ** 2 for v in blk) / K
        nb += 1
    return tot / nb


print("Designing the codebook from the theory, then measuring it out-of-sample\n")
print("MSE per element, block-scaled, relative to E2M1 (the MXFP4 element). Lower is better.\n")

DATA = {d: sample(d, 400000) for d in DISTS}

for dname, dist in DISTS.items():
    print(f"  {dname}")
    for K in (16, 32, 64):
        lv_opt = lloyd(*p_eff(dist, K), nlev=8)
        cands = {
            "e2m1 (MXFP4)": fp_levels(2, 1),
            "e1m2": fp_levels(1, 2),
            "e3m0": fp_levels(3, 0),
            "int4": [i / 7 for i in range(8)],
            "nf4-style": nf4_style(dist),
            "DERIVED": lv_opt,
        }
        m = {n: measured(lv, DATA[dname], K) for n, lv in cands.items()}
        ref = m["e2m1 (MXFP4)"]
        best = min(m, key=lambda n: m[n])
        row = "  ".join(f"{n}:{m[n]/ref:.3f}" for n in cands)
        print(f"    K={K:<4} {row}")
        print(f"    {'':<7} best = {best}"
              + (f"   ({(1 - m[best]/ref)*100:.1f}% below MXFP4)" if best == "DERIVED" else ""))
    lv16 = lloyd(*p_eff(dist, 16), nlev=8)
    lv64 = lloyd(*p_eff(dist, 64), nlev=8)
    drift = max(abs(a - b) for a, b in zip(lv16, lv64))
    print(f"    K-dependence of the optimum: max level shift K=16 -> K=64 is {drift:.4f}")
    print(f"      K=16 " + " ".join(f"{v:.3f}" for v in lv16))
    print(f"      K=64 " + " ".join(f"{v:.3f}" for v in lv64))
    print()
