#!/usr/bin/env python3
"""Resolve the arXiv references in a LaTeX bibliography and compare titles.

The published preprints were audited from their HTML renderings. main_ru.tex -- the
Russian submission for VAK journals, 56 bibitems, actively edited -- has never been
checked, and it is a different document with a different bibliography.

Same method as the HTML auditors: resolve every arXiv id in one batched request and
compare the cited title against the real one. A difference is a LEAD.

    python3 research/audit_tex_refs.py main_ru.tex
"""
from __future__ import annotations

import re
import subprocess
import sys


def norm(t: str) -> set[str]:
    t = re.sub(r"[^a-z0-9 ]", " ", t.lower())
    stop = {"a", "an", "the", "of", "for", "and", "on", "in", "to", "with", "at",
            "its", "by", "from", "is", "are"}
    return {w for w in t.split() if w and w not in stop}


def fetch(ids):
    if not ids:
        return {}
    url = ("https://export.arxiv.org/api/query?max_results=200&id_list="
           + ",".join(sorted(set(ids))))
    out = subprocess.check_output(["curl", "-sS", "--max-time", "120", url],
                                  text=True)
    found = {}
    for chunk in out.split("<entry>")[1:]:
        m = re.search(r"arxiv\.org/abs/([0-9]{4}\.[0-9]{4,5})", chunk)
        t = re.search(r"<title>(.*?)</title>", chunk, re.S)
        names = re.findall(r"<name>(.*?)</name>", chunk, re.S)
        if m and t:
            found[m.group(1)] = (" ".join(t.group(1).split()),
                                 [n.strip() for n in names])
    return found


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
    _require_inputs(sys.argv, 'a .tex manuscript')
    src = open(sys.argv[1], encoding="utf-8", errors="replace").read()
    items = re.split(r"\\bibitem", src)[1:]
    print(f"bibitems: {len(items)}")

    ids = []
    for it in items:
        m = re.search(r"arXiv[:\s]*\{?([0-9]{4}\.[0-9]{4,5})", it, re.I)
        if m:
            ids.append(m.group(1))
    meta = fetch(ids)
    print(f"carrying an arXiv id: {len(ids)}   resolved: {len(meta)}\n")

    agree = leads = 0
    for n, it in enumerate(items, 1):
        m = re.search(r"arXiv[:\s]*\{?([0-9]{4}\.[0-9]{4,5})", it, re.I)
        if not m or m.group(1) not in meta:
            continue
        real, names = meta[m.group(1)]
        # cited title: the first ``...'' or "..." group in the entry
        q = re.search(r"``(.+?)''|“(.+?)”", it, re.S)
        cited = " ".join((q.group(1) or q.group(2)).split()) if q else ""
        if not cited:
            leads += 1
            print(f"[{n:>2}] arXiv:{m.group(1)}  NO TITLE in the entry")
            print(f"     actual: {real}\n")
            continue
        a, b = norm(cited), norm(real)
        ov = len(a & b) / max(1, len(a | b))
        if ov >= 0.6:
            agree += 1
            continue
        leads += 1
        print(f"[{n:>2}] arXiv:{m.group(1)}   overlap {ov:.0%}")
        print(f"     cited : {cited[:96]}")
        print(f"     actual: {real[:96]}")
        print(f"     authors: {'; '.join(names[:3])}\n")

    print(f"\ntitles agree : {agree}")
    print(f"LEADS        : {leads}")
    print("\nA lead is not a defect -- abbreviations lower the overlap honestly.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
