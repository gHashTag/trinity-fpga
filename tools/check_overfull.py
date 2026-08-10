#!/usr/bin/env python3
"""Does anything run off the page?

The build reported zero errors and zero undefined references while a display
equation stuck 57.5pt past the right margin and seven paragraphs and table rows
did the same. LaTeX calls an overfull box a warning, prints it among hundreds of
lines of engine chatter, and typesets the page anyway.

It is not a warning to a reader. It is text they cannot see.

Threshold is 2pt: below that the overhang is inside the margin's own slack and
invisible in print.
"""
import re, subprocess, sys, pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
PAPER = ROOT / "research" / "arxiv_tnf" / "tnf_paper.tex"
THRESHOLD_PT = 2.0

try:
    out = subprocess.run(["tectonic", "-X", "compile", str(PAPER),
                          "--outdir", str(PAPER.parent)],
                         capture_output=True, text=True, timeout=900)
except FileNotFoundError:
    print("tectonic not on PATH -- cannot check"); sys.exit(0)
except subprocess.TimeoutExpired:
    print("FAIL: build timed out"); sys.exit(1)

log = out.stdout + out.stderr
OVER = re.compile(r"Overfull \\hbox \(([\d.]+)pt too wide\)"
                  r"(?:[^\n]*?at lines? ([\d-]+))?")
hits = {}
for m in OVER.finditer(log):
    pts = float(m.group(1))
    if pts < THRESHOLD_PT: continue
    where = m.group(2) or "?"
    hits[(where, round(pts, 2))] = hits.get((where, round(pts, 2)), 0) + 1

print(f"overfull boxes over {THRESHOLD_PT}pt: {len(hits)}")
if hits:
    print("\nFAIL: text runs off the page\n")
    for (where, pts), _ in sorted(hits.items(), key=lambda kv: -kv[0][1]):
        print(f"  {pts:6.2f}pt too wide, at line(s) {where}")
    sys.exit(1)
print("OK: nothing runs off the page")
