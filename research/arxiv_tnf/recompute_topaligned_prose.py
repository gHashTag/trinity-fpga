#!/usr/bin/env python3
"""Adjudicate tnf_topaligned_cost.json: which part of the paper does it back?

VERDICT (this script proves both halves):
  1. NEGATIVE -- the record does NOT back tab:alloc, the forward-matcher's best
     candidate (66.7%). tab:alloc prints per-rung error-loss factors
     (predicted 2^k, measured 4.03x/15.43x/15.99x/15.24x) from an
     800-probe exact-arithmetic workload. The record holds binade-width
     enumeration and window-fraction combinatorics; none of the measured
     factors appear anywhere in it, and it has no rung/probe/error fields.
  2. POSITIVE -- the record backs PROSE ONLY: the statement and proof of
     Corollary cor:topaligned (and one Delta(2)=4 in the paragraph above it).
     Its generator gen_topaligned_cost.py says so in its own docstring
     ("Backs Corollary cor:topaligned") -- Rule 1, metadata outranks scores.
     Every numeric claim of that prose is recomputed here from first
     principles and compared at PRINTED precision, conditionally on the
     phrase being present in tnf_paper.tex.

No table prints these values: 137, 0.6309 and the 57.1/52.0/50.6/50.2
sequence occur only at lines ~3040-3075 (corollary + proof), verified by
exhaustive grep during adjudication.
"""
import json
import math
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
PAPER = HERE / "tnf_paper.tex"
RECORD = HERE / "measurements" / "tnf_topaligned_cost.json"

failures = []
cells_matching = 0
cells_total = 0


def check(name, ok, detail=""):
    global cells_matching, cells_total
    cells_total += 1
    cells_matching += bool(ok)
    tag = "PASS" if ok else "FAIL"
    print(f"  [{tag}] {name}" + (f"  ({detail})" if detail else ""))
    if not ok:
        failures.append(f"{name}: {detail}")


def hard(name, ok, detail=""):
    """Structural assertion; not a printed cell."""
    tag = "PASS" if ok else "FAIL"
    print(f"  [{tag}] {name}" + (f"  ({detail})" if detail else ""))
    if not ok:
        failures.append(f"{name}: {detail}")


# ---------------------------------------------------------------- load
tex = PAPER.read_text(encoding="utf-8")
rec = json.loads(RECORD.read_text(encoding="utf-8"))

print("== Rule 1: the record's own metadata ==")
hard("record status field", rec.get("status") == "[proved -- enumeration]",
     repr(rec.get("status")))
gen_doc = (HERE / "measurements" / "gen_topaligned_cost.py").read_text()
hard("generator docstring names cor:topaligned",
     "Backs Corollary cor:topaligned" in gen_doc)

# ------------------------------------------------- exact recomputation
# Widths by exact integer arithmetic (no float ceil): smallest w with
# 3^w >= target.  Centred: thm:optimal, 3^w >= b+1.  Top-aligned:
# cor:topaligned, 3^w >= 2b+1.
def width(target):
    w, p = 0, 1
    while p < target:
        w += 1
        p *= 3
    return w


B = list(range(1, 201))
worse = [b for b in B if width(2 * b + 1) > width(b + 1)]
never_below = all(width(2 * b + 1) >= width(b + 1) for b in B)
recovered = math.log(2, 3)

usable = {}
for et in range(2, 9):
    delta = (3 ** et - 1) // 2
    usable[et] = (delta, 2 * delta - 1, round(100.0 * delta / (2 * delta - 1), 1))

print("\n== Record internal consistency (identities to exact/1e-9) ==")
hard("b_range pinned [1,200]", rec["b_range"] == [1, 200], str(rec["b_range"]))
hard("n_needing_extra_trit == exact enumeration",
     rec["n_needing_extra_trit"] == len(worse),
     f"record {rec['n_needing_extra_trit']} vs exact {len(worse)}")
hard("first_needing_extra_trit == first 14 of exact enumeration",
     rec["first_needing_extra_trit"] == worse[:14])
hard("top_aligned_never_below_centred == exact",
     rec["top_aligned_never_below_centred"] == never_below)
hard("trits_recovered == round(log_3 2, 4)",
     abs(rec["trits_recovered_by_centring"] - round(recovered, 4)) < 1e-9)
