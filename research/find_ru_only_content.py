#!/usr/bin/env python3
"""What does the Russian manuscript discuss that the English preprints never mention?

Pass 87 found, by accident, that main_ru.tex acknowledges GF16's layout as identical
to IBM DLFloat -- a precise concession of prior art, with the DOI -- and that neither
published English paper mentions DLFloat or Agrawal at all.

It was found by following a DOI into the body text. This looks for the rest on
purpose: named technical entities and section headings present in the Russian
manuscript and absent from both preprints.

A gap is a LEAD. Much of it will be Russian-venue apparatus -- GOST references, ВАК
formatting, translated terminology -- which has no business in an arXiv preprint.
What matters is a SUBSTANTIVE claim, comparison or concession that exists in one and
not the other.

    python3 research/find_ru_only_content.py main_ru.tex A.html B.html
"""
from __future__ import annotations

import html
import re
import sys

# entities worth comparing: format names, vendor names, standards, surnames
ENTITY = re.compile(
    r"\b(?:[A-Z][A-Za-z]*(?:Float|float|FP\d*|fp\d*)\w*|"      # DLFloat, bfloat16
    r"[A-Z]{2,}\d*(?:[_-]?[A-Z0-9]+)*|"                        # IEEE, OCP, MXFP4
    r"[A-Z][a-z]{3,}(?= (?:et al|и др|and )))\b")

STOP = {
    "IEEE", "GF", "GOLDENFLOAT", "GOST", "ГОСТ", "PDF", "JSON", "CSV", "API",
    "ARITH", "DOI", "URL", "HTML", "LATEX", "TEX", "RISC", "CPU", "GPU", "FPGA",
    "RTL", "ULP", "NAN", "SHA", "MIT", "BSD", "README", "SSOT", "CI", "VSA",
}


def text_of(path):
    raw = open(path, encoding="utf-8", errors="replace").read()
    if path.endswith(".tex"):
        raw = re.sub(r"%.*", " ", raw)
        raw = re.sub(r"\\[a-zA-Z]+\*?(\[[^\]]*\])?", " ", raw)
        return raw
    raw = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", raw, flags=re.S | re.I)
    return html.unescape(re.sub(r"<[^>]+>", " ", raw))


def entities(t):
    out = {}
    for m in ENTITY.finditer(t):
        e = m.group(0)
        if e.upper() in STOP or len(e) < 4:
            continue
        a = max(0, m.start() - 70)
        out.setdefault(e, " ".join(t[a:m.end() + 90].split()))
    return out


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
    _require_inputs(sys.argv, 'two documents to compare')
    ru = text_of(sys.argv[1])
    eng = " ".join(text_of(p) for p in sys.argv[2:])
    eng_low = eng.lower()

    ru_ents = entities(ru)
    only = {e: c for e, c in ru_ents.items() if e.lower() not in eng_low}

    print(f"entities in the Russian manuscript : {len(ru_ents)}")
    print(f"absent from BOTH English preprints : {len(only)}\n")

    for e in sorted(only, key=lambda x: -len(only[x])):
        print(f"  {e}")
        print(f"      …{only[e][:150]}…\n")

    print("""A gap is a lead, not a finding. Russian-venue apparatus -- GOST
references, translated terminology -- belongs in one document and not the other.
What matters is a substantive claim, comparison or concession present in one and
absent from the other, which is what DLFloat turned out to be.""")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
