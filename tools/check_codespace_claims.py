#!/usr/bin/env python3
"""Every live utilisation claim in the prose is bound to a format and verified.

Twice in two nights this work asserted a property of the silicon from the
specification instead of reading it off the silicon: rung A "discards 37.5% of
its offset codes" (measured: it discards 1.6%), and GFTernary "uses all four of
its codes and discards nothing" (measured 75%). Both were arithmetic on a format
definition, both wrong, and the second defended our own first place.

An earlier version of this gate tried to bind percentages to formats by nearest
name in the surrounding prose. It could not: it attributed rung A's own figure
to binary16 because binary16 was mentioned closer, and flagged the withdrawn
figures quoted inside their own retractions. Guessing at prose does not work.

So the paper marks its live claims instead. \\codeuse{format}{percent} prints the
percent and names the format; this gate checks each against code_use.json.
Unmarked percentages sitting in a code-space context are counted and printed --
not failed, because a retraction must be able to quote the number it retracts --
so a claim drifting out of the marked set is visible rather than silent.
"""
import json, pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
D = ROOT / "research" / "arxiv_tnf"
paper = (D / "tnf_paper.tex").read_text()
cu = json.loads((D / "code_use.json").read_text())

MARKED = re.compile(r"\\codeuse\{([^}]+)\}\{([\d.]+)\}")
CONTEXT = re.compile(r"utilisation|code space|effective bits|discard", re.I)
PCT = re.compile(r"\$?(\d{1,3}(?:\.\d)?)\\%")

fails, marked = [], 0
for m in MARKED.finditer(paper):
    fmt, val = m.group(1), float(m.group(2))
    marked += 1
    if fmt not in cu:
        fails.append(f"{fmt}: marked in the paper but absent from code_use.json")
        continue
    want = cu[fmt]["use"] * 100
    if abs(val - want) > 0.15:
        fails.append(f"{fmt}: paper says {val}\\%, sweep says {want:.1f}\\%")

# how many code-space percentages are NOT marked -- reported, never failed
unmarked = 0
spans = [(m.start(), m.end()) for m in MARKED.finditer(paper)]
def inside(pos): return any(a <= pos < b for a, b in spans)
def in_tabular(pos):
    return paper.rfind(r"\begin{tabular}", 0, pos) > paper.rfind(r"\end{tabular}", 0, pos)
for m in PCT.finditer(paper):
    if inside(m.start()) or in_tabular(m.start()): continue
    lo, hi = max(0, m.start() - 220), min(len(paper), m.end() + 160)
    if CONTEXT.search(paper[lo:hi]): unmarked += 1

print(f"marked utilisation claims: {marked}   unmarked code-space percentages: {unmarked}")
if fails:
    print(f"\nFAIL: {len(fails)} marked claim(s) disagree with the sweep\n")
    for x in fails: print(f"  {x}")
    sys.exit(1)
print("OK: every marked utilisation claim matches code_use.json")
