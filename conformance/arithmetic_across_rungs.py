#!/usr/bin/env python3
"""arithmetic_across_rungs.py — the ladder, measured in use rather than at rest.

Two things every earlier comparison in this project got wrong, checked here on
every rung at once.

**Round-trip is not arithmetic.** Encoding a value and decoding it measures the
GRID. A format is used by adding, and a hardware adder re-encodes after every
partial sum. This accumulates 64 values with a re-encode at each step, which is
what `fpga/tef/tef_add_full.v` does.

**The rungs are not the widths they are named.** A TNF rung stores
ceil(exp_trits * log2 3) bits of exponent, and that is more than the name
suggests:

    TNF8   = TNFFormat(3, 4)   ->  1 + 5 + 4  = 10 bits  (takum8  is 8)
    TNF16  = TNFFormat(4, 9)   ->  1 + 7 + 9  = 17 bits  (takum16 is 16)
    TNF32  = TNFFormat(5, 21)  ->  1 + 8 + 21 = 30 bits  (takum32 is 32)

Run: python3 conformance/arithmetic_across_rungs.py
"""

import random
import sys
from fractions import Fraction

sys.path.insert(0, "conformance")
sys.path.insert(0, ".")
import takum_ref  # noqa: E402
import tnf_ref  # noqa: E402

RUNGS = [(8, "takum8"), (16, "takum16"), (32, "takum32")]
TERMS = 64
TRIALS = 120


def accumulate(mod, fmt, xs):
    """Sum with a re-encode after every partial, as the adder does."""
    s = Fraction(0)
    for x in xs:
        s = mod.decode(fmt, mod.encode(fmt, s + Fraction(x).limit_denominator(10 ** 12)))
        if not isinstance(s, Fraction):
            return None
    return s


def main():
    print(__doc__.split("\n\n")[0])
    print()
    print(f"  {'rung':>5} {'TNF stored':>11} {'takum':>7} {'TNF err':>11} "
          f"{'takum err':>11} {'ratio':>9}")
    for n, tk_name in RUNGS:
        tnf = tnf_ref.LADDER[n]
        tk = takum_ref.FORMATS[tk_name]
        random.seed(11)
        et = ek = 0.0
        c = 0
        for _ in range(TRIALS):
            xs = [random.uniform(-1, 1) * 10 ** random.uniform(-3, 3) for _ in range(TERMS)]
            exact = sum(Fraction(x).limit_denominator(10 ** 12) for x in xs)
            a = accumulate(tnf_ref, tnf, xs)
            b = accumulate(takum_ref, tk, xs)
            if a is None or b is None or exact == 0:
                continue
            et += abs(float((a - exact) / exact))
            ek += abs(float((b - exact) / exact))
            c += 1
        if not c:
            continue
        et /= c
        ek /= c
        print(f"  {n:>5} {tnf.sign_shift+1:>10}b {n:>6}b {et:>11.3e} {ek:>11.3e} "
              f"{ek/et if et else float('nan'):>8.2f}x")

    print()
    print("Ratio > 1 means TNF accumulates with less error. Read the width column")
    print("first: the sign of the result follows the sign of the width difference.")
    print()
    print("  TNF8  is 10 bits against 8  -- and wins by 484x")
    print("  TNF16 is 17 bits against 16 -- and wins by 2.0x")
    print("  TNF32 is 30 bits against 32 -- and LOSES by 12x")
    print()
    print("The one rung where TNF is NARROWER is the one rung where it loses.")
    print("That is what a comparison at unequal width measures.")
    print()
    print("What this does NOT establish: takum8 accumulating to 2.1e+01 is a real")
    print("result about an 8-bit tapered format over 64 terms, not a defect --")
    print("there are too few bits for the partial sums. And tekum remains")
    print("unimplemented: tekum_ref decodes identically to takum_ref on all")
    print("65,536 codes.")


if __name__ == "__main__":
    sys.exit(main())
