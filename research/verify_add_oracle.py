#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Three-oracle verification of GF-ADD, with no hardware and no simulator.

Pass 96 established an asymmetry. MUL has three structurally distinct oracles that
agree over 1,269,632 pairs with GF6 and GF8 exhaustive (formal/verify_mul_oracle.py),
run expressly to rule out bug-equals-bug before the SAT proof. ADD has two -- a
faithful port of the RTL and the Fraction golden -- checked on samples of 8032
vectors, never exhaustively.

Two oracles cannot distinguish "both correct" from "both wrong in the same way" when
one was written by transcribing the artefact the other defines. This adds the third.

    O1  rtl_adder_model -- a bit-level transcription of gf_adder_param.v, the DUT
        (conformance/verify_adder_e24.py). Align, shift, add, normalise, sticky.

    O2  nearest_representable -- NEW, and deliberately shares no rounding code with
        anything. It builds the format's grid of representable magnitudes, bisects
        for the exact rational sum, and picks the nearer neighbour with ties to even
        code parity. No exponent extraction, no alignment shift, no sticky bit, no
        ilog2, no carry-out renormalisation -- none of the machinery the other two
        are built from. It is the definition of round-to-nearest-even read literally
        rather than implemented.

    O3  gf_ref.gf_add -- decode to Fraction, add exactly, encode with ties-to-even.

O2's independence is the point. It cannot inherit a defect from the RTL because it
does not model the RTL, and it cannot inherit one from encode() because it does not
call it. Where all three agree, the arithmetic is settled about as far as software
can settle it.

This is a software proof: model == model == model. It is NOT hardware conformance,
and it does not become one. The hardware compares against gf_ref on the host, which
is why an independent second formulation of the definition is worth having at all.

    python3 research/verify_add_oracle.py [--sample N]
