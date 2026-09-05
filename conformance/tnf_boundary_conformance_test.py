#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tnf_boundary_conformance_test.py — exhaustive boundary conformance for the whole
TNF ladder, on both ladder versions.

Why this file exists
--------------------
The P0 defect fixed on 13 August 2026 lived at the underflow boundary and was
found only because an accuracy sweep pushed the oracle far outside the range the
conformance vectors cover.  The vectors sample the interior densely and the
boundary barely at all, so the boundary is where the next silent defect will be.
This test states the boundary contract explicitly and checks every clause on
every rung, so a regression fails here rather than in a downstream measurement.

Contract, per rung (E_t trits of balanced exponent, M mantissa bits):

  R1  offset field 0        decodes to exactly zero, both signs
  R2  offset field max      is the special row: mantissa 0 -> +-Inf, else NaN
  R3  min normal            2^(1-exp_offset) round-trips exactly
  R4  max finite            (2 - 2^-M) * 2^(offset_max-1-exp_offset) round-trips exactly
  R5  every representable magnitude at the two ends of the exponent range
      round-trips exactly.  Exhaustive over all M-bit mantissas where 2^M is
      enumerable (M <= 16, which covers TNF4/8/16 completely); above that the
      mantissa is sampled at the 4096 values that matter -- the two ends of the
      field, both sides of every power-of-two carry position, and a fixed
      deterministic spread -- because 2^115 mantissas cannot be enumerated and
      pretending otherwise would be the same overclaim the ladder forbids.
  R6  underflow: no code word is ever negative; magnitude below min normal goes
      to zero or to min normal, nearest wins, ties to zero, sign preserved
  R7  overflow: max_finite stays finite; the round-to-nearest-even threshold
      above it (max_finite + half an ulp of the top binade) goes to signed Inf,
      as does anything higher; the code word stays non-negative throughout
  R8  signed zero: encode(-0) and encode(0) both decode to zero; the sign bit
      may be set but must not leak into the payload
  R9  commutativity of add and mul holds ACROSS the boundary (one operand at a
      range end, the other anywhere), which the interior sweep cannot see
  R10 monotonicity at the ends: consecutive code words in the lowest and highest
      normal binade decode to strictly increasing magnitudes

