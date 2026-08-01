#!/usr/bin/env python3
"""Where three GoldenFloat documents cite the same work, do they cite it the same way?

Paper A (33 refs), Paper B (20) and main_ru.tex (56) overlap. Pass 84 found the
Hunhold paraphrases identical in Paper A and the Russian manuscript, which suggests
copying. Where a shared work is cited DIFFERENTLY, the difference says which document
was edited last -- and gives the author a third opinion on the right title.

Keyed on arXiv id, which is the only identifier all three use consistently.

    python3 research/compare_three_bibliographies.py A.html B.html main_ru.tex
"""
from __future__ import annotations

import collections
import html
import re
import sys


def from_html(path):
    raw = open(path, encoding="utf-8", errors="replace").read()
    out = {}
    for i, item in enumerate(re.findall(
            r'<li[^>]*class="[^"]*ltx_bibitem[^"]*"[^>]*>(.*?)</li>',
            raw, re.S | re.I), 1):
        txt = " ".join(html.unescape(re.sub(r"<[^>]+>", " ", item)).split())
        m = re.search(r"arXiv[:\s]*([0-9]{4}\.[0-9]{4,5})", txt, re.I)
        q = re.search(r"[“\"']([^”\"']{6,200})[”\"']", txt)
        if m:
            out[m.group(1)] = (f"[{i}]", q.group(1).strip().rstrip(",") if q
                               else "(no title)")
    return out


def from_tex(path):
    src = open(path, encoding="utf-8", errors="replace").read()
    out = {}
    for i, it in enumerate(re.split(r"\\bibitem", src)[1:], 1):
        m = re.search(r"arXiv[:\s]*\{?([0-9]{4}\.[0-9]{4,5})", it, re.I)
        q = re.search(r"``(.+?)''|“(.+?)”", it, re.S)
        if m:
            title = " ".join((q.group(1) or q.group(2)).split()) if q else "(no title)"
            out[m.group(1)] = (f"[{i}]", title)
    return out


def canon(t):
    t = re.sub(r"[^a-z0-9 ]", " ", t.lower())
    return " ".join(sorted(w for w in t.split() if len(w) > 2))


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
    _require_inputs(sys.argv, 'bibliography documents')
    docs = {}
    for p in sys.argv[1:]:
        label = ("Paper A" if p.endswith(("05017v3.html", "pA.html"))
                 else "Paper B" if p.endswith(("09686v2.html", "pB.html"))
                 else "main_ru")
        docs[label] = from_tex(p) if p.endswith(".tex") else from_html(p)
        print(f"{label:<9} {len(docs[label])} entries with an arXiv id")

    everywhere = collections.defaultdict(dict)
    for label, refs in docs.items():
        for aid, (num, title) in refs.items():
            everywhere[aid][label] = (num, title)

    shared = {a: v for a, v in everywhere.items() if len(v) > 1}
    print(f"\nworks cited by more than one document: {len(shared)}\n")

    same = diff = 0
    for aid, per_doc in sorted(shared.items()):
        forms = {canon(t) for _, t in per_doc.values()}
        if len(forms) == 1:
            same += 1
            continue
        diff += 1
        print(f"arXiv:{aid} — cited {len(per_doc)} ways")
        for label in ("Paper A", "Paper B", "main_ru"):
            if label in per_doc:
                num, title = per_doc[label]
                print(f"    {label:<9} {num:<6} {title[:88]}")
        print()

    print(f"shared works cited identically : {same}")
    print(f"shared works cited differently : {diff}")
    print("\nA difference is not a defect by itself -- but where one form matches the")
    print("real title and another does not, the documents disagree about a fact, and")
    print("only one of them can be right.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
