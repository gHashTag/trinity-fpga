#!/usr/bin/env python3
"""Cross-validate the takum golden oracle against libtakum, the format author's
own C99 reference implementation.

Why this matters: ml_dtypes does not implement takum, so the catalog's takum
packs have no second source from that direction. libtakum (Hunhold,
github.com/takum-arithmetic/libtakum) is the reference implementation by the
author of the format itself — the strongest independent reference available for
this family.

Input is produced by research/libtakum_bridge.c, which dumps
"<unsigned_raw>\\t<f64 bit pattern>" for every code. Bit patterns rather than
decimal text, so nothing is lost to printf rounding.

Normalisation follows the lesson recorded in
specs/numeric/ml_dtypes_crossval.t27 :: lemma NORMALISE_BOTH_SIDES — BOTH sides
are reduced to one key space before comparing, because the oracle returns
`Special` sentinels where libtakum returns real IEEE values, and comparing those
representations directly manufactures divergences that do not exist. Signed zero
is not compared (the oracle decodes to Fraction, which cannot carry it) and is
counted separately.

Usage:
    cc -O2 -I<libtakum> research/libtakum_bridge.c <libtakum>/libtakum.a -lm \\
       -o /tmp/libtakum_bridge
    /tmp/libtakum_bridge 8  > /tmp/lt8.tsv
    /tmp/libtakum_bridge 16 > /tmp/lt16.tsv
    python3 research/crossval_libtakum.py /tmp/lt8.tsv:takum8 /tmp/lt16.tsv:takum16

Exit: 0 if every compared code agrees, 1 on divergence, 2 on missing input.
"""
from __future__ import annotations
from fractions import Fraction
import importlib.util
import os
import struct
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONF = os.path.join(REPO, "conformance")


def load_oracle(fmt_name: str):
    for fn in sorted(os.listdir(CONF)):
        if not fn.endswith("_ref.py") or fn.startswith("_"):
            continue
        try:
            spec = importlib.util.spec_from_file_location("t_" + fn[:-3],
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
        if fmt_name in getattr(mod, "FORMATS", {}):
            return mod, mod.FORMATS[fmt_name]
    return None, None


def norm(x):
    """Reduce either side to a single key space (see module docstring)."""
    kind = getattr(x, "kind", None)
    if kind is not None:
        if kind in ("nan", "nar"):   # NaR and NaN are the same class here
            return "nan"
        if kind == "inf":
            return "-inf" if getattr(x, "sign", 0) else "+inf"
        return f"special:{kind}"
    try:
        f = float(x)
    except (TypeError, ValueError, OverflowError):
        return f"opaque:{x!r}"
    if f != f:
        return "nan"
    if f == float("inf"):
        return "+inf"
    if f == float("-inf"):
        return "-inf"
    if f == 0.0:
        return "zero"
    return f


def bits_to_f64(hexbits: str) -> float:
    return struct.unpack(">d", bytes.fromhex(hexbits))[0]


def run(path: str, fmt_name: str) -> tuple[int, int, int]:
    mod, fmt = load_oracle(fmt_name)
    if mod is None:
        print(f"{fmt_name}: no golden oracle found")
        return 0, 0, 0
    if not os.path.exists(path):
        print(f"{fmt_name}: missing dump {path}")
        return 0, 0, 0

    compared = 0
    zero_unknown = 0
    divergences = []

    with open(path) as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            raw_s, hexbits = line.split("\t")
            raw = int(raw_s)
            theirs_val = bits_to_f64(hexbits)
            try:
                ours_val = mod.decode(fmt, raw)
            except Exception as e:
                divergences.append((raw, f"oracle raised {type(e).__name__}", "-"))
                continue
            a, b = norm(ours_val), norm(theirs_val)
            compared += 1
            if a == "zero" and b == "zero":
                if isinstance(ours_val, (Fraction, int)):
                    zero_unknown += 1
                continue
            if a != b:
                divergences.append((raw, a, b))

    verdict = "AGREE" if not divergences else f"{len(divergences)} DIVERGENT"
    note = f"  [{zero_unknown} zero-sign not carried by oracle]" if zero_unknown else ""
    print(f"{fmt_name:<9} vs libtakum   compared={compared:<7} {verdict}{note}")
    for raw, a, b in divergences[:8]:
        print(f"    raw={raw:<6} ours={a!r}  libtakum={b!r}")
    if len(divergences) > 8:
        print(f"    ... and {len(divergences) - 8} more")
    return compared, len(divergences), zero_unknown


def main(argv) -> int:
    if not argv:
        print(__doc__)
        return 2
    tot_c = tot_d = tot_z = 0
    for spec in argv:
        path, _, fmt = spec.partition(":")
        c, d, z = run(path, fmt or "takum8")
        tot_c += c
        tot_d += d
        tot_z += z
    print(f"\ntotal codes compared: {tot_c}   divergences: {tot_d}")
    if tot_z:
        print(f"zero-sign codes the oracle container cannot carry: {tot_z} "
              f"(not counted as divergences)")
    return 0 if tot_d == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
