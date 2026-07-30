"""Checker — audit an external decoder against a golden oracle.

The core question the SDK answers for an ML team:
  "Does MY fp8/mxfp8/nf4 decoder produce the same value as the independent
   Trinity golden reference, over a representative input sweep?"

`check_decoder` runs the user's `decode(raw)->value` over random raws (within the
format width) plus any SSOT vectors it can find, and reports the match rate with a
sample of mismatches. Comparison is on the *mathematical value* (golden is exact,
via `fractions.Fraction`); NaN/Inf/zero are compared by class so a correct decoder
is not penalised for NaN-payload differences.
"""
from __future__ import annotations
import json
import os
import random

from .registry import get_format, catalog, FormatEntry

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
VECTORS = os.path.join(REPO, "conformance", "vectors")


def _norm(value):
    """Normalise a decoded value to a comparison key.

    Finite numbers -> binary64 float (golden is exact; a correct decoder matches
    it, possibly via correct rounding). Specials (NaN/Inf/zero sentinels) ->
    a stable string so two NaNs compare equal regardless of payload.
    """
    # Specials in the refs carry a .kind or are non-numeric sentinels.
    kind = getattr(value, "kind", None)
    if kind is not None:
        return f"special:{kind}"
    try:
        f = float(value)
    except (TypeError, ValueError):
        return f"opaque:{value!r}"
    if f != f:  # NaN
        return "special:nan"
    if f == float("inf"):
        return "special:inf"
    if f == float("-inf"):
        return "special:-inf"
    return f  # finite -> binary64 key (sign/zero/0.0 vs -0.0 preserved by float)


def _vector_raws(name: str, limit: int = 4096):
    """Pull a handful of input raw codes from SSOT vector files if present.
    Schemas vary; we opportunistically grab any integer-looking `a`/`raw` field.
    """
    raws = []
    if not os.path.isdir(VECTORS):
        return raws
    for fn in os.listdir(VECTORS):
        if not (fn.startswith(name + "_") and fn.endswith(".json")):
            continue
        try:
            with open(os.path.join(VECTORS, fn)) as f:
                data = json.load(f)
        except Exception:
            continue
        for v in data.get("vectors", [])[:limit]:
            for k in ("a", "raw", "in", "x"):
                val = v.get(k) if isinstance(v, dict) else None
                if isinstance(val, str):
                    try:
                        raws.append(int(val, 0))
                    except ValueError:
                        pass
                elif isinstance(val, int):
                    raws.append(val)
                if raws:
                    break
        if len(raws) >= limit:
            break
    return raws[:limit]


def check_decoder(name: str, user_decode, n_random: int = 1000,
                  seed: int = 0, use_vectors: bool = True, show: int = 10):
    """Run `user_decode(raw)->value` against the golden for format `name`.

    Returns dict: {format, width, matched, total, rate, mismatches[:show]}.
    """
    entry: FormatEntry = get_format(name)
    width = entry.width or 16
    span = 1 << width
    rng = random.Random(seed)

    raws = []
    if use_vectors:
        raws.extend(_vector_raws(entry.name))
    # always include the named SSOT specials/corners if decode handles them
    if n_random > 0:
        for _ in range(n_random):
            raws.append(rng.randrange(span))
    # corners
    raws.extend([0, span - 1, 1 << (width - 1)] if width < 62 else [0, span - 1])
    # de-dup, keep order
    seen = set()
    ordered = []
    for r in raws:
        if r not in seen and 0 <= r < span:
            seen.add(r)
            ordered.append(r)

    matched = 0
    mism = []
    for raw in ordered:
        try:
            g = _norm(entry.decode(raw))
        except Exception as e:
            g = f"golden_error:{type(e).__name__}"
        try:
            u = _norm(user_decode(raw))
        except Exception as e:
            u = f"user_error:{type(e).__name__}"
        ok = (g == u) or (isinstance(g, str) and g.startswith("special:nan")
                          and isinstance(u, str) and u.startswith("special:nan"))
        if ok:
            matched += 1
        elif len(mism) < show:
            mism.append({"raw": raw, "golden": _short(g), "user": _short(u)})
    total = len(ordered)
    return {
        "format": entry.name,
        "family": entry.family,
        "width": width,
        "matched": matched,
        "total": total,
        "rate": (matched / total) if total else 0.0,
        "mismatches": mism,
    }


def _short(v):
    s = repr(v)
    return s if len(s) <= 24 else s[:21] + "..."


def audit_report(verbose: bool = False):
    """One-command status of the whole catalog: family coverage + per-format
    golden self-load. (Value-level audit needs a user decoder; see check_decoder.)
    """
    cat = catalog()
    fams: dict[str, list[str]] = {}
    load_errors = []
    for name, e in cat.items():
        fams.setdefault(e.family, []).append(name)
        # sanity: golden decode of 0 should not crash
        try:
            e.decode(0)
        except Exception as ex:
            load_errors.append((name, type(ex).__name__, str(ex)[:60]))
    lines = [f"Trinity conformance catalog: {len(cat)} formats across "
             f"{len(fams)} families."]
    for fam in sorted(fams, key=lambda f: -len(fams[f])):
        lines.append(f"  {fam:<12} {len(fams[fam]):>3}  {', '.join(fams[fam][:8])}"
                     + (" ..." if len(fams[fam]) > 8 else ""))
    if load_errors:
        lines.append(f"  [warn] {len(load_errors)} format(s) failed golden decode(0): "
                     + ", ".join(n for n, _, _ in load_errors[:8]))
    if verbose:
        for fam in sorted(fams):
            lines.append(f"  {fam}: {', '.join(fams[fam])}")
    return "\n".join(lines)
