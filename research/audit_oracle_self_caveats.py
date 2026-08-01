#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Which oracles say something about themselves that a reader should know first?

Pass 129 retracted a publication recommendation because conformance/tekum_ref.py
declares, four lines from the top of the file, that it implements a structural model
reverse-engineered from a related format and interpreted linearly where the real one is
logarithmic, with three "TODO: verify from full paper" markers open. Every measurement
made about that oracle across seven passes was sound, and none could have caught it: a
self-consistent model of the wrong format is self-consistent.

So the question is how many others say something similar. This reads the header of
every oracle module and reports the ones whose own text hedges.

It is a surface-form scan, which the t27-spec skill says finds mostly correct text, so
it obeys that section's rule: it prints the sentence it matched, ranks by how strong
the hedge is, and separates a hit count from a finding count. Nothing here is a defect
until the sentence has been read.

    python3 research/audit_oracle_self_caveats.py [--all]
"""
from __future__ import annotations

import argparse
import os
import re

CONF = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "conformance")

# Ordered strongest first. The Russian terms are here because the oracles are
# commented in Russian and an English-only pattern would have missed tekum_ref.py.
HEDGES = [
    (3, re.compile(r"TODO:\s*verify|# *TODO", re.I), "an open TODO"),
    (3, re.compile(r"обратн\w*\s+инженер|reverse[- ]engineer", re.I),
     "reverse-engineered"),
    (3, re.compile(r"working hypothesis|рабочая гипотеза|гипотеза", re.I),
     "a stated hypothesis"),
    (2, re.compile(r"структурная модель|structural model|working model", re.I),
     "a structural model rather than an implementation"),
    (2, re.compile(r"не даёт|does not give|not machine-parseable|недоступн", re.I),
     "a source it could not read"),
    (2, re.compile(r"\[смоделировано\]|\bsimulated\b|\bapproximat", re.I),
     "modelled rather than measured"),
    (1, re.compile(r"assum\w+|предполага", re.I), "an assumption"),
    (1, re.compile(r"\bunverified\b|непровер", re.I), "something unverified"),
]

HEADER_LINES = 40


def header_of(path: str) -> str:
    out = []
    with open(path, encoding="utf-8", errors="replace") as fh:
        for i, line in enumerate(fh):
            if i >= HEADER_LINES:
                break
            out.append(line)
    return "".join(out)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true",
                    help="scan the whole file, not just the header")
    args = ap.parse_args()

    files = sorted(f for f in os.listdir(CONF)
                   if f.endswith("_ref.py") and not f.startswith("_"))
    hits = []
    for fn in files:
        path = os.path.join(CONF, fn)
        text = open(path, encoding="utf-8", errors="replace").read() if args.all \
            else header_of(path)
        found = []
        for weight, rx, label in HEDGES:
            m = rx.search(text)
            if m:
                line = text[:m.start()].count("\n") + 1
                sentence = " ".join(
                    text[max(0, m.start() - 90):m.end() + 130].split())
                found.append((weight, label, line, sentence))
        if found:
            found.sort(reverse=True)
            hits.append((fn, found))

    print(f"oracle modules: {len(files)}")
    print(f"  whose {'text' if args.all else 'header'} hedges about itself: "
          f"{len(hits)}\n")

    strong = [h for h in hits if h[1][0][0] == 3]
    print(f"Strongest first. {len(strong)} carry an open TODO, a reverse-engineering "
          f"note, or a stated hypothesis.\n")

    for fn, found in sorted(hits, key=lambda h: -h[1][0][0]):
        weight, label, line, sentence = found[0]
        mark = "***" if weight == 3 else ("* " if weight == 2 else "  ")
        print(f"{mark} {fn}  L{line}: {label}")
        print(f"      …{sentence[:150]}…")
        if len(found) > 1:
            print(f"      and {len(found) - 1} more: "
                  f"{', '.join(l for _, l, _, _ in found[1:])}")
        print()

    print("""A hit is not a defect. An oracle that says "assumed" about a documented
convention is being careful, and most of these will be. What pass 129 found was
different in kind -- a module stating that it implements a model of a format whose
specification it could not obtain -- and that shape is what the top of this list is
for. Read the sentence before drawing anything from the count.""")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
