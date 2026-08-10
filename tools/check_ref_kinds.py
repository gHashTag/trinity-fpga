#!/usr/bin/env python3
"""Does a reference point at an object of the kind its sentence names?

The hygiene gate catches a \\ref with no \\label and a \\label defined twice.
Neither covers the case where the label exists, is unique, and is the wrong
object: the paper said "Appendix~\\ref{sec:limits}" in a document with no
appendix, and "Section~\\ref{sec:blockrelated}" inside the section labelled
sec:blockrelated -- a section pointing at itself.

LaTeX resolves both silently and correctly by its own rules. The sentence is
what is wrong, and the sentence names the kind.

For each label this records the environment it was defined in, then checks every
reference whose preceding word declares a kind.
"""
import re, pathlib, sys, collections

ROOT = pathlib.Path(__file__).resolve().parents[1]
TEX = sorted(ROOT.glob("research/**/*.tex"))

# the word before the tie, and the environments it may legitimately name
KIND = {
    "theorem": {"theorem"}, "theorems": {"theorem"},
    "corollary": {"corollary"}, "lemma": {"lemma"},
    "proposition": {"proposition"}, "definition": {"definition"},
    "table": {"table", "table*"}, "tables": {"table", "table*"},
    "figure": {"figure", "figure*"},
    "section": {"section", "subsection", "subsubsection"},
    "sections": {"section", "subsection", "subsubsection"},
    "appendix": {"appendix"},
    "equation": {"equation", "align", "gather"},
}
OPENER = re.compile(r"\\(?:begin\{(theorem|corollary|lemma|proposition|definition|"
                    r"table\*?|figure\*?|equation|align|gather)\}"
                    r"|(section|subsection|subsubsection|appendix)\*?\{)")

fails, checked = [], 0
for f in TEX:
    src = f.read_text(errors="ignore")
    rel = f.relative_to(ROOT)

    # environment each label sits in: the nearest opener before it
    kind_of, span_of = {}, {}
    opens = [(m.start(), m.group(1) or m.group(2)) for m in OPENER.finditer(src)]
    for m in re.finditer(r"\\label\{([^}]+)\}", src):
        prev = [o for o in opens if o[0] < m.start()]
        if prev:
            kind_of[m.group(1)] = prev[-1][1]
            span_of[m.group(1)] = prev[-1][0]

    for m in re.finditer(r"(\w+)~?\\ref\{([^}]+)\}", src):
        word, lab = m.group(1).lower(), m.group(2)
        if word not in KIND or lab not in kind_of: continue
        checked += 1
        line = src[:m.start()].count("\n") + 1
        actual = kind_of[lab]
        if actual not in KIND[word]:
            fails.append(f"{rel}:{line}: '{m.group(1)}~\\ref{{{lab}}}' but {lab} "
                         f"labels a {actual}")
        # a sectioning reference that resolves to the section containing it
        if actual in ("section", "subsection", "subsubsection"):
            start = span_of[lab]
            nxt = [o[0] for o in opens if o[0] > start and o[1] in
                   ("section", "subsection", "subsubsection")]
            end = nxt[0] if nxt else len(src)
            if start < m.start() < end:
                fails.append(f"{rel}:{line}: '{m.group(1)}~\\ref{{{lab}}}' sits inside "
                             f"the very {actual} it points at")

BASE = pathlib.Path(__file__).with_name("ref_kinds_baseline.txt")
print(f"kind-declaring references checked: {checked}")
uniq = sorted(set(fails))
if "--update-baseline" in sys.argv:
    BASE.write_text("\n".join(uniq) + ("\n" if uniq else ""))
    print(f"baseline written: {len(uniq)} known"); sys.exit(0)
known = {l for l in BASE.read_text().splitlines() if l.strip()} if BASE.exists() else set()
new = sorted(set(uniq) - known)
if new:
    print(f"\nFAIL: {len(new)} reference(s) naming the wrong kind\n")
    for x in new: print(f"  {x}")
    sys.exit(1)
print(f"OK: every kind-declaring reference points at that kind ({len(known)} known)")
