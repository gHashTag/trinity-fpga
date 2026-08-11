#!/usr/bin/env python3
"""Every row's code utilisation is measured, not computed.

This paper published a caveat it had computed: rung A discards 37.5% of its
offset codes, therefore 15.32 effective bits, therefore its win over binary16 is
bought. Sweeping the RTL gave 98.4% -- the out-of-specification offsets decode
to distinct values rather than being discarded, and the caveat was false in the
direction that made our own result look worse.

The same iteration also published that GFTernary "uses all four of its codes and
discards nothing". Measured: three values in two bits, 75%.

Both errors have one shape: a property of the silicon asserted from the
specification instead of read off the silicon. This gate requires that every row
of the throughput table carries a utilisation figure produced by
tools/measure_code_use.py, and that the figure in the table matches the one in
code_use.json rather than drifting from it.
"""
import json, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
D = ROOT / "research" / "arxiv_tnf"
table = json.loads((D / "full_table.json").read_text())
if not (D / "code_use.json").exists():
    print("FAIL: code_use.json is missing -- run tools/measure_code_use.py"); sys.exit(1)
cu = json.loads((D / "code_use.json").read_text())

fails = []
for row in table:
    f = row["format"]
    if row.get("code_use") is None:
        fails.append(f"{f}: no measured code utilisation"); continue
    if f not in cu:
        fails.append(f"{f}: table carries a utilisation with no entry in code_use.json"); continue
    if abs(cu[f]["use"] - row["code_use"]) > 5e-4:
        fails.append(f"{f}: table says {row['code_use']:.4f}, measurement says "
                     f"{cu[f]['use']:.4f} -- the table drifted from the sweep")

print(f"rows checked: {len(table)}   measured formats: {len(cu)}")
if fails:
    print(f"\nFAIL: {len(fails)} row(s) without a measured utilisation\n")
    for x in fails: print(f"  {x}")
    sys.exit(1)
print("OK: every row's utilisation comes from a sweep of its own RTL")
