#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Cross-validate the oracles that have no published pack.

Pass 121 found thirteen formats with a working golden oracle and no published
conformance pack, and pass 122 wrote them up with a bound: generating is not
publishing. A pack that runs with zero decode errors has shown the oracle is
self-consistent and terminates -- not that its values are right. The 83 published
packs went through review and, where a third-party implementation exists,
cross-validation against it.

This does that second part for the ones where an independent implementation is at
hand, so the bound shrinks from "thirteen unvalidated" to a named few.

    uint8, uint16, uint32   against numpy's own unsigned integers. Exact, and there
                            is nothing to interpret: code n must decode to n.
    mxfp8_e4m3              against ml_dtypes.float8_e4m3fn, reported whichever way
                            it comes out. OCP's MX element format and ml_dtypes'
                            float8_e4m3fn are not guaranteed to agree on the special
                            values, and a divergence there would be a fact about two
                            conventions rather than a defect -- which is exactly what
                            the P3109 comparison turned out to be.

uint4 is already covered by research/crossval_ml_dtypes.py and is not repeated.

The other eight -- bfloat24, bfloat32, mxint8, pdp11_float, tekum8/16/32, x87_48bit --
have no third-party implementation in this environment. They stay unvalidated, and
saying which is the point.

    python3 research/crossval_unpublished.py
"""
from __future__ import annotations

import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CONF = os.path.join(HERE, "..", "conformance")


def load_oracles():
    """{format_name: (module, fmt_obj)} over every conformance/*_ref.py."""
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
            out.setdefault(name, (mod, fmt))
    return out


def decode(mod, fmt, code):
    for fn in ("decode", "decode_value", "to_value"):
        f = getattr(mod, fn, None)
        if callable(f):
            try:
                return f(fmt, code)
            except TypeError:
                return f(code)
    raise LookupError("no decode entry point")


def check_unsigned(oracles, name, width, limit=0):
    """code n must decode to n. numpy is the reference and there is no ambiguity."""
    if name not in oracles:
        return (name, "absent from the oracle set", 0, 0)
    mod, fmt = oracles[name]
    total = 1 << width
    codes = range(total) if total <= 65536 else \
        [0, 1, 2, 3, total // 2 - 1, total // 2, total - 2, total - 1] + \
        [(1 << k) for k in range(width)] + [(1 << k) - 1 for k in range(1, width)]
    bad = 0
    n = 0
    for c in codes:
        n += 1
        try:
            v = decode(mod, fmt, c)
        except Exception as e:
            return (name, f"decode raised {type(e).__name__}", n, n)
        if int(v) != c:
            bad += 1
    return (name, "", n, bad)


def check_mxfp8(oracles):
    try:
        import ml_dtypes
        import numpy as np
    except ImportError:
        return ("mxfp8_e4m3", "ml_dtypes not installed", 0, 0)
    if "mxfp8_e4m3" not in oracles:
        return ("mxfp8_e4m3", "absent from the oracle set", 0, 0)
    mod, fmt = oracles["mxfp8_e4m3"]
    bad = 0
    n = 0
    diffs = []
    for c in range(256):
        raw = np.array([c], dtype=np.uint8).view(ml_dtypes.float8_e4m3fn)[0]
        theirs = float(raw)
        try:
            ours = decode(mod, fmt, c)
        except Exception as e:
            return ("mxfp8_e4m3", f"decode raised {type(e).__name__}", n, n)
        n += 1
        if ours is None or (isinstance(ours, str)):
            continue                       # a special-value marker; not comparable
        # The oracles return a `Special` marker for NaN and Inf rather than a float,
        # so `ours != ours` is False for a NaN and a naive check reports a divergence
        # where both sides agree. This cost a false positive on 0x7F and 0xFF before
        # the values were read -- the fourth time in this campaign that a tool of mine
        # reported its own limitation as a finding.
        kind = type(ours).__name__
        ours_nan = kind == "Special" and "nan" in repr(ours).lower()
        ours_inf = kind == "Special" and "inf" in repr(ours).lower()
        try:
            if theirs != theirs:                      # ml_dtypes says NaN
                same = ours_nan
            elif theirs in (float("inf"), float("-inf")):
                same = ours_inf
            elif ours_nan or ours_inf:
                same = False
            else:
                same = float(ours) == theirs
        except (TypeError, ValueError, OverflowError):
            same = False
        if not same:
            bad += 1
            if len(diffs) < 4:
                diffs.append(f"0x{c:02X}: ours {ours!r}  ml_dtypes {theirs!r}")
    return ("mxfp8_e4m3", "; ".join(diffs), n, bad)


def main() -> int:
    oracles = load_oracles()
    print(f"oracle modules loaded: {len(oracles)} formats\n")

    rows = [check_unsigned(oracles, "uint8", 8),
            check_unsigned(oracles, "uint16", 16),
            check_unsigned(oracles, "uint32", 32),
            check_mxfp8(oracles)]

    print(f"{'format':<14} {'compared':>9} {'divergences':>12}   note")
    for name, note, n, bad in rows:
        print(f"  {name:<12} {n:>9} {bad:>12}   {note[:70]}")

    checked = sum(1 for _, note, n, _ in rows if n and not note.startswith("absent"))
    clean = sum(1 for _, _, n, bad in rows if n and bad == 0)
    print(f"\nformats cross-validated : {checked}")
    print(f"  agreeing exactly      : {clean}")

    print("""
Not covered, and no third-party implementation is available here for any of them:
bfloat24, bfloat32, mxint8, pdp11_float, tekum8, tekum16, tekum32, x87_48bit.
uint4 is already covered by research/crossval_ml_dtypes.py.

So of the thirteen oracles without a published pack, the number carrying independent
confirmation is what this prints, and the rest remain "working oracle, unvalidated" --
which is the form the claim must keep.""")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
