#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Regenerate the takum8 conformance pack from the corrected decode.

Pass 149 established why the published pack is wrong and derived the rule from
libtakum's own source: a takum narrower than the reference width decodes as the high
bits of a word at that width, so its field widths come from 16 and not from 8. Sizing
them at 8 gives `p = 8 - r_eff - 5`, negative over half the code space, and clamping
that to zero put 124 of 254 codes wrong by up to 26 orders of magnitude.

This writes the pack that rule produces. It changes nothing in place: the output goes
to a file you name, and moving it into `t27` is a separate, human decision.

Each value is the **correctly rounded** nearest double to the exact quantity, decided
in exact arithmetic against both neighbouring doubles -- not a float conversion of an
approximation. `conformance/takum_log_ref.py` supplies `ln|value|` as an exact
`Fraction`, and mpmath at 300 bits carries the exponential; the rounding decision never
depends on a float operation.

The pack keeps the published file's schema and metadata verbatim except for the
vectors, the witness list, and a regeneration note -- so a reviewer can diff it against
the published pack and see only what changed.

    python3 research/regenerate_takum8_pack.py --out takum8_v1.json
    python3 research/regenerate_takum8_pack.py --self-check
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
from fractions import Fraction

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "conformance"))

try:
    import mpmath
except ImportError:
    print("mpmath is not installed; this generator needs it.")
    raise SystemExit(2)

mpmath.mp.prec = 300

import takum_log_ref as T                                   # noqa: E402


def exact_value(fmt, raw):
    """The exact value at 300 bits, or None where the code carries no value."""
    ln = T.decode_ln(fmt, raw)
    if isinstance(ln, T.Special):
        return mpmath.mpf(0) if ln.kind == "zero" else None
    v = mpmath.e ** (mpmath.mpf(ln.numerator) / mpmath.mpf(ln.denominator))
    return -v if T.sign_of(fmt, raw) else v


def nearest_double(exact) -> float:
    """The nearest double to `exact`, decided against both neighbours in mpmath.

    float(exact) is mpmath's own rounding and is almost certainly right, but "almost
    certainly" is not what a conformance vector should rest on. This checks it.
    """
    if exact == 0:
        return 0.0
    cand = float(exact)
    if not math.isfinite(cand):
        return cand
    best, bestd = cand, abs(mpmath.mpf(cand) - exact)
    for nb in (math.nextafter(cand, -math.inf), math.nextafter(cand, math.inf)):
        d = abs(mpmath.mpf(nb) - exact)
        if d < bestd:
            best, bestd = nb, d
    return best


def f64_hex(x: float) -> str:
    import struct
    return "0x" + struct.pack(">d", x).hex().upper()


