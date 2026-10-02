#!/usr/bin/env python3
"""For each credited hardware cell, show the heading that credited it.

Pass 93 found one false positive -- takum32 credited by a comment saying it is
unroutable -- and fixed the attribution to use only the comment's claim region. The
fix was validated on that single case.

A fix confirmed on the example that motivated it is not confirmed. This prints, for
every credited cell, the heading of the comment it came from, so each attribution can
be read rather than assumed.

    python3 research/audit_hw_attribution.py
"""
from __future__ import annotations

import json
import re
import subprocess

LINKS = {
    "ci": re.compile(r"github\.com/[^\s)]*/(?:actions/runs|runs)/\d+", re.I),
    "sha": re.compile(r"\b[0-9a-f]{64}\b", re.I),
    "uart": re.compile(r"HW RESULT:\s*(\d+)/(\d+)\s*bit-exact", re.I),
    "idcode": re.compile(r"0x[01]3636093", re.I),
}

CELL = re.compile(r"\b(gf\d+|gfternary|bcd|binary\d+|decimal\d+|fp8_e\dm\d|fp8|"
                  r"fp6_e\dm\d|fp4_e\dm\d|bfloat\d+|mxfp\d+|mxgf\d+|posit\d+|"
                  r"takum\d+|tekum\d+|afp|cray_float|vax_[dfgh]|ms_mbf\d+|"
                  r"ibm_hfp\d+|int\d+|uint\d+|lns\d+|nf4|pdp11_float|"
                  r"x87_\w+|double_double|quad_double)\b", re.I)

NEGATIVE = re.compile(r"unroutable|not routable|impossible|still (?:un|not)|"
                      r"cannot|fails to route|no cell|structural", re.I)


def claim_region(body):
    parts = []
    lines = body.strip().splitlines()
    if lines:
        parts.append(lines[0])
    for m in re.finditer(r"HW RESULT:", body, re.I):
        parts.append(body[max(0, m.start() - 260):m.end() + 120])
    return "\n".join(parts)


def main() -> int:
    credited = {}
    for page in range(1, 6):
        raw = subprocess.run(
            ["gh", "api", "repos/gHashTag/trinity-fpga/issues/199/comments"
             f"?per_page=100&page={page}"], capture_output=True, text=True).stdout
        try:
            chunk = json.loads(raw)
        except json.JSONDecodeError:
            break
        if not chunk:
            break
        for c in chunk:
            body = c.get("body") or ""
            if not all(p.search(body) for p in LINKS.values()):
                continue
            region = claim_region(body)
            head = " ".join((body.strip().splitlines() or [""])[0].split())[:118]
            m = LINKS["uart"].search(body)
            res = f"{m.group(1)}/{m.group(2)}" if m else "?"
            for cell in {x.lower() for x in CELL.findall(region)}:
                spans = [region[max(0, mm.start() - 60):mm.end() + 60]
                         for mm in re.finditer(re.escape(cell), region, re.I)]
                if spans and all(NEGATIVE.search(s) for s in spans):
                    continue
                credited.setdefault(cell, (head, res, c["id"]))

    print(f"credited cells: {len(credited)}\n")
    suspicious = 0
    for cell, (head, res, cid) in sorted(credited.items()):
        # the attribution is sound when the cell name is in the heading itself
        in_head = re.search(rf"\b{re.escape(cell)}\b", head, re.I) is not None
        mark = "  " if in_head else "??"
        if not in_head:
            suspicious += 1
        print(f"{mark} {cell:<14} {res:<14} {head}")

    print(f"\ncells named in their own heading      : {len(credited) - suspicious}")
    print(f"cells credited from the HW RESULT area : {suspicious}")
    print("""
The second group is not wrong by construction -- a heading may name a family while
the result line names the member. They are the ones to read.""")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
