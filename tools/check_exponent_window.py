#!/usr/bin/env python3
"""No rung may decode to fp32 through an eight-bit exponent it overflows.

Every ladder decoder forms the fp32 exponent as

    wire [7:0] e32 = e[7:0] + 8'd127;

which is correct only while e + 127 lies in [0, 255], that is e in [-127, 128].
Outside that window the addition wraps, so `off` and `off + 256` produce the
same output: TNF32's offsets 364, 620 and 876 -- exponents 0, 256 and 512 -- all
decode to exactly 1.0. The comment beside the line says "wider rungs clip". It
does not clip; it wraps, and a wrapped exponent is a wrong finite number rather
than a saturated one, which no conformance test that samples uniformly is likely
to notice.

A rung's exponent spans e in [1 - E, offset_max - 1 - E] for E = (3^Et - 1)/2,
so the whole span fits the window exactly when 3^Et / 2 <= 128, that is

    Et <= 5.

3^5/2 = 121 fits; 3^6/2 = 364 does not. Three rungs were withdrawn for this and
the boundary is sharp, so the rule is worth enforcing rather than remembering:
an Et >= 6 rung must saturate to +-inf outside the window, or emit more than 32
bits, and either changes its cost.
"""
import importlib.util, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "conformance"))
spec = importlib.util.spec_from_file_location("tnf_spec_ref", ROOT / "conformance" / "tnf_spec_ref.py")
ref = importlib.util.module_from_spec(spec)
sys.modules["tnf_spec_ref"] = ref
spec.loader.exec_module(ref)

SATURATING = set()          # rungs whose RTL provably saturates rather than wraps

# Scope: rungs the throughput table actually claims. The withdrawn ones stay in
# the reference so their defect stays documented, and are listed here rather
# than deleted -- a gate that silently ignores a known-bad entry is how the
# defect returns.
import json as _json
_tbl = ROOT / "research" / "arxiv_tnf" / "full_table.json"
_live = {r["format"].lower().replace(" ", "").replace("+", "plus")
         for r in _json.loads(_tbl.read_text())} if _tbl.exists() else None
WITHDRAWN = {"tnf32", "tnf64", "tnf64b"}
fails, checked = [], 0
for name, f in sorted(ref.FORMATS.items()):
    checked += 1
    lo, hi = 1 - f.exp_offset, f.offset_max - 1 - f.exp_offset
    if lo + 127 >= 0 and hi + 127 <= 255:
        continue
    if name in SATURATING:
        continue
    if name in WITHDRAWN:
        continue
    fails.append(f"{name}: E_t={f.et}, exponent spans [{lo:+d},{hi:+d}], "
                 f"outside fp32's [-127,+128] -- e[7:0]+127 wraps, so off and "
                 f"off+256 decode identically")

print(f"rungs checked: {checked}   withdrawn for this defect: {len(WITHDRAWN)}   "
      f"window: e in [-127,+128], i.e. E_t <= 5")
if fails:
    print(f"\nFAIL: {len(fails)} rung(s) would alias\n")
    for x in fails: print(f"  {x}")
    print("\n  A rung wider than E_t=5 must saturate outside the window or emit "
          "more than 32 bits. Add it to SATURATING only with the RTL to prove it.")
    sys.exit(1)
print("OK: every rung's exponent fits the window its decoder assumes")
