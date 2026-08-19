#!/usr/bin/env python3
"""Does a document agree with itself?

Every gate here compares a document against something else -- data files, the
tree, a sibling artefact. None of them compares a document against itself, and
the paper carried three different counts of its own retractions in three places:
four in the roadmap, eleven in the abstract, sixteen in the method section.

A number a document states about its own contents is checkable against those
contents, and nothing was checking it. This does that: it counts the retraction
marks in the body and requires every sentence claiming a retraction count to
agree with the count.

The class generalises past this one number -- any 'we do N of X' where X is
countable in the same file belongs here.
"""
import re, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
PAPER = ROOT / "research" / "arxiv_tnf" / "tnf_paper.tex"
WORDS = {"one":1,"two":2,"three":3,"four":4,"five":5,"six":6,"seven":7,"eight":8,
         "nine":9,"ten":10,"eleven":11,"twelve":12,"thirteen":13,"fourteen":14,
         "fifteen":15,"sixteen":16,"seventeen":17,"eighteen":18,"nineteen":19,
         "twenty":20}

t = PAPER.read_text()
fails = []

# 1. count the marks the body actually carries
MARK = re.compile(r"\\paragraph\{[^}]*[Ww]ithdraw[^}]*\}"
                  r"|\\paragraph\{[^}]*[Rr]etract[^}]*\}"
                  r"|(?<!are )(?<!not )\bis withdrawn\b"
                  r"|\bare withdrawn\b|\bis retracted\b"
                  r"|\bwe withdraw\b")
# A \paragraph heading announcing a withdrawal and the sentence closing it are
# ONE retraction, not two. A summary sentence counting the retractions is not a
# retraction at all. Counting raw marks gave eight where the body holds five,
# which is the same class of error the gate exists to catch.
raw = [(m.start(), m.group(0)) for m in MARK.finditer(t)]
marks, last_head = [], -10**9
for pos, txt in raw:
    if re.search(r"(?:claims?|retractions?)\s+[^.]{0,60}(?:retracted|falsified)", 
                 t[max(0,pos-160):pos+60], re.I) and "paragraph" not in txt:
        continue                       # this is the summary sentence itself
    if txt.startswith("\\paragraph"):
        marks.append(pos); last_head = pos; continue
    if pos - last_head < 2000:
        continue                       # closes a heading already counted
    marks.append(pos)
marked = len(marks)

# 2. every sentence claiming a count must agree, EXCEPT ones explicitly scoped
#    to the campaign rather than to this document
CLAIM = re.compile(r"([A-Z][a-z]+|\d+)\s+(?:of our own\s+)?"
                   r"(?:retractions?|claims?)\s+[^.]{0,90}?"
                   r"(?:retracted|withdrawn|falsified)[^.]*\.", re.I)
for m in CLAIM.finditer(t):
    s = re.sub(r"\s+", " ", m.group(0))
    tok = m.group(1).lower()
    n = WORDS.get(tok, int(tok) if tok.isdigit() else None)
    if n is None: continue
    if "during the campaign" in s or "during this work" in s or "during the work" in s:
        continue        # scoped to the campaign, not to what this file marks
    if n != marked:
        fails.append(f"claims {n} retractions but the body marks {marked}: {s[:100]}")

print(f"retraction marks in the body: {marked}")
if fails:
    print(f"\nFAIL: {len(fails)} self-inconsistency(ies)\n")
    for f in fails: print(f"  {f}")
    sys.exit(1)
print("OK: every stated count agrees with what the document contains")
