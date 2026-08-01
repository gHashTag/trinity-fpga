#!/usr/bin/env python3
"""Where the three documents state the same number, do they state it about the same thing?

Pass 89 found the FPGA part discrepancy exactly this way: "323 MHz" appears in Paper
A and in main_ru.tex, and the surrounding text names a different Xilinx part in each.
The number matched; the claim did not.

That is a cheap, repeatable check over text already fetched. Match on the NUMBER,
then compare the technical entities around it -- part numbers, format names,
standards, units. A shared number whose neighbourhood differs is a lead.

    python3 research/compare_shared_numbers.py A.html B.html main_ru.tex
"""
from __future__ import annotations

import collections
import html
import re
import sys

# numbers worth comparing: not years, not small ordinals
NUM = re.compile(r"(?<![\w.])(\d{2,3}(?:[.,]\d+)?|\d{1,3}/\d{1,3})(?![\w.])")

# entities that identify WHAT a number is about
ENT = re.compile(
    r"\b(?:XC7A\w+|GF\d+|posit\d*|takum\d*|bfloat\d+|binary\d+|fp\d+|MXFP\d+|"
    r"MHz|МГц|LUT|digits|знаков|formats|форматов|packs|пакетов|vectors|"
    r"testbench|окружение|baud|бод|bits|бит)\b", re.I)

SKIP = {"20", "19", "26", "25", "24", "23", "22", "21"}      # year fragments


def text_of(path):
    raw = open(path, encoding="utf-8", errors="replace").read()
    if path.endswith(".tex"):
        raw = re.sub(r"%.*", " ", raw)
        raw = re.sub(r"\\[a-zA-Z]+\*?", " ", raw)
    else:
        raw = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", raw, flags=re.S | re.I)
        raw = re.sub(r"<[^>]+>", " ", raw)
    return " ".join(html.unescape(raw).split())


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
    _require_inputs(sys.argv, 'documents')
    docs = {}
    for p in sys.argv[1:]:
        label = ("Paper A" if "pA" in p or "05017" in p
                 else "Paper B" if "pB" in p or "09686" in p else "main_ru")
        docs[label] = text_of(p)

    # number -> {doc: set(entities seen near it)}
    seen = collections.defaultdict(lambda: collections.defaultdict(set))
    ctx = collections.defaultdict(dict)
    for label, t in docs.items():
        for m in NUM.finditer(t):
            n = m.group(1)
            if n in SKIP:
                continue
            a, b = max(0, m.start() - 110), min(len(t), m.end() + 110)
            around = t[a:b]
            ents = {e.upper() for e in ENT.findall(around)}
            if not ents:
                continue
            seen[n][label] |= ents
            ctx[n].setdefault(label, around)

    shared = {n: d for n, d in seen.items() if len(d) > 1}
    print(f"numbers appearing near technical entities in 2+ documents: {len(shared)}\n")

    flagged = 0
    for n in sorted(shared, key=lambda x: (len(x), x)):
        per = shared[n]
        # A lead is a CLASS CONFLICT: both documents name a member of the same
        # class of entity, and they name DIFFERENT members. Two different XC7A
        # parts for one result is a conflict; one document merely mentioning MHz
        # where the other does not is ordinary sentence variation.
        #
        # The first version flagged the latter and produced 25 hits, all innocent.
        labels = sorted(per)
        CLASSES = {"part": re.compile(r"^XC7A"), "rung": re.compile(r"^GF\d+$")}
        disagree = False
        for cname, cpat in CLASSES.items():
            members = {L: {e for e in per[L] if cpat.match(e)} for L in labels}
            named = [L for L in labels if members[L]]
            for i in range(len(named)):
                for j in range(i + 1, len(named)):
                    if members[named[i]] != members[named[j]]:
                        disagree = True
        if not disagree:
            continue
        flagged += 1
        print(f"=== {n} — described differently")
        for L in labels:
            only = per[L] - set().union(*(per[k] for k in labels if k != L))
            mark = f"  ONLY HERE: {', '.join(sorted(only))}" if only else ""
            print(f"  {L:<9}{mark}")
            print(f"      …{ctx[n][L][:150]}…")
        print()

    print(f"shared numbers with incompatible surroundings: {flagged}")
    print("\nMost will be innocent -- the same number used for two unrelated things.")
    print("What this is looking for is one number, one claim, two descriptions.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
