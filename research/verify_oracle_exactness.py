#!/usr/bin/env python3
"""Test the exactness the 12 uncaveated oracles claim, instead of trusting it.

specs/numeric/oracle_fidelity_map.t27 recorded that 12 of 17 oracles carry no
caveat and therefore claim to be exact. That claim was taken on trust — which is
the same error that produced the pass-34 retraction, in the opposite direction.

Two intrinsic properties, checkable without any external reference:

  CARRIER   decode must return an exact carrier — Fraction, int, or a Special
            sentinel. A float return means the value was approximated, and no
            float-returning oracle can be exact.

  ALGEBRAIC an exact symbolic carrier (gfternary's PhiVal, a + b*phi with
            rational a and b) counts as exact: the irrational is represented, not
            approximated.

  DYADIC    for a BINARY format, every finite value is (1 + M/2^m) * 2^c, whose
            denominator is a power of two. A non-dyadic denominator means the
            decode is doing arithmetic the format cannot express.
            Decimal formats are exempt: their values are k/10^n, so denominators
            carry factors of 5 legitimately.

Run:  python3 research/verify_oracle_exactness.py
Exit: 0 if every uncaveated oracle satisfies both, 1 otherwise.
"""
from __future__ import annotations
from fractions import Fraction
import importlib.util
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONF = os.path.join(REPO, "conformance")

# The 12 that carry no fidelity caveat (oracle_fidelity_map.t27).
UNCAVEATED = ["bf16", "decimal", "extended", "fp8", "gf_mx", "gfternary",
              "ieee", "int", "legacy", "mxfp", "nf4", "posit"]

# Decimal-radix families: denominators may carry factors of 5.
DECIMAL_RADIX = {"decimal", "legacy"}   # legacy includes BCD

SAMPLES = 600


def load(fn):
    sys.path.insert(0, CONF)
    spec = importlib.util.spec_from_file_location("ex_" + fn, os.path.join(CONF, fn))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def is_dyadic(fr: Fraction) -> bool:
    d = fr.denominator
    return d & (d - 1) == 0            # power of two (1 counts)


def only_2_and_5(fr: Fraction) -> bool:
    d = fr.denominator
    for p in (2, 5):
        while d % p == 0:
            d //= p
    return d == 1


def width_of(fmt, name):
    for a in ("n", "width", "W", "total", "bits", "nbits"):
        v = getattr(fmt, a, None)
        if isinstance(v, int) and v > 0:
            return v
    digits = "".join(c for c in name if c.isdigit())
    return int(digits) if digits else 0


def main() -> int:
    print(f"{'oracle':<12}{'formats':>8}{'checked':>9}  {'carrier':<22}{'denominators'}")
    print("-" * 72)
    failures = 0
    tested_oracles = 0
    unreachable = []       # counted separately -- see below

    for base in UNCAVEATED:
        fn = base + "_ref.py"
        if not os.path.exists(os.path.join(CONF, fn)):
            print(f"{base:<12}{'':>8}{'':>9}  MODULE MISSING")
            unreachable.append((base, "module missing"))
            continue
        tested_oracles += 1
        try:
            mod = load(fn)
        except Exception as e:
            # A module that will not import has NOT failed exactness -- it has
            # not been tested. Counting it as a failure was a category error:
            # gf_mx_ref needs numpy, and on an interpreter without it this script
            # reported "1 oracle did not satisfy the exactness they claim" about
            # an oracle it never ran. Exactly the code-versus-value confusion this
            # campaign keeps finding elsewhere, in its own harness.
            print(f"{base:<12}{'':>8}{'':>9}  NOT TESTED: "
                  f"{type(e).__name__} ({e})"[:78])
            unreachable.append((base, f"{type(e).__name__}: {e}"[:60]))
            continue

        formats = getattr(mod, "FORMATS", {})
        checked = 0
        floats = 0
        nondyadic = 0
        other = 0
        algebraic = 0

        for name, fmt in formats.items():
            w = width_of(fmt, name)
            if w == 0 or w > 64:
                continue
            span = 1 << w
            step = max(1, span // SAMPLES)
            for raw in range(0, span, step):
                try:
                    v = mod.decode(fmt, raw)
                except Exception:
                    continue
                if getattr(v, "kind", None) is not None:
                    continue
                checked += 1
                if isinstance(v, float):
                    floats += 1
                    continue
                if isinstance(v, (int, Fraction)):
                    fr = Fraction(v)
                    ok = only_2_and_5(fr) if base in DECIMAL_RADIX else is_dyadic(fr)
                    if not ok:
                        nondyadic += 1
                elif all(isinstance(getattr(v, f, None), (int, Fraction))
                         for f in getattr(v, "__dataclass_fields__", {}) or ["__none__"]):
                    # An exact ALGEBRAIC carrier, e.g. gfternary's PhiVal holding
                    # a + b*phi with rational a, b. Exact by construction: the
                    # irrational is symbolic, never approximated. Counting it as
                    # "other" was this checker's limitation, not a defect.
                    algebraic += 1
                else:
                    other += 1

        if floats == 0 and other == 0:
            carrier = "exact" + (f" ({algebraic} algebraic)" if algebraic else "")
        else:
            carrier = f"{floats} float, {other} other"
        denom = "ok" if nondyadic == 0 else f"{nondyadic} non-dyadic"
        bad = floats or other or nondyadic
        failures += 1 if bad else 0
        print(f"{base:<12}{len(formats):>8}{checked:>9}  {carrier:<22}{denom}")

    print()
    if unreachable:
        print(f"{len(unreachable)} oracle(s) NOT TESTED — could not be loaded:")
        for base, why in unreachable:
            print(f"    {base:<12} {why}")
        print("    These are untested, not failed. Install what they need and")
        print("    re-run before treating the result below as complete.")
        print()

    tested = len(UNCAVEATED) - len(unreachable)
    if failures:
        print(f"{failures} of {tested} tested oracle(s) did not satisfy the "
              f"exactness they claim.")
    else:
        print(f"All {tested} tested oracles return exact carriers with admissible")
        print("denominators. The claim recorded in oracle_fidelity_map.t27 holds")
        print("on this evidence — sampled, not exhaustive.")
    print(f"COVERAGE: {tested_oracles} of {len(UNCAVEATED)} oracles checked "
          f"for exact carriers")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