uf = rec["usable_fraction_by_exponent_width"]
hard("usable-fraction keys are Et=2..8 exactly",
     sorted(int(k) for k in uf) == list(range(2, 9)))
for et in range(2, 9):
    row = uf[str(et)]
    d, w, p = usable[et]
    hard(f"Et={et}: delta=(3^Et-1)/2, rows=2d-1, reachable=d, pct identity",
         row["delta"] == d and row["window_rows"] == w
         and row["reachable_rows"] == d and abs(row["usable_pct"] - p) < 1e-9,
         f"record {row} vs exact ({d},{w},{p})")

# ------------------------------------- NEGATIVE: tab:alloc adjudication
print("\n== NEGATIVE: tab:alloc cannot be produced from this record ==")
m = re.search(r"\\label\{tab:alloc\}(.*?)\\bottomrule", tex, re.S)
hard("tab:alloc found in paper", m is not None)
rows = re.findall(
    r"^(TNF\d+)\s*&\s*\$(\d+)\$\s*&\s*\$(\d+)\\times\$\s*&\s*\$([\d.]+)\\times\$",
    m.group(1), re.M) if m else []
# Rule 4: vacuous-pass guard -- the table must parse to exactly 4 rows.
hard("tab:alloc parses to exactly 4 printed rows (vacuous-pass guard)",
     len(rows) == 4, f"parsed {len(rows)}")
alloc = {r[0]: (int(r[1]), int(r[2]), float(r[3])) for r in rows}
hard("tab:alloc rungs are TNF16/64/128/256",
     sorted(alloc) == ["TNF128", "TNF16", "TNF256", "TNF64"])

# Flatten every numeric atom in the record.
def atoms(x, out):
    if isinstance(x, dict):
        for v in x.values():
            atoms(v, out)
    elif isinstance(x, list):
        for v in x.values() if isinstance(x, dict) else x:
            atoms(v, out)
    elif isinstance(x, (int, float)) and not isinstance(x, bool):
        out.add(round(float(x), 6))


rec_atoms = set()
atoms(rec, rec_atoms)
measured = [alloc[r][2] for r in sorted(alloc)] if alloc else []
hard("no measured factor (4.03/15.43/15.99/15.24) occurs anywhere in record",
     all(round(v, 6) not in rec_atoms for v in measured),
     f"measured={measured}")
hard("record has no rung/probe/error/measured keys",
     not re.search(r"rung|probe|error|measured|TNF\d",
                   json.dumps(rec), re.I))
print("  -> tab:alloc's measured column needs an 800-probe exact-arithmetic")
print("     error workload (caption, line ~1670); the record holds only binade")
print("     width enumeration and window combinatorics. Disjoint. NOT BACKED.")

# ------------------------------------- POSITIVE: prose of cor:topaligned
print("\n== POSITIVE: prose cells of cor:topaligned, at printed precision ==")
cor = re.search(r"\\label\{cor:topaligned\}.*?\\end\{proof\}", tex, re.S)
hard("cor:topaligned statement+proof located", cor is not None)
cortex = cor.group(0) if cor else ""

# c1: statement: "exceeds it for $137$ of the first $200$ values of $b$"
p1 = re.search(r"exceeds it for \$(\d+)\$ of the first \$(\d+)\$ values", cortex)
if p1:
    check("statement: 'exceeds it for $137$ of the first $200$'",
          int(p1.group(1)) == len(worse) and int(p1.group(2)) == 200,
          f"printed {p1.group(1)}/{p1.group(2)}, exact {len(worse)}/200")
else:
    check("statement '137 of first 200' phrase present", False, "phrase gone")

# c2: proof: "$137$ of $b = 1 \ldots 200$ is by enumeration"
p2 = re.search(r"\$(\d+)\$ of \$b = 1 \\ldots (\d+)\$ is by enumeration", cortex)
if p2:
    check("proof: '$137$ of $b = 1 \\ldots 200$ ... by enumeration'",
          int(p2.group(1)) == len(worse) and int(p2.group(2)) == 200,
          f"printed {p2.group(1)}, exact {len(worse)}")
else:
    check("proof '137 ... by enumeration' phrase present", False, "phrase gone")

