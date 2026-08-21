#!/usr/bin/env python3
"""W965: characterise rung 16, both ladder versions, against peers of two kinds.

W954 showed the eighth rung was never measured because a name was bound to the wrong
object. Rung 16 has the same hazard twice over: LADDER (v1-research) gives
TNFFormat(4, 9) at 17 bits, get_ladder(DEFAULT) (v2-spec) gives TNFFormat(4, 11) at
19 bits. Both are characterised here, labelled by version, never by name alone.

Peers come in two kinds because W954 also showed that matching WIDTH alone prices the
range one format buys and the other does not:
  * width-matched   -- a float of the same physical width with a conventional exponent
  * range-matched   -- the exponent widened until the span meets the rung's

Decomposition is exact integer arithmetic: a float IS dyadic, so Fraction(v) is exact
and limit_denominator is both unnecessary and, over half a million values, ruinously
slow -- the first version of this rig ran past ten minutes on it.
"""
import json, math, os, pathlib, sys, time
from fractions import Fraction
import numpy as np

S = pathlib.Path(os.environ.get("T27_WORK") or pathlib.Path(__file__).resolve().parent)
sys.path.insert(0, os.environ.get("T27_CONFORMANCE") or str(S / "oracles"))
import tnf_ref as T, fp8_ref as F8


def stats(mod, fmt, W, label):
    t0 = time.time()
    vals = []
    for c in range(1 << W):
        try:
            v = float(mod.decode(fmt, c))
        except Exception:
            continue
        if np.isfinite(v):
            vals.append(v)
    nz = [Fraction(abs(v)) for v in vals if v != 0]          # exact: floats are dyadic
    fb = max(f.denominator.bit_length() - 1 for f in nz)     # fractional bits needed
    odd, smax = set(), 0
    for f in nz:
        M = f.numerator << (fb - (f.denominator.bit_length() - 1))
        s = 0
        while M and M % 2 == 0:
            M >>= 1
            s += 1
        odd.add(M)
        if s > smax:
            smax = s
    ob = max(m.bit_length() for m in odd)
    hi = max(nz); lo = min(nz)
    b = math.log2(hi.numerator / hi.denominator) - math.log2(lo.numerator / lo.denominator)
    print(f"  {label:24} {W:3d}b {len(set(vals)):7d} знач {b:7.2f} бинад  "
          f"нечёт {ob:2d}  сдвиг<={smax:3d}  шина {2*ob+2*smax:4d}  ({time.time()-t0:.0f} с)",
          flush=True)
    return dict(width=W, values=len(set(vals)), binades=round(b, 2), odd_bits=ob,
                max_shift=smax, aligned=2 * ob + 2 * smax, label=label)


_F = F8.FPxFormat
CASES = [
    ("TNF16_v1research_17b", T, T.TNFFormat(4, 9), 17, "TNF16 v1-research (4,9)"),
    ("TNF16_v2spec_19b",     T, T.TNFFormat(4, 11), 19, "TNF16 v2-spec (4,11)"),
    ("fp17_e6m10", F8, _F("fp17_e6m10", 6, 10, 31), 17, "fp17 e6m10 (ширина)"),
    ("fp19_e6m12", F8, _F("fp19_e6m12", 6, 12, 31), 19, "fp19 e6m12 (ширина)"),
    ("fp17_e7m9",  F8, _F("fp17_e7m9", 7, 9, 63),   17, "fp17 e7m9 (диапазон)"),
    ("fp19_e7m11", F8, _F("fp19_e7m11", 7, 11, 63), 19, "fp19 e7m11 (диапазон)"),
]
out = {}
for key, mod, fmt, W, label in CASES:
    out[key] = stats(mod, fmt, W, label)
    (S / "rung16_w965.json").write_text(json.dumps(out, indent=1))
print("\nWROTE " + str(S / "rung16_w965.json"), flush=True)
