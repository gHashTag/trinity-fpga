#!/usr/bin/env python3
"""Check T39 — the geometric scale grid uniquely minimises expected headroom waste.

T38 (SCALE_PHASE_THEOREM) says an E8M0 scale wastes 1 - frac(log2 a - log2 T)
bits of headroom on each block, and 1/2 bit in expectation over log-uniform block
maxima. T37 (GEOMETRIC_SCALE) measured that a geometric scale grid beats a float
one at every width, the advantage rising to 1/ln 2.

T39 derives the second from the first. A scale grid with 2^m points per octave
partitions each octave of log-magnitude into 2^m gaps g_1..g_{2^m} summing to 1
bit. A block whose maximum lands inside gap i is rounded up to the top of that
gap, so its waste is uniform on [0, g_i]. Weighting each gap by its own length
(log-uniform maxima land in a gap in proportion to its length):

    E[waste] = sum_i g_i * (g_i / 2) / sum_i g_i = (1/2) * sum_i g_i^2

Minimising sum g_i^2 subject to sum g_i = 1 gives g_i = 2^-m for every i, i.e.
EQUAL SPACING IN LOG — a geometric grid — with

    E[waste] = 2^-(m+1)  bits,

and any other grid is strictly worse by (1/2)(sum g_i^2 - 2^-m) > 0.

The claims checked here:
  C1  the formula E[waste] = (1/2) sum g_i^2 matches a direct simulation
  C2  the geometric grid attains 2^-(m+1) exactly
  C3  a float grid (equally spaced MANTISSA, i.e. 2^e(1+j/2^m)) is strictly worse
      at every m >= 1, and equals the geometric grid only at m = 0
  C4  m = 0 recovers T38's 1/2 bit for both grids, since one gap cannot be unequal
  C5  no random grid beats the geometric one (the optimality is not an artefact
      of comparing against one alternative)

    python3 verify_grid_optimality.py
"""
import math
import random
import sys


def gaps_geometric(m):
    """2^m equal gaps, in bits."""
    n = 2 ** m
    return [1.0 / n] * n


def gaps_float(m):
    """The gaps a float scale 2^e (1 + j/2^m) makes, in bits."""
    n = 2 ** m
    pts = [1.0 + j / n for j in range(n)] + [2.0]
    return [math.log2(pts[i + 1] / pts[i]) for i in range(n)]


def expected_waste_formula(gaps):
    return 0.5 * sum(g * g for g in gaps)


def expected_waste_simulated(gaps, n=400000, seed=11):
    """Direct simulation: drop log-uniform maxima, round up to the grid."""
    rng = random.Random(seed)
    edges = [0.0]
    for g in gaps:
        edges.append(edges[-1] + g)
    total = 0.0
    for _ in range(n):
        x = rng.random()                      # position within the octave, bits
        for e in edges[1:]:
            if x <= e:
                total += e - x
                break
    return total / n


def main():
    fails = 0

    print("C1  formula vs direct simulation of the rounding")
    print(f"    {'grid':<12} {'m':>2} {'formula':>10} {'simulated':>11} {'|diff|':>9}")
    for m in (0, 1, 2, 3):
        for name, gf in (("geometric", gaps_geometric), ("float", gaps_float)):
            g = gf(m)
            f = expected_waste_formula(g)
            s = expected_waste_simulated(g)
            d = abs(f - s)
            ok = d < 3e-3
            fails += not ok
            print(f"    {name:<12} {m:>2} {f:>10.6f} {s:>11.6f} {d:>9.2e}"
                  f"  {'ok' if ok else 'FAIL'}")

    print("\nC2/C3  geometric attains 2^-(m+1); float is strictly worse for m >= 1")
    print(f"    {'m':>2} {'2^-(m+1)':>10} {'geometric':>11} {'float':>11} {'float/geo':>10}")
    for m in range(0, 9):
        pred = 2.0 ** (-(m + 1))
        wg = expected_waste_formula(gaps_geometric(m))
        wf = expected_waste_formula(gaps_float(m))
        ok2 = abs(wg - pred) < 1e-12
        ok3 = (wf > wg + 1e-15) if m >= 1 else (abs(wf - wg) < 1e-12)
        fails += (not ok2) + (not ok3)
        print(f"    {m:>2} {pred:>10.7f} {wg:>11.7f} {wf:>11.7f} {wf/wg:>10.6f}"
              f"  {'ok' if ok2 and ok3 else 'FAIL'}")

    print("\nC4  m = 0 is T38's 1/2 bit, and the two grids coincide there")
    w0g = expected_waste_formula(gaps_geometric(0))
    w0f = expected_waste_formula(gaps_float(0))
    ok = abs(w0g - 0.5) < 1e-12 and abs(w0f - 0.5) < 1e-12
    fails += not ok
    print(f"    geometric {w0g:.6f}   float {w0f:.6f}   {'ok' if ok else 'FAIL'}")

    print("\nC5  no random grid beats the geometric one")
    rng = random.Random(7)
    for m in (2, 3, 4):
        wg = expected_waste_formula(gaps_geometric(m))
        n = 2 ** m
        best = None
        for _ in range(20000):
            raw = [rng.random() + 1e-9 for _ in range(n)]
            tot = sum(raw)
            g = [x / tot for x in raw]
            w = expected_waste_formula(g)
            if best is None or w < best:
                best = w
        ok = best >= wg - 1e-12
        fails += not ok
        print(f"    m={m}  geometric {wg:.7f}   best of 20000 random {best:.7f}"
              f"  {'ok' if ok else 'FAIL — a random grid beat it'}")

    print("\nC6  the float/geometric ratio has a closed form: 1/(2 ln^2 2)")
    target = 1.0 / (2.0 * math.log(2) ** 2)
    print(f"    predicted limit 1/(2 ln^2 2) = {target:.9f}")
    for m in (6, 10, 14, 18):
        r = expected_waste_formula(gaps_float(m)) / expected_waste_formula(gaps_geometric(m))
        d = abs(r - target)
        ok = d < 10.0 ** (-(min(m, 12) // 2))
        fails += not ok
        print(f"    m={m:<3} ratio {r:.9f}   |ratio - limit| {d:.2e}  {'ok' if ok else 'FAIL'}")

    print()
    if fails:
        print(f"RESULT: {fails} check(s) FAILED — T39 as stated does not hold.")
        return 1
    print("RESULT: T39 holds. Expected headroom waste is (1/2) sum g_i^2, minimised")
    print("        uniquely by equal log-spacing at 2^-(m+1) bits; a float scale is")
    print("        strictly worse at every mantissa width, and m = 0 recovers T38's")
    print("        1/2 bit for E8M0. The float penalty converges to 1/(2 ln^2 2),")
    print("        about 4.07 percent -- a different constant from T37's 1/ln 2,")
    print("        because T37 measures accuracy and this measures headroom.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
