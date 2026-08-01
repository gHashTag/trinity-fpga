#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A conformance suite passed 512/512 on silicon while the cell was defective.

This reproduces, in software and from the vector sets alone, a result the project
already has from hardware: gf16 ADD reported 512/512 bit-exact on an AX7203 while the
adder it exercised carried an IEEE-754 ordering defect, and gf16 SUB -- the same cell,
reached through a sign flip -- reported 508/512 and exposed it.

The defect (fixed in 711f5d572): gf_adder_param's result mux evaluated zero-passthrough
(x + 0 = x) BEFORE the NaN branch, so a zero paired with a NaN returned that NaN's raw
payload verbatim instead of the canonical quiet NaN.

Why ADD could not catch it, and why that is the interesting part:

  - ADD's vector set carries exactly one NaN, 0x7E01. For gf16 the canonical quiet NaN
    IS 0x7E01, so the buggy passthrough returned the correct value by coincidence.
  - ADD pairs every a against cov[:8], and those eight are +0, -0, two subnormals and
    four ordinary finites. No NaN sits in the b-position at all.
  - SUB's set seeds eight specials including 0xFFFF -- a NaN whose payload is not the
    canonical one. Paired with a zero, the defect shows immediately.

So the difference was not the hardware, not the operation, and not the sample size.
Both suites ran 512 pairs on the same silicon against the same shared cell. One
contained a NaN whose payload differed from the canonical quiet NaN and the other did
not, and that alone decided whether a real defect was visible.

That is a transferable statement about conformance-vector design, and it is the
argument for enumerating structural boundaries rather than sampling: see
research/verify_add_oracle.py, whose boundary set carries non-canonical payloads for
this reason.

    python3 research/vector_blindness.py
"""
from __future__ import annotations

import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "conformance"))

from gf_ref import FORMATS, gf_add                      # noqa: E402

FMT = FORMATS["gf16"]
SIGN = 1 << FMT.sign_shift
T = 1 << (FMT.exp_bits + FMT.mant_bits + 1)


def _is_zero(x: int) -> bool:
    return ((x >> FMT.mant_bits) & FMT.exp_max) == 0 and (x & FMT.mant_max) == 0


def _is_nan(x: int) -> bool:
    return (((x >> FMT.mant_bits) & FMT.exp_max) == FMT.exp_max
            and (x & FMT.mant_max) != 0)


def prefix_add(a: int, b: int) -> int:
    """The pre-711f5d572 ordering: zero-passthrough wins over the NaN branch."""
    if _is_zero(a) and _is_zero(b):
        return gf_add(FMT, a, b)
    if _is_zero(a):
        return b                                        # raw payload, verbatim
    if _is_zero(b):
        return a
    return gf_add(FMT, a, b)


def add_vectors():
    """gf16_add_conformance_ax7203.py's own set: CORNERS + 52 seeded randoms."""
    corners = [0x0000, 0x8000, 0x0001, 0x01FF,
               0x3C00, 0x3E00, 0xBE00, 0x4000,
               0x7DFF, 0x7E00, 0xFE00, 0x7E01]
    rnd = random.Random(42)
    cov = corners + [rnd.randint(0, T - 1) for _ in range(52)]
    return cov, [(a, b) for a in cov for b in cov[:8]]


def sub_vectors():
    """gf16_sub_conformance_ax7203.py's own set: 8 specials + seeded randoms."""
    specials = [0x0000, 0x0001, 0x7C00, 0x7C01, 0xFC00, 0xFFFF, SIGN, 0x3C00]
    rnd = random.Random(42)
    cov = specials + [rnd.randint(0, T - 1) for _ in range(64 - len(specials))]
    return cov, [(a, b) for a in cov for b in cov[:8]]


def main() -> int:
    print("=== Why gf16 ADD passed 512/512 with a defective adder ===\n")
    print(f"canonical quiet NaN for gf16: 0x{FMT.quiet_nan:04X}\n")

    cov_a, pairs_a = add_vectors()
    fails_a = [(a, b) for a, b in pairs_a if prefix_add(a, b) != gf_add(FMT, a, b)]

    cov_s, pairs_s = sub_vectors()
    fails_s = [(a, b) for a, b in pairs_s
               if prefix_add(a, b ^ SIGN) != gf_add(FMT, a, b ^ SIGN)]

    print(f"ADD  {len(pairs_a):4d} pairs   failures under the pre-fix defect: "
          f"{len(fails_a)}")
    print(f"SUB  {len(pairs_s):4d} pairs   failures under the pre-fix defect: "
          f"{len(fails_s)}\n")

    for a, b in fails_s:
        bn = b ^ SIGN
        print(f"    SUB(0x{a:04X},0x{b:04X}) -> ADD(0x{a:04X},0x{bn:04X})   "
              f"defective=0x{prefix_add(a, bn):04X}   "
              f"correct=0x{gf_add(FMT, a, bn):04X}")

    nans_a = [x for x in cov_a if _is_nan(x)]
    nans_b = [x for x in cov_a[:8] if _is_nan(x)]
    nans_s = [x for x in cov_s if _is_nan(x)]
    print(f"\nADD: NaNs anywhere in its vectors : "
          f"{[f'0x{x:04X}' for x in nans_a]}"
          f"   all canonical? {all(x == FMT.quiet_nan for x in nans_a)}")
    print(f"ADD: NaNs in the b-position set   : {len(nans_b)}")
    print(f"SUB: NaNs anywhere in its vectors : "
          f"{[f'0x{x:04X}' for x in nans_s]}"
          f"   all canonical? {all(x == FMT.quiet_nan for x in nans_s)}")

    ok = (len(fails_a) == 0 and len(fails_s) == 4)
    print(f"""
The hardware reported 512/512 for ADD and 508/512 for SUB. Replaying the pre-fix
behaviour over each suite's own vectors gives {len(fails_a)} and {len(fails_s)}.
{"Exact match -- the silicon result is explained by vector selection alone."
 if ok else "MISMATCH -- the reproduction does not hold and this file is wrong."}

Nothing here needs a board. The whole difference lives in which NaN payloads the two
suites happened to contain.""")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
