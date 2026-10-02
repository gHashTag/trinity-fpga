#!/usr/bin/env python3
"""How many of the 83 conformance packs have hardware confirmation?

Two lines of this campaign ran separately: the 83-pack software corpus, and the
Tier-E hardware matrix in trinity-fpga#199. Crossing them answers the first question
a reader asks of a hardware-backed catalogue -- which formats have hardware.

ATTRIBUTION IS THE WHOLE PROBLEM, and the first version got it wrong. It credited a
format whenever its name appeared anywhere in a comment, so a comment reading
"takum32/64 still unroutable" -- a statement that takum32 is NOT verified -- was
counted as evidence FOR takum32. Proximity is not attribution.

A cell is credited only when the format is named in the comment's CLAIM: the heading
line, or immediately around the "HW RESULT" line. Everything else is prose that may
be saying the opposite.

    python3 research/map_hw_to_corpus.py
"""
from __future__ import annotations

import base64
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

# phrases that mean the named format is NOT verified in this comment
NEGATIVE = re.compile(r"unroutable|not routable|impossible|still (?:un|not)|"
                      r"cannot|fails to route|no cell|structural", re.I)


def claim_region(body: str) -> str:
    """The heading plus the text around the HW RESULT line."""
    parts = []
    first = body.strip().splitlines()[0] if body.strip() else ""
    parts.append(first)
    for m in re.finditer(r"HW RESULT:", body, re.I):
        a = max(0, m.start() - 260)
        parts.append(body[a:m.end() + 120])
    return "\n".join(parts)


def hw_cells():
    found, rejected = {}, []
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
            m = LINKS["uart"].search(body)
            res = f"{m.group(1)}/{m.group(2)}" if m else "?"
            region = claim_region(body)
            for cell in {x.lower() for x in CELL.findall(region)}:
                # drop a name that appears only inside a negative statement
                spans = [region[max(0, mm.start() - 60):mm.end() + 60]
                         for mm in re.finditer(re.escape(cell), region, re.I)]
                if spans and all(NEGATIVE.search(s) for s in spans):
                    rejected.append(cell)
                    continue
                found.setdefault(cell, res)
    return found, sorted(set(rejected))


def corpus_ids():
    raw = subprocess.run(
        ["gh", "api", "repos/gHashTag/t27/contents/conformance/vectors/"
         "INDEX_all_formats.json", "--jq", ".content"],
        capture_output=True, text=True).stdout
    idx = json.loads(base64.b64decode(raw))
    return {e["id"]: e.get("kind", "?") for e in idx["packs"]}


def main() -> int:
    hw, rejected = hw_cells()
    packs = corpus_ids()

    both = {k: (packs[k], hw[k]) for k in packs if k in hw}
    sw_only = sorted(k for k in packs if k not in hw)

    print(f"Tier-E cells credited from the claim region : {len(hw)}")
    print(f"names dropped as NEGATIVE mentions          : {len(rejected)}"
          + (f"  ({', '.join(rejected)})" if rejected else ""))
    print(f"packs in the corpus                         : {len(packs)}\n")

    print(f"packs WITH hardware confirmation : {len(both)}")
    for k, (kind, res) in sorted(both.items()):
        print(f"    {k:<14} {kind:<10} {res}")

    print(f"\npacks with SOFTWARE evidence only : {len(sw_only)}")
    print("    " + ", ".join(sw_only))

    pct = 100 * len(both) / max(1, len(packs))
    print(f"\n{len(both)} of {len(packs)} packs ({pct:.0f}%) carry hardware evidence.")
    print("""
The remainder are not unverified -- they carry the software conformance the corpus is
built on. What they lack is a physical-board result, which is a different and stronger
claim.""")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
