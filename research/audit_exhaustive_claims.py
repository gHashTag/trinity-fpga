#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A claim of "exhaustive" is arithmetic, so it can be checked.

`specs/numeric/catalog_coverage_delta.t27` said:

    Two are exhaustive over the whole code space: binary16 and takum32, at
    65,536/65,536 each.

binary16 is 16 bits, so 65,536 is the whole code space. **takum32 is 32 bits**, where
the whole code space is 4,294,967,296 -- so 65,536 is 0.00153% of it. The same sweep
that shows this also shows the sentence is wrong in the other direction: eleven cells
record a count equal to 2^width, not two.

That pairing is worth stating plainly. One is an over-claim a reviewer would catch and
which costs more than it gains; the other is an under-claim that gives away credit the
corpus has already earned. The largest defect found in either paper was of the second
kind -- an abstract reporting six packs where the body had 83.

The rule needs no judgement:

    a cell may be called exhaustive only if its count == 2 ** width

Widths come from the format name where the name states one (`fp8_e5m2`, `binary16`,
`takum32`) and from an explicit table otherwise. A format whose width cannot be
resolved is skipped and said to be skipped, rather than assumed.

    python3 research/audit_exhaustive_claims.py [--self-check]
"""
from __future__ import annotations

import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

SPEC = "specs/numeric/catalog_coverage_delta.t27"

# Widths that the name does not state. Everything else is derived from the name.
EXPLICIT = {
    "bfloat16": 16, "double_double": 128, "quad_double": 256,
    "ibm_hfp32": 32, "ibm_hfp64": 64, "ibm_hfp128": 128,
    "ms_mbf32": 32, "ms_mbf64": 64,
    "vax_f": 32, "vax_d": 64, "vax_g": 64, "vax_h": 128,
    "nf4": 4, "int4": 4, "int8": 8, "int16": 16, "int32": 32, "int64": 64,
    "uint4": 4, "uint8": 8, "uint16": 16, "uint32": 32,
    "x87_fp80": 80, "x87_48bit": 48, "pdp11_float": 32, "mxint8": 8,
    "bcd": None, "block_fp": None, "shared_exp": None, "per_channel_scale": None,
    "stochastic_rounding": None, "tapered_fp": None, "unum_i": None,
    "unum_ii": None, "q_format": None, "afp": None, "cray_float": 64,
}

NAME_WIDTH = re.compile(
    r"^(?:fp|gf|binary|decimal|posit|takum|lns|tekum|mxfp|mxgf|q)(\d+)")

# "name 256/256" or "gf4/6/8 up to 512/512" -- only the first shape is unambiguous.
CELL = re.compile(r"\b([a-z][a-z0-9_]*)\s+(\d+)\s*/\s*(\d+)\b")


def width_of(name: str):
    if name in EXPLICIT:
        return EXPLICIT[name]
    m = NAME_WIDTH.match(name)
    return int(m.group(1)) if m else None


def cells(text: str):
    """(name, count) for every unambiguous `name N/N` cell in the text."""
    out = {}
    for m in CELL.finditer(text):
        name, a, b = m.group(1), int(m.group(2)), int(m.group(3))
        if a != b:                      # a partial result is not a coverage cell
            continue
        out[name] = a
    return out


def self_check() -> int:
    """The rule must reject the sentence this file was written for."""
    bad = 0
    for name, count, should_be_exhaustive in (
            ("binary16", 65536, True),
            ("takum32", 65536, False),
            ("takum8", 256, True)):
        w = width_of(name)
        got = (count == 2 ** w)
        ok = got == should_be_exhaustive
        bad += not ok
        print(f"  {name:<10} {w:>3} bits, count {count:>6} -> "
              f"exhaustive={got}, expected {should_be_exhaustive}  "
              f"{'ok' if ok else 'MISSED'}")
    print(f"\nself-check: {'PASS' if bad == 0 else f'FAIL ({bad})'}")
    return bad


def main() -> int:
    if "--self-check" in sys.argv:
        return 1 if self_check() else 0

    path = os.path.join(ROOT, SPEC)
    if not os.path.exists(path):
        print(f"not found: {SPEC}")
        return 2
    text = open(path, encoding="utf-8", errors="replace").read()

    found = cells(text)
    exhaustive, sampled, unknown = [], [], []
    for name, count in sorted(found.items()):
        w = width_of(name)
        if w is None:
            unknown.append(name)
            continue
        (exhaustive if count == 2 ** w else sampled).append((name, w, count))

    print(f"{SPEC}")
    print(f"  coverage cells of the form `name N/N` : {len(found)}")
    print(f"  width resolved                        : "
          f"{len(exhaustive) + len(sampled)}")
    print(f"  width NOT resolved, skipped           : {len(unknown)}"
          f"{'  (' + ', '.join(sorted(unknown)[:8]) + ')' if unknown else ''}\n")

    print(f"genuinely exhaustive (count == 2^width) : {len(exhaustive)}")
    for name, w, count in exhaustive:
        print(f"    {name:<14} {w:>3} bits  {count:>10,} = 2^{w}")

    print(f"\nsampled (count < 2^width)               : {len(sampled)}")
    print(f"COVERAGE: {len(exhaustive) + len(sampled)} coverage cells with a resolvable width")

    # The claim in prose, checked against the arithmetic above.
    bad = 0
    claim = re.search(
        r"(\w+)\s+are exhaustive over the whole code space:\s*([^.]+)\.", text)
    if claim:
        # Drop the trailing "at 65,536/65,536 each" before splitting, or its digits
        # get counted as format names.
        listed = re.sub(r",?\s*at\s.*$", "", claim.group(2)).strip()
        named = [n.strip().split()[0]
                 for n in re.split(r",| and ", listed) if n.strip()]
        print(f"\nthe spec's prose names: {named}")
        real = {n for n, _, _ in exhaustive}
        for n in named:
            w = width_of(n)
            if w is None:
                continue
            if n not in real:
                bad += 1
                c = found.get(n)
                print(f"  OVER-CLAIM  {n} is {w} bits, so exhaustive means "
                      f"{2 ** w:,} codes; the cell records {c:,} "
                      f"({c / 2 ** w * 100:.5f}%)")
        missing = sorted(real - set(named))
        if missing:
            bad += 1
            print(f"  UNDER-CLAIM the prose names {len(named)}, but "
                  f"{len(real)} cells are exhaustive; unnamed: "
                  f"{', '.join(missing)}")

    print(f"\nclaims disagreeing with the arithmetic: {bad}")
    print("""
Both directions matter. An over-claim is what a reviewer catches, and it costs more
than it gains. An under-claim gives away credit already earned -- the largest defect
found in either paper was of that kind, an abstract reporting six packs where the body
had 83.""")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
