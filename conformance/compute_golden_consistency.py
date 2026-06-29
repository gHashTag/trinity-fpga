#!/usr/bin/env python3
"""Compute-golden consistency: gf6/gf8/gf12 self-contained integer refs must match
the proven gf_ref.py oracle over a coverage sample.

gf4/16/20/24 use gf_ref.py directly (consistent by construction); gf6/gf8/gf12
have INDEPENDENT self-contained integer references (only gf6/gf8 are HW-proven).
This cross-check regression-protects them against divergence from gf_ref.py —
the same protection golden_consistency.py gives the decode host goldens.

  python3 conformance/compute_golden_consistency.py
"""
import sys, random
sys.path.insert(0, "conformance") if "conformance" not in sys.path else None
from gf_ref import FORMATS, gf_add
from gf6_add_conformance_ax7203 import gf6_add
from gf8_add_conformance_ax7203 import gf8_add
from gf12_add_conformance_ax7203 import gf12_add

CHECKS = [
    ("gf6",  FORMATS["gf6"],  gf6_add,  0x3F,  [0x00,0x01,0x3F,0x20,0x10,0x30,0x0F,0x08]),
    ("gf8",  FORMATS["gf8"],  gf8_add,  0xFF,  [0x00,0x01,0x7F,0xFF,0x10,0x40,0x80,0x90]),
    ("gf12", FORMATS["gf12"], gf12_add, 0xFFF, [0x000,0x001,0x7FF,0x400,0x3C0,0x3FF,0x010,0x100]),
]


def main():
    rnd = random.Random(42)
    bad = chk = 0
    for name, fmt, fn, mask, corners in CHECKS:
        samp = corners + [rnd.randint(0, mask) for _ in range(200)]
        nb = 0
        for a in samp:
            for b in samp[:8]:
                chk += 1
                if fn(a, b) != gf_add(fmt, a, b):
                    nb += 1
                    bad += 1
                    if nb <= 4:
                        print(f"[{name}] a=0x{a:x} b=0x{b:x} self_ref!=gf_ref")
        print(f"[{name}] sample cross-check, {nb} mismatches")
    print(f"COMPUTE GOLDEN CONSISTENCY: {chk} pairs, {bad} total mismatches")
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
