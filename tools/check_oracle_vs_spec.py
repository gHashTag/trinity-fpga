#!/usr/bin/env python3
"""Fail when an oracle's special values disagree with the spec they claim to model.

Written after a conformance run reported 110 mismatches out of 994 for the GF16
multiplier and three independently stored copies of the RTL produced the same
110 — which is the shape of a convention difference, not a bug. It was: the spec
declares GF16_NAN = 0xFE01 with the sign bit SET, while the oracle builds a
quiet NaN generically as (exp_max << mant_bits) | 1 = 0x7E01 for the whole GF
family. The RTL followed the spec; the oracle followed its own rule; and the
vector pack shipped the oracle's answer as "expected" with a note that mentions
neither choice.

Nothing was watching for that. A reviewer comparing a spec-conformant design
against those vectors would have concluded the design was broken.

The gate reads the constants out of the .t27 spec and compares them with what
the oracle produces. A divergence is allowed — the oracle deliberately uses
gradual underflow where the spec flushes subnormals, and says so in a comment —
but it must be declared in ALLOWED below, with the reason, so it is a decision
on the record rather than a surprise in a report.

Exit 0 when every format agrees or diverges by declaration, 1 otherwise.
"""
import os
import re
import sys
from pathlib import Path

# Repo-relative so the gate runs on any checkout; override with T27_SPECS.
T27 = Path(os.environ.get("T27_SPECS", Path(__file__).resolve().parents[2] / "t27" / "specs" / "numeric"))
CONF = Path(__file__).resolve().parents[1] / "conformance"

# Divergences that are known, intended and written down. Anything not here is a
# failure, which is the point: silence is what let this one travel.
ALLOWED = {
    ("gf16", "quiet_nan"): (
        "spec 0xFE01 carries the sign bit; the oracle uses the family-generic "
        "sign-clear form. Undeclared until 2026-08-11 — it produced 55 of the "
        "110 GF16 multiplier mismatches."
    ),
}

CONSTS = {
    "quiet_nan": r"GF16_NAN\s*:\s*u16\s*=\s*(0x[0-9A-Fa-f]+)",
    "pos_inf": r"GF16_INF_POS\s*:\s*u16\s*=\s*(0x[0-9A-Fa-f]+)",
    "neg_inf": r"GF16_INF_NEG\s*:\s*u16\s*=\s*(0x[0-9A-Fa-f]+)",
    "pos_zero": r"GF16_ZERO_POS\s*:\s*u16\s*=\s*(0x[0-9A-Fa-f]+)",
    "neg_zero": r"GF16_ZERO_NEG\s*:\s*u16\s*=\s*(0x[0-9A-Fa-f]+)",
}


def spec_constants(name: str):
    f = T27 / f"{name}.t27"
    if not f.is_file():
        return None
    txt = f.read_text(encoding="utf-8", errors="ignore")
    out = {}
    for key, pat in CONSTS.items():
        m = re.search(pat, txt)
        if m:
            out[key] = int(m.group(1), 16)
    return out or None


def main():
    sys.path.insert(0, str(CONF))
    try:
        import gf_ref
    except Exception as e:  # pragma: no cover
        print(f"  cannot import the oracle: {e}")
        return 1

    fails = 0
    checked = 0
    for name, fmt in sorted(gf_ref.FORMATS.items()):
        spec = spec_constants(name)
        if not spec:
            continue
        for key, want in spec.items():
            got = getattr(fmt, key, None)
            if got is None:
                continue
            checked += 1
            if got == want:
                continue
            why = ALLOWED.get((name, key))
            if why:
                print(f"  DECLARED  {name}.{key}: spec 0x{want:04X} vs oracle 0x{got:04X} — {why}")
            else:
                print(f"  MISMATCH  {name}.{key}: spec says 0x{want:04X}, oracle produces 0x{got:04X}")
                fails += 1
    if not checked:
        print("  nothing was compared — the spec path or the constant patterns are wrong")
        return 1
    print(f"  compared {checked} constants across the formats that have a .t27 spec")
    print("  OK" if not fails else f"  {fails} undeclared divergence(s)")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
