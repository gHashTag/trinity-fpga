#!/usr/bin/env python3
"""Is every recorded finding still in the paper?

An external session reset this tree to origin/main and orphaned four commits.
One of them carried a paragraph of the paper; every gate stayed green and the
paragraph was simply absent, found by accident two iterations later.

Gates check the paper against itself, against data files, against the tree.
Nothing checked it against the campaign's own record of what it should contain.
This does: each finding is a name and the literals that must appear if it landed.
"""
import pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
PAPER = ROOT / "research" / "arxiv_tnf" / "tnf_paper.tex"

# finding -> literals that must be present if it landed
FINDINGS = [
    ("closure removes the machinery",  ["cor:closure", "1756"]),
    ("pipelining floor",               ["thm:normfloor", "249.44"]),
    ("multiply-free hierarchy",        ["thm:hierarchy", "1.3247"]),
    ("one-adder family",               ["thm:oneadder", "815.66"]),
    ("ladder law",                     ["thm:ladder", "24.43"]),
    ("optimal-ratio closed form",      ["thm:optratio", "1.4115"]),
    ("curvature correction",           ["thm:curvature"]),
    ("block-axis bound",               ["thm:block", "22.2976"]),
    ("geometric beats float",          ["thm:geoscale", "1.442"]),
    ("scale-cost frontier",            ["tab:frontier", "21.3545"]),
    ("Siegel's floor",                 ["thm:siegel", "1.3247179"]),
    ("the assembled node",             ["tab:node", "28.0"]),
    ("node pipelining",                ["tab:nodepipe", "126.73"]),
    ("three digits forced",            ["frougny2011"]),
    ("full throughput table",          ["tab:fullthroughput", "0.1797"]),
    ("decoder conformance",            ["98.7"]),
    ("exactness in silicon",           ["zero disagreements", "514229"]),
    ("GF-T against TNF",               ["tab:gftvstnf"]),
    ("matched widths against posit",   ["tab:tnet", "3.99"]),
]

tex = PAPER.read_text()
missing = [(n, [k for k in ks if k not in tex]) for n, ks in FINDINGS]
missing = [(n, a) for n, a in missing if a]

print(f"findings checked: {len(FINDINGS)}")
if missing:
    print(f"\nFAIL: {len(missing)} finding(s) not in the paper\n")
    for n, a in missing: print(f"  {n}: missing {a}")
    print("\n  A finding that left the paper without leaving the record is what "
          "an external reset looks like.")
    sys.exit(1)
print("OK: every recorded finding is present")
