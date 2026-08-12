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
# NOTE (2026-08-12): this was PASSIVE VOICE ONLY, and a mutation test proved
# the consequence: a withdrawal written "We withdraw the X figure" opened no
# zone, so the gate never went on to check whether X was still asserted live
# elsewhere. The same hole was found the same day in check_self_consistency.
# One author, one habit, two gates.
# A DECIMAL POINT IS NOT A FULL STOP. Splitting sentences on [^.]* truncated
# "We withdraw the $77.77\\%$ figure." at the decimal, so the only kind of
# number this gate exists to track fell outside its own zone. The passive
# branch survived only because its zone is the whole paragraph. Found by
# mutation test, not by reading.
SENT = r"(?:[^.]|\.(?=\d))*"
WD = re.compile(SENT + r"(?:\b(?:is|are|was|were)\s+(?:withdrawn|retracted)\b"
                r"|\b[Ww]e (?:withdraw|retract)\b"
                r"|\b(?:is|are|was|were) now retired\b"
                r"|\bretired that sentence\b)" + SENT + r"\.")
# The two voices need different zones, and conflating them produced false
# positives the moment the active voice was added. "X is withdrawn" typically
# HEADS a paragraph that then discusses the replacement, so the paragraph is the
# right zone. "We withdraw X" names its object in the SAME SENTENCE and is
# normally embedded in a paragraph of live measurements -- taking the paragraph
# there flagged 1.02 and 1.31, which are current measured ratios that happen to
# sit beside a sentence retracting something else.
PASSIVE = re.compile(r"\b(?:is|are|was|were)\s+(?:withdrawn|retracted)\b")
zones = []
for m in WD.finditer(t):
    if PASSIVE.search(m.group(0)):
        start = t.rfind("\n\n", 0, m.start()) + 2
        end = t.find("\n\n", m.end())
        zones.append((start, end if end > 0 else len(t)))
    else:
        zones.append((m.start(), m.end()))       # the sentence only

NUM = re.compile(r"\$?(\d+\.\d{2,})\$?")
withdrawn = collections.defaultdict(list)
for s, e in zones:
    zone = t[s:e]
    for m in NUM.finditer(zone):
        # a number introduced by the withdrawal as its replacement is not the
        # withdrawn one. The replacement follows 'against', 'median of', 'is now'.
        before = zone[max(0, m.start()-70):m.start()].lower()
        if any(k in before for k in ("against ", "median of", "is now", "corrected",
                                     "audited", "the two are")):
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

# A number equal to a measured MHz in the regenerated table is a live
# measurement, not a resurrected claim -- a withdrawn figure and a current
# one can collide by arithmetic. Read from the JSON the table is
# machine-written from, so the exclusion cannot be gamed by editing prose.
import json as _json
_measured = set()

# The three-horn sweep lives in its own file, not in full_table.json, so its
# frequencies and the percentages derived from them read as resurrected
# withdrawn figures. Read them from the sweep rather than baselining by hand --
# a hand-kept exclusion list is the transcription this gate exists to prevent.
_horns = pathlib.Path("research/arxiv_tnf/horns54.txt")
if _horns.exists():
    _rows = {}
    for _l in _horns.read_text().splitlines():
        _l = _l.strip()
        if not _l or _l == "DONE" or "BUILD_FAIL" in _l: continue
        _q = _l.split("|"); _rows[_q[0]] = (int(_q[1]), [float(_x) for _x in _q[2].split()])
    import statistics as _st
    for _n, (_lut, _v) in _rows.items():
        _measured.update({f"{_x:.2f}" for _x in _v})
        _measured.add(f"{_st.mean(_v):.2f}")
        _measured.add(f"{_st.mean(_v)/_lut:.4f}")
        _measured.add(str(_lut))
    # and the pairwise percentages the paper prints from them
    if len(_rows) == 3:
        _base = _st.mean(_rows["extend"][1]) / _rows["extend"][0]
        for _n, (_lut, _v) in _rows.items():
            _measured.add(f"{abs(_st.mean(_v)/_lut/_base - 1)*100:.2f}")
    _measured.add("0.90")   # the control's p-value, this iteration's measurement

# Ratios the paper prints between two measured rows are themselves live figures.
# tab:tnet divides one row by another, and 2.11 collided with a withdrawn number.
try:
    _t = _json.load(open("research/arxiv_tnf/full_table.json"))
    _by = {r["format"]: r["mhz_per_lut"] for r in _t}
    for _a, _b in (("TNF8", "posit8"), ("TNF16", "posit16"), ("TNF16c", "binary16"),
                   ("TNF17e", "binary16"), ("GFTernary", "binary32")):
        if _a in _by and _b in _by:
            _measured.add(f"{_by[_a]/_by[_b]:.2f}")
except Exception:
    pass
for _f in ("full_table", "rejected_measured"):
    for _r in _json.load(open(f"research/arxiv_tnf/{_f}.json")):
        _measured.update({f"{_r['mhz']:.2f}", f"{_r['mhz_per_lut']:.4f}",
                          str(_r['lut']), f"{_r['spread']:.2f}"})
        # the table now prints five-seed RANGES, so each endpoint and each seed
        # is itself a live measurement and must not read as a resurrected figure
        # 54-seed rows carry a mean and a 95% half-width; both are live
        if _r.get("ci95"): _measured.add(f"{_r['ci95']:.4f}")
        for _v in (_r.get("seeds54") or []): _measured.add(f"{_v:.2f}")
        _s = _r.get("seeds")
        if _s:
            _measured.update(f"{_v:.2f}" for _v in _s)
            _measured.update({f"{min(_s)/_r['lut']:.4f}", f"{max(_s)/_r['lut']:.4f}"})

fails = []
for val, _ in sorted(withdrawn.items()):
    if val in _measured: continue
    # whole-number matching: 2.44 must not match 2.4455, and a value the
    # withdrawal itself introduces as the CORRECTED one is not withdrawn.
    pat = re.compile(r"(?<![\d.])" + re.escape(val) + r"(?![\d])")
    live = [m.start() for m in pat.finditer(t) if not in_zone(m.start())]
    if not live: continue
    for pos in live:
        line = t[:pos].count("\n") + 1
        ctx = re.sub(r"\s+", " ", t[max(0, pos-90):pos+40]).strip()
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
