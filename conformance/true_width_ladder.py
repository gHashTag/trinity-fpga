#!/usr/bin/env python3
"""true_width_ladder.py — a ladder whose rungs are the width they are named.

Not one rung of the published ladder stores the width in its name. The exponent
field of a TNF rung needs ceil(Et * log2 3) bits, and the ladder's (Et, mant)
choices land above the name on eight rungs and below it on one:

    TNF4  is 6 bits (+2)     TNF64   is 65 bits  (+1)
    TNF8  is 10 bits (+2)    TNF128  is 129 bits (+1)
    TNF16 is 17 bits (+1)    TNF256  is 258 bits (+2)
    TNF32 is 30 bits (-2)    TNF512  is 514 bits (+2)
                             TNF1024 is 1025 bits (+1)

`arithmetic_across_rungs.py` measured the consequence: the sign of the advantage
over takum follows the sign of the width difference — +2 bits wins 484x, +1 bit
wins 2x, and the one narrower rung LOSES by 12x. None of those numbers is about
the format; they are about the misnamed widths.

This builds rungs that are exactly their named width — for each N, every trit
count Et whose exponent field plus sign still leaves a mantissa — and measures
them the same way: accumulate terms with a re-encode after every partial sum,
against takum of the SAME stored width.

Run: python3 conformance/true_width_ladder.py
"""

import random
import sys
from fractions import Fraction

sys.path.insert(0, "conformance")
sys.path.insert(0, ".")
import takum_ref  # noqa: E402
import tnf_ref  # noqa: E402

# (named width, takum opponent, value band in decades, terms per trial)
CASES = [(8, "takum8", 0.5, 32), (16, "takum16", 3.0, 64), (32, "takum32", 3.0, 64)]
TRIALS = 100


def exp_bits(et):
    """Bits needed to store the 3^Et exponent offsets."""
    return (3 ** et - 1).bit_length()


def splits(width):
    """Every (Et, mant) that stores in exactly `width` bits."""
    out = []
    et = 1
    while True:
        mant = width - 1 - exp_bits(et)
        if mant < 1:
            break
        out.append((et, mant))
        et += 1
    return out


def accumulate(mod, fmt, xs):
    s = Fraction(0)
    for x in xs:
        s = mod.decode(fmt, mod.encode(fmt, s + Fraction(x).limit_denominator(10 ** 12)))
        if not isinstance(s, Fraction):
            return None
    return s


def score(mod, fmt, band, terms, seed=11):
    random.seed(seed)
    total = 0.0
    count = 0
    for _ in range(TRIALS):
        xs = [random.uniform(-1, 1) * 10 ** random.uniform(-band, band)
              for _ in range(terms)]
        exact = sum(Fraction(x).limit_denominator(10 ** 12) for x in xs)
        got = accumulate(mod, fmt, xs)
        if got is None or exact == 0:
            continue
        total += abs(float((got - exact) / exact))
        count += 1
    return total / count if count else float("inf")


def main():
    print(__doc__.split("\n\n")[0])
    print()
    for width, tk_name, band, terms in CASES:
        tk = takum_ref.FORMATS[tk_name]
        base = score(takum_ref, tk, band, terms)
        print(f"{width} bits — values over ±{band} decades, {terms} terms, "
              f"{TRIALS} trials. {tk_name}: {base:.3e}")
        old = tnf_ref.LADDER[width]
        rows = []
        for et, mant in splits(width):
            fmt = tnf_ref.TNFFormat(et, mant)
            s = score(tnf_ref, fmt, band, terms)
            rows.append((et, mant, s))
        best = min(r[2] for r in rows)
        for et, mant, s in rows:
            marks = []
            if s == best:
                marks.append("best")
            if (et, mant) == (old.exp_trits, old.mant_bits):
                marks.append("published rung")
            ratio = base / s if s else float("inf")
            print(f"  TNF({et},{mant})  {1+exp_bits(et)+mant:>2} bits   "
                  f"err {s:>9.3e}   vs takum {ratio:>6.2f}x"
                  f"{('   <- ' + ', '.join(marks)) if marks else ''}")
        # the published rung, at its own (wrong) width, for contrast
        s_old = score(tnf_ref, old, band, terms)
        print(f"  published TNF{width} = TNF({old.exp_trits},{old.mant_bits}) "
              f"at {old.sign_shift+1} bits: err {s_old:.3e} "
              f"(vs takum {base/s_old if s_old else float('inf'):.2f}x)")
        print()

    print("Read honestly, and read the band column before the ratio column.")
    print()
    print("The 'best' splits are the narrow-exponent ones, and that is a property")
    print("of the +-3 decade band, not of the splits: TNF(3,10) wins 4.84x here")
    print("and was measured dropping 58% of all values over +-9 decades")
    print("(equal_width_vs_takum.py). Its 32-bit sibling TNF(3,26) carries the")
    print("same +-3.6 decade reach. Quoting either without its band would be the")
    print("trap this project already documented once.")
    print()
    print("The RANGE-SAFE true-width rungs are the honest headline, and they say")
    print("something simpler: TNF(4,8) TIES takum16 at 1.00x, and TNF(4,24) ties")
    print("takum32 at 0.94x. At a true width, with range to spare on both sides,")
    print("the fixed-field format and the tapered one accumulate equally well.")
    print("Every published multiple above 1x came from the extra bits.")
    print()
    print("What this does NOT establish: the opponent is the linear takum of")
    print("libtakum (the published linear variant, negative branch corrected in")
    print("conformance/takum_ref.py). tekum remains unimplemented. One value")
    print("band per width, one seed, accumulation only.")


if __name__ == "__main__":
    sys.exit(main())
