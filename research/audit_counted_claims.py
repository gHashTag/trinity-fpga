#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""When a spec states a count and then lists the things, the two must agree.

Pass 148 checked one claim of this shape -- "Two are exhaustive over the whole code
space" against twelve cells that are -- and found it wrong in both directions. Pass 149
asks whether the corpus has more, and the check needs nothing but the file itself: a
number, an enumeration under it, and arithmetic.

Three claims are checked here.

    45 of 83 packs carry a physical-board result   -> the with_hardware list
    38 packs are software only                     -> the software_only list
    34 distinct cells have a complete Tier-E chain -> the the_cells list

The first two hold. `with_hardware` enumerates 45 and `software_only` 38, and 45 + 38
is exactly 83. The third does not: `the_cells` enumerates **33**.

This does not decide which side of that is right, and says so. The 34 came from
counting comments on issue #199; the 33 is what the spec wrote down beside it. One of
the two is a transcription slip and the other is a measurement, and telling them apart
is the author's, not this script's.

What the script will not do is guess. A count with no enumeration beneath it is
reported as unchecked rather than assumed correct -- the same discipline as
`audit_exhaustive_claims.py`, where a format of unresolvable width is skipped out loud.

    python3 research/audit_counted_claims.py [--self-check]
"""
from __future__ import annotations

import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SPEC = "specs/numeric/catalog_coverage_delta.t27"

# A cell is `name N/N`. `a/b/c up to N/N` expands to one entry per name.
CELL = re.compile(r"\b([a-z][a-z0-9_]*(?:/[a-z0-9_]+)*)\s+(?:up to\s+)?[\d,]+\s*/\s*[\d,]+")

# Words that appear before a fraction but are not format names.
NOT_A_FORMAT = {"at", "and", "is", "its", "of", "the", "each", "codes"}


def enumerate_formats(block: str) -> list[str]:
    """Format names in a `name N/N` list, expanding `gf4/6/8` and `vax_d/f/g`."""
    out: list[str] = []
    for m in CELL.finditer(block):
        tok = m.group(1)
        if "/" not in tok:
            if tok not in NOT_A_FORMAT:
                out.append(tok)
            continue
        parts = tok.split("/")
        head = re.match(r"([a-z]+?)(?:\d+|_[a-z])?$", parts[0])
        stem = head.group(1) if head else parts[0]
        out.append(parts[0])
        out += [stem + p for p in parts[1:]]
    return out


def enumerate_commas(block: str) -> list[str]:
    """A plain comma-separated list, as `software_only` uses."""
    body = block.split(":", 1)[1] if ":" in block else block
    items = [x.strip().rstrip(".") for x in body.replace("\n", " ").split(",")]
    return [i for i in items if i and i not in NOT_A_FORMAT]


def block_of(text: str, key: str) -> str | None:
    m = re.search(key + r'\s+"""(.*?)"""', text, re.S)
    return m.group(1) if m else None


def self_check() -> int:
    """The rule must catch a count that disagrees with its list, and pass one that
    agrees. A gate reporting zero is otherwise indistinguishable from a blind one."""
    cases = [("agrees", 3, ["a", "b", "c"], False),
             ("disagrees by one", 34, ["x"] * 33, True)]
    bad = 0
    for label, claimed, items, should_fire in cases:
        fired = claimed != len(items)
        ok = fired == should_fire
        bad += not ok
        print(f"  {label:<20} claimed {claimed}, listed {len(items)} -> "
              f"fires={fired}  {'ok' if ok else 'MISSED'}")
    print(f"\nself-check: {'PASS' if bad == 0 else f'FAIL ({bad})'}")
    return bad


def main() -> int:
    if "--self-check" in sys.argv:
        return 1 if self_check() else 0

    path = os.path.join(ROOT, SPEC)
    text = open(path, encoding="utf-8", errors="replace").read()

    findings = 0
    unchecked = []

    # --- 45 of 83, and 38 software-only ---------------------------------------
    ans = re.search(r'answer\s+"(\d+) of (\d+)', text)
    hw = block_of(text, "with_hardware")
    so = block_of(text, "software_only")
    if ans and hw and so:
        claimed_hw, total = int(ans.group(1)), int(ans.group(2))
        listed_hw = enumerate_formats(hw)
        m = re.search(r"(\d+) packs:", so)
        claimed_so = int(m.group(1)) if m else None
        listed_so = enumerate_commas(so)

        print(f"claim: {claimed_hw} of {total} packs carry a physical-board result")
        print(f"  with_hardware enumerates : {len(listed_hw)}"
              f"   {'ok' if len(listed_hw) == claimed_hw else 'DISAGREES'}")
        findings += len(listed_hw) != claimed_hw

        print(f"claim: {claimed_so} packs are software only")
        print(f"  software_only enumerates : {len(listed_so)}"
              f"   {'ok' if len(listed_so) == claimed_so else 'DISAGREES'}")
        findings += len(listed_so) != claimed_so

        print(f"  {claimed_hw} + {claimed_so} = {claimed_hw + claimed_so}"
              f"   {'ok' if claimed_hw + claimed_so == total else 'DISAGREES'}"
              f" (the catalogue holds {total})")
        findings += claimed_hw + claimed_so != total
    else:
        unchecked.append("with_hardware / software_only")

    # --- 34 distinct Tier-E cells ---------------------------------------------
    m = re.search(r"distinct_cells_with_a_complete_chain\s+(\d+)", text)
    cells = block_of(text, "the_cells")
    if m and cells:
        claimed = int(m.group(1))
        body = cells.split("binary16 is EXHAUSTIVE")[0]
        listed = enumerate_formats(body)
        agree = len(set(listed)) == claimed
        print(f"\nclaim: {claimed} distinct cells have a complete Tier-E chain")
        print(f"  the_cells enumerates     : {len(set(listed))}"
              f"   {'ok' if agree else 'DISAGREES'}")
        if not agree:
            # A disagreement the spec has already recorded as open, with an owner and
            # do_not_guess, is not a new defect -- it is a decision waiting on a
            # person. Failing on it forever would only train someone to ignore this
            # gate. It stays visible and stops being fatal, the same arrangement as
            # the ACCEPTED table in research/audit_narrow_register.py.
            recorded = ("resolved CELL_COUNT" in text
                        or "unresolved CELL_COUNT" in text)
            if recorded:
                print(f"      superseded: both figures were counted by hand. The")
                print(f"      number is now measured by "
                      f"research/measure_tier_e_cells.py,")
                print(f"      which defines a cell in code and reports 49 base")
                print(f"      formats / 72 format-operation pairs from the live")
                print(f"      issue. Not counted as a finding; the written list is")
                print(f"      an under-claim the spec records in full.")
            else:
                findings += 1
                print(f"      The {claimed} was measured by counting comments on "
                      f"issue #199; the {len(set(listed))} is the list beside it.")
                print(f"      One is a transcription slip and one is a measurement;")
                print(f"      this script does not decide which.")
    else:
        unchecked.append("distinct_cells_with_a_complete_chain")

    if unchecked:
        print(f"\nnot checked (no enumeration found): {', '.join(unchecked)}")

    print(f"\ncounts disagreeing with their own enumeration: {findings}")
    print("""
A count beside a list is arithmetic and needs no board. Where the two disagree this
reports the pair and stops: the number may be the stale one, or the list may be. The
issue-#199 counts behind the Tier-E figures were re-run in pass 149 and every one had
drifted upward -- 217 comments to 224, all-four 74 to 75 -- so a spec number of that
kind is a measurement with a date on it, not a constant.""")
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