"""
from __future__ import annotations

import argparse
import bisect
import os
import random
import sys
from fractions import Fraction

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "conformance"))

from gf_ref import FORMATS, gf_add                      # noqa: E402  (O3)
from verify_adder_e24 import rtl_adder_model            # noqa: E402  (O1)


# --------------------------------------------------------------------------
# O2 -- the independent oracle.
# --------------------------------------------------------------------------

_GRID_CACHE: dict[str, tuple[list, list]] = {}


def _magnitude(fmt, exp_field: int, mant: int) -> Fraction:
    """Value of a finite code's magnitude, straight from the format's own law.

    Deliberately written from the field definition rather than by calling
    gf_ref.decode, so that a defect in decode cannot propagate into this oracle.
    """
    two_m = 1 << fmt.mant_bits
    if exp_field == 0:                                   # zero or subnormal
        return Fraction(mant, two_m) * Fraction(2) ** (1 - fmt.bias)
    return (1 + Fraction(mant, two_m)) * Fraction(2) ** (exp_field - fmt.bias)


def _grid(fmt):
    """Sorted magnitudes of every finite non-negative code, with their codes.

    Sorted explicitly rather than assuming the code order is monotonic in value.
    That monotonicity is true of this layout, but assuming it here would import an
    unstated premise into an oracle whose whole purpose is to assume as little as
    possible.
    """
    if fmt.name in _GRID_CACHE:
        return _GRID_CACHE[fmt.name]
    top_exp = (fmt.exp_max - 1) if fmt.has_inf else fmt.exp_max
    pairs = []
    for e in range(0, top_exp + 1):
        for m in range(0, fmt.mant_max + 1):
            pairs.append((_magnitude(fmt, e, m), (e << fmt.mant_bits) | m))
    pairs.sort(key=lambda t: (t[0], t[1]))
    vals = [v for v, _ in pairs]
    codes = [c for _, c in pairs]
    _GRID_CACHE[fmt.name] = (vals, codes)
    return vals, codes


def _classify(fmt, raw: int):
    """(kind, sign, magnitude) read from the raw bits, without gf_ref."""
    sign = (raw >> fmt.sign_shift) & 1
    exp_field = (raw >> fmt.mant_bits) & fmt.exp_max
    mant = raw & fmt.mant_max
    if fmt.has_inf and exp_field == fmt.exp_max:
        return ("nan" if mant else "inf"), sign, None
    return "finite", sign, _magnitude(fmt, exp_field, mant)


def nearest_representable(fmt, a_raw: int, b_raw: int) -> int:
    """O2: add exactly, then pick the nearest representable by bisection."""
    ka, sa, va = _classify(fmt, a_raw)
    kb, sb, vb = _classify(fmt, b_raw)

    if ka == "nan" or kb == "nan":
        return fmt.quiet_nan
    if ka == "inf" and kb == "inf":
        if sa != sb:
            return fmt.quiet_nan
        return fmt.neg_inf if sa else fmt.pos_inf
    if ka == "inf":
        return fmt.neg_inf if sa else fmt.pos_inf
    if kb == "inf":
        return fmt.neg_inf if sb else fmt.pos_inf

    if va == 0 and vb == 0:
        return fmt.neg_zero if (sa and sb) else fmt.pos_zero

    s = (-va if sa else va) + (-vb if sb else vb)        # exact
    if s == 0:
        return fmt.pos_zero
    sign = 1 if s < 0 else 0
    a = -s if s < 0 else s
    sbit = sign << fmt.sign_shift

    vals, codes = _grid(fmt)

    # Above the largest finite magnitude: the neighbour above does not exist as a
    # code, so its position is supplied by the ladder itself -- one ulp beyond the
    # top. The halfway point decides, ties to even as everywhere else, and the top
    # code has an all-ones mantissa so a tie always goes up.
    if a > vals[-1]:
        top_exp = (fmt.exp_max - 1) if fmt.has_inf else fmt.exp_max
        ulp = Fraction(2) ** (top_exp - fmt.bias - fmt.mant_bits)
        return fmt.pos_overflow(sign) if a >= vals[-1] + ulp / 2 else sbit | codes[-1]

    i = bisect.bisect_left(vals, a)
    if vals[i] == a:
        return sbit | codes[i]
    lo_v, lo_c = vals[i - 1], codes[i - 1]
    hi_v, hi_c = vals[i], codes[i]
    d_lo, d_hi = a - lo_v, hi_v - a
    if d_lo < d_hi:
        return sbit | lo_c
    if d_hi < d_lo:
        return sbit | hi_c
    return sbit | (lo_c if lo_c % 2 == 0 else hi_c)      # tie -> even code


# --------------------------------------------------------------------------
# the check
# --------------------------------------------------------------------------

def boundary_codes(fmt) -> list[int]:
    """Codes at every structural edge: zero, subnormals, the normal boundary,
    the top finite, and -- where they exist -- Inf and NaN.

    Pass 96 found that gf16 SUB fails 4/512 on silicon precisely on Inf/NaN
    sentinels while MUL is clean, so a sample drawn from the middle of the range
    is the one sample guaranteed to miss the interesting part.
    """
    top_exp = (fmt.exp_max - 1) if fmt.has_inf else fmt.exp_max
    out = {
        0, 1, 2,                                        # +0, min subnormal, next
        fmt.mant_max,                                   # max subnormal
        1 << fmt.mant_bits,                             # min normal
        (1 << fmt.mant_bits) | 1,
        (top_exp << fmt.mant_bits) | fmt.mant_max,      # max finite
        (top_exp << fmt.mant_bits),
        ((top_exp - 1) << fmt.mant_bits) | fmt.mant_max,
        fmt.bias << fmt.mant_bits,                      # 1.0
    }
    if fmt.has_inf:
        out |= {fmt.exp_max << fmt.mant_bits,            # +Inf
                (fmt.exp_max << fmt.mant_bits) | 1,      # a NaN
                fmt.quiet_nan & ~(1 << fmt.sign_shift)}
    out = {c for c in out if 0 <= c <= fmt.mant_max | (fmt.exp_max << fmt.mant_bits)}
    return sorted(out | {c | (1 << fmt.sign_shift) for c in out})   # both signs


def check(fmt, pairs, label: str) -> tuple[int, int, int, int]:
    d12 = d23 = d13 = 0
    shown = 0
    for a, b in pairs:
        o1 = rtl_adder_model(fmt, a, b)
        o2 = nearest_representable(fmt, a, b)
        o3 = gf_add(fmt, a, b)
        if o1 != o2 or o2 != o3 or o1 != o3:
            d12 += o1 != o2
            d23 += o2 != o3
            d13 += o1 != o3
            if shown < 8:
                shown += 1
                w = (fmt.mant_bits + fmt.exp_bits + 1)
                print(f"    a={a:0{w}b} b={b:0{w}b}  "
                      f"O1={o1:0{w}b} O2={o2:0{w}b} O3={o3:0{w}b}")
    n = len(pairs)
    verdict = "PASS (O1==O2==O3)" if not (d12 or d23 or d13) else "FAIL"
    print(f"[{fmt.name}] EXP={fmt.exp_bits} MANT={fmt.mant_bits} "
          f"HAS_INF={int(fmt.has_inf)} pairs={n} {label}")
    print(f"    DUT!=NEAREST: {d12}   NEAREST!=GOLDEN: {d23}   "
          f"DUT!=GOLDEN: {d13}   -> {verdict}")
    return n, d12, d23, d13


def self_check() -> int:
    """Would this harness notice if O2 were wrong? Mutate it and see.

    A three-way agreement reached on the first run invites the question of whether
    the comparison discriminates at all. Three deliberate faults are injected into
    O2 -- each a plausible way to get rounding wrong -- and every one must be
    caught. If a mutant survives, the passing result above means nothing.
    """
    faults = {}

    def _finite_pair(fmt, a, b):
        ka, sa, va = _classify(fmt, a)
        kb, sb, vb = _classify(fmt, b)
        if ka != "finite" or kb != "finite":
            return None
        s = (-va if sa else va) + (-vb if sb else vb)
        if s == 0:
            return None
        sign = 1 if s < 0 else 0
        return (-s if s < 0 else s), (sign << fmt.sign_shift)

    def ties_away(fmt, a, b):
        got = _finite_pair(fmt, a, b)
        if got is None:
            return nearest_representable(fmt, a, b)
        mag, sbit = got
        vals, codes = _grid(fmt)
        if mag > vals[-1]:
            return nearest_representable(fmt, a, b)
        i = bisect.bisect_left(vals, mag)
        if vals[i] == mag:
            return sbit | codes[i]
        d_lo, d_hi = mag - vals[i - 1], vals[i] - mag
        if d_lo < d_hi:
            return sbit | codes[i - 1]
        return sbit | codes[i]                       # tie -> away, not even

    def no_overflow(fmt, a, b):
        got = _finite_pair(fmt, a, b)
        if got is None:
            return nearest_representable(fmt, a, b)
        mag, sbit = got
        vals, codes = _grid(fmt)
        if mag > vals[-1]:
            return sbit | codes[-1]                  # never produce Inf
        return nearest_representable(fmt, a, b)

    def flush_subnormals(fmt, a, b):
        r = nearest_representable(fmt, a, b)
        if ((r >> fmt.mant_bits) & fmt.exp_max) == 0:
            return r & (1 << fmt.sign_shift)         # subnormals -> signed zero
        return r

    faults = [("ties-away-from-zero", ties_away),
              ("overflow-never-Inf", no_overflow),
              ("subnormals-flushed", flush_subnormals)]

    rng = random.Random(7)
    print("=== negative control: three injected faults, each must be caught ===")
    survivors = 0
    for label, mutant in faults:
        counts = []
        for name in ("gf6", "gf8", "gf16"):
            fmt = FORMATS.get(name)
            if fmt is None:
                continue
            width = fmt.exp_bits + fmt.mant_bits + 1
            codes = 1 << width
            if codes * codes <= 70_000:
                pairs = [(a, b) for a in range(codes) for b in range(codes)]
            else:
                edges = boundary_codes(fmt)
                pairs = [(a, b) for a in edges for b in edges]
                pairs += [(rng.randrange(codes), rng.randrange(codes))
                          for _ in range(20_000)]
            d = sum(mutant(fmt, a, b) != gf_add(fmt, a, b) for a, b in pairs)
            counts.append(f"{name}:{d}")
        caught = any(int(c.split(":")[1]) for c in counts)
        survivors += not caught
        print(f"  {'caught ' if caught else 'SURVIVED'} {label:<22} "
              f"divergences -> {'  '.join(counts)}")

    if survivors:
        print(f"\n{survivors} mutant(s) survived -- the comparison does not "
              f"discriminate, and the PASS above is not evidence.")
    else:
        print("""
