#!/usr/bin/env python3
"""Golden consistency check: HW-conformance host goldens (corona_decode_host)
must EXACTLY equal the decode_verify oracles across the FULL code space.

The host goldens drive HW conformance (only corner-tested via --self-test); the
decode_verify oracles are exhaustive-RTL-verified. This cross-check confirms they
agree on EVERY code (incl. NaN conventions), so a future edit to either can't
make the HW-conformance golden diverge from the RTL-verified oracle.

  python3 conformance/golden_consistency.py
"""
import sys
sys.path.insert(0, "conformance") if "conformance" not in sys.path else None
import corona_decode_host_ax7203 as h
import decode_verify as dv

# (host FMT const, decode_verify oracle name, n_codes). lns8 excluded (host packs
# {sign,magnitude}, oracle returns bare magnitude — different contracts).
FORMATS = [
    (h.FMT_FP8,      "fp8_e4m3",  256),
    (h.FMT_FP8_E5M2, "fp8_e5m2",  256),
    (h.FMT_INT8,     "int8",      256),
    (h.FMT_POSIT8,   "posit8",    256),
    (h.FMT_FP6_E2M3, "fp6_e2m3",   64),
    (h.FMT_FP6_E3M2, "fp6_e3m2",   64),
    (h.FMT_FP4,      "fp4_e2m1",   16),
    (h.FMT_INT4,     "int4",       16),
    (h.FMT_BINARY16, "binary16", 65536),
]


def main():
    total_bad = checked = 0
    for fmtc, name, n in FORMATS:
        bad = 0
        for code in range(n):
            hg = h.golden(fmtc, code)
            og, _ = dv.oracle(name, code)
            checked += 1
            if hg != og:
                bad += 1
                if bad <= 4:
                    print(f"[{name}] code=0x{code:x} host=0x{hg:08x} oracle=0x{og:08x}")
        total_bad += bad
        print(f"[{name}] {n} codes, {bad} mismatches")
    print(f"GOLDEN CONSISTENCY: {checked} codes checked, {total_bad} total mismatches")
    return 0 if total_bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
