"""FP8 audit — expose where a *naive* FP8 decoder disagrees with the golden.

FP8 is not one format: the two common encodings differ in exactly the places a
naive, IEEE-binary16-style decoder gets wrong.

  * fp8_e5m2  — IEEE-like: exp==max & mant==0 -> Inf, else NaN. A naive IEEE
    decoder is usually correct here.
  * fp8_e4m3  — OCP/"E4M3FN": there is NO Inf, and NaN happens ONLY at
    exp==max & mant==max (0x7f / 0xff). Every other exp==max pattern is a
    FINITE normal (up to +-448). A naive decoder that applies the IEEE rule
    "exp all-ones => Inf/NaN" silently turns the 14 largest finite magnitudes
    into Inf/NaN. This is the classic bug that corrupts fp8 inference at the
    top of the range.

This module ships a deliberately naive IEEE-rule decoder and audits it against
the Trinity golden, so a user can see the exact raws (and the values) a naive
implementation would get wrong before trusting their own kernel.
"""
from __future__ import annotations
from fractions import Fraction

from .registry import get_format, FormatEntry
from .checker import check_decoder, _norm


def naive_ieee_fp8(name: str):
    """Return a naive `decode(raw)->float` for an fp8 format that applies the
    textbook IEEE rule (exp all-ones => Inf/NaN). Correct for e5m2, WRONG for
    e4m3 at the top of the finite range. Returned as a plain callable so it can
    also be fed to `check_decoder`.
    """
    entry: FormatEntry = get_format(name)
    fmt = entry.fmt
    exp_bits = fmt.exp_bits
    mant_bits = fmt.mant_bits
    bias = fmt.bias
    exp_max = (1 << exp_bits) - 1
    mant_mask = (1 << mant_bits) - 1
    sign_shift = exp_bits + mant_bits
    mask = (1 << (1 + exp_bits + mant_bits)) - 1

    def decode(raw: int):
        raw &= mask
        sign = (raw >> sign_shift) & 1
        exp = (raw >> mant_bits) & exp_max
        mant = raw & mant_mask
        # NAIVE IEEE RULE — applied unconditionally (this is the bug for e4m3)
        if exp == exp_max:
            if mant == 0:
                return float("-inf") if sign else float("inf")
            return float("nan")
        if exp == 0:
            if mant == 0:
                return -0.0 if sign else 0.0
            val = (mant / (1 << mant_bits)) * 2.0 ** (1 - bias)
        else:
            val = (1 + mant / (1 << mant_bits)) * 2.0 ** (exp - bias)
        return -val if sign else val

    return decode


def audit_fp8(name: str = "fp8_e4m3", show: int = 12):
    """Audit the built-in naive IEEE decoder against the golden for `name`.

    Sweeps the full 256-code space (fp8 is 8-bit) and returns the match rate
    plus the specific raws where the naive decoder diverges, annotated with what
    the golden says vs what the naive decoder produced.
    """
    entry: FormatEntry = get_format(name)
    width = entry.width or 8
    naive = naive_ieee_fp8(name)

    diverge = []
    matched = 0
    for raw in range(1 << width):
        g = entry.decode(raw)
        u = naive(raw)
        ng, nu = _norm(g), _norm(u)
        ok = (ng == nu) or (isinstance(ng, str) and ng.startswith("special:nan")
                            and isinstance(nu, str) and nu.startswith("special:nan"))
        if ok:
            matched += 1
        else:
            diverge.append({
                "raw": raw,
                "golden": _fmtval(g),
                "naive": _fmtval(u),
            })
    total = 1 << width
    return {
        "format": entry.name,
        "width": width,
        "matched": matched,
        "total": total,
        "rate": matched / total,
        "diverge_count": len(diverge),
        "diverge": diverge[:show],
        "note": ("e4m3 has NO Inf and NaN only at exp=max&mant=max; the naive "
                 "IEEE rule mis-decodes the top finite range."
                 if entry.name.endswith("e4m3") else
                 "e5m2 is IEEE-like; a naive IEEE decoder should match."),
    }


def _fmtval(v):
    kind = getattr(v, "kind", None)
    if kind is not None:
        sign = getattr(v, "sign", 0)
        return f"{'-' if sign else ''}{kind}"
    try:
        return repr(float(v))
    except (TypeError, ValueError):
        return repr(v)
