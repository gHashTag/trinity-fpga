#!/usr/bin/env python3
"""Cross-validate the Trinity golden oracles against ml_dtypes (Google/JAX).

arXiv:2606.09686 states that its conformance packs are "cross-validated against
ml_dtypes 0.5.4 (Google/JAX); any divergence is documented explicitly and
interpreted as a spec-permitted interpretation gap rather than hidden."

This script performs that cross-validation independently: for every format both
sides implement, it enumerates the codes and compares the decoded value produced
by `conformance/*_ref.py` with the one produced by ml_dtypes.

Comparison is on the binary64 value, with both sides normalised into the SAME key
space. NaN is compared by class (any NaN matches any NaN) because NaN payload is
not part of these format specifications, and infinity likewise — the oracles
return `Special` sentinels where ml_dtypes returns real IEEE values, and comparing
those representations directly manufactures divergences that do not exist.

Signed zero is deliberately NOT compared. The oracles decode to
`fractions.Fraction`, which cannot represent -0.0, so any -0.0/+0.0 disagreement
would describe the container rather than the format. Such codes are counted and
reported separately instead of being scored as divergences.

Run:  python3 research/crossval_ml_dtypes.py
Exit: 0 if every compared code agrees, 1 on any divergence, 2 if ml_dtypes absent.
"""
from __future__ import annotations
import importlib.util
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONF = os.path.join(REPO, "conformance")

# our oracle format id -> (ml_dtypes attribute, storage bit width)
MAPPING = [
    ("bfloat16",  "bfloat16",        16),
    ("fp8_e4m3",  "float8_e4m3fn",    8),
    ("fp8_e5m2",  "float8_e5m2",      8),
    ("fp4_e2m1",  "float4_e2m1fn",    4),
    ("fp6_e2m3",  "float6_e2m3fn",    6),
    ("fp6_e3m2",  "float6_e3m2fn",    6),
    ("int4",      "int4",             4),
    ("uint4",     "uint4",            4),
]


def load_oracles():
    out = {}
    for fn in sorted(os.listdir(CONF)):
        if not fn.endswith("_ref.py") or fn.startswith("_"):
            continue
        try:
            spec = importlib.util.spec_from_file_location("x_" + fn[:-3],
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


def norm(x):
    """Normalise BOTH sides to the same key space.

    Deliberately symmetric: the oracles return `Special` sentinels while
    ml_dtypes returns real IEEE values, and comparing those representations
    directly manufactures divergences that do not exist. Infinity and NaN are
    therefore reduced to one key each.

    Zero sign is NOT compared here. The oracles decode to `fractions.Fraction`,
    which cannot represent -0.0, so a signed-zero comparison against them says
    something about the container, not about the format. Signed zero is counted
    separately -- see ZERO_SIGN below.
    """
    kind = getattr(x, "kind", None)
    if kind is not None:                       # oracle Special sentinel
        if kind == "nan":
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
        return "zero"                          # sign handled separately
    return f


def zero_sign(x):
    """'+', '-' or None if the representation cannot carry a zero sign."""
    try:
        f = float(x)
    except Exception:
        return None
    if f != 0.0:
        return None
    from fractions import Fraction
    if isinstance(x, (Fraction, int)):
        return None                            # container cannot carry the sign
    import math
    return "-" if math.copysign(1.0, f) < 0 else "+"


def main() -> int:
    try:
        import ml_dtypes
        import numpy as np
    except ImportError as e:
        print(f"ml_dtypes / numpy not available: {e}")
        print("install with:  python3 -m pip install 'ml_dtypes==0.5.4' numpy")
        return 2

    version = getattr(ml_dtypes, "__version__", "unknown")
    print(f"ml_dtypes {version}")
    if version != "0.5.4":
        print(f"  NOTE: the paper cross-validates against 0.5.4; this is {version}. "
              f"Divergences below may reflect a version difference, not a defect.")
    print()

    oracles = load_oracles()
    total_cmp = total_div = total_zero_unknown = 0
    skipped = []

    for our_name, ml_name, width in MAPPING:
        if our_name not in oracles:
            skipped.append(f"{our_name} (no golden oracle)")
            continue
        ml_type = getattr(ml_dtypes, ml_name, None)
        if ml_type is None:
            skipped.append(f"{our_name} (ml_dtypes has no {ml_name})")
            continue

        mod, fmt = oracles[our_name]
        store = np.uint8 if width <= 8 else np.uint16
        codes = 1 << width
        divergences = []
        compared = 0
        zero_sign_unknown = 0

        for raw in range(codes):
            try:
                raw_ours = mod.decode(fmt, raw)
                ours = norm(raw_ours)
            except Exception as e:
                divergences.append((raw, f"oracle raised {type(e).__name__}", "-"))
                continue
            try:
                arr = np.array([raw], dtype=store).view(ml_type)
                theirs_val = np.float64(arr[0])
                theirs = norm(theirs_val)
            except Exception as e:
                divergences.append((raw, ours, f"ml_dtypes raised {type(e).__name__}"))
                continue
            compared += 1
            if ours == "zero" and theirs == "zero":
                if zero_sign(raw_ours) is None and zero_sign(theirs_val) is not None:
                    zero_sign_unknown += 1
                continue
            if ours != theirs:
                divergences.append((raw, ours, theirs))

        total_cmp += compared
        total_div += len(divergences)
        total_zero_unknown += zero_sign_unknown
        verdict = "AGREE" if not divergences else f"{len(divergences)} DIVERGENT"
        note = (f"  [{zero_sign_unknown} zero-sign not carried by oracle]"
                if zero_sign_unknown else "")
        print(f"{our_name:<10} vs ml_dtypes.{ml_name:<16} "
              f"codes={codes:<6} compared={compared:<6} {verdict}{note}")
        for raw, a, b in divergences[:5]:
            print(f"    raw=0x{raw:0{max(2, width // 4)}x}  ours={a!r}  ml_dtypes={b!r}")
        if len(divergences) > 5:
            print(f"    ... and {len(divergences) - 5} more")

    print()
    if skipped:
        print("skipped:")
        for s in skipped:
            print(f"  {s}")
    print(f"\ntotal codes compared: {total_cmp}   divergences: {total_div}")
    if total_zero_unknown:
        print(f"zero-sign codes where the oracle container cannot carry the sign: "
              f"{total_zero_unknown} (not counted as divergences)")
    return 0 if total_div == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