# c3: "it never falls below $E_t^{*}$"
check("statement: 'never falls below $E_t^{*}$'",
      ("never falls below" in cortex) and never_below,
      f"exact never_below={never_below}")

# c4: "recovers $\log_3 2 = 0.6309$ trits"
p4 = re.search(r"\\log_3 2 = ([\d.]+)\$? trits", cortex)
if p4:
    check("statement: 'recovers $\\log_3 2 = 0.6309$ trits'",
          abs(float(p4.group(1)) - round(recovered, 4)) < 1e-12,
          f"printed {p4.group(1)}, exact {recovered:.6f} -> {round(recovered,4)}")
else:
    check("'log_3 2 = 0.6309' phrase present", False, "phrase gone")

# c5-c8: proof: "falls from $57.1\%$ at $E_t=2$ through $52.0\%$, $50.6\%$,
# $50.2\%$ to $1/2$"
p5 = re.search(
    r"falls\s+from\s+\$([\d.]+)\\%\$\s+at\s+\$E_t=2\$\s+through\s+"
    r"\$([\d.]+)\\%\$,\s+\$([\d.]+)\\%\$,\s+\$([\d.]+)\\%\$\s+to\s+\$1/2\$",
    cortex, re.S)
if p5:
    for i, et in enumerate(range(2, 6)):
        printed = float(p5.group(i + 1))
        exact = usable[et][2]
        check(f"proof: usable fraction Et={et} = {printed}%",
              abs(printed - exact) < 1e-9, f"exact {exact}%")
    # c9: the stated limit "to $1/2$": sequence is decreasing toward 0.5
    seq = [usable[et][0] / usable[et][1] for et in range(2, 9)]
    check("proof: 'to $1/2$' -- fractions decrease monotonically toward 0.5",
          all(a > b for a, b in zip(seq, seq[1:])) and abs(seq[-1] - 0.5) < 1e-3,
          f"Et=8 fraction {seq[-1]:.6f}")
else:
    for et in range(2, 6):
        check(f"usable-fraction phrase for Et={et} present", False, "phrase gone")
    check("'to $1/2$' phrase present", False, "phrase gone")

# c10: paragraph above the corollary: "But $\Delta(2)=4$"
p10 = re.search(r"\\Delta\(2\)=(\d+)\$", tex)
if p10:
    check("adjacent prose: '$\\Delta(2)=4$'",
          int(p10.group(1)) == usable[2][0], f"exact Delta(2)={usable[2][0]}")
else:
    check("'Delta(2)=4' phrase present", False, "phrase gone")

# Rule 5 sanity: these values occur in NO table environment.
in_tables = "\n".join(re.findall(r"\\begin\{table\}.*?\\end\{table\}", tex, re.S))
hard("record's signature values (137 extra-trit count, 0.6309, 57.1%) "
     "appear in no table environment",
     not re.search(r"0\.6309|57\.1", in_tables)
     and not re.search(r"\$137\$", in_tables))

# ------------------------------------------ Rule 6: unprinted selection
print("\n== Rule 6: record rows the paper never prints ==")
print(f"  first_needing_extra_trit list itself is unprinted: "
      f"{rec['first_needing_extra_trit']}")
print(f"  Et=6: usable_pct {uf['6']['usable_pct']}%  (prose compresses to 'to 1/2')")
print(f"  Et=7: usable_pct {uf['7']['usable_pct']}%  (unprinted)")
print(f"  Et=8: usable_pct {uf['8']['usable_pct']}%  (unprinted; delta=3280)")
print("  Nothing hidden is damaging: the unprinted tail only strengthens the")
print("  printed monotone claim.")

# ---------------------------------------------------------------- exit
print(f"\ncells: {cells_matching}/{cells_total} prose cells match at printed "
      f"precision; {len(failures)} failure(s)")
if failures:
    for f in failures:
        print(f"  DEFECT: {f}")
    print("VERDICT: FAIL")
    sys.exit(1)
print("VERDICT: tnf_topaligned_cost.json backs the PROSE of cor:topaligned "
      "(statement + proof + one Delta(2)=4); it backs NO table, and provably "
      "not tab:alloc.")
sys.exit(0)
