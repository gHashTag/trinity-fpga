#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""What would change if takum8 were regenerated from the logarithmic oracle?

Pass 135 built conformance/takum_log_ref.py, which reproduces the logarithmic takum
definition exactly and agrees with the mpmath witness on every code with a worst
relative difference of zero. An oracle without a pack is a proposal; this produces the
ledger.

For every code in the published takum8 pack, this reports what the published vector
says, what the logarithmic oracle says, and the distance between them. Nothing is
written into t27 and no pack is replaced.

Read the "same" column first. Where the two agree, the published vector needs no
change; where they do not, the size of the difference is what decides whether this is
a regeneration or a withdrawal.

    python3 research/compare_takum_packs.py [--pack PATH] [--show N]
"""
from __future__ import annotations

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "conformance"))

try:
    import mpmath
except ImportError:
    print("mpmath is not installed; this comparison needs it.")
    raise SystemExit(2)

mpmath.mp.prec = 200

import takum_log_ref as T                               # noqa: E402

DEFAULT = os.path.join(
    "/private/tmp/claude-501/-Users-playom-trinity-fpga",
    "3a885a60-490c-4733-abfd-86bfa298080d/scratchpad/takum8.json")


def exact_value(fmt, raw):
    """The logarithmic definition's value at 200-bit precision, or None for NaR."""
    ln = T.decode_ln(fmt, raw)
    if isinstance(ln, T.Special):
        return mpmath.mpf(0) if ln.kind == "zero" else None
    v = mpmath.e ** (mpmath.mpf(ln.numerator) / mpmath.mpf(ln.denominator))
    return -v if T.sign_of(fmt, raw) else v


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pack", default=DEFAULT)
    ap.add_argument("--show", type=int, default=6)
    args = ap.parse_args()

    if not os.path.exists(args.pack):
        print(f"pack not found: {args.pack}")
        print("  gh api repos/gHashTag/t27/contents/conformance/vectors/"
              "takum8_conformance_v0.json --jq .content | base64 -d > takum8.json")
        return 2

    pack = json.load(open(args.pack, encoding="utf-8"))
    fmt = T.FORMATS["takum8"]
    vectors = pack["vectors"]

    bit_key = next((k for k in vectors[0] if k.endswith("_bits_int")), None)
    val_key = next((k for k in vectors[0] if k.startswith("decoded_f64")
                    and not k.endswith("_hex")), None)
    if not (bit_key and val_key):
        print(f"unexpected pack shape; keys are {list(vectors[0])}")
        return 2

    same = 0
    diff = []
    unrepresentable = 0

    for e in vectors:
        raw = e[bit_key]
        published = e[val_key]
        exact = exact_value(fmt, raw)
        if exact is None:                                # NaR
            continue
        if exact == 0:
            same += published == 0
            continue
        if published == 0:
            diff.append((mpmath.inf, raw, published, exact))
            continue
        rel = abs((mpmath.mpf(published) - exact) / exact)
        if rel == 0:
            same += 1
        else:
            diff.append((rel, raw, published, exact))
        if abs(mpmath.log(abs(exact), 2)) > 1023:
            unrepresentable += 1

    print(f"published takum8 vectors compared : {len(vectors)}")
    print(f"  identical to the logarithmic definition : {same}")
    print(f"  differing                               : {len(diff)}")
    if unrepresentable:
        print(f"  whose exact value is outside float64 range : {unrepresentable}")

    if diff:
        diff.sort(key=lambda d: -d[0] if d[0] != mpmath.inf else -mpmath.mpf('1e400'))
        print(f"\nlargest disagreements (relative):")
        for rel, raw, pub, ex in diff[:args.show]:
            r = "published is 0" if rel == mpmath.inf else mpmath.nstr(rel, 5)
            print(f"  0x{raw:02X}  published {pub!r:<24} exact {mpmath.nstr(ex, 12)}")
            print(f"        relative difference {r}")

    print(f"""
What this decides. {same} of the published vectors already match the logarithmic
definition and would survive a regeneration untouched. {len(diff)} would change.

The ledger is the point: "regenerate takum8" is a decision about {len(diff)} vectors,
not about the pack as a whole, and the sizes above say whether those are roundings or
different numbers.""")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
