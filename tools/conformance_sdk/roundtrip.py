"""Round-trip auditing — encode/decode consistency against a golden oracle.

Two independent properties a correct codec must satisfy:

1. ENCODE-STABILITY (raw -> value -> raw):
   For every bit pattern `raw`, `encode(decode(raw))` must return a raw that
   decodes to the *same value* as the original. It need not be the identical
   bit pattern (NaN payloads, -0 vs +0, and redundant encodings are allowed to
   differ), so we compare on the decoded value, not on the raw bits. This is the
   real "round-trip" property: no representable value is lost by the codec.

2. DECODE-PROJECTION (value -> raw -> value):
   For an arbitrary real input, `decode(encode(x))` must be the nearest
   representable value to `x` (idempotent thereafter). We check idempotence:
   re-encoding the projected value reproduces the same raw.

`encode` is optional per ref; formats without it are reported as skipped.
Comparison uses the same value-normalisation as the decoder checker (golden is
exact via `fractions.Fraction`; specials compared by class).
"""
from __future__ import annotations
import random

from .registry import get_format, FormatEntry
from .checker import _norm, _short


def check_roundtrip(name: str, n_random: int = 4096, seed: int = 0,
                    exhaustive_max_width: int = 16, show: int = 10):
    """Audit encode/decode round-trip for one format.

    For widths <= `exhaustive_max_width` every bit pattern is swept; otherwise a
    random sample of `n_random` raws (plus corners) is used.

    Returns dict with per-property match counts and a sample of failures.
    """
    entry: FormatEntry = get_format(name)
    if not hasattr(entry.ref, "encode"):
        return {"format": entry.name, "family": entry.family, "width": entry.width,
                "skipped": True, "reason": "ref has no encode()"}

    width = entry.width or 16
    span = 1 << width

    if width <= exhaustive_max_width:
        raws = range(span)
        mode = f"exhaustive({span})"
    else:
        rng = random.Random(seed)
        sample = {rng.randrange(span) for _ in range(n_random)}
        sample.update({0, span - 1, 1 << (width - 1)})
        raws = sorted(sample)
        mode = f"random({len(raws)})"

    stable_ok = stable_total = 0
    idem_ok = idem_total = 0
    fails = []

    for raw in raws:
        stable_total += 1
        try:
            v0 = entry.decode(raw)
            raw2 = entry.encode(v0)
            v1 = entry.decode(raw2)
            n0, n1 = _norm(v0), _norm(v1)
            ok = (n0 == n1) or (isinstance(n0, str) and n0.startswith("special:nan")
                                and isinstance(n1, str) and n1.startswith("special:nan"))
        except Exception as e:
            ok = False
            n0 = f"err:{type(e).__name__}"
            raw2 = None
        if ok:
            stable_ok += 1
        elif len(fails) < show:
            fails.append({"prop": "encode-stable", "raw": raw,
                          "v0": _short(_norm_or_str(entry, raw, "decode")),
                          "raw2": ("0x%x" % raw2) if raw2 is not None else "-"})

        # decode-projection idempotence: encode(v0) already computed -> re-encode v1
        idem_total += 1
        try:
            raw3 = entry.encode(v1) if raw2 is not None else None
            idem = (raw3 == raw2)
        except Exception:
            idem = False
        if idem:
            idem_ok += 1
        elif len([f for f in fails if f["prop"] == "idempotent"]) < show:
            fails.append({"prop": "idempotent", "raw": raw,
                          "raw2": ("0x%x" % raw2) if raw2 is not None else "-",
                          "raw3": ("0x%x" % raw3) if raw2 is not None and raw3 is not None else "-"})

    return {
        "format": entry.name, "family": entry.family, "width": width,
        "mode": mode, "skipped": False,
        "stable_ok": stable_ok, "stable_total": stable_total,
        "stable_rate": stable_ok / stable_total if stable_total else 0.0,
        "idem_ok": idem_ok, "idem_total": idem_total,
        "idem_rate": idem_ok / idem_total if idem_total else 0.0,
        "fails": fails[:show],
    }


def _norm_or_str(entry, raw, _which):
    try:
        return entry.decode(raw)
    except Exception as e:
        return f"err:{type(e).__name__}"


def encode_value(name: str, value_str: str):
    """Encode a single human value into this format and show the round-trip.

    `value_str` may be a decimal ("0.375"), a fraction ("3/8"), or one of the
    special tokens nan / inf / -inf. Returns dict with raw (hex/bin) and the
    value it decodes back to (to expose rounding).
    """
    from fractions import Fraction
    entry: FormatEntry = get_format(name)
    if not hasattr(entry.ref, "encode"):
        raise SystemExit(f"{entry.family}_ref has no encode(); cannot encode {name}")

    tok = value_str.strip().lower()
    # try to build a Special the ref understands
    val = None
    if tok in ("nan", "inf", "+inf", "-inf"):
        Special = _find_special(entry.ref)
        if Special is None:
            raise SystemExit(f"{entry.family}_ref exposes no Special type for {tok!r}")
        if tok == "nan":
            val = Special("nan")
        else:
            val = Special("inf", 1 if tok.startswith("-") else 0)
    else:
        try:
            val = Fraction(value_str) if "/" in value_str else Fraction(str(float(value_str)))
        except (ValueError, ZeroDivisionError):
            raise SystemExit(f"cannot parse value {value_str!r}")

    raw = entry.encode(val)
    back = entry.decode(raw)
    width = entry.width or 16
    return {
        "format": entry.name, "width": width,
        "input": value_str,
        "raw": raw, "raw_hex": "0x%x" % raw, "raw_bin": format(raw, "0%db" % width),
        "decodes_to": _pretty(back),
        "exact": _norm(val) == _norm(back) if not isinstance(val, str) else None,
    }


def _find_special(ref):
    for attr in ("Special", "FPSpecial", "Sentinel"):
        t = getattr(ref, attr, None)
        if t is not None:
            return t
    return None


def _pretty(v):
    kind = getattr(v, "kind", None)
    if kind is not None:
        sign = getattr(v, "sign", 0)
        return f"{'-' if sign else ''}{kind}"
    try:
        f = float(v)
        return repr(f)
    except (TypeError, ValueError):
        return repr(v)
