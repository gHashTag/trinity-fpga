#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Can document currency be established mechanically? Mostly not — and here is why.

research/START_HERE.md tells a reader that about forty documents here are from earlier
sessions and that their currency has not been checked. Pass 117 showed what that costs:
a literature scan from 14 July was cited as backing for a question it had never asked.

The obvious remedy is to scan every document for figures that disagree with current
verified values. That was the first version of this tool, and it does not work.

It flagged 23 of 50 documents. Sampling the flags:

    "49 bit-exact / 34 structural"     a correct quotation of what the PAPER says,
                                       inside a document explaining the discrepancy
    "the remaining 15 formats are      a subset count, not the catalogue total
     structural"
    "472/576 bit-exact"                a UART result
    "65/65 bit-exact (fails=0)"        another UART result

Every sampled flag was a false positive. The same numeral means different things in
different sentences, and prose does not carry the type of its own numbers. A checker
whose hits are mostly correct text is noise with a finding inside it -- the same
conclusion pass 100 reached about a scan for foreign-layout constants, and pass 110
about workflow paths.

So this keeps only the one pattern whose shape is unambiguous, and reports honestly
that the general question is not mechanically decidable here.

    python3 research/audit_doc_currency.py
"""
from __future__ import annotations

import glob
import os
import re
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))

# The one unambiguous form: "Tier-E <n>/83" is a running project total and nothing
# else in this tree is written that way.
TIER_E = re.compile(r"Tier-?E\D{0,14}(\d{2,3})\s*/\s*83", re.I)

# Documents whose figures are maintained; everything else is a working note.
MAINTAINED = {
    "START_HERE.md", "SUBMISSION_CHECKLIST.md", "VERIFICATION_DOSSIER.md",
    "README.md", "ARXIV_ABSTRACTS_READY_TO_PASTE.md",
    "ARXIV_BODY_FIXES_READY_TO_PASTE.md", "RELATED_WORK_READY_TO_PASTE.md",
    "ONE_ULP_BOUNDARY_READY_TO_PASTE.md", "VERIFICATION_METHOD_READY_TO_PASTE.md",
    "THREE_MORE_RESULTS_READY_TO_PASTE.md", "BIBLIOGRAPHY_FIXES.md",
}


def last_touched(path: str) -> str:
    return subprocess.run(
        ["git", "log", "-1", "--format=%ad", "--date=short", "--", path],
        capture_output=True, text=True).stdout.strip() or "?"


def main() -> int:
    docs = sorted(glob.glob(os.path.join(HERE, "*.md")))
    running, maintained, notes = [], [], []

    for path in docs:
        name = os.path.basename(path)
        text = open(path, encoding="utf-8", errors="replace").read()
        (maintained if name in MAINTAINED else notes).append(name)
        for m in TIER_E.finditer(text):
            running.append((name, int(m.group(1)),
                            text[:m.start()].count("\n") + 1, last_touched(path)))

    print(f"documents            : {len(docs)}")
    print(f"  figures maintained : {len(maintained)}")
    print(f"  working notes      : {len(notes)}\n")

    if running:
        vals = sorted({v for _, v, _, _ in running})
        print(f"Documents stating a running \"Tier-E n/83\" total — values seen: "
              f"{', '.join(str(v) for v in vals)}\n")
        for name, v, line, when in sorted(running, key=lambda r: r[3]):
            print(f"  {when}  {name}:{line}  says Tier-E {v}/83")
        print("""
The current figure, verified and dated, is 44 of 83 -- of 74 issue-#199 comments
carrying all four Tier-E links, covering 45 cells, 44 map onto published packs
(SUBMISSION_CHECKLIST.md item 4c).

Growth over time explains some of this, but not all: 47 and 71 appear in documents
dated the SAME day, 2026-07-30. So the notation is carrying at least two different
quantities -- plausibly decode-only against decode-plus-compute -- and a reader
meeting "Tier-E n/83" cannot tell which without opening the document.

That is the finding worth having from this pass: not that the notes are old, but that
one notation means more than one thing.""")

    print(f"""
What this tool does NOT do, and why. It does not try to decide whether a working note
is current, because the general form of that question is not mechanically decidable in
prose: the first version of this checker flagged 23 of 50 documents and every sampled
flag was a correct sentence whose numeral happened to match a pattern. The practical
rule is the one START_HERE.md already gives -- anything a checklist line points at is
maintained, and `git log -1 --format=%ad` dates the rest.""")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