Exit code is non-zero on any violation, so this is usable as a CI gate.
"""
from fractions import Fraction
import itertools
import sys

sys.path.insert(0, "/tmp/tfpga/conformance")
import tnf_ref as T


def pow2(e):
    return Fraction(1 << e, 1) if e >= 0 else Fraction(1, 1 << -e)


class Report:
    def __init__(self):
        self.fails = []
        self.checks = 0

    def ok(self, cond, rule, rung, ladder, detail=""):
        self.checks += 1
        if not cond:
            self.fails.append((ladder, rung, rule, detail))


def min_normal(f):
    return pow2(1 - f.exp_offset)


def max_finite(f):
    return (Fraction(2) - Fraction(1, f.mant)) * pow2(f.offset_max - 1 - f.exp_offset)


def check_rung(rep, ladder_name, width, f):
    R = lambda rule, cond, detail="": rep.ok(cond, rule, width, ladder_name, detail)
    mask = (1 << f.sign_shift) - 1

    # ---- R1 zero row
    for sign in (0, 1):
        raw = sign << f.sign_shift
        R("R1", T.decode(f, raw) == 0, f"sign={sign} decode={T.decode(f, raw)!r}")

    # ---- R2 special row
    raw_inf = f.inf
    d = T.decode(f, raw_inf)
    R("R2", d == float("inf"), f"+Inf got {d!r}")
    d = T.decode(f, (1 << f.sign_shift) | raw_inf)
    R("R2", d == float("-inf"), f"-Inf got {d!r}")
    if f.mant_bits >= 1:
        d = T.decode(f, raw_inf | 1)
        R("R2", d != d, f"NaN got {d!r}")          # NaN != NaN
    R("R2", T.is_special(f, raw_inf), "is_special(+Inf)")

    # ---- R3 / R4 the two finite ends round-trip exactly
    for name, v in (("min_normal", min_normal(f)), ("max_finite", max_finite(f))):
        for s in (1, -1):
            x = s * v
            raw = T.encode(f, x)
            R("R3/R4", raw >= 0, f"{name} s={s} negative code word {raw}")
            back = T.decode(f, raw)
            R("R3/R4", back == x, f"{name} s={s} got {back!r} want {x!r}")
            R("R3/R4", T.encode(f, back) == raw, f"{name} s={s} not a fixpoint")

    # ---- R5 exhaustive over the two end binades (all mantissas)
    ends = (1, f.offset_max - 1)
    if f.mant_bits <= 16:
        mants = range(f.mant)
        r5_mode = "exhaustive"
    else:
        s = {0, 1, 2, f.mant - 1, f.mant - 2, f.mant // 2}
        for k in range(f.mant_bits):
            s |= {(1 << k) - 1, 1 << k, (1 << k) + 1}
        step = max(1, f.mant // 4096)
        s |= set(range(0, f.mant, step))
        mants = sorted(x for x in s if 0 <= x < f.mant)
        r5_mode = f"sampled {len(mants)}"
    for off in ends:
        e = off - f.exp_offset
        for m in mants:
            v = (Fraction(1) + Fraction(m, f.mant)) * pow2(e)
            for s in (1, -1):
                x = s * v
                raw = T.encode(f, x)
                R("R5", raw >= 0, f"off={off} m={m} s={s} negative code word")
                R("R5", T.decode(f, raw) == x,
                  f"off={off} m={m} s={s} got {T.decode(f, raw)!r}")
                R("R5", (raw & mask) == (off << f.exp_shift) | m,
                  f"off={off} m={m} payload {raw & mask:#x}")

    # ---- R6 underflow behaviour
    mn = min_normal(f)
    probes = [(mn / 2, "exact tie"), (mn / 2 - mn / 1024, "below tie"),
              (mn / 2 + mn / 1024, "above tie"), (mn / 4, "quarter"),
              (mn / (1 << 40), "far below"), (mn * Fraction(999, 1000), "just below mn")]
    for v, why in probes:
        for s in (1, -1):
            x = s * v
            raw = T.encode(f, x)
            R("R6", raw >= 0, f"{why} s={s} negative code word {raw}")
            payload = raw & mask
            got = T.decode(f, raw)
            expect_zero = (abs(x) * 2 <= mn)
            if expect_zero:
                R("R6", got == 0, f"{why} s={s} want 0 got {got!r}")
                R("R6", payload == 0, f"{why} s={s} payload {payload:#x} not clean")
            else:
                R("R6", abs(got) == mn, f"{why} s={s} want {mn!r} got {got!r}")
                R("R6", (got < 0) == (x < 0), f"{why} s={s} sign lost")
            R("R6", not T.is_special(f, raw), f"{why} s={s} became special")

    # ---- R7 overflow behaviour
    mx = max_finite(f)
    top = pow2(f.offset_max - f.exp_offset)
    ulp_top = pow2(f.offset_max - 1 - f.exp_offset) / f.mant
    # max_finite itself and just under the rounding threshold must stay finite
    for v, why in ((mx, "max_finite"), (mx + ulp_top / 4, "under threshold")):
        for s in (1, -1):
            raw = T.encode(f, s * v)
            got = T.decode(f, raw)
            R("R7", raw >= 0, f"{why} s={s} negative code word")
            R("R7", got == s * mx, f"{why} s={s} did not stay at max_finite")
    # at and above the threshold must be signed infinity
    for v, why in ((mx + ulp_top / 2, "tie at threshold"), (top, "special row magnitude"),
                   (top * 4, "far above"), (mx * 2, "double max")):
        for s in (1, -1):
            x = s * v
            raw = T.encode(f, x)
            R("R7", raw >= 0, f"{why} s={s} negative code word")
            got = T.decode(f, raw)
            R("R7", got == (float("-inf") if s < 0 else float("inf")),
              f"{why} s={s} did not overflow")

    # ---- R8 signed zero
    for z in (0, Fraction(0), -0.0):
        raw = T.encode(f, z)
        R("R8", raw >= 0 and T.decode(f, raw) == 0, f"zero {z!r} -> {raw}")
        R("R8", (raw & mask) == 0, f"zero {z!r} payload {raw & mask:#x}")

    # ---- R9 commutativity across the boundary
    end_words = [T.encode(f, min_normal(f)), T.encode(f, max_finite(f)),
                 0, (1 << f.sign_shift), f.inf,
                 T.encode(f, -min_normal(f)), T.encode(f, -max_finite(f))]
    partners = [T.encode(f, Fraction(1)), T.encode(f, Fraction(-1)),
                T.encode(f, Fraction(3, 2)), T.encode(f, min_normal(f) * 4),
                T.encode(f, max_finite(f) / 4), 0, f.inf]
    for a, b in itertools.product(end_words, partners):
        R("R9", T.tef_add(f, a, b) == T.tef_add(f, b, a), f"add {a:#x} {b:#x}")
        R("R9", T.tef_mul(f, a, b) == T.tef_mul(f, b, a), f"mul {a:#x} {b:#x}")

    # ---- R10 monotonicity in the two end binades
    for off in ends:
        prev = None
        for m in mants:
            v = T.decode(f, (off << f.exp_shift) | m)
            if prev is not None:
                R("R10", v > prev, f"off={off} m={m} not increasing")
            prev = v


def main():
    sys.set_int_max_str_digits(1_000_000)      # TNF1024 magnitudes are ~300 digits
    rep = Report()
    for ladder_name, ladder in T.LADDERS.items():
        for width, f in sorted(ladder.items()):
            before = len(rep.fails)
            check_rung(rep, ladder_name, width, f)
            new = len(rep.fails) - before
            mode = "exhaustive" if f.mant_bits <= 16 else "sampled"
            print(f"  {ladder_name:<12} TNF{width:<5} E_t={f.exp_trits:<3} M={f.mant_bits:<5} "
                  f"R5 {mode:<10} {('FAIL %d' % new) if new else 'ok'}", flush=True)
    print(f"\nboundary checks run: {rep.checks}")
    if rep.fails:
        print(f"VIOLATIONS: {len(rep.fails)}")
        for ladder, rung, rule, detail in rep.fails[:40]:
            print(f"  {ladder} TNF{rung} {rule}: {detail}")
        return 1
    print("BOUNDARY SELF-TEST PASS — all rules on every rung of both ladders")
    return 0


if __name__ == "__main__":
    sys.exit(main())
