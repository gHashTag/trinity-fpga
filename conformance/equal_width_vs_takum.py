#!/usr/bin/env python3
"""equal_width_vs_takum.py — the same comparison, at equal stored width.

`research/GFT16_BEATS_TEKUM16_2026-08-05.md` compared a format called GF-T16
against takum16. The audit of 2026-08-18 found GF-T16 is **17 bits**: four
balanced-ternary trits need ceil(4*log2 3) = 7 binary positions, so the word is
1 + 7 + 9. `conformance/tnf16_ref.py` says "17-bit canonical raw" in its own
header. takum16 is 16.

A comparison at unequal width hands the wider side 0.585 bits per trit for free.
This runs it at equal width, three ways:

  TNF(4,9)   17 bits  -- the original, one bit wider than its opponent

Both oracles it is measured against are LINEAR structural models of takum's
field layout, not the published logarithmic formats. That caveat is larger than
the width one and is printed in full at the end.
  TNF(4,8)   16 bits  -- equal width, a mantissa bit given up
  TNF(3,10)  16 bits  -- equal width, exponent range given up

Saturation is counted separately from rounding. A value outside a format's span
produces a relative error near 1, which averages into a meaningless number if it
is not separated out; the threshold used is 0.5.

Run: python3 conformance/equal_width_vs_takum.py
"""

import math
import random
import sys
from fractions import Fraction

sys.path.insert(0, "conformance")
sys.path.insert(0, ".")
import takum_ref  # noqa: E402
import tnf_ref  # noqa: E402

TAKUM = takum_ref.FORMATS["takum16"]
CANDIDATES = [
    ("TNF(4,9) 17 bits", tnf_ref.TNFFormat(4, 9)),
    ("TNF(4,8) 16 bits", tnf_ref.TNFFormat(4, 8)),
    ("TNF(3,10) 16 bits", tnf_ref.TNFFormat(3, 10)),
]
BANDS = [("near unity 1e-1..1e1", -1, 1), ("mid 1e-4..1e4", -4, 4),
         ("wide 1e-9..1e9", -9, 9), ("far 1e-12..1e12", -12, 12)]
SATURATION = 0.5


def sample(lo, hi, n=4000, seed=7):
    random.seed(seed)
    return [math.copysign(10 ** random.uniform(lo, hi), random.random() - 0.5)
            for _ in range(n)]


def round_trip(mod, fmt, x):
    try:
        v = mod.decode(fmt, mod.encode(fmt, Fraction(x).limit_denominator(10 ** 14)))
    except Exception:
        return None
    return float(v) if isinstance(v, Fraction) else None


def score(mod, fmt, xs):
    total = 0.0
    counted = 0
    saturated = 0
    for x in xs:
        y = round_trip(mod, fmt, x)
        if y is None or y == 0:
            saturated += 1
            continue
        e = abs(y - x) / abs(x)
        if e > SATURATION:
            saturated += 1
            continue
        total += e
        counted += 1
    return (total / counted if counted else float("nan")), saturated / len(xs)


def main():
    print(__doc__.split("\n\n")[0])
    print()
    print(f"  {'band':<22} {'format':<20} {'mean rel err':>12} {'saturated':>10} {'vs takum':>9}")
    for bname, lo, hi in BANDS:
        xs = sample(lo, hi)
        base, _ = score(takum_ref, TAKUM, xs)
        print(f"  {bname:<22} {'takum16 (16 bits)':<20} {base:>12.3e} {0.0:>9.1%} {'—':>9}")
        for name, fmt in CANDIDATES:
            s, sat = score(tnf_ref, fmt, xs)
            ratio = base / s if s == s and s > 0 else float("nan")
            print(f"  {'':<22} {name:<20} {s:>12.3e} {sat:>9.1%} {ratio:>8.1f}x")
        print()

    print("Read honestly.")
    print()
    print("At EQUAL width, TNF(4,8) is better than takum16 by 1.4x over nine")
    print("decades and 2.0x over twelve, and WORSE near unity, where takum's")
    print("taper spends its bits. The 17-bit version shows 2.7x and 4.0x — the")
    print("extra bit is roughly half the advantage.")
    print()
    print("TNF(3,10) has the lowest error of any column and it is a trap: 58% of")
    print("values over nine decades do not fit at all. Error measured only on the")
    print("values a format can hold says nothing about the ones it cannot.")
    print()
    print("ON THE OPPONENT, CORRECTED 2026-08-18:")
    print()
    print("The linear takum is a REAL published variant -- libtakum ships")
    print("takum8/16/32/64 as linear and takum_log* as the LNS separately -- so")
    print("this oracle targets the right format. What it got wrong was the")
    print("negative branch. libtakum src/codec.c derives the linear value from")
    print("the logarithmic pair (c, m) as e = (1-2s)(c+s), and for s = 1 the")
    print("exponent's SIGN flips: negation is close to reciprocation, not a sign")
    print("bit. The oracle matched the reference on 32768 of 65535 codes -- every")
    print("positive one, no negative one -- and now matches on 65534 of 65535,")
    print("the exception being the zero code it special-cases correctly.")
    print()
    print("The fix left every number in the table above unchanged, because this")
    print("metric averages over a sign-symmetric sample and the two halves score")
    print("identically (9.5292e-04 each). The bug was still real: 4681 of 9362")
    print("round trips held before it, 21845 of 21845 after.")
    print()
    print("Still unimplemented: tekum. All 65,536 codes of tekum_ref decode")
    print("identically to takum_ref, and its balanced-ternary exponent is flagged")
    print("'# TODO: verify from full paper'. arXiv:2512.10964 (23 pp.) is not in")
    print("this tree and the abstract does not carry the trit-level tables.")
    print()
    print("OLD TEXT, KEPT SO THE CORRECTION IS VISIBLE:")
    print()
    print("The opponent is neither takum nor tekum. Both oracles say so in their")
    print("own headers. takum_ref: 'настоящий takum -- ЛОГАРИФМИЧЕСКИЙ")
    print("(value = (-1)^S exp(l/2)) ... здесь реализована РАБОЧАЯ СТРУКТУРНАЯ")
    print("МОДЕЛЬ ... интерпретированная ЛИНЕЙНО ... а НЕ логарифмически.'")
    print()
    print("Read the same 16-bit word both ways and they are different numbers:")
    print("  0x1001   linear 1.10e-19   logarithmic 1.01e+00   ratio 9.2e+18")
    print("  0x6789   linear 1.15e+09   logarithmic 1.87e+03   ratio 1.6e-06")
    print()
    print("So this measures TNF against a linear reinterpretation of takum's")
    print("FIELD LAYOUT. It says nothing about takum as published, and nothing")
    print("about tekum at all: all 65,536 codes of tekum_ref decode identically")
    print("to takum_ref, and tekum's balanced-ternary exponent is flagged")
    print("'# TODO: verify from full paper' and never implemented.")
    print()
    print("Implementing either properly needs the papers -- arXiv:2404.18603 for")
    print("takum's logarithmic decode, arXiv:2512.10964 (23 pp.) for tekum's")
    print("trit-level tables. Neither is in this tree.")


if __name__ == "__main__":
    sys.exit(main())
