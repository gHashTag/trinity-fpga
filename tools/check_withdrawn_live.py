#!/usr/bin/env python3
"""Is a number the paper withdraws still asserted as live somewhere else?

The paper carried two paragraphs about the same measurement eighteen lines
apart. The first said an int8 datapath scores 0.189 MHz/LUT above GFTernary's
0.177 "and that number is real"; the second said those figures came from a
single placement run and are withdrawn, the audited five-seed medians being
0.180 and 0.181. The ABSTRACT quoted the withdrawn figure.

Nothing checked it. The traceability gate asks whether a number appears in a
data file, which a withdrawn number does -- it was measured, once. The
self-consistency gate counts retractions but does not follow their contents.

This finds every distinctive numeric literal inside a withdrawal passage and
asks whether it also appears outside one.

NEGATIVE TEST DISCIPLINE. A test that patches this paper by string replacement
must assert the file CHANGED. A replace whose target is absent is a no-op, and
the gate then reports OK because nothing was injected -- indistinguishable, in
the output, from a gate that has gone blind. That mistake was made twice while
building this file.
"""
import re, pathlib, sys, collections

ROOT = pathlib.Path(__file__).resolve().parents[1]
PAPER = ROOT / "research" / "arxiv_tnf" / "tnf_paper.tex"
t = PAPER.read_text()

# a withdrawal passage: from the sentence announcing it to the end of its paragraph
WD = re.compile(r"[^.]*\b(?:is|are|was|were)\s+(?:withdrawn|retracted)\b[^.]*\.")
zones = []
for m in WD.finditer(t):
    # the paragraph containing it
    start = t.rfind("\n\n", 0, m.start()) + 2
    end = t.find("\n\n", m.end())
    zones.append((start, end if end > 0 else len(t)))

# A number's UNIT is part of its identity. `2.44\%` (a retracted excess
# reconstruction error) and `2.44\mathrm{e}{-4}` (a mean relative error in the
# precision table) are different quantities; a regex stopping at the backslash
# reads both as bare "2.44" and flags the second because the first was
# withdrawn. Capture the LaTeX suffix so the two cannot be confused.
NUM = re.compile(r"\$?(\d+\.\d{2,}(?:\\mathrm\{e\}\{-?\d+\}|\\%)?)\$?")
withdrawn = collections.defaultdict(list)
for s, e in zones:
    zone = t[s:e]
    for m in NUM.finditer(zone):
        # a number introduced by the withdrawal as its replacement is not the
        # withdrawn one. The replacement follows 'against', 'median of', 'is now'.
        # A qualifier naming the number as the AUDITED replacement can stand on
        # either side of it: "0.180 at a median of five placement seeds" puts it
        # after. Looking only backwards flagged the corrected figure as the
        # withdrawn one, which is the exact inversion this gate exists to catch.
        before = zone[max(0, m.start()-70):m.start()].lower()
        after = zone[m.end():m.end()+70].lower()
        # BEFORE-keys mark the number as the replacement the withdrawal offers.
        # AFTER-keys must be a STRICTLY SMALLER set: "0.189 against 0.177" is a
        # withdrawn pair, so `against` following a number says nothing about it.
        # Putting the full set on both sides made this gate blind to an injected
        # 0.189 -- caught by the negative test the header demands, not by review.
        BEFORE = ("against ", "median of", "is now", "corrected", "audited",
                  "the two are")
        AFTER = ("at a median of", "median of five", "seed median", "five-seed")
        if any(k in before for k in BEFORE) or any(k in after for k in AFTER):
            continue
        # A value that is a simple dyadic fraction -- 0.5, 0.25, 0.125 -- is not
        # distinctive: it names a bit width in one sentence and a storage cost in
        # another, and matching on the digits alone conflates them.
        try:
            v = float(m.group(1))
            if v and abs(v * 1024 - round(v * 1024)) < 1e-9 and round(v * 1024) % 128 == 0:
                continue
        except ValueError:
            pass
        withdrawn[m.group(1)].append(s + m.start())

def in_zone(pos):
    return any(s <= pos < e for s, e in zones)

fails = []
for val, _ in sorted(withdrawn.items()):
    # whole-number matching: 2.44 must not match 2.4455, and a value the
    # withdrawal itself introduces as the CORRECTED one is not withdrawn.
    # A bare value must not match a suffixed one: "2.44" must not find
    # "2.44\mathrm{e}{-4}". Forbid a LaTeX suffix after an unsuffixed value.
    tail = r"(?![\d])" if ("\\" in val) else r"(?![\d]|\\mathrm|\\%)"
    pat = re.compile(r"(?<![\d.])" + re.escape(val) + tail)
    live = [m.start() for m in pat.finditer(t) if not in_zone(m.start())]
    if not live: continue
    for pos in live:
        line = t[:pos].count("\n") + 1
        # Do not let the key cross a table row boundary. The baseline recorded
        # "all 131072  14" and the same unchanged row now keys "... 13", because
        # the window reached past `\\` into the NEXT row's index and that index
        # shifted when a row was added elsewhere. The gate's own comment warns
        # that a line-number key rots; a key spanning rows rots the same way.
        window = t[max(0, pos-90):pos+40]
        cut = window.find("\\\\", pos - max(0, pos-90))
        if cut > 0:
            window = window[:cut]
        ctx = re.sub(r"\s+", " ", window).strip()
        # Keyed on the value and its surrounding words, not the line number:
        # a baseline keyed on line numbers rots on every edit above it.
        key = re.sub(r"[^a-z0-9 ]", "", ctx[-70:].lower())[-52:]
        fails.append(f"{val} live near: {key}   (line {line})")

BASE = pathlib.Path(__file__).with_name("withdrawn_live_baseline.txt")
print(f"withdrawal passages: {len(zones)}   distinct numbers inside them: {len(withdrawn)}")
uniq = sorted(set(fails))
if "--update-baseline" in sys.argv:
    BASE.write_text("\n".join(uniq) + ("\n" if uniq else ""))
    print(f"baseline written: {len(uniq)} known"); sys.exit(0)
raw = [l for l in BASE.read_text().splitlines() if l.strip()] if BASE.exists() else []
strip = lambda x: re.sub(r"\s*\(line \d+\)$", "", x)
known = {strip(l) for l in raw}
new = sorted({u for u in uniq if strip(u) not in known})
if new:
    print(f"\nFAIL: {len(new)} withdrawn number(s) still asserted live\n")
    for x in new: print(f"  {x}")
    sys.exit(1)
print(f"OK: no withdrawn number is asserted live ({len(known)} known)")
