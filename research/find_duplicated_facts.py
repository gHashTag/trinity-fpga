#!/usr/bin/env python3
"""Find claims that appear in more than one document, and check whether they agree.

Three separate failures in ten passes had one shape: a fact recorded in two places
and updated in one. The checklist contradicted itself on P3109's version; a
"do-not-touch" row rested on a repository that exists; the paste-ready LaTeX covered
11 defects while the table listed 20.

Each was found by accident. This looks for the rest on purpose.

Method: pull every distinctive NUMBER together with the noun it qualifies -- "83
packs", "66,224 codes", "252 configurations" -- and group by that noun across
documents. A noun carrying two different numbers is either a genuine distinction or
a drift, and the output shows enough context to tell which.

    python3 research/find_duplicated_facts.py research/*.md
"""
from __future__ import annotations

import collections
import os
import re
import sys

# numbers with a following noun; the noun is the key
PAT = re.compile(
    r"\b(\d[\d,]{0,12})\s+"
    r"(packs?|codes?|vectors?|formats?|configurations?|entries|references|"
    r"bibitems?|widths?|oracles?|passes|divergences?|tables?|scripts?|"
    r"families|digits?|violations?|pairs?)\b", re.I)

IGNORE_CONTEXT = re.compile(r"(pass \d+|20\d\d-\d\d-\d\d)", re.I)


def sentences(text):
    return re.split(r"(?<=[.!?])\s+|\n\n", text)


def _require_inputs(argv, what):
    """Refuse to report a result after scanning nothing.

    A form-based scan that finds nothing has established nothing (skill t27-spec).
    Run with no arguments, an argv-driven tool scans no files -- and a "0" printed
    from that is indistinguishable from a clean result. So say so and exit 2.
    """
    paths = [a for a in argv[1:] if not a.startswith("-")]
    if not paths:
        import sys as _s
        print(f"nothing to scan: this tool reads {what} named on the command line.")
        print(f"  usage: python3 {argv[0]} <file> [file ...]")
        print("Exiting 2 rather than reporting a zero from an empty scan.")
        raise SystemExit(2)
    return paths


def main() -> int:
    _require_inputs(sys.argv, 'markdown documents')
    paths = [p for p in sys.argv[1:] if p.endswith(".md")]
    facts = collections.defaultdict(list)   # noun -> [(number, file, context)]

    for path in paths:
        try:
            text = open(path, encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        for sent in sentences(text):
            flat = " ".join(sent.split())
            for m in PAT.finditer(flat):
                num, noun = m.group(1).replace(",", ""), m.group(2).lower().rstrip("s")
                a = max(0, m.start() - 46)
                facts[noun].append((num, os.path.basename(path),
                                    flat[a:m.end() + 30].strip()))

    print(f"documents scanned: {len(paths)}\n")

    disagreements = 0
    for noun in sorted(facts):
        rows = facts[noun]
        files = {f for _, f, _ in rows}
        values = {n for n, _, _ in rows}
        if len(files) < 2 or len(values) < 2:
            continue                     # single document, or all agree
        disagreements += 1
        print(f"=== '{noun}' carries {len(values)} different numbers "
              f"across {len(files)} files")
        seen = set()
        for num, fname, ctx in sorted(rows, key=lambda r: (r[0], r[1])):
            if (num, fname) in seen:
                continue
            seen.add((num, fname))
            print(f"    {num:>8}  {fname:<34} …{ctx[-72:]}")
        print()

    print(f"nouns with more than one value across documents: {disagreements}")
    print("\nNot every one is a defect -- '83 formats' and '20 entries' are different")
    print("facts that share a noun. The output shows context so the distinction can")
    print("be made by reading. What it finds reliably is the pair that should have")
    print("been one number and is two.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
