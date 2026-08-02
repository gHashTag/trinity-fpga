#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Count Tier-E cells from issue #199 by a definition written down in code.

`catalog_coverage_delta.t27` records `distinct_cells_with_a_complete_chain 34` beside a
list of 33 names. Pass 149 could not settle which was right, because "cell" had never
been defined anywhere -- it was a number someone had counted once, and a number counted
once is a transcription, not a measurement.

This defines it. A Tier-E proof comment is one carrying **all four** links the standard
requires:

    a public CI run URL          github.com/.../actions/runs/N
    a bitstream SHA-256          a 64-hex-digit string
    a UART conformance line      HW RESULT: N/N bit-exact
    a matching IDCODE            0x13636093

and the cell it proves is the backticked name in its `### Tier-E proof:` title, with the
operation taken from the trailing `-op` or the parenthesised note. Both readings of
"cell" are reported, because the corpus has used the word both ways:

    distinct (format, operation) pairs
    distinct base formats

Everything here is derived from the live issue, so the answer carries a date. Pass 149
already showed these figures drift: the issue grew from 217 comments to 224 between
pass 91 and pass 149, and every link count rose with it.

    python3 research/measure_tier_e_cells.py
    python3 research/measure_tier_e_cells.py --self-check
"""
from __future__ import annotations

import base64
import json
import re
import subprocess
import sys

ISSUE = 199
REPO = "gHashTag/trinity-fpga"

CI = re.compile(r"actions/runs/\d+")
SHA = re.compile(r"\b[0-9a-f]{64}\b")
UART = re.compile(r"HW RESULT:\s*[\d,]+\s*/\s*[\d,]+\s*bit-?exact", re.I)
IDCODE = re.compile(r"0x13636093", re.I)
TITLE = re.compile(r"Tier-E proof:\s*`([^`]+)`\s*(?:\(([^)]*)\))?", re.I)

LINKS = (("ci_url", CI), ("sha256", SHA), ("uart_log", UART), ("idcode", IDCODE))


def fetch() -> list[str]:
    out = subprocess.run(
        ["gh", "issue", "view", str(ISSUE), "--repo", REPO,
         "--json", "comments", "--jq", ".comments[] | @base64"],
        capture_output=True, text=True, timeout=180)
    if out.returncode != 0:
        raise RuntimeError(out.stderr.strip() or "gh failed")
    return [json.loads(base64.b64decode(line)).get("body", "")
            for line in out.stdout.split() if line.strip()]


def self_check() -> int:
    """The four link patterns must each fire on a real proof and stay silent on a
    comment missing that link. Without this the count is only as good as four regexes
    nobody ever exercised."""
    good = ("### Tier-E proof: `gf16` (add)\n"
            "- CI run: https://github.com/x/y/actions/runs/28503459393\n"
            "- Bitstream SHA256: `76204d1e469a0b052845680d22848e4fc63c9ffee17c9"
            "0219c5ac162b077ae94`\n"
            "- IDCODE recheck: `0x13636093`\n"
            "```\nHW RESULT: 256/256 bit-exact (fails=0)\n```\n")
    bad = 0
    for name, rx in LINKS:
        if not rx.search(good):
            print(f"  {name:<9} MISSED a link that is present"); bad += 1
        else:
            print(f"  {name:<9} fires on a complete proof            ok")
    for name, rx in LINKS:
        stripped = good
        for m in list(rx.finditer(good))[::-1]:
            stripped = stripped[:m.start()] + stripped[m.end():]
        if rx.search(stripped):
            print(f"  {name:<9} still fires with the link removed  WRONG"); bad += 1
    m = TITLE.search(good)
    if not (m and m.group(1) == "gf16"):
        print("  title     did not yield the cell name             WRONG"); bad += 1
    else:
        print("  title     yields the cell name                    ok")
    print(f"\nself-check: {'PASS' if bad == 0 else f'FAIL ({bad})'}")
    return bad


def main() -> int:
    if "--self-check" in sys.argv:
        return 1 if self_check() else 0

    try:
        bodies = fetch()
    except Exception as e:                                   # network, auth, rate
        print(f"could not read issue #{ISSUE}: {e}")
        print("This measurement needs the live issue; nothing is assumed in its "
              "absence.")
        return 2

    counts = {n: 0 for n, _ in LINKS}
    four = []
    for b in bodies:
        hits = 0
        for name, rx in LINKS:
            if rx.search(b):
                counts[name] += 1
                hits += 1
        if hits == 4:
            four.append(b)

    pairs, formats, untitled = set(), set(), 0
    for b in four:
        m = TITLE.search(b)
        if not m:
            untitled += 1
            continue
        name = m.group(1).strip()
        base = name.split("-")[0]
        op = name.split("-", 1)[1] if "-" in name else (m.group(2) or "").strip()
        formats.add(base)
        pairs.add((base, op.lower()))

    print(f"issue #{ISSUE}, read live")
    print(f"  comments                          : {len(bodies)}")
    for name, _ in LINKS:
        print(f"  carrying {name:<20}     : {counts[name]}")
    print(f"  carrying ALL FOUR                 : {len(four)}")
    print(f"    of those, without a proof title : {untitled}\n")

    print(f"distinct (format, operation) cells  : {len(pairs)}")
    print(f"distinct base formats               : {len(formats)}\n")
    print(f"COVERAGE: {len(bodies)} issue comments, {len(four)} with all four links")
    print("  " + ", ".join(sorted(formats)))

    print("""
Both readings are given because the corpus has used "cell" both ways, and neither is
derivable from the other. What matters is that either can now be recomputed: the
definition is four regexes and a title pattern, all of them exercised by --self-check,
rather than a number someone counted once.

The figures carry a date. They rose between pass 91 and pass 149 as the issue grew, and
they will rise again.""")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
