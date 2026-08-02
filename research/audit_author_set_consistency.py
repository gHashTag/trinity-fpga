#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Do the nine author-facing documents agree with each other?

Pass 139 found `START_HERE.md` still carrying a claim retracted ten passes earlier, in
a file edited twice in that span. It was found by accident. This looks for the class.

The method avoids the trap recorded in the t27-spec skill. Checking a number against
"the truth" is a surface-form scan and finds mostly correct text, because the same
numeral means different things in different sentences. What *is* mechanically decidable
is disagreement **between** documents: the same subject stated twice with different
figures. One of the two is stale, and which one needs a human — but the pair is a real
signal rather than a pattern match.

Subjects are matched on a short phrase rather than on the number, so "83 formats" and
"83 packs" are one subject while "13 oracles" and "13 families" are two.

Every pair it reports is printed with both sentences, because the tool cannot tell
which side is right and should not pretend to.

    python3 research/audit_author_set_consistency.py
"""
from __future__ import annotations

import os
import re
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))

AUTHOR_SET = [
    "START_HERE.md",
    "SUBMISSION_CHECKLIST.md",
    "VERIFICATION_DOSSIER.md",
    "ARXIV_ABSTRACTS_READY_TO_PASTE.md",
    "ARXIV_BODY_FIXES_READY_TO_PASTE.md",
    "RELATED_WORK_READY_TO_PASTE.md",
    "ONE_ULP_BOUNDARY_READY_TO_PASTE.md",
    "VERIFICATION_METHOD_READY_TO_PASTE.md",
    "THREE_MORE_RESULTS_READY_TO_PASTE.md",
    "THIRTEEN_MORE_FORMATS_READY_TO_PASTE.md",
]

# A subject is a phrase that should carry one number across the whole set.
SUBJECTS = [
    ("formats in the catalogue",
     re.compile(r"(\d{1,3})\s+(?:published\s+)?(?:formats|packs)\b", re.I)),
    ("bit-exact packs",
     re.compile(r"(\d{1,3})\s+bit-?exact\s+(?:packs|conformance)", re.I)),
    ("structural packs",
     re.compile(r"(\d{1,3})\s+structural\b", re.I)),
    ("unpublished oracles",
     re.compile(r"(\d{1,3})\s+(?:unpublished\s+)?oracles?\s+(?:with|beyond|that)", re.I)),
    ("oracles validated",
     re.compile(r"(?:^|\s)(\w+|\d+)\s+of\s+the\s+thirteen\s+are\s+now\s+validated", re.I)),
    ("Tier-E cells of 83",
     re.compile(r"(\d{1,3})\s*(?:of|/)\s*(?:the\s+)?83\s+formats", re.I)),
    ("ADD oracle pairs",
     re.compile(r"([\d,]{5,})\s+pairs.{0,40}(?:ADD|addition)", re.I | re.S)),
    ("ml_dtypes codes",
     re.compile(r"([\d,]{5,})\s+codes\s+compared", re.I)),
    ("P3109 configurations",
     re.compile(r"(\d{2,4})\s+configurations", re.I)),
    ("references to fix",
     re.compile(r"(\d{1,3})\s+reference\s+defects", re.I)),
]

WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
         "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11,
         "twelve": 12, "thirteen": 13}


def normalise(tok: str):
    t = tok.strip().lower().replace(",", "")
    if t in WORDS:
        return WORDS[t]
    return int(t) if t.isdigit() else None



# ---------------------------------------------------------------- references

# Files these documents legitimately cite that do not live in this repository.
# Naming them is the honest alternative to a blanket exemption: each is a real file
# somewhere, and a reader needs to be told where.
ELSEWHERE = {
    "ERRATA_2026-06-14.md": "t27",
    "cocotb_ref_model.py": "t27",
    "gen_all_formats.py": "t27, conformance/vectors/",
    "gf_preprint_v19.tex": "the goldenfloat-preprint repository",
    "main_ru.tex": "the trinity-papers-ru repository",
    "INDEX_all_formats.json": "t27, conformance/vectors/",
}

CITED = re.compile(r"`([\w./-]+\.(?:md|tex|py|t27|json|v|yml))`")


def check_references() -> int:
    """Every file the author-facing documents cite must resolve, or be named as
    living elsewhere. A citation that resolves for the writer and not for the reader
    is the smallest version of the defect this whole set exists to report."""
    import subprocess

    unresolved = []
    total = 0
    for name in AUTHOR_SET:
        path = os.path.join(HERE, name)
        if not os.path.exists(path):
            continue
        text = open(path, encoding="utf-8", errors="replace").read()
        for tok in sorted(set(CITED.findall(text))):
            total += 1
            base = os.path.basename(tok)
            if base in ELSEWHERE:
                continue
            if subprocess.run(["git", "ls-files", "--error-unmatch", tok],
                              capture_output=True).returncode == 0:
                continue
            if subprocess.run(["git", "ls-files", "*" + base],
                              capture_output=True, text=True).stdout.strip():
                continue
            line = text[:text.index("`" + tok + "`")].count("\n") + 1
            unresolved.append((tok, name, line))

    print(f"\nfile citations across the set : {total}")
    print(f"  unresolved                  : {len(unresolved)}")
    for tok, name, line in unresolved:
        print(f"  {name}:{line}  cites {tok}, which is not in this repository")
        print(f"      either add it, correct the path, or name where it lives")
    if not unresolved:
        print("  (files known to live elsewhere are listed in ELSEWHERE and named "
              "in the text)")
    return len(unresolved)


def main() -> int:
    seen = defaultdict(list)          # subject -> [(value, file, sentence)]
    missing = []

    for name in AUTHOR_SET:
        path = os.path.join(HERE, name)
        if not os.path.exists(path):
            missing.append(name)
            continue
        text = open(path, encoding="utf-8", errors="replace").read()
        for subject, rx in SUBJECTS:
            for m in rx.finditer(text):
                val = normalise(m.group(1))
                if val is None:
                    continue
                line = text[:m.start()].count("\n") + 1
                sentence = " ".join(
                    text[max(0, m.start() - 80):m.end() + 90].split())
                seen[subject].append((val, name, line, sentence))

    print(f"documents in the author-facing set : {len(AUTHOR_SET)}")
    if missing:
        print(f"  NOT FOUND (not checked)          : {', '.join(missing)}")
    print(f"  subjects looked for                : {len(SUBJECTS)}\n")

    disagreements = 0
    for subject, rows in sorted(seen.items()):
        values = {v for v, _, _, _ in rows}
        if len(values) <= 1:
            continue
        disagreements += 1
        print(f"DISAGREEMENT — {subject}: values seen {sorted(values)}")
        shown = set()
        for val, name, line, sentence in rows:
            if (val, name) in shown:
                continue
            shown.add((val, name))
            print(f"  {val:>6}  {name}:{line}")
            print(f"          …{sentence[:130]}…")
        print()

    agreed = sum(1 for rows in seen.values() if len({v for v, *_ in rows}) == 1)
    print(f"subjects stated consistently across documents : {agreed}")
    print(f"subjects stated inconsistently                : {disagreements}")

    bad_refs = check_references()

    print("""
Each pair above is printed with both sentences because this tool cannot tell which
side is right. A disagreement is a place to read, not a defect -- "83 formats" and "83
packs" are one subject, and a document quoting what a PAPER says will differ from one
stating what the corpus holds, correctly.""")
    return 1 if bad_refs else 0


if __name__ == "__main__":
    raise SystemExit(main())
