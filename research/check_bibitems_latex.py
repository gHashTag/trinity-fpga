#!/usr/bin/env python3
"""Static safety check for generated LaTeX bibitems.

There is no TeX toolchain here and installing TeX Live to verify one file would be
disproportionate, so this is a SUBSTITUTE for compiling, not a compilation. It
checks the failure modes that actually break a bibliography built from fetched
metadata:

  - characters that are special in LaTeX and were not escaped: & % # _ $ ~ ^
  - non-ASCII, which breaks pdflatex without inputenc/fontspec
  - unbalanced braces
  - unpaired ``...'' quotes
  - a \\bibitem key repeated

None of this proves the file compiles. It proves the file does not contain the
things that stop it compiling, which is what can be established without TeX.

    python3 research/check_bibitems_latex.py research/CORRECTED_BIBITEMS.tex
"""
from __future__ import annotations

import re
import sys
import unicodedata

SPECIAL = "&%#_$~^"


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
    _require_inputs(sys.argv, 'a .tex bibliography')
    path = sys.argv[1]
    lines = open(path, encoding="utf-8").read().splitlines()

    problems = []
    keys = {}
    depth = 0

    for n, raw in enumerate(lines, 1):
        line = raw
        if line.lstrip().startswith("%"):          # a comment line
            continue
        # strip escaped specials and \url{...}, whose contents are verbatim-ish
        probe = re.sub(r"\\[&%#_$~^\\]", "", line)
        probe = re.sub(r"\\url\{[^}]*\}", "", probe)
        probe = re.sub(r"\\texttt\{[^}]*\}", "", probe)
        # The citation KEY is an argument, not typeset text: underscores in it are
        # legal and common. Scanning it flagged four correct \bibitem lines on the
        # pass-85 run -- the second time this checker's first answer was wrong,
        # after the line-local quote test.
        probe = re.sub(r"\\bibitem\{[^}]*\}", "", probe)

        for ch in SPECIAL:
            if ch in probe:
                problems.append((n, f"unescaped '{ch}'", line.strip()[:74]))

        for ch in line:
            if ord(ch) > 127:
                name = unicodedata.name(ch, "?")
                problems.append((n, f"non-ASCII {ch!r} ({name})", line.strip()[:74]))
                break

        depth += line.count("{") - line.count("}")

        # Quote pairing is counted over the WHOLE file below, not per line: a title
        # legitimately spans two lines, and a line-local test flags every one of
        # them. The first version of this check reported two such false problems.

        m = re.search(r"\\bibitem\{([^}]*)\}", line)
        if m:
            k = m.group(1)
            if k in keys:
                problems.append((n, f"duplicate key '{k}' (first at line {keys[k]})",
                                 line.strip()[:74]))
            keys[k] = n

    if depth != 0:
        problems.append((0, f"braces unbalanced overall: net {depth:+d}", ""))

    body = "\n".join(l for l in lines if not l.lstrip().startswith("%"))
    o, c = body.count("``"), body.count("''")
    if o != c:
        problems.append((0, f"quote pairing over the file: {o} `` vs {c} ''", ""))

    print(f"file        : {path}")
    print(f"bibitems    : {len(keys)}")
    print(f"problems    : {len(problems)}\n")
    for n, what, ctx in problems:
        print(f"  line {n:>4}  {what}")
        if ctx:
            print(f"            {ctx}")

    if not problems:
        print("No LaTeX-breaking construct found.")
        print("This is NOT a compilation -- it checks for the things that stop one.")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