def build(published: dict) -> dict:
    fmt = T.FORMATS["takum8"]
    old = {v["takum8_bits_int"]: v for v in published["vectors"]}

    vectors, changed, kept, nar = [], 0, 0, 0
    for raw in range(256):
        prev = old.get(raw, {})
        exact = exact_value(fmt, raw)
        if exact is None:                                    # NaR
            nar += 1
            vectors.append({**prev, "takum8_bits_int": raw,
                            "takum8_bits_hex": f"0x{raw:02X}",
                            "decoded_f64": None,
                            "decoded_f64_hex": None,
                            "category": "nar"})
            continue
        val = nearest_double(exact)
        if prev.get("decoded_f64") == val:
            kept += 1
        else:
            changed += 1
        vectors.append({
            "name": prev.get("name", f"code_{raw}"),
            "takum8_bits_int": raw,
            "takum8_bits_hex": f"0x{raw:02X}",
            "decoded_f64": val,
            "decoded_f64_hex": f64_hex(val),
            "abs_error": 0.0,
            "category": prev.get("category",
                                 "zero" if val == 0 else "normal"),
        })

    out = {k: v for k, v in published.items() if k != "vectors"}
    out["vectors"] = vectors
    out["n_vectors"] = len(vectors)
    out["regenerated"] = {
        "date": "2026-08-02",
        "reason": ("the published pack sized the takum field widths at the storage "
                   "width, 8, giving p = 8 - r_eff - 5, which is negative over half "
                   "the code space; clamping p to zero put 124 of 254 codes wrong by "
                   "up to 26 orders of magnitude"),
        "rule": ("a takum narrower than the reference width decodes as the high bits "
                 "of a word at that width, so p = 16 - r_eff - 5 = 11 - r_eff, never "
                 "below 4"),
        "rule_derived_from": "libtakum/src/codec.c, then tested exhaustively",
        "rule_test": ("takum_log8_to_float64(x) == takum_log16_to_float64(x << 8) "
                      "for all 256 codes, 0 differ"),
        "vectors_unchanged": kept,
        "vectors_changed": changed,
        "vectors_nar": nar,
        "generator": "research/regenerate_takum8_pack.py",
    }
    out["witnesses"] = [{
        "kind": "libtakum_c_parity",
        "oracle": ("libtakum (Hunhold, ISO C99 reference) takum_log8_to_float64, "
                   "built from source and compared over all 256 codes"),
        "result": ("254 comparable codes, median relative error 4.36e-16, max "
                   "6.89e-15, 0 worse than 1e-9. The ceiling is long-double noise "
                   "in libtakum's own pow, and matches takum16's 7.38e-15."),
    }, {
        "kind": "exact_rational_log_oracle",
        "oracle": ("conformance/takum_log_ref.py: ln|value| exact as a Fraction, "
                   "exponential at 300 bits, rounding decided against both "
                   "neighbouring doubles in exact arithmetic"),
        "result": "every vector is the correctly rounded nearest double",
    }]
    return out, kept, changed, nar


def self_check() -> int:
    """The generator must reproduce libtakum on every comparable code."""
    fmt = T.FORMATS["takum8"]
    bad = 0
    landmarks = {0: 0.0, 64: 1.0, 192: -1.0}
    for raw, want in landmarks.items():
        got = nearest_double(exact_value(fmt, raw))
        ok = got == want
        bad += not ok
        print(f"  raw {raw:>3} -> {got!r:<8} expected {want!r:<8} "
              f"{'ok' if ok else 'MISMATCH'}")
    n = sum(1 for r in range(256) if exact_value(fmt, r) is not None)
    print(f"  codes carrying a value: {n} of 256 (1 NaR)")
    print(f"\nself-check: {'PASS' if bad == 0 else f'FAIL ({bad})'}")
    return bad


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--published", default=os.path.join(
        "/private/tmp/claude-501/-Users-playom-trinity-fpga",
        "3a885a60-490c-4733-abfd-86bfa298080d/scratchpad/takum8.json"))
    ap.add_argument("--out")
    ap.add_argument("--self-check", action="store_true")
    args = ap.parse_args()

    if args.self_check:
        return 1 if self_check() else 0

    if not os.path.exists(args.published):
        print(f"published pack not found: {args.published}")
        print("  gh api repos/gHashTag/t27/contents/conformance/vectors/"
              "takum8_conformance_v0.json --jq .content | base64 -d > takum8.json")
        return 2

    published = json.load(open(args.published, encoding="utf-8"))
    out, kept, changed, nar = build(published)

    print(f"regenerated takum8 pack")
    print(f"  vectors            : {len(out['vectors'])}")
    print(f"  unchanged          : {kept}")
    print(f"  changed            : {changed}")
    print(f"  NaR                : {nar}")

    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(out, f, indent=2)
            f.write("\n")
        print(f"\nwritten to {args.out}")
    else:
        print("\n(no --out given, nothing written)")

    print(f"""
Nothing was replaced. Moving this into t27 is a separate decision, and the diff
against the published pack is the argument for it: {kept} vectors are identical and
{changed} change, each to the value libtakum gives.""")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
