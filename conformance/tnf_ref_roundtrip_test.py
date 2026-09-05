#!/usr/bin/env python3
"""Round-trip self-test for the TNF reference oracle, at every rung.

Exists because the ladder's existing check is add/mul commutativity, and
commutativity is blind to a sign inversion: it survives on both sides of
a + b == b + a. A sign-placement defect went unnoticed that way, and TNF32
returned -1.5 for 1.5 while passing the commutativity suite.

    python3 conformance/tnf_ref_roundtrip_test.py
"""
import math
import sys

from tnf_ref import TNFFormat, encode, decode

# (name, exp_trits, mant_bits) from research/GF_T_GOLD_STANDARD_LADDER.
RUNGS = [
    ("TNF4", 2, 1), ("TNF8", 3, 4), ("TNF16", 4, 9), ("TNF32", 6, 25),
    ("TNF64", 7, 52), ("TNF128", 8, 115), ("TNF256", 9, 242),
    ("TNF512", 10, 497), ("TNF1024", 11, 1006),
]

# Values a sign or field-placement defect shows up on immediately. Kept modest so
# that narrow rungs are exercised inside their range rather than at saturation.
PROBES = [1.0, -1.0, 1.5, -1.5, 2.0, -2.0, 3.0, -3.0, 1.25, -1.25]


def main():
    failures = []
    for name, et, mb in RUNGS:
        fmt = TNFFormat(et, mb)
        for v in PROBES:
            got = decode(fmt, encode(fmt, v))
            try:
                got = float(got)
            except (TypeError, ValueError):
                failures.append((name, v, repr(got))); continue
            if math.isinf(got) or math.isnan(got):
                failures.append((name, v, got)); continue
            # Sign must survive exactly; magnitude to the rung's precision.
            if (got < 0) != (v < 0):
                failures.append((name, v, got)); continue
            if abs(got - v) > abs(v) * 0.5:
                failures.append((name, v, got))

    for name, v, got in failures:
        print(f"FAIL {name}: {v} round-tripped to {got}")
    print(f"\n{len(RUNGS) * len(PROBES) - len(failures)}"
          f"/{len(RUNGS) * len(PROBES)} round-trips exact in sign and close in magnitude")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
