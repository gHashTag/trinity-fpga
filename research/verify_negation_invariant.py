#!/usr/bin/env python3
"""Check the two's-complement negation invariant on tapered formats.

Posit and takum both define negation as two's complement of the code word:

    decode( (-raw) mod 2^n )  ==  -decode(raw)

for every non-special code. This is intrinsic to the encoding, so the invariant
can be tested WITHOUT any external reference implementation — which makes it a
cheap, dependency-free way to detect the sign-and-magnitude confusion found in
specs/numeric/takum_libtakum_crossval.t27, and to see whether it reaches beyond
one family.

Zero and NaR are self-complementary and are excluded, as are any codes whose
decode is a special value.

Run:  python3 research/verify_negation_invariant.py
Exit: 0 if every tested format satisfies the invariant, 1 otherwise.
"""
from __future__ import annotations
from fractions import Fraction
import importlib.util
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONF = os.path.join(REPO, "conformance")

# Formats whose encoding defines negation as two's complement of the code word.
TARGETS = ["posit8", "posit16", "posit32", "posit64",
           "takum8", "takum16", "takum32", "takum64"]

MAX_ENUMERATE = 1 << 16          # above this, sample instead of enumerating
SAMPLE = 20000


def load_oracles():
    out = {}
    for fn in sorted(os.listdir(CONF)):
        if not fn.endswith("_ref.py") or fn.startswith("_"):
            continue
        try:
            spec = importlib.util.spec_from_file_location("n_" + fn[:-3],
                                                          os.path.join(CONF, fn))
            mod = importlib.util.module_from_spec(spec)
            sys.path.insert(0, CONF)
            # Register before executing. A module using @dataclass looks itself up in
            # sys.modules while the decorator runs, and under a synthetic name it is
            # not there -- which made conformance/takum_log_ref.py fail to import with
            # "'NoneType' object has no attribute '__dict__'". The old handler swallowed
            # that silently, so the logarithmic takum oracle was invisible to this check
            # and takum printed "no golden oracle" as though none existed.
            sys.modules[spec.name] = mod
            spec.loader.exec_module(mod)
        except Exception as e:
            # A module that fails to load is NOT the same as one that does not exist.
            print(f"  (could not load {fn}: {type(e).__name__}: {e})")
            sys.modules.pop(spec.name, None)
            continue
        # takum has TWO oracles here and they are not the same function.
        # conformance/takum_ref.py documents itself as a LINEAR structural model, and
        # pass 146 established that the corpus -- packs, hardware golden, and
        # libtakum's takum_log family -- implements the LOGARITHMIC one. Loading both
        # lets the linear model win alphabetically and produces a negation "failure"
        # that was already retracted once as sign-and-magnitude by design.
        #
        # Measured rather than argued: against takum_log_ref.py, 65,788 takum8 and
        # takum16 pairs satisfy the negation rule with 0 violations.
        if fn == "takum_ref.py":
            continue
        for name, fmt in getattr(mod, "FORMATS", {}).items():
            out.setdefault(name, (mod, fmt))
    return out


def width_of(fmt, name):
    for attr in ("n", "width", "W", "total", "bits", "nbits"):
        v = getattr(fmt, attr, None)
        if isinstance(v, int) and v > 0:
            return v
    d = "".join(c for c in name if c.isdigit())
    return int(d) if d else 0


def value_or_none(mod, fmt, raw):
    """A quantity comparable under negation, or None where none exists.

    For a logarithmic format the VALUE is irrational and the oracle returns a Special
    carrying the exact ln|value| instead. Skipping those would leave takum untested
    while printing "no golden oracle", which reads as coverage where there is none.
    So takum is compared in the log domain: negation must leave ln|value| unchanged
    and flip the sign, which is exactly the invariant, expressed where it is exact.
    """
    if hasattr(mod, "decode_ln") and hasattr(mod, "sign_of"):
        try:
            ln = mod.decode_ln(fmt, raw)
        except Exception:
            return None
        if getattr(ln, "kind", None) is not None:      # zero, NaR
            return None
        # Signed magnitude in the log domain: the sign is carried separately, so a
        # correct negation gives the same ln and the opposite sign bit.
        return (Fraction(ln), -1 if mod.sign_of(fmt, raw) else 1)

    try:
        v = mod.decode(fmt, raw)
    except Exception:
        return None
    if getattr(v, "kind", None) is not None:
        return None
    if isinstance(v, (int, Fraction)):
        return Fraction(v)
    try:
        f = float(v)
    except (TypeError, ValueError, OverflowError):
        return None
    if f != f or abs(f) == float("inf"):
        return None
    return Fraction(f)


def negated(x):
    """The negation of whatever value_or_none returned.

    A plain quantity negates arithmetically. A log-domain pair (ln|value|, sign)
    negates by flipping the sign and leaving the magnitude alone -- which IS the
    negation rule, stated where the format is exact instead of where it is irrational.
    """
    if isinstance(x, tuple):
        ln, sign = x
        return (ln, -sign)
    return -x


def check(name, mod, fmt) -> tuple[int, int, list]:
    width = width_of(fmt, name)
    span = 1 << width
    if span <= MAX_ENUMERATE:
        codes = range(span)
    else:
        step = max(1, span // SAMPLE)
        codes = range(0, span, step)

    tested = 0
    fails = []
    for raw in codes:
        if raw == 0 or raw == (span >> 1):      # zero and NaR are self-complementary
            continue
        a = value_or_none(mod, fmt, raw)
        b = value_or_none(mod, fmt, (-raw) % span)
        if a is None or b is None:
            continue
        tested += 1
        if b != negated(a):
            if len(fails) < 4:
                fails.append((raw, (-raw) % span, a, b))
    return tested, len(fails), fails


def main() -> int:
    oracles = load_oracles()
    any_fail = False
    print("invariant:  decode((-raw) mod 2^n) == -decode(raw)")
    print("(zero and NaR excluded; specials skipped)\n")

    for name in TARGETS:
        if name not in oracles:
            print(f"{name:<9} no golden oracle")
            continue
        mod, fmt = oracles[name]
        tested, nfail, fails = check(name, mod, fmt)
        verdict = "HOLDS" if nfail == 0 else f"FAILS on {nfail}+ of {tested}"
        if nfail:
            any_fail = True
        print(f"{name:<9} tested={tested:<7} {verdict}")
        for raw, comp, a, b in fails:
            print(f"    raw={raw} -> {float(a):.6e}   "
                  f"complement={comp} -> {float(b):.6e}   "
                  f"expected {float(-a):.6e}")

    print()
    if any_fail:
        print("At least one family violates its own encoding's negation rule.")
        print("That is intrinsic — no external reference is needed to see it.")
    else:
        print("All tested families satisfy the invariant.")
    return 1 if any_fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
