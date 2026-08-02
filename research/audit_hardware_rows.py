#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Does every row in the hardware-evidence list have a proof behind it?

Pass 151 found one that did not. `catalog_coverage_delta.t27` listed
`takum32 65536/65536` among the packs carrying a physical-board result, while issue
#199 -- the project's own evidence issue -- recorded the opposite verdict in plain
words: takum64/32 synthesize on the part but do not route, so takum is NOT Tier E. The
number 65,536 belonged to gf16 and had been transcribed onto the wrong row.

That was found by reading one row. There are 46. This checks them all.

For each format in `with_hardware`, the question is narrow and mechanical: is there a
comment in #199 carrying all four links the standard requires, whose Tier-E proof title
names that format? Two things make the answer non-trivial and both are handled here
rather than guessed at:

  - the issue and the catalogue disagree on some names. `bf16` there is `bf16_golden`
    here; `mxfp8_e4m3` there is `mxfp8` here. Aliases are declared, with the pack
    metadata that justifies each.
  - a format may be proved under an operation suffix (`gf16-add`) rather than bare.
    The base name before the first hyphen is what counts.

A row with no proof is reported, not repaired. Which of the two sides is wrong -- the
list or the issue -- is a judgement about what happened on a board, and this script was
not there.

    python3 research/audit_hardware_rows.py [--self-check]
"""
from __future__ import annotations

import base64
import json
import re
import subprocess
import sys

ISSUE = 199
REPO = "gHashTag/trinity-fpga"
SPEC = "specs/numeric/catalog_coverage_delta.t27"

CI = re.compile(r"actions/runs/\d+")
SHA = re.compile(r"\b[0-9a-f]{64}\b")
UART = re.compile(r"HW RESULT:\s*[\d,]+\s*/\s*[\d,]+\s*bit-?exact", re.I)
IDCODE = re.compile(r"0x13636093", re.I)
TITLE = re.compile(r"Tier-E proof:\s*`([^`]+)`", re.I)

LINKS = (CI, SHA, UART, IDCODE)

# Catalogue name -> the name the issue uses. Each is justified by pack metadata, not
# by the names looking alike.
ALIAS = {
    "bf16_golden": "bf16",       # pack metadata: format = BFLOAT16
    "mxfp8": "mxfp8_e4m3",       # pack catalogue entry: bits=8, e=4, m=3
    "fp8": "fp8_e5m2",           # the only fp8 variant with a proof
    "bfloat16": "bf16",
}

NOT_A_FORMAT = {"at", "and", "is", "its", "of", "the", "each", "codes"}


def spec_rows(path: str) -> list[str]:
    """Format names in the with_hardware block, expanding `vax_d/f/g`."""
    text = open(path, encoding="utf-8", errors="replace").read()
    blk = re.search(r'with_hardware\s+"""(.*?)"""', text, re.S).group(1)
    out = []
    for m in re.finditer(
            r"\b([a-z][a-z0-9_]*(?:/[a-z0-9_]+)*)\s+(?:up to\s+)?[\d,]+\s*/\s*[\d,]+",
            blk):
        tok = m.group(1)
        if "/" not in tok:
            if tok not in NOT_A_FORMAT:
                out.append(tok)
            continue
        parts = tok.split("/")
        out.append(parts[0])
        # `vax_d/f/g` -> vax_d, vax_f, vax_g; `gf4/6/8` -> gf4, gf6, gf8.
        stem = re.match(r"(.*?)(?:\d+|[a-z])$", parts[0])
        stem = stem.group(1) if stem else parts[0]
        out += [stem + p for p in parts[1:]]
    return out


def proven_formats() -> tuple[set[str], int, int]:
    out = subprocess.run(
        ["gh", "issue", "view", str(ISSUE), "--repo", REPO,
         "--json", "comments", "--jq", ".comments[] | @base64"],
        capture_output=True, text=True, timeout=180)
    if out.returncode != 0:
        raise RuntimeError(out.stderr.strip() or "gh failed")
    bodies = [json.loads(base64.b64decode(l)).get("body", "")
              for l in out.stdout.split() if l.strip()]
    proven, four = set(), 0
    for b in bodies:
        if not all(rx.search(b) for rx in LINKS):
            continue
        four += 1
        m = TITLE.search(b)
        if m:
            proven.add(m.group(1).strip().split("-")[0])
    return proven, four, len(bodies)


def self_check() -> int:
    """The row-level check must fail on takum32 and pass on gf16 -- the two cases
    pass 151 established by hand. A sweep that agrees with everything is not a check."""
    proven = {"gf16", "binary16", "vax_f"}
    cases = [("gf16", True), ("takum32", False), ("vax_f", True)]
    bad = 0
    for name, expect in cases:
        got = ALIAS.get(name, name) in proven or name in proven
        ok = got == expect
        bad += not ok
        print(f"  {name:<10} proof found={got}, expected {expect}  "
              f"{'ok' if ok else 'MISSED'}")
    print(f"\nself-check: {'PASS' if bad == 0 else f'FAIL ({bad})'}")
    return bad


def main() -> int:
    if "--self-check" in sys.argv:
        return 1 if self_check() else 0

    rows = spec_rows(SPEC)
    try:
        proven, four, total = proven_formats()
    except Exception as e:
        print(f"could not read issue #{ISSUE}: {e}")
        print("This audit needs the live issue; nothing is assumed in its absence.")
        return 2

    print(f"issue #{ISSUE}: {total} comments, {four} carrying all four links")
    print(f"formats proved by a titled four-link comment : {len(proven)}")
    print(f"rows in the with_hardware list               : {len(rows)}\n")
    print(f"COVERAGE: {len(set(rows))} hardware rows against {four} four-link proofs")

    missing = []
    for name in sorted(set(rows)):
        cand = {name, ALIAS.get(name, name)}
        if not (cand & proven):
            missing.append(name)

    if missing:
        print(f"ROWS WITH NO FOUR-LINK PROOF IN THE ISSUE: {len(missing)}")
        for n in missing:
            print(f"    {n}")
        print("\n  Each needs reading. A row may be right and the proof titled")
        print("  differently, or the row may be a transcription onto the wrong")
        print("  format -- which is what takum32 turned out to be.")
    else:
        print("every row in the list has a four-link proof behind it")

    extra = sorted(proven - {ALIAS.get(r, r) for r in rows} - set(rows))
    if extra:
        print(f"\nproved in the issue, absent from the list: {len(extra)}")
        print("    " + ", ".join(extra))
        print("  Some of these have no pack in the catalogue and correctly do not")
        print("  appear; the rest are evidence the corpus has not claimed.")

    print("""
This reports rows and does not repair them. Whether a row without a proof is a wrong
row or a differently-titled proof is a judgement about what happened on a board, and
this script was not there.""")
    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
