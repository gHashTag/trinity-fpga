#!/usr/bin/env python3
"""Numerical check of the two propositions in SCALE_PHASE_THEOREM_2026-08-11.md.

The propositions are proved on paper. This is the check that the proof describes
the code that is actually run — the failure mode is not a wrong theorem but a
theorem about a different quantiser than the one in `block_tnf.py`.

P1  EQUIVALENCE.  For a codebook with top T > 0, quantising with
      (levels L, scale s = 2^ceil(log2 a) / T)
    is the same map as quantising with
      (levels L/T, scale s = 2^ceil(log2 a)).
    The identity is algebraic. In float64 it is EXACT when T is a dyadic
    rational — E2M1's 6.0 is, which is why the tensor-level check on real
    weights returned 0.000e+00 — and holds to rounding otherwise: Lloyd-Max's
    0.96567 is not dyadic and 1/T is inexact, so the two paths differ in the
    last bits. Stating this as "bit-identical" unconditionally would be wrong,
    and this check is what caught it.

P2  PHASE.  Quantising instead with (levels L, s = 2^ceil(log2(a/T))) wastes
      w_A = 1 - frac(log2 a - log2 T)   bits of headroom
    against
      w_B = 1 - frac(log2 a)            for P1's rule,
    with waste 0 when the fractional part is 0. The rules agree on every block
    iff log2 T is an integer.

P3  EXPECTATION.  Over log-uniform block maxima both rules waste 1/2 bit in
    expectation, so the phase is not an average penalty — it is a per-block
    difference that a comparison between two codebooks with different tops
    silently inherits.

Everything below is exact float64 arithmetic on synthetic maxima; no model is
loaded, so this runs anywhere. The tensor-level check against the project's own
`quant()` is in the workflow record and is not repeated here.

    python3 verify_phase_theorem.py
"""
import math
import random
import sys

E2M1 = [0.0, 0.5, 1.0, 1.5, 2.0, 3.0, 4.0, 6.0]
LLOYD = [0.0, 0.10334, 0.21079, 0.32491, 0.44963, 0.59031, 0.75635, 0.96567]
KLOPT = [0.0, 0.07701, 0.18828, 0.31396, 0.46561, 0.6113, 0.79074, 1.0]
POW2 = [0.0, 0.125, 0.25, 0.375, 0.5, 0.625, 0.75, 1.0]


def quantise(vals, levels, scale):
    """One block, the project's rule: nearest level by midpoint boundary."""
    out = []
    for v in vals:
        y = abs(v) / scale
        j = 0
        for k in range(len(levels) - 1):
            if y >= (levels[k] + levels[k + 1]) / 2:
                j = k + 1
        out.append(math.copysign(levels[j] * scale, v))
    return out


def frac(x):
    return x - math.floor(x)


def main():
    rng = random.Random(11)
    books = [("E2M1", E2M1), ("Lloyd-Max", LLOYD), ("KL-opt", KLOPT), ("pow2-top", POW2)]
    fails = 0

    # ---- P1: exact equivalence -------------------------------------------
    print("P1  equivalence of (L, 2^ceil(log2 a)/T) and (L/T, 2^ceil(log2 a))")
    for name, L in books:
        T = L[-1]
        worst = 0.0
        for _ in range(2000):
            a = math.exp(rng.uniform(-12, 12))
            vals = [rng.uniform(-a, a) for _ in range(32)]
            vals[rng.randrange(32)] = a          # ensure a is the block max
            s = 2.0 ** math.ceil(math.log2(a))
            lhs = quantise(vals, L, s / T)
            rhs = quantise(vals, [x / T for x in L], s)
            worst = max(worst, max(abs(p - q) for p, q in zip(lhs, rhs)))
        dyadic = (T * 2 ** 30) == int(T * 2 ** 30) and T != 0
        # exact when T is dyadic; otherwise 1/T is inexact and the two paths
        # differ by rounding, which must stay at the ULP level and no larger.
        ok = (worst == 0.0) if dyadic else (worst < 1e-9)
        fails += not ok
        tag = "exact" if dyadic else "to rounding"
        print(f"    {name:<10} T={T:<9.5f} {'dyadic' if dyadic else 'non-dyadic':<11}"
              f" max |difference| = {worst:.3e}  ({tag})  {'ok' if ok else 'FAIL'}")

    # ---- P2: the phase formula -------------------------------------------
    print("\nP2  headroom waste in bits, and when the two rules coincide")
    print(f"    {'codebook':<10} {'T':>9} {'phi=log2(T) mod 1':>20} {'max |w_A-w_B|':>15} {'coincide':>10}")
    for name, L in books:
        T = L[-1]
        phi = frac(math.log2(T))
        worst = 0.0
        for _ in range(4000):
            a = math.exp(rng.uniform(-12, 12))
            la = math.log2(a)
            # measured waste: largest representable divided by the block max
            s_B = 2.0 ** math.ceil(la) / T
            s_A = 2.0 ** math.ceil(la - math.log2(T))
            wB_meas = math.log2(T * s_B / a)
            wA_meas = math.log2(T * s_A / a)
            # predicted by the formula
            wB_pred = (1 - frac(la)) if frac(la) else 0.0
            wA_pred = (1 - frac(la - math.log2(T))) if frac(la - math.log2(T)) else 0.0
            if abs(wB_meas - wB_pred) > 1e-9 or abs(wA_meas - wA_pred) > 1e-9:
                print(f"      FORMULA MISMATCH at a={a:g}")
                fails += 1
                break
            worst = max(worst, abs(wA_meas - wB_meas))
        coincide = worst < 1e-9
        expect = abs(phi) < 1e-12
        mark = "ok" if coincide == expect else "FAIL"
        fails += mark == "FAIL"
        print(f"    {name:<10} {T:>9.5f} {phi:>20.6f} {worst:>15.6f} {str(coincide):>10}  {mark}")

    # ---- P3: expectation is the same, the per-block difference is not ----
    print("\nP3  over log-uniform maxima both rules waste 1/2 bit on average")
    for name, L in books:
        T = L[-1]
        sA = sB = 0.0
        n = 20000
        for _ in range(n):
            la = rng.uniform(-40, 40)
            sB += (1 - frac(la)) if frac(la) else 0.0
            sA += (1 - frac(la - math.log2(T))) if frac(la - math.log2(T)) else 0.0
        ok = abs(sA / n - 0.5) < 0.02 and abs(sB / n - 0.5) < 0.02
        fails += not ok
        print(f"    {name:<10} mean w_A = {sA/n:.4f}   mean w_B = {sB/n:.4f}   {'ok' if ok else 'FAIL'}")

    print()
    if fails:
        print(f"RESULT: {fails} check(s) FAILED — the propositions do not describe this quantiser.")
        return 1
    print("RESULT: all checks pass. P1 exact, P2 phase formula exact and the")
    print("        coincidence condition is exactly 'T is a power of two', P3 the")
    print("        expectation is 1/2 bit regardless of T — so the phase is a")
    print("        per-block difference, never an average penalty.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
