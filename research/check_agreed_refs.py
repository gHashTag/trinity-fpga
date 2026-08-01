#!/usr/bin/env python3
"""Are the references all three documents cite IDENTICALLY actually correct?

Pass 85 found 23 works cited by more than one document: 6 differently, 17
identically. The 6 were examined because they disagreed. The 17 were not examined at
all -- agreement was treated as a reason not to look.

That is exactly backwards for bibliographies maintained by copying. Consistent
copying propagates an error consistently, so a work cited the same way everywhere is
the one nobody will ever notice is wrong.

    python3 research/check_agreed_refs.py A.html B.html main_ru.tex
"""
from __future__ import annotations

import collections
import html
import re
import subprocess
import sys
import time


def strip(s):
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", s)).split())


def from_html(path):
    raw = open(path, encoding="utf-8", errors="replace").read()
    out = {}
    for i, item in enumerate(re.findall(
            r'<li[^>]*class="[^"]*ltx_bibitem[^"]*"[^>]*>(.*?)</li>',
            raw, re.S | re.I), 1):
        txt = strip(item)
        m = re.search(r"arXiv[:\s]*([0-9]{4}\.[0-9]{4,5})", txt, re.I)
        q = re.search(r"[“\"']([^”\"']{6,200})[”\"']", txt)
        if m:
            out[m.group(1)] = (f"[{i}]", q.group(1).strip().rstrip(",") if q else "")
    return out


def from_tex(path):
    src = open(path, encoding="utf-8", errors="replace").read()
    out = {}
    for i, it in enumerate(re.split(r"\\bibitem", src)[1:], 1):
        m = re.search(r"arXiv[:\s]*\{?([0-9]{4}\.[0-9]{4,5})", it, re.I)
        q = re.search(r"``(.+?)''|“(.+?)”", it, re.S)
        if m:
            out[m.group(1)] = (f"[{i}]",
                               " ".join((q.group(1) or q.group(2)).split())
                               if q else "")
    return out


def canon(t):
    t = re.sub(r"[^a-z0-9 ]", " ", t.lower())
    return " ".join(sorted(w for w in t.split() if len(w) > 2))


def norm(t):
    t = re.sub(r"[^a-z0-9 ]", " ", t.lower())
    stop = {"a", "an", "the", "of", "for", "and", "on", "in", "to", "with", "at",
            "its", "by", "from", "is", "are"}
    return {w for w in t.split() if w and w not in stop}


def fetch(ids, attempts=4):
    url = ("https://export.arxiv.org/api/query?max_results=200&id_list="
           + ",".join(sorted(set(ids))))
    out = ""
    for n in range(attempts):
        out = subprocess.check_output(["curl", "-sS", "--max-time", "120", url],
                                      text=True)
        if out.count("<entry>") >= max(1, len(set(ids)) // 2):
            break
        time.sleep(6 * (n + 1))
    found = {}
    for chunk in out.split("<entry>")[1:]:
        m = re.search(r"arxiv\.org/abs/([0-9]{4}\.[0-9]{4,5})", chunk)
        t = re.search(r"<title>(.*?)</title>", chunk, re.S)
        if m and t:
            found[m.group(1)] = " ".join(t.group(1).split())
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
    _require_inputs(sys.argv, 'bibliography documents')
    docs = {}
    for p in sys.argv[1:]:
        label = ("Paper A" if "pA" in p or "05017" in p
                 else "Paper B" if "pB" in p or "09686" in p else "main_ru")
        docs[label] = from_tex(p) if p.endswith(".tex") else from_html(p)

    per_work = collections.defaultdict(dict)
    for label, refs in docs.items():
        for aid, (num, title) in refs.items():
            per_work[aid][label] = (num, title)

    agreed = {a: v for a, v in per_work.items()
              if len(v) > 1 and len({canon(t) for _, t in v.values()}) == 1}
    print(f"works cited by 2+ documents in IDENTICAL form: {len(agreed)}\n")

    real = fetch(list(agreed))
    if len(real) < len(agreed):
        print(f"only {len(real)} of {len(agreed)} resolved -- arXiv is throttling.")
        print("Re-run in a few minutes rather than trusting a partial answer.")
        return 2

    ok = wrong = 0
    for aid, per_doc in sorted(agreed.items()):
        cited = next(iter(per_doc.values()))[1]
        ov = len(norm(cited) & norm(real[aid])) / max(1, len(norm(cited) | norm(real[aid])))
        where = ", ".join(f"{k} {v[0]}" for k, v in sorted(per_doc.items()))
        if ov >= 0.6:
            ok += 1
            continue
        wrong += 1
        print(f"arXiv:{aid}  cited identically in {len(per_doc)} documents "
              f"({where}) — overlap {ov:.0%}")
        print(f"    all say : {cited[:96]}")
        print(f"    actually: {real[aid][:96]}\n")

    print(f"agreed AND correct : {ok}")
    print(f"agreed AND WRONG   : {wrong}")
    if wrong:
        print("\nEach of these is wrong in every document at once, which is what")
        print("copying a bibliography does. Agreement was never evidence.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
