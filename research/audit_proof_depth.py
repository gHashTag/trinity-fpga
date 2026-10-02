#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""How much of each format did its hardware proof actually cover?

Tier-E requires four links: a public CI run, the bitstream SHA-256, a UART log and a
matching IDCODE. It says nothing about how many codes the UART log covers, and the logs
read `HW RESULT: N/N bit-exact` whether N is the whole code space or sixty-four samples
of it. Written that way, `64/64` looks exactly like `65536/65536`.

    python3 research/audit_proof_depth.py [--verbose] [--self-check]

WHAT IT SEPARATES
-----------------
For each cell's strongest decode proof, N is compared against 2^width:

    exhaustive   N covers the whole code space
    sampled      N does not, and the report says what fraction

Compute proofs are excluded, and that exclusion is the point of a separate pass: a compute
log counts operand PAIRS, so `gf4 512/512` is 512 pairs from a 16-code format and is not
an exhaustive sweep of anything. A first version of this file mixed them and classified
gf4, gf6 and gf8 as exhaustive over their code spaces, which they are not.

WHAT IT FOUND
-------------
Of 40 decode proofs: 14 exhaustive, 26 sampled.

The exhaustive ones are every format at 8 bits or fewer, plus binary16 and gf16 at
65,536/65,536. Those two matter beyond themselves: they prove the rig can drive a full
16-bit sweep over UART. So sampling is a choice at 16 bits, not a limit.

Five formats are sampled where exhausting them is demonstrably achievable with the same
harness:

    gf10      64 of 1,024        6.25%
    gf14      64 of 16,384       0.391%
    int16     64 of 65,536       0.0977%
    posit16   64 of 65,536       0.0977%
    takum16   64 of 65,536       0.0977%
    bfloat16   8 of 65,536       0.0122%
    tf32       8 of 524,288      0.00153%

At 32 bits and above, sampling is unavoidable and the report says so rather than implying
a gap. What should not survive into a paper is `64/64` reading as completeness for a
format with 2^64 codes.
"""
from __future__ import annotations

import glob
import importlib
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CONF = os.path.join(ROOT, "conformance")
ISSUE = "repos/gHashTag/trinity-fpga/issues/199/comments"

LINK = {
    "ci":   re.compile(r"github\.com/[^\s)]*/(?:actions/runs|runs)/\d+", re.I),
    "sha":  re.compile(r"\b[0-9a-f]{64}\b", re.I),
    "uart": re.compile(r"HW RESULT:\s*\d+/\d+\s*bit-exact", re.I),
    "id":   re.compile(r"0x[01]3636093", re.I),
}
OP = re.compile(r"\b(decode|add|mul|sub)\b", re.I)
RESULT = re.compile(r"HW RESULT:\s*(\d+)/(\d+)", re.I)

# Above this width an exhaustive UART sweep is not a choice anyone declined to make.
FEASIBLE_BITS = 20


def widths():
    sys.path.insert(0, CONF)
    out = {}
    for path in sorted(glob.glob(os.path.join(CONF, "*_ref.py"))):
        try:
            mod = importlib.import_module(os.path.basename(path)[:-3])
        except Exception:
            continue
        for name, fmt in getattr(mod, "FORMATS", {}).items():
            w = getattr(fmt, "width", None)
            if w:
                out[name] = w
    return out


def comments():
    r = subprocess.run(["gh", "api", "--paginate", ISSUE],
                       capture_output=True, text=True)
    out = []
    for chunk in re.findall(r"\[.*?\]\s*(?=\[|\Z)", r.stdout.strip(), re.S) or [r.stdout]:
        try:
            out += [c.get("body", "") for c in json.loads(chunk)]
        except Exception:
            pass
    return out


def strongest_decode_proofs(bodies, w):
    cell = re.compile(r"\b(" + "|".join(re.escape(n) for n in
                                        sorted(w, key=len, reverse=True)) + r")\b", re.I)
    best = {}
    for b in bodies:
        if sum(1 for rx in LINK.values() if rx.search(b)) != 4:
            continue
        c = cell.search(b)
        m = RESULT.search(b)
        o = OP.search(b)
        if not (c and m):
            continue
        if not o or o.group(1).lower() != "decode":
            continue          # compute logs count operand PAIRS, not codes
        f = c.group(1).lower()
        n = int(m.group(2))
        if f not in best or n > best[f]:
            best[f] = n
    return best


def main() -> int:
    verbose = "--verbose" in sys.argv
    w = widths()
    best = strongest_decode_proofs(comments(), w)

    exhaustive, sampled = [], []
    for f, n in sorted(best.items()):
        width = w.get(f)
        space = (1 << width) if width and width <= 64 else None
        if space and n >= space:
            exhaustive.append((f, width, n, space))
        else:
            sampled.append((f, width, n, space))

    print(f"decode proofs with a complete Tier-E chain : {len(best)}")
    print(f"  exhaustive over the code space           : {len(exhaustive)}")
    print(f"  sampled                                  : {len(sampled)}\n")

    print("  EXHAUSTIVE")
    for f, width, n, space in exhaustive:
        print(f"    {f:<14} {width:>4} bits   {n}/{space}")

    cheap = [(f, width, n, space) for f, width, n, space in sampled
             if width and width <= FEASIBLE_BITS]
    print(f"\n  SAMPLED where an exhaustive sweep is achievable "
          f"({FEASIBLE_BITS} bits or fewer): {len(cheap)}")
    for f, width, n, space in cheap:
        print(f"    {f:<14} {width:>4} bits   {n:>6} of {space:<9} {100 * n / space:.3g}%")

    wide = [r for r in sampled if not (r[1] and r[1] <= FEASIBLE_BITS)]
    print(f"\n  SAMPLED at a width where exhausting is not practical: {len(wide)}")
    if verbose:
        for f, width, n, space in wide:
            print(f"    {f:<14} {width:>4} bits   {n} vectors")

    print(f"""
