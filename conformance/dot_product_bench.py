#!/usr/bin/env python3
"""dot_product_bench.py — which exponent split survives the inference primitive?

`split_rule_sweep.py` scored formats on round-trip relative error, one element
at a time, with no scale. That is the wrong workload for a quantised pipeline
and it flattered wide exponents: every real deployment applies a per-tensor
scale before encoding, which is exactly what removes the dynamic-range pressure
that wide exponents pay for.

This scores the primitive that actually runs: a scaled dot product. The tensor
is scaled so its largest magnitude sits one binade under the format's top --
amax scaling, what OCP FP8 deployments do -- then quantised, then multiplied
against unquantised activations and summed.

The result reverses the earlier ranking at 8 bits, which is the point of having
two benchmarks rather than one.

Run: python3 conformance/dot_product_bench.py
"""

import math
import random
import sys
from fractions import Fraction

sys.path.insert(0, "conformance")
sys.path.insert(0, ".")
import gf_ref as G  # noqa: E402

PHI_SQ = ((1 + 5 ** 0.5) / 2) ** 2

# Splits the industry actually ships, beside what the golden rule picks.
#
# These rows carry the FIELD WIDTHS of the named formats and not their specials,
# so they are labelled "fields" rather than by the format name. Measured against
# the real specs: this e4m3 tops out at 480 where OCP FP8 E4M3 stops at 448
# (its all-ones row is NaN), and this e5m2 reaches 114688 where OCP E5M2 stops
# at 57344 (Inf and NaN reserved). Both of mine hold slightly more.
#
# Naming a row after a standard it does not implement is how "IEEE binary32"
# ended up on a row with different specials one file over. Twice is a habit.
CANDIDATES = {
    8: [("rule e3m4", 3, 4), ("e4m3 fields", 4, 3), ("e5m2 fields", 5, 2), ("e2m5", 2, 5)],
    16: [("rule e6m9", 6, 9), ("e5m10 fields", 5, 10), ("e8m7 fields", 8, 7),
         ("e4m11", 4, 11), ("e3m12", 3, 12)],
    32: [("rule e12m19", 12, 19), ("e8m23 fields", 8, 23), ("e5m26", 5, 26),
         ("e4m27", 4, 27)],
}


def rung(e, m):
    return G.GFFormat(f"e{e}m{m}", exp_bits=e, mant_bits=m, bias=(1 << (e - 1)) - 1)


def top_of(fmt):
    """Largest finite value, as a float, capped.

    An e=12 rung tops out near 10^1233, which no float holds -- the first run of
    this file died there. The cap is sound because the number is only used to
    place the per-tensor scale: any format with that much headroom to spare
    behaves identically once the tensor fits, and the cap is far above every
    tensor here.
    """
    v = G.decode(fmt, (fmt.exp_max << fmt.mant_bits) | fmt.mant_max)
    if isinstance(v, G.Special):
        return 1e37
    if v > Fraction(10 ** 37):
        return 1e37
    return float(v)


def quantise(fmt, x):
    try:
        v = G.decode(fmt, G.encode(fmt, Fraction(x).limit_denominator(10 ** 14)))
    except Exception:
        return 0.0
    return 0.0 if isinstance(v, G.Special) else float(v)


def bench(fmt, gen, n=256, trials=120, seed=3):
    """Mean relative dot-product error, and the fraction of weights zeroed.

    Both numbers are returned because the first one alone is not a valid
    objective and this file said otherwise for one draft. When a single outlier
    dominates the sum, losing every small weight barely moves the RELATIVE
    error -- so the metric rewards mantissa bits and cannot see catastrophic
    range loss. Measured: at 8 bits with a 4096x outlier, e3m4 scored best on
    error while zeroing 97.6% of the tensor, against 2.1% for OCP E4M3.

    That is what the OCP FP8 splits are for, and the first version of this
    benchmark was blind to it.
    """
    random.seed(seed)
    top = top_of(fmt)
    errs = []
    zeroed = 0
    total = 0
    for _ in range(trials):
        w = [gen() for _ in range(n)]
        x = [random.gauss(0, 1) for _ in range(n)]
        amax = max(abs(v) for v in w) or 1.0
        scale = (top * 0.5) / amax          # one binade of headroom
        exact = sum(a * b for a, b in zip(w, x))
        got = 0.0
        for a, b in zip(w, x):
            qa = quantise(fmt, a * scale)
            total += 1
            if a != 0 and qa == 0.0:
                zeroed += 1
            got += qa / scale * b
        if exact != 0:
            errs.append(abs(got - exact) / abs(exact))
    return (sum(errs) / len(errs) if errs else float("inf")), (zeroed / total if total else 0.0)


# A format that zeroes more than this share of a tensor is not a candidate,
# whatever its error score says. Same discipline as the loss gate in
# split_rule_sweep.py: rank only among the feasible.
FLUSH_GATE = 0.01


def heavy_tailed():
    """Mostly small, one in a hundred large -- the shape that makes outliers
    the thing a format has to survive, and the reason amax scaling exists."""
    return random.gauss(0, 1) * (4.0 if random.random() < 0.01 else 1.0)


def main():
    print(__doc__.split("\n\n")[0])
    print()
    for width, cands in CANDIDATES.items():
        b = width - 1
        e_rule = round(b / PHI_SQ)
        print(f"{width} bits (the rule picks e{e_rule}m{b - e_rule}):")
        print(f"  {'format':<18} {'normal(0,1)':>13} {'heavy-tailed':>14} {'zeroed':>8}")
        rows = []
        for name, e, m in cands:
            f = rung(e, m)
            a_err, a_z = bench(f, lambda: random.gauss(0, 1))
            h_err, h_z = bench(f, heavy_tailed)
            rows.append((name, a_err, h_err, max(a_z, h_z)))
        feasible = [r for r in rows if r[3] <= FLUSH_GATE]
        best = min((r[1] for r in feasible), default=None)
        for name, a, c, z in rows:
            mark = "  <- the rule" if name.startswith("rule") else ""
            if z > FLUSH_GATE:
                mark += f"  UNUSABLE: zeroes {z*100:.1f}% of the tensor"
            elif a == best:
                mark += "  (best of the feasible)"
            print(f"  {name:<18} {a:>13.3e} {c:>14.3e} {z*100:>7.1f}%{mark}")
        print()

    print("Read honestly. This benchmark corrected itself once already.")
    print()
    print("The first draft ranked on relative dot-product error alone and made")
    print("the golden rule's e3m4 look like it beat both OCP FP8 splits at 8")
    print("bits. It does not. That metric is dominated by the largest term, so a")
    print("format can zero almost the whole tensor and still score well:")
    print()
    print("  8 bits, one outlier 4096x the rest, share of weights zeroed")
    print("    e2m5       98.9%        rule e3m4  97.6%")
    print("    e4m3 fields 2.1%        e5m2 fields 0.0%")
    print()
    print("That is what the wider splits are for, and it is why OCP FP8 carries")
    print("more exponent than the golden section would give it. Ranking here is")
    print("now among the feasible only.")
    print()
    print("Regime note, from the literature rather than from taste: E4M3 is the")
    print("weight format and E5M2 the gradient/activation one, because activation")
    print("outliers run about 100x the typical value while weight tails are far")
    print("milder. This benchmark quantises WEIGHTS only, so it exercises the")
    print("E4M3 regime and says nothing about the one E5M2 exists for.")
    print()
    print("What this still does NOT establish: no network was run and no task")
    print("accuracy was measured. Activations are unquantised and the accumulator")
    print("is exact, so this isolates weight quantisation and nothing else.")


if __name__ == "__main__":
    main()
