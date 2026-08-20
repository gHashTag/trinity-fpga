#!/usr/bin/env python3
"""Do the numbers in the paper appear anywhere in the data behind it?

Three gates already guard code against code: catalogue against oracle, oracle
against RTL, RTL against build script, design against harness. Enumerating every
pair in the project that must agree shows all three sit in one region -- and that
**no pair with a document on either side is checked at all**.

Twenty claims were withdrawn during this work. A withdrawn claim's number does
not remove itself from a paper. This looks for distinctive numeric literals in
the paper that appear in no data file, which is where a stale figure hides.

It cannot prove a number is right. It finds numbers with no source, which is a
strictly weaker and still useful thing.
"""
import re, pathlib, sys, collections

ROOT = pathlib.Path(__file__).resolve().parents[1]
PAPER = ROOT / "research" / "arxiv_tnf" / "tnf_paper.tex"

# Where a number in the paper could legitimately come from
SOURCES = [p for pat in ("research/**/*.md", "research/**/*.py", "research/**/*.json",
                         "research/**/*.txt", "fpga/**/*.md", "fpga/**/*.v",
                         "conformance/**/*.py",
                         "conformance/**/*.json", "conformance/**/*.txt",
                         "docs/**/*.md", "*.md")
             for p in ROOT.glob(pat)
             if p.is_file() and p != PAPER and p.stat().st_size < 2_000_000]

def literals(text):
    """Distinctive numbers: 3+ significant digits, or a decimal with 2+ places.
    Small integers and years are too common to trace."""
    out = set()
    for m in re.finditer(r'(?<![\w.])(\d{1,3}(?:[, ]\d{3})+|\d+\.\d{2,}|\d{3,})(?![\w])', text):
        v = m.group(1).replace(",", "").replace(" ", "")
        if v in {"1000","2026","2020","2023","2024","2025","100","200","500"}: continue
        if re.fullmatch(r'\d{4}', v) and 1900 < int(v) < 2100: continue
        out.add(v)
    return out

paper_txt = PAPER.read_text(encoding="utf-8")
# strip LaTeX comments and the bibliography, where numbers are page/year noise
paper_txt = re.sub(r'(?<!\\)%.*', '', paper_txt)
paper_txt = paper_txt.split(r'\begin{thebibliography}')[0]
want = literals(paper_txt)

haystack = []
for p in SOURCES:
    try: haystack.append(p.read_text(errors="ignore"))
    except Exception: pass
blob = "\n".join(haystack).replace(",", "").replace(" ", "")

# A number stated next to the formula that produces it is derived, not measured,
# and has no business in a data file. Only quantities carrying a unit or sitting
# in a results table are traceable claims.
MEASURED = re.compile(r'(LUT|MHz|\\,MHz|bits?|binade|LUTs)')
# A figure attributed to someone else's paper is their measurement, not ours, and
# has no business in our data files. Excluded rather than reported as missing.
CITED = re.compile(r'(studies report|reported|literature|\\cite|according to|others report)')
DERIVED  = re.compile(r'(\\log|\\ln|\\kappa|\\tfrac|\\frac|=\s*$)')

def is_measured(v):
    for m in re.finditer(r'(?<![\w.])' + re.escape(v) + r'(?![\w])', paper_txt):
        w = paper_txt[max(0, m.start()-90): m.end()+40]
        if DERIVED.search(w) or CITED.search(w): continue
        if MEASURED.search(w): return True
    return False

def sourced(v):
    """A paper may round what a data file records: 0.181 for 0.1807. Accept a
    data literal that starts with the paper's digits, so rounding is not counted
    as a missing source."""
    if v in blob: return True
    if "." in v:
        return re.search(r'(?<![\d.])' + re.escape(v) + r'\d', blob) is not None
    return False

all_missing = sorted((v for v in want if not sourced(v)), key=lambda s: (-len(s), s))
missing = [v for v in all_missing if is_measured(v)]
derived = [v for v in all_missing if v not in missing]
print(f"unsourced but derived in place (formula alongside): {len(derived)}")

print(f"paper: {PAPER.relative_to(ROOT)}")
print(f"distinctive literals in paper: {len(want)}")
print(f"data files searched: {len(SOURCES)}")
print(f"literals with no source AND carrying a unit: {len(missing)}")
if missing:
    print("\nNot found in any data file -- candidates for stale or unsourced figures:\n")
    for v in missing[:40]:
        ctx = re.search(r'.{0,70}(?<![\w.])' + re.escape(v) + r'(?![\w]).{0,50}', paper_txt, re.S)
        c = " ".join(ctx.group(0).split()) if ctx else ""
        print(f"  {v:>12s}  {c[:100]}")
    if len(missing) > 40: print(f"  ... and {len(missing)-40} more")

# Until now this ended `sys.exit(0)` unconditionally: it reported unsourced
# figures and passed regardless, so CI ran it as a check that could not go red.
# A gate that cannot fail is green for the same reason an unplugged one is.
#
# Unsourced is not automatically wrong — a figure may be derived in place or
# quoted from someone else's paper — so failing on the whole set would block
# every pull request forever. It fails on what is NEW instead, exactly as
# check_withdrawn_live does: the accepted set lives in a baseline file, and a
# figure that was not there before has to be either sourced or added
# deliberately, with a human deciding which.
BASELINE = ROOT / "tools" / "paper_numbers_baseline.txt"
if "--write-baseline" in sys.argv:
    BASELINE.write_text("\n".join(missing) + ("\n" if missing else ""))
    print(f"baseline written: {len(missing)} accepted")
    sys.exit(0)

known = set()
if BASELINE.is_file():
    known = {l.strip() for l in BASELINE.read_text().splitlines() if l.strip()}
new_unsourced = sorted(set(missing) - known, key=lambda s: (-len(s), s))
if new_unsourced:
    print(f"\nFAIL: {len(new_unsourced)} NEW unsourced figure(s) carrying a unit:")
    for v in new_unsourced[:20]:
        print(f"  {v}")
    print("\nEither trace the figure to a data file, or accept it deliberately:")
    print("  python3 tools/check_paper_numbers.py --write-baseline")
    sys.exit(1)
print(f"OK: no new unsourced figure ({len(known)} accepted)")
sys.exit(0)
