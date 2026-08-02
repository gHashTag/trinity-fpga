#!/usr/bin/env python3
"""Derive a t27 conformance pack from an existing golden oracle.

Motivation (specs/numeric/catalog_coverage_delta.t27): thirteen formats carry a
golden decode oracle but have no published conformance pack. (This line said twelve
until 2026-08-02; measured against t27's INDEX_all_formats.json the set is
bfloat24, bfloat32, mxfp8_e4m3, mxint8, pdp11_float, tekum8, tekum16, tekum32,
uint4, uint8, uint16, uint32 and x87_48bit -- 1,161 vectors, zero decode errors.) Because the oracle
already exists, the pack is DERIVABLE rather than new work — this script performs
that derivation.

Output conforms to `t27-conformance/v0.1`, the schema used by the packs in
gHashTag/t27 conformance/vectors, and follows their observed conventions:

    width <= 8   -> vector_mode "exhaustive"     (every code)
    width >  8   -> vector_mode "curated_named"  (principled corners)

The packs written here are **candidates for review**, not published artefacts.
They are emitted under conformance/vectors_generated/ and are deliberately NOT
written into gHashTag/t27.

Usage:
    python3 research/gen_conformance_pack.py tekum8 tekum16 tekum32
    python3 research/gen_conformance_pack.py --list
"""
from __future__ import annotations
from fractions import Fraction
import hashlib
import importlib.util
import json
import os
import struct
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONF = os.path.join(REPO, "conformance")
OUT = os.path.join(CONF, "vectors_generated")

SSOT = "https://github.com/gHashTag/t27/blob/master/conformance/FORMAT-SPEC-001.json"
PREPRINT = "https://arxiv.org/abs/2606.05017"
ANCHOR_IDENTITY = "phi^2 + 1/phi^2 = 3"


def load_oracles():
    """{format_name: (module, fmt_obj, family)} over every conformance/*_ref.py."""
    out = {}
    for fn in sorted(os.listdir(CONF)):
        if not fn.endswith("_ref.py") or fn.startswith("_"):
            continue
        try:
            spec = importlib.util.spec_from_file_location("orc_" + fn[:-3],
                                                          os.path.join(CONF, fn))
            mod = importlib.util.module_from_spec(spec)
            # Register before executing: a module using @dataclass looks itself up in
            # sys.modules while the decorator runs, and under a synthetic name it is not
            # there. conformance/takum_log_ref.py fails exactly that way, so an
            # unregistered loader omitted it silently.
            sys.modules[spec.name] = mod
            sys.path.insert(0, CONF)
            spec.loader.exec_module(mod)
        except Exception:
            continue
        for name, fmt in getattr(mod, "FORMATS", {}).items():
            out.setdefault(name, (mod, fmt, fn[:-7]))
    return out


def width_of(fmt, name: str) -> int:
    for attr in ("n", "width", "W", "total", "bits", "nbits"):
        v = getattr(fmt, attr, None)
        if isinstance(v, int) and v > 0:
            return v
    digits = "".join(c for c in name if c.isdigit())
    return int(digits) if digits else 0


def f64_hex(x: float) -> str:
    return "0x" + struct.pack(">d", x).hex()


def to_f64(value):
    """Golden value (Fraction | float | Special) -> (f64_or_None, note)."""
    kind = getattr(value, "kind", None)
    if kind is not None:
        sign = getattr(value, "sign", 0)
        if kind == "nan":
            return None, "NaR/NaN"
        if kind == "inf":
            return None, ("-inf" if sign else "+inf")
        return None, str(kind)
    try:
        return float(value), None
    except (TypeError, ValueError, OverflowError):
        return None, "not representable in binary64"


def curated_raws(mod, fmt, width: int) -> list[tuple[str, int]]:
    """Principled corners for formats too wide to enumerate.

    Corners alone are not enough. A pack is supposed to let a third party check
    the format's properties from the pack itself, and an audit of the pass-11
    packs found that curated mode could not attest to the NEGATION rule at all:
    without the complement of a code present, decode(-raw) == -decode(raw) is
    untestable. Both complements of each seed are therefore included.
    """
    span = 1 << width
    msb = 1 << (width - 1)
    picks = [("zero", 0), ("msb_set", msb),
             ("all_ones", span - 1), ("lsb_set", 1)]
    if hasattr(mod, "encode"):
        for label, val in (("one", 1), ("minus_one", -1), ("two", 2),
                           ("half", Fraction(1, 2)), ("three", 3)):
            try:
                raw = mod.encode(fmt, val)
                if isinstance(raw, int) and 0 <= raw < span:
                    picks.append((label, raw))
            except Exception:
                pass

    # Negation witnesses: for each finite seed, add BOTH candidate complements so
    # the pack can attest to which negation rule the format obeys.
    seeds = [r for _, r in picks if r not in (0, msb)]
    for raw in list(seeds):
        for label, comp in ((f"twos_comp_of_0x{raw:x}", (-raw) % span),
                            (f"xor_comp_of_0x{raw:x}", raw ^ msb)):
            if 0 <= comp < span:
                picks.append((label, comp))
    seen, ordered = set(), []
    for label, raw in picks:
        if raw not in seen:
            seen.add(raw)
            ordered.append((label, raw))
    return ordered


