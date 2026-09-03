#!/usr/bin/env python3
"""Is the reference list connected, and does any work appear in it twice?

Two entries for one paper give it two numbers in the printed list, and the text
then cites the same work under both -- so a reader following the two citations
finds two references and cannot tell they are one. Measured before this file
existed: `fibbinary` and `fiandaca2025fibbinary` were the same arXiv preprint
(2511.01921), and `wintersteiger2025` and `wintersteiger2025formal` were the same
ARITH 2025 paper under one DOI. Each pair was cited once under each key, five
thousand lines apart, which is exactly how a duplicate survives proofreading.

The Wintersteiger pair also DISAGREED about its own page range -- 157--166 in one
entry and 157--160 in the other, at the same DOI -- so a duplicate is not only
redundant, it is a place for two versions of a fact to live.

WHAT THIS DOES NOT CHECK. Whether a reference exists, is correctly attributed, or
says what the citing sentence claims. That needs the sources, and no automated
check here can substitute for reading them.

MATCHING IS ON THE NORMALISED TITLE, NOT A SUBSTRING. Titles are compared after
case-folding and stripping punctuation and LaTeX markup. Substring containment was
tried and rejected: it pairs "Posit arithmetic" with "Posit arithmetic hardware
codec design", which are different works.
"""
import re
import pathlib
import sys
import collections

ROOT = pathlib.Path(__file__).resolve().parents[1]
PAPER = ROOT / "research" / "arxiv_tnf" / "tnf_paper.tex"


def entries(tex):
    out = {}
    parts = re.split(r"\\bibitem\{([^}]+)\}", tex)
    for i in range(1, len(parts), 2):
        body = parts[i + 1]
        end = body.find("\\end{thebibliography}")
        out[parts[i]] = re.sub(r"\s+", " ", (body[:end] if end > 0 else body)).strip()
    return out


def title_of(body):
    m = re.search(r"``(.{6,}?)''", body) or re.search(r"\\newblock (.{8,}?)\.", body)
    if not m:
        return None
    t = m.group(1)
    t = re.sub(r"\\[a-zA-Z]+\{([^}]*)\}", r"\1", t)
    t = re.sub(r"[^a-z0-9 ]", "", t.lower())
    return re.sub(r"\s+", " ", t).strip()


def ident_of(body):
    """A DOI or arXiv id, which pins two entries to one work more firmly than a title."""
    m = re.search(r"(?:doi:?\s*|DOI\s*)(10\.\d{4,}/[^\s,}]+)", body)
    if m:
        return "doi:" + m.group(1).rstrip(".")
    m = re.search(r"arXiv:\s*(\d{4}\.\d{4,5})", body)
    if m:
        return "arxiv:" + m.group(1)
    return None


def main():
    tex = PAPER.read_text()
    items = entries(tex)
    if not items:
        print("FAIL: no \\bibitem entries found")
        return 1

    cites = collections.Counter()
    for m in re.finditer(r"\\cite\{([^}]+)\}", tex):
        for k in m.group(1).split(","):
            cites[k.strip()] += 1

    fails = []
    dangling = sorted(k for k in cites if k not in items)
    uncited = sorted(k for k in items if k not in cites)
    for k in dangling:
        fails.append(f"\\cite{{{k}}} has no \\bibitem")
    for k in uncited:
        fails.append(f"\\bibitem{{{k}}} is never cited")

    by_title = collections.defaultdict(list)
    by_ident = collections.defaultdict(list)
    for k, v in items.items():
        t = title_of(v)
        if t:
            by_title[t].append(k)
        i = ident_of(v)
        if i:
            by_ident[i].append(k)
    seen_pairs = set()
    for group in list(by_title.values()) + list(by_ident.values()):
        if len(group) < 2:
            continue
        key = tuple(sorted(group))
        if key in seen_pairs:
            continue
        seen_pairs.add(key)
        fails.append(f"one work under {len(group)} keys: {', '.join(sorted(group))}")

    print(f"entries {len(items)}   distinct keys cited {len(cites)}   citations {sum(cites.values())}")
    print(f"dangling {len(dangling)}   uncited {len(uncited)}   duplicate works {len(seen_pairs)}")
    if fails:
        print(f"\nFAIL: {len(fails)} problem(s)\n")
        for f in fails:
            print(f"  {f}")
        return 1
    print("\nOK: every entry is cited, every citation resolves, no work appears twice")
    return 0


if __name__ == "__main__":
    sys.exit(main())
