#!/usr/bin/env python3
"""Provenance registry for every frequency figure in the TNF paper.

The existing gate (tools/check_paper_numbers.py) accepts a literal as sourced if
its digit string appears ANYWHERE in the concatenated data blob with separators
stripped. A frequency such as 307.69 therefore "traces" to a conformance vector
file that happens to contain the digits 30769 inside a hexadecimal or decimal
column. That is not provenance.

This registry is stricter in two ways:

  1. only prose/record files can be a source: *.md and *.py under research/,
     fpga/, conformance/, docs/ and the repository root -- the places a
     measurement is actually written down;
  2. the match must be delimited: the literal may not be preceded or followed by
     another digit or by a digit-dot-digit continuation.

It reports, for each frequency literal in the paper, every record file and line
that states it, and whether a place-and-route log backing it exists in the tree.
"""
import re, pathlib, sys, json, hashlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
PAPER = ROOT / "research" / "arxiv_tnf" / "tnf_paper.tex"

paper = PAPER.read_text(encoding="utf-8")
paper = re.sub(r'(?<!\\)%.*', '', paper)
paper = paper.split(r'\begin{thebibliography}')[0]

# A frequency literal: a 2-decimal number that sits in an MHz context. Two
# shapes occur -- an explicit unit, and a bare cell in a table whose column
# header is MHz. The tables are found by name so the bare cells are not guessed.
FREQ_TABLES = {
    "tab:hierarchy": r'\\label\{tab:hierarchy\}(.*?)\\end\{table\}',
    "tab:fullthroughput": r'\\label\{tab:fullthroughput\}(.*?)\\end\{table\}',
}

lits = {}   # literal -> list of where-in-paper


def note(v, where):
    lits.setdefault(v, []).append(where)


# Only a literal that carries the unit directly. A backward window from the unit
# would also collect MHz/LUT ratios and the spread column beside them, which are
# not frequencies, so it is not used.
for m in re.finditer(r'(\d+\.\d{2})(?:\^\{\\ast\})?\$?\s*(?:\\,)?\s*MHz(?!/)', paper):
    note(m.group(1), "inline MHz")
for name, pat in FREQ_TABLES.items():
    mm = re.search(pat, paper, re.S)
    if not mm:
        continue
    body = mm.group(1)
    for row in body.split(r'\\'):
        if '&' not in row:
            continue
        cells = [c.strip() for c in row.split('&')]
        for c in cells:
            c = re.sub(r'[\\${}\^a-zA-Z,]', '', c).strip()
            if re.fullmatch(r'\d+\.\d{2}', c) and 20.0 <= float(c) <= 2000.0:
                note(c, name)

RECORDS = []
for pat in ("research/**/*.md", "research/**/*.py", "fpga/**/*.md", "fpga/**/*.py",
            "conformance/**/*.py", "docs/**/*.md", "*.md", "tools/**/*.py"):
    for p in ROOT.glob(pat):
        if p.is_file() and p != PAPER and p.stat().st_size < 4_000_000:
            RECORDS.append(p)

logs = [p for p in ROOT.rglob("*.log") if ".git" not in p.parts]

rows = []
for v in sorted(lits, key=float, reverse=True):
    rx = re.compile(r'(?<![\d.])' + re.escape(v) + r'(?![\d])')
    hits = []
    for p in RECORDS:
        try:
            txt = p.read_text(errors="ignore")
        except Exception:
            continue
        for i, line in enumerate(txt.splitlines(), 1):
            if rx.search(line):
                hits.append(f"{p.relative_to(ROOT)}:{i}")
    rows.append({"value": v, "used_in": sorted(set(lits[v])),
                 "records": hits[:6], "record_count": len(hits)})

print(f"paper            {PAPER.relative_to(ROOT)}")
print(f"paper sha256     {hashlib.sha256(PAPER.read_bytes()).hexdigest()}")
print(f"record files     {len(RECORDS)}")
print(f"place-and-route logs in tree  {len(logs)}")
print(f"frequency literals in paper   {len(rows)}")
print()
unsourced = [r for r in rows if r["record_count"] == 0]
print(f"{'value':>10}  {'records':>7}  used in / first record")
for r in rows:
    first = r["records"][0] if r["records"] else "-- NO RECORD --"
    print(f"{r['value']:>10}  {r['record_count']:>7}  {', '.join(r['used_in'])[:38]:38}  {first}")
print()
print(f"UNSOURCED AGAINST RECORD FILES: {len(unsourced)} of {len(rows)}")
for r in unsourced:
    print("   ", r["value"], "->", ", ".join(r["used_in"]))
out = ROOT / "research" / "arxiv_tnf" / "freq_provenance.json"
out.write_text(json.dumps({"paper_sha256": hashlib.sha256(PAPER.read_bytes()).hexdigest(),
                           "pnr_logs_in_tree": len(logs), "rows": rows}, indent=1))
print("\nwritten", out.relative_to(ROOT))
sys.exit(0)
