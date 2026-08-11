#!/usr/bin/env python3
"""One rung name, one meaning.

conformance/tnf_spec_ref.py and conformance/tnf_ladder_invariants_test.py each
declare a ladder, under the same names, disagreeing on tnf16 (M=9 against M=11)
and tnf64 (52 against 56). Both passed their own tests for the whole campaign,
because neither said which unit it counted: one is a POSITION budget
(N = 1 + E_t + M), the other a STORED-BIT width (1 + ceil(E_t log2 3) + M).

The RTL implements the stored-bit ladder, so the invariants test has been
exercising rungs that no silicon realises. That is the failure the debugging
doctrine names directly: resolve a contradiction immediately, never append a
second truth beside the first.

This gate requires each file to declare UNIT, requires the two units to differ
(if they were the same the ladders would have to be identical), and checks that
each ladder is internally consistent with its own declared unit.
"""
import importlib.util, math, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parents[1]

def load(name):
    p = ROOT / "conformance" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, p)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    sys.path.insert(0, str(ROOT / "conformance"))
    spec.loader.exec_module(m)
    return m

fails = []
try:
    ref = load("tnf_spec_ref")
except Exception as e:
    print(f"FAIL: tnf_spec_ref did not load: {e}"); sys.exit(1)

inv_src = (ROOT / "conformance" / "tnf_ladder_invariants_test.py").read_text()
inv_unit = None
for line in inv_src.splitlines():
    if line.startswith("UNIT"):
        inv_unit = line.split("=", 1)[1].strip().strip('"\'')
ref_unit = getattr(ref, "UNIT", None)

if ref_unit is None:
    fails.append("tnf_spec_ref.py does not declare UNIT")
if inv_unit is None:
    fails.append("tnf_ladder_invariants_test.py does not declare UNIT")
if ref_unit and inv_unit and ref_unit == inv_unit:
    fails.append(f"both ladders declare UNIT={ref_unit!r} yet give different M "
                 f"for the same names -- one of them is wrong")

# the stored-bit ladder must be self-consistent: width == 1 + ceil(Et log2 3) + M
if ref_unit == "stored bits":
    for name, f in ref.FORMATS.items():
        want = 1 + math.ceil(f.et * math.log2(3)) + f.mant_bits
        if f.width != want:
            fails.append(f"{name}: declares width {f.width}, stored-bit rule gives {want}")

print(f"ladders checked: 2   units: tnf_spec_ref={ref_unit!r}, invariants={inv_unit!r}")
if fails:
    print(f"\nFAIL: {len(fails)} problem(s)\n")
    for x in fails: print(f"  {x}")
    sys.exit(1)
print("OK: each ladder declares its unit and is consistent within it")
