#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Do the corpus's format tables describe layouts that can exist?

Pass 146 traced a takum8 defect to a field that did not fit the width it was decoded
at. Pass 147 asked whether that shape appears anywhere else and found it immediately,
in `conformance/compute_conformance_template.py` -- the host that drives hardware
compute conformance:

    "gf4":  (4,  2, 2, 1)     1+E+M = 5 for a 4-bit format; the exponent field works
                              out to [3:2] and overlaps the sign bit at 3
    "gf24": (24, 7, 17, 63)   1+E+M = 25 for a 24-bit format

Both were wrong against `conformance/gf_ref.py` AND against the RTL's own
`gf_adder_param #(.EXP_BITS(...), .MANT_BITS(...))` parameters, which agree with each
other. Neither was reported by anything, because a Python tuple has no width and
nothing was checking.

Two invariants decide it without needing to know any format's intent:

    1 + E + M == width          the fields must account for the word, exactly
    exp_hi < sign_bit           they must not overlap

Both are properties of a sign-exponent-mantissa layout as such. A table that fails
either describes a layout that cannot exist, whatever the format is.

Where a second table names the same format, the two are compared as well -- that is
how the gf4 and gf24 rows were caught, and disagreement between tables is a fact
about the corpus rather than a judgement about a format.

    python3 research/audit_format_tables.py
"""
from __future__ import annotations

import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# (path, description, regex yielding name, width, E, M) -- width None means "derive".
TABLES = [
    ("conformance/compute_conformance_template.py",
     "the hardware compute host",
     re.compile(r'"(\w+)":\s*\((\d+),\s*(\d+),\s*(\d+),\s*(-?\d+)\)'),
     ("name", "width", "E", "M", "bias")),
    ("conformance/gf_ref.py",
     "the GF reference model",
     re.compile(r'"(\w+)":\s*GFFormat\("\w+",\s*exp_bits=(\d+),\s*'
                r'mant_bits=(\d+),\s*bias=([^),]+)\)'),
     ("name", "E", "M", "bias")),
]


def parse(path: str, rx, fields):
    """Rows as {name: (width_or_None, E, M, bias_or_None)}."""
    full = os.path.join(ROOT, path)
    if not os.path.exists(full):
        return {}
    text = open(full, encoding="utf-8", errors="replace").read()
    rows = {}
    for m in rx.finditer(text):
        g = dict(zip(fields, m.groups()))
        try:
            bias = int(eval(g["bias"], {"__builtins__": {}}, {}))
        except Exception:
            bias = None
        rows[g["name"]] = (
            int(g["width"]) if "width" in g else None,
            int(g["E"]), int(g["M"]), bias)
    return rows


def derived_width(name: str):
    """A width implied by the format's own name, e.g. gf24 -> 24. None if unclear."""
    m = re.fullmatch(r"[a-z_]+?(\d+)", name)
    return int(m.group(1)) if m else None


def self_check() -> int:
    """Feed the invariants the two rows as they stood before pass 147.

    A gate that reports zero proves nothing on its own -- it reads the same as a gate
    that cannot see. These are the exact rows this file was written for, and both must
    fail both invariants.
    """
    historical = {"gf4": (4, 2, 2), "gf24": (24, 7, 17)}
    missed = 0
    for name, (w, E, M) in historical.items():
        total = 1 + E + M
        sign_bit = w - 1
        exp_hi = M + E - 1
        caught = []
        if total != w:
            caught.append(f"1+E+M = {total}, but the format is {w} bits")
        if exp_hi >= sign_bit:
            caught.append(f"exponent field [{exp_hi}:{M}] reaches the sign bit "
                          f"at {sign_bit}")
        print(f"  historical {name:<5} (E={E}, M={M}): "
              f"{len(caught)} invariant(s) fired")
        for c in caught:
            print(f"      {c}")
        if not caught:
            missed += 1
    print(f"\nself-check: {'PASS' if missed == 0 else f'FAIL ({missed} missed)'}")
    return missed


def main() -> int:
    import sys as _sys
    if "--self-check" in _sys.argv:
        return 1 if self_check() else 0

    parsed = {}
    for path, desc, rx, fields in TABLES:
        rows = parse(path, rx, fields)
        parsed[path] = (desc, rows)
        print(f"{path}\n  {desc}: {len(rows)} rows")

    print()
    bad = 0

    # ---- invariant 1 and 2: the layout must be able to exist -------------------
    for path, (desc, rows) in parsed.items():
        for name, (width, E, M, bias) in sorted(rows.items()):
            w = width if width is not None else derived_width(name)
            if w is None:
                continue
            total = 1 + E + M
            sign_bit = w - 1
            exp_hi = M + E - 1
            problems = []
            if total != w:
                problems.append(f"1+E+M = {total}, but the format is {w} bits")
            if exp_hi >= sign_bit:
                problems.append(
                    f"exponent field [{exp_hi}:{M}] reaches the sign bit at {sign_bit}")
            if problems:
                bad += 1
                print(f"IMPOSSIBLE LAYOUT  {path}  {name}  (E={E}, M={M})")
                for p in problems:
                    print(f"    {p}")

    # ---- invariant 3: tables naming the same format must agree ----------------
    names = set()
    for _, (_, rows) in parsed.items():
        names |= set(rows)
    for name in sorted(names):
        seen = {p: r[name] for p, (_, r) in parsed.items() if name in r}
        if len(seen) < 2:
            continue
        em = {(v[1], v[2]) for v in seen.values()}
        bi = {v[3] for v in seen.values() if v[3] is not None}
        if len(em) > 1 or len(bi) > 1:
            bad += 1
            print(f"TABLES DISAGREE  {name}")
            for p, v in seen.items():
                print(f"    {p}: E={v[1]} M={v[2]} bias={v[3]}")

    print(f"\nrows describing a layout that cannot exist, or disagreeing across "
          f"tables: {bad}")
    print(f"COVERAGE: {sum(len(r) for _, r in parsed.values())} format-table rows")
    print("""
Both invariants hold for any sign-exponent-mantissa format, so neither needs to know
what a format means. A failure is not a matter of opinion: the fields either account
for the word or they do not. Where two tables name one format and differ, read both --
this reports the disagreement and does not decide it.""")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
