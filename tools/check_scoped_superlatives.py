#!/usr/bin/env python3
"""A superlative about a format must carry its scope in the same sentence.

Two sections of this paper made compatible claims that read as contradictory
because one of them dropped its scope. Section 'A geometric scale grid dominates
a float one' says phi^k is the finest grid available at four bits AMONG
MULTIPLY-FREE ONES. The block-axis section, written later, said a plain binary
ladder beats the ternary one -- true on accuracy, and silent on the fact that
the winning ladder is not multiply-free and so is not in the other section's
competition at all.

Neither sentence was wrong. The second was unscoped, and an unscoped superlative
next to a scoped one reads as a contradiction to every reader who does not hold
both in mind at once. That is the defect this gate catches: not a false claim,
a claim missing the condition that makes it true.

A sentence containing a superlative verb ('beats', 'dominates', 'wins',
'leads', 'is best', 'is the finest', 'is optimal') within reach of a format name
must also contain a scope marker -- 'among', 'at equal', 'multiply-free', 'on
this axis', 'for accuracy', 'at N bits', 'within', 'of the', 'per' -- or be
listed in SCOPED_BY_CONTEXT with the reason its scope is unambiguous from
structure (a table row, a caption naming the axis).
"""
import json, pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
PAPER = ROOT / "research" / "arxiv_tnf" / "tnf_paper.tex"
t = PAPER.read_text()

FORMATS = {f["format"] for f in
           json.loads((ROOT / "research" / "arxiv_tnf" / "full_table.json").read_text())}
FORMATS |= {"MXFP4", "NVFP4", "posit", "takum", "phi", "varphi", "TNF", "GF-T"}

SUPER = re.compile(r"\b(beats|dominates|wins|leads|outperforms|is the (?:finest|best|"
                   r"cheapest|smallest)|is optimal|strictly dominates)\b", re.I)
SCOPE = re.compile(
    r"\bamong\b|\bat equal\b|multiply-free|on (?:this|that) axis|for accuracy|"
    r"\bwithin\b|at the same|per binade|same storage|equal storage|"
    # width and budget scopes, written as digits or as words
    r"at \$?\d|at (?:two|three|four|five|six|seven|eight|nine|ten|sixteen) bits?|"
    r"\bbits?\b.{0,24}\b(?:class|budget|storage|field)\b|"
    # metric scopes -- a superlative on a named metric is scoped by it
    r"on (?:squared error|perplexity|throughput|area|accuracy|this flow)|"
    r"exactly on|in the range|of (?:four|the four|the seven|the twenty)|"
    r"tested|by a factor of|of \$?\d+\$? of|in this table|here\b", re.I)

# Sentences whose scope is unambiguous from surrounding structure rather than
# from words inside them. Each needs a reason, not just a listing.
SCOPED_BY_CONTEXT = {
    "the throughput table's own caption states the harness and the seed count",
}

# split on sentence ends, keeping LaTeX intact enough
body = t[t.find(r"\section{"):]
sentences = re.split(r"(?<=\.)\s+(?=[A-Z\\])", body)

fails, checked = [], 0
for s in sentences:
    if not SUPER.search(s):
        continue
    if not any(f.lower() in s.lower() for f in FORMATS):
        continue
    checked += 1
    if SCOPE.search(s):
        continue
    flat = re.sub(r"\s+", " ", s).strip()
    fails.append(flat[:150])

# ADVISORY, NOT GATING -- and the reason is worth stating rather than hiding.
# Precision measured on this paper is roughly one real finding in five: table
# captions, incidental verbs ("the linear algebra that dominates a network's
# work") and scopes phrased in ways no pattern anticipates all trip it. A gate
# with that false-positive rate sends an author to edit correct sentences, which
# costs more than the defect it catches. It exits zero and prints, so a human
# reads the list and decides.
#
# It has already earned its keep twice: it surfaced the phi 4b/32 claim that
# needed the block-axis result beside it, and the 14.97x squared-error figure an
# independent instrument could not reproduce.
print(f"superlative claims about a named format: {checked}   unscoped: {len(set(fails))}")
if fails:
    print("\nADVISORY -- read these, do not assume they are defects:\n")
    for x in sorted(set(fails))[:12]:
        print(f"  {x}")
    if len(set(fails)) > 12: print(f"  ... and {len(set(fails))-12} more")
sys.exit(0)