def build_pack(name: str, mod, fmt, family: str) -> dict:
    width = width_of(fmt, name)
    if width == 0:
        raise ValueError(f"cannot determine width for {name}")

    exhaustive = width <= 8
    if exhaustive:
        items = [(f"code_0x{r:0{(width + 3) // 4}x}", r) for r in range(1 << width)]
    else:
        items = curated_raws(mod, fmt, width)

    hexw = (width + 3) // 4
    vectors, max_finite = [], None
    for label, raw in items:
        try:
            decoded = mod.decode(fmt, raw)
        except Exception as e:
            vectors.append({"name": label, f"{name}_bits_int": raw,
                            "decode_error": type(e).__name__})
            continue
        val, note = to_f64(decoded)
        entry = {
            "name": label,
            f"{name}_bits_hex": f"0x{raw:0{hexw}x}",
            f"{name}_bits_int": raw,
        }
        if val is None:
            entry["decoded_f64"] = None
            entry["note"] = note
        else:
            entry["decoded_f64"] = val
            entry["decoded_f64_hex"] = f64_hex(val)
            entry["abs_error"] = 0.0
            if val == val and abs(val) != float("inf"):
                if max_finite is None or abs(val) > abs(max_finite):
                    max_finite = val
        vectors.append(entry)

    # Anchor: is 3.0 an exact grid point of this format?
    anchor = {"value": None, "expected": 3.0, "ieee754_exact": False,
              "note": "not evaluated"}
    if hasattr(mod, "encode"):
        try:
            raw3 = mod.encode(fmt, 3)
            back, _ = to_f64(mod.decode(fmt, raw3))
            anchor = {"value": back, "expected": 3.0,
                      "ieee754_exact": (back == 3.0),
                      "note": ("exact grid point" if back == 3.0 else
                               "3.0 is not an exact grid point of this format")}
        except Exception:
            anchor["note"] = "encode/decode of 3.0 raised"

    return {
        "schema": "t27-conformance/v0.1",
        "format": name.upper(),
        "format_name": name,
        "bitexact": True,
        "format_notes": (f"Derived from the golden oracle conformance/{family}_ref.py "
                         f"by research/gen_conformance_pack.py. "
                         f"{'Exhaustive over all codes.' if exhaustive else 'Curated corner vectors.'} "
                         f"CANDIDATE pack — not yet reviewed or published."),
        "catalog": {"id": name, "bits": width, "status": "Candidate",
                    "source": f"conformance/{family}_ref.py"},
        "ssot": SSOT,
        "preprint": PREPRINT,
        "anchor_identity": ANCHOR_IDENTITY,
        "anchor_check": anchor,
        "round_trip_policy": ("decode: exact bits->f64 via the golden oracle. "
                              "Values outside binary64 range are recorded as null "
                              "with a note rather than clamped."),
        "vector_mode": "exhaustive" if exhaustive else "curated_named",
        "n_vectors": len(vectors),
        "max_finite": max_finite,
        "vectors": vectors,
    }


def main(argv) -> int:
    oracles = load_oracles()
    if not argv or argv[0] == "--list":
        print(f"{len(oracles)} formats with a golden oracle:")
        print("  " + " ".join(sorted(oracles)))
        return 0

    os.makedirs(OUT, exist_ok=True)
    rc = 0
    for name in argv:
        if name not in oracles:
            print(f"SKIP {name}: no golden oracle")
            rc = 1
            continue
        mod, fmt, family = oracles[name]
        try:
            pack = build_pack(name, mod, fmt, family)
        except Exception as e:
            print(f"FAIL {name}: {type(e).__name__}: {e}")
            rc = 1
            continue
        blob = json.dumps(pack, indent=2, ensure_ascii=False, allow_nan=False)
        path = os.path.join(OUT, f"{name}_conformance_v0.json")
        with open(path, "w") as f:
            f.write(blob + "\n")
        digest = hashlib.sha256((blob + "\n").encode()).hexdigest()
        errs = sum(1 for v in pack["vectors"] if "decode_error" in v)
        print(f"OK   {name:<10} mode={pack['vector_mode']:<14} "
              f"n={pack['n_vectors']:<6} decode_errors={errs}  sha256={digest[:16]}…")
    return rc


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
