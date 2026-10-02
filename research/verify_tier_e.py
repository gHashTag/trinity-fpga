#!/usr/bin/env python3
"""Does the Tier-E evidence chain actually hold in issue #199?

main_ru.tex defines Tier-E as requiring ALL FOUR of:

  1. a public openXC7 CI run reporting success, with the URL
  2. the SHA-256 of the specific bitstream
  3. a UART log "HW RESULT: N/N bit-exact (fails=0)" at 160000 baud from the board
  4. a matching IDCODE (0x13636093, or its version-0 variant 0x03636093)

and states that a GREEN commit message or a passing simulation does NOT count. The
proofs are said to be published per-cell in gHashTag/trinity-fpga#199.

That is a falsifiable claim about a public artefact, and it is the strongest
unverified statement in any of the three documents. This counts, per comment, how
many of the four links are actually present.

    python3 research/verify_tier_e.py
"""
from __future__ import annotations

import json
import re
import subprocess

ISSUE = ("repos/gHashTag/trinity-fpga/issues/199/comments"
         "?per_page=100&page={page}")

LINKS = {
    "CI url":   re.compile(r"github\.com/[^\s)]*/(?:actions/runs|runs)/\d+", re.I),
    "sha256":   re.compile(r"\b[0-9a-f]{64}\b", re.I),
    "UART log": re.compile(r"HW RESULT:\s*\d+/\d+\s*bit-exact", re.I),
    "IDCODE":   re.compile(r"0x[01]3636093", re.I),
}


def _cell_pattern():
    r"""Format names taken from the oracles, not from a list written by hand.

    The pattern here used to be an allow-list:

        gf\w+|bcd|binary\d+|decimal\d+|fp8\w*|bfloat\d+|mxfp\d+|posit\d+|
        takum\d+|afp|cray\w*|vax\w*|int\d+|uint\d+

    It has no lns, no x87, no ibm_hfp, no pdp11, no ms_mbf, no tekum, no
    double_double. Every comment about one of those got "?" for a cell name, and
    seen.setdefault collapsed all of them into a single "?" entry -- which is why 75
    complete chains reported as 34 distinct cells, and why passes 203 and 204 stated
    that no LNS cell appears in this ledger. They were wrong, and the reason was here.

    An allow-list is a snapshot of the corpus on the day it was typed. The corpus is
    enumerable, so this asks it.
    """
    import glob
    import importlib
    import os
    import sys
    conf = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "conformance")
    sys.path.insert(0, conf)
    names = set()
    for path in sorted(glob.glob(os.path.join(conf, "*_ref.py"))):
        try:
            mod = importlib.import_module(os.path.basename(path)[:-3])
        except Exception:
            continue
        names |= set(getattr(mod, "FORMATS", {}))
    # Longest first, so gf1024 is not matched as gf10.
    alts = "|".join(re.escape(n) for n in sorted(names, key=len, reverse=True))
    return r"\b(" + alts + r")\b"


_UNUSED = {
}


def comments():
    out = []
    for page in range(1, 6):
        raw = subprocess.run(["gh", "api", ISSUE.format(page=page)],
                             capture_output=True, text=True).stdout
        try:
            chunk = json.loads(raw)
        except json.JSONDecodeError:
            break
        if not chunk:
            break
        out.extend(chunk)
    return out


CELL_RE = _cell_pattern()


def main() -> int:
    cs = comments()
    print(f"comments fetched: {len(cs)}\n")

    per_link = {k: 0 for k in LINKS}
    complete = []
    partial = []

    for c in cs:
        body = c.get("body") or ""
        have = {k: bool(p.search(body)) for k, p in LINKS.items()}
        for k, v in have.items():
            per_link[k] += 1 if v else 0
        n = sum(have.values())
        if n == 4:
            m = re.search(r"HW RESULT:\s*(\d+/\d+)", body, re.I)
            cell = re.search(CELL_RE, body, re.I)
            complete.append((cell.group(1).lower() if cell else "?",
                             m.group(1) if m else "?"))
        elif n >= 2:
            partial.append((c.get("id"), n))

    print("how many comments carry each link:")
    for k, v in per_link.items():
        print(f"  {k:<9} {v}")

    print(f"\ncomments with ALL FOUR links (Tier-E as defined) : {len(complete)}")
    print(f"comments with two or three                       : {len(partial)}")

    if complete:
        seen = {}
        # All of them, not the first. seen.setdefault kept whichever proof appeared
        # earliest and dropped the rest, and 11 cells have more than one: for gf16 that
        # hid the exhaustive 65536/65536 behind a 512/512, and for lns16 it showed 64/64
        # while hiding the 472/576 that carries 104 known limitations. The view
        # understated the strongest evidence and overstated the weakest at the same time.
        for cell, res in complete:
            seen.setdefault(cell, []).append(res)
        print(f"\ndistinct cells with a complete chain: {len(seen)}")
        for cell, results in sorted(seen.items()):
            uniq = sorted(set(results),
                          key=lambda r: -int(r.split("/")[0]) if "/" in r else 0)
            best = uniq[0] if uniq else "?"
            extra = f"   (+{len(uniq) - 1} more: {', '.join(uniq[1:])})" \
                if len(uniq) > 1 else ""
            partial = [r for r in uniq if "/" in r
                       and r.split("/")[0] != r.split("/")[1]]
            mark = "  PARTIAL" if partial else ""
            print(f"    {cell:<12} {best}{extra}{mark}")

    print("""
What this checks is PRESENCE of the four links in one comment, which is what
Tier-E's own definition requires. It does not re-run the CI, re-hash the bitstream,
or re-read the UART -- those would need the board.""")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
