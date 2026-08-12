import bisect
#!/usr/bin/env python3
"""Do the numbers in the paper appear anywhere in the data behind it?

Three gates already guard code against code: catalogue against oracle, oracle
against RTL, RTL against build script, design against harness. Enumerating every
pair in the project that must agree shows all three sit in one region -- and that
**no pair with a document on either side is checked at all**.

Sixteen claims were withdrawn during this work. A withdrawn claim's number does
not remove itself from a paper. This looks for distinctive numeric literals in
the paper that appear in no data file, which is where a stale figure hides.

It cannot prove a number is right. It finds numbers with no source, which is a
strictly weaker and still useful thing.
"""
import bisect, re, pathlib, sys, collections

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
# The haystack is 61 MB across ~6,000 files. The first version ran a regex over
# all of it once per paper literal, which is quadratic in the literal count and
# stopped terminating when the paper reached 82 pages. Extract every numeric
# literal from the haystack ONCE into a set, then answer each query by lookup.
_blob = "\n".join(haystack)
def _isnum(x):
    try: float(x); return True
    except ValueError: return False

LIT = re.compile(r'(?<![\w.])(\d{1,3}(?:[, ]\d{3})+|\d+\.\d+|\d+)(?![\w])')
data_lits = {m.group(1).replace(",", "").replace(" ", "") for m in LIT.finditer(_blob)}
del _blob, haystack
# Rounding is numeric, not textual. The first version asked whether a data
# literal STARTS with the paper's digits, which accepts truncation (0.1428 for
# 0.14285) and rejects rounding up (0.1429 for the same value) -- so every
# round-half-up figure in the throughput table read as unsourced. Compare values
# with the tolerance the paper's own precision implies.
_vals = sorted({float(x) for x in data_lits if _isnum(x)})

# Paper occurrences indexed once, so is_measured is a dict lookup rather than a
# fresh scan of the paper per literal. Removed by an earlier edit; restored.
MEASURED = re.compile(r'(LUT|MHz|\\,MHz|bits?|binade|LUTs|\\times|\\%)')
CITED = re.compile(r'(studies report|reported|literature|\\cite|according to|others report)')
DERIVED = re.compile(r'(\\log|\\ln|\\kappa|\\tfrac|\\frac|=\s*$)')
_occ = {}
for _m in LIT.finditer(paper_txt):
    _v = _m.group(1).replace(",", "").replace(" ", "")
    _occ.setdefault(_v, []).append((_m.start(), _m.end()))

def is_measured(v):
    for a, b in _occ.get(v, ()):
        w = paper_txt[max(0, a-90): b+40]
        if DERIVED.search(w) or CITED.search(w): continue
        if MEASURED.search(w): return True
    return False

def sourced(v):
    """A paper rounds what a data file records. Accept any data value within
    half a unit of the paper's last printed digit -- which covers rounding in
    either direction, where a prefix test covers only truncation."""
    if v in data_lits: return True
    if not _isnum(v): return False
    x = float(v)
    tol = 0.5 * 10 ** (-(len(v.split(".")[1])) ) if "." in v else 0.5
    i = bisect.bisect_left(_vals, x - tol)
    return i < len(_vals) and _vals[i] <= x + tol

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
sys.exit(0)
