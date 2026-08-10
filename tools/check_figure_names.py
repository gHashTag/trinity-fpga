#!/usr/bin/env python3
"""Do the figures still say what the text stopped saying?

Three figures in the paper carried "TEF" and "GF-T", the format's names one and
two renames ago, long after every sentence had been changed to TNF. Two of them
had no generator at all -- the PDFs sat in the tree and the code that drew them
did not -- and a file nobody regenerates is a file nobody renames.

No gate here could see it. The traceability gate reads the .tex; the figures are
vector graphics whose text is inside the PDF.

Superseded names are listed explicitly rather than inferred, because the point
is to fail on the ones we know we have renamed away from.
"""
import subprocess, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
FIGDIR = ROOT / "research" / "arxiv_tnf"
# GF-T is NOT superseded: it is one of the four families -- golden-ratio rule on
# a ternary axis -- and appears legitimately beside GF, BNF and TNF. Listing it
# here would have failed the paper for naming its own format. TEF is superseded
# (the ladder that carried it is now TNF) and tekum was a misreading of takum.
SUPERSEDED = ["TEF", "tekum"]

fails, checked = [], 0
for f in sorted(FIGDIR.glob("*.pdf")):
    if f.name.endswith("_paper.pdf"): continue
    try:
        txt = subprocess.run(["pdftotext", str(f), "-"],
                             capture_output=True, text=True, timeout=60).stdout
    except FileNotFoundError:
        print("pdftotext not available -- cannot check"); sys.exit(0)
    checked += 1
    for name in SUPERSEDED:
        if name in txt:
            fails.append(f"{f.name}: contains the superseded name '{name}'")

print(f"figures checked: {checked}")
if fails:
    print(f"\nFAIL: {len(fails)} figure(s) carry a superseded name\n")
    for x in fails: print(f"  {x}")
    print("\n  Regenerate with research/arxiv_tnf/gen_figures.py")
    sys.exit(1)
print("OK: no figure carries a superseded name")