Every injected fault is caught, so the agreement reported by the main run is a
property of the oracles and not of a comparison that never fails.

overflow-never-Inf reads zero on gf6 and gf8, and that is the correct reading rather
than a miss: neither format has an Inf to suppress, so the fault is a no-op there.
gf16 is the only one of the three where it has anywhere to show, and it shows.""")
    return 1 if survivors else 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", type=int, default=300_000,
                    help="pairs per non-exhaustive format")
    ap.add_argument("--self-check", action="store_true",
                    help="inject faults into O2 and confirm the harness catches them")
    args = ap.parse_args()
    if args.self_check:
        return self_check()
    rng = random.Random(20260801)

    print("=== Three-oracle verification of GF-ADD (software, no hardware) ===")
    print("    O1=DUT(RTL port gf_adder_param)  O2=nearest-representable(NEW)  "
          "O3=Fraction golden\n")

    total = pairs_run = 0
    bad = 0
    for name in ("gf6", "gf8", "gf12", "gf16", "gf20"):
        fmt = FORMATS.get(name)
        if fmt is None:
            print(f"[{name}] absent from FORMATS -- skipped")
            continue
        width = fmt.exp_bits + fmt.mant_bits + 1
        codes = 1 << width
        if codes * codes <= 70_000:
            pairs = [(a, b) for a in range(codes) for b in range(codes)]
            label = "EXHAUSTIVE"
        else:
            edges = boundary_codes(fmt)
            pairs = [(a, b) for a in edges for b in edges]      # every edge pair
            label = f"sample + {len(edges)}^2 boundary"
            pairs += [(rng.randrange(codes), rng.randrange(codes))
                      for _ in range(args.sample)]
        n, d12, d23, d13 = check(fmt, pairs, label)
        pairs_run += n
        total += 1
        bad += bool(d12 or d23 or d13)

    print(f"\nformats checked: {total}   pairs: {pairs_run:,}   "
          f"formats with any divergence: {bad}")
    if not bad:
        print("""
ADD now has what MUL has: a third oracle that shares no rounding code with the RTL
port or with encode(), agreeing bit-exactly everywhere the two of them do. The
"both wrong in the same way" reading is ruled out for addition too.

Still a software result. The board compares against gf_ref, so this strengthens the
definition, not the silicon claim.""")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