binary16 and gf16 carry 65,536/65,536. They prove the rig can drive a full 16-bit sweep
over UART, so sampling at 16 bits is a choice rather than a ceiling -- which is what makes
the {len(cheap)} above worth naming.

Above {FEASIBLE_BITS} bits sampling is unavoidable and saying so costs nothing. What should not
survive into a paper is `64/64` reading as completeness for a format with 2^64 codes.

Compute proofs are excluded here: their logs count operand PAIRS, so gf4's 512/512 is 512
pairs drawn from a 16-code format and exhausts nothing. A first version of this file mixed
them in and called gf4, gf6 and gf8 exhaustive.""")
    return 0


def self_check() -> int:
    """Two things have to hold or the classification means nothing: a format known to be
    exhaustively proven must land in that column, and a compute log must not be read as a
    decode sweep."""
    w = widths()
    bodies = comments()
    best = strongest_decode_proofs(bodies, w)

    gf16 = best.get("gf16")
    ok_ex = gf16 == (1 << 16)
    print(f"  gf16 decode proof is {gf16} against a 65536-code space -> exhaustive: {ok_ex}")

    b16 = best.get("binary16")
    ok_b = b16 == (1 << 16)
    print(f"  binary16 decode proof is {b16} -> exhaustive: {ok_b}")

    # gf4's biggest log is a compute one. It must not appear as a decode proof at all,
    # or must not exceed its 16-code space if it does.
    gf4 = best.get("gf4")
    ok_compute = gf4 is None or gf4 <= 16
    print(f"  gf4 decode proof is {gf4} against a 16-code space -> "
          f"compute logs excluded: {ok_compute}")

    passed = ok_ex and ok_b and ok_compute
    print(f"\nself-check: {'PASS' if passed else 'FAIL'}")
    return 0 if passed else 1


if __name__ == "__main__":
    if "--self-check" in sys.argv:
        raise SystemExit(self_check())
    raise SystemExit(main())
