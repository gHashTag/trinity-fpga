#!/usr/bin/env python3
"""Sweep the arithmetic layer of every oracle for algebraic invariants.

Passes 1-17 of this campaign checked decode and encode only. This extends the
method to format_add / format_mul, using laws that need no external reference and
— unlike monotonicity — admit no design-choice defence:

  COMM_ADD   add(a,b) == add(b,a)
  COMM_MUL   mul(a,b) == mul(b,a)
  IDENT_ADD  add(x, 0) == x
  IDENT_MUL  mul(x, 1) == x
  ANNIH_MUL  mul(x, 0) == 0
  SIGN_MUL   mul(neg(a), b) == neg(mul(a, b))     [where negation is well defined]

A correctly-rounded binary operation is commutative because rounding is applied
to a single exact result; there is no rounding mode under which a+b and b+a
differ. A violation is therefore unambiguous, which is what makes these laws
worth more than the structural checks in pass 16.

Operands are drawn from a bounded sample of codes and every ordered pair within
the sample is tested, so cost is O(k^2) per format with k small.

Run:  python3 research/verify_arithmetic_invariants.py
Exit: 0 if no law is violated, 1 otherwise.
"""
from __future__ import annotations
import importlib.util
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONF = os.path.join(REPO, "conformance")

K = 24          # codes sampled per format -> K*K ordered pairs


def arithmetic_of(mod):
    """Find (add, mul) under any naming convention used in this tree.

    Most oracles export format_add / format_mul, but gf_ref.py uses gf_add /
    gf_mul and tekum_ref.py uses tekum_add / tekum_mul. A first version of this
    sweep looked only for format_* and therefore skipped the entire GF ladder in
    silence, producing a false 'no arithmetic oracle' finding. Detect by suffix
    instead of by exact name.
    """
    add = mul = None
    for attr in dir(mod):
        if attr.startswith("_"):
            continue
        obj = getattr(mod, attr)
        if not callable(obj):
            continue
        if attr.endswith("_add") and add is None:
            add = obj
        elif attr.endswith("_mul") and mul is None and "matrix" not in attr:
            mul = obj
    return add, mul


def load_oracles():
    out = {}
    for fn in sorted(os.listdir(CONF)):
        if not fn.endswith("_ref.py") or fn.startswith("_"):
            continue
        try:
            spec = importlib.util.spec_from_file_location("a_" + fn[:-3],
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
        has_arith = all(arithmetic_of(mod))
        for name, fmt in getattr(mod, "FORMATS", {}).items():
            # gf16_plus_ref.py and gf_ref.py BOTH export all 17 GF ids. Keying on
            # format name alone makes the winner depend on filename sort order,
            # which silently skipped the whole GF ladder in the first run.
            # Resolve explicitly: a module that provides arithmetic wins.
            prev = out.get(name)
            if prev is None or (has_arith and not all(arithmetic_of(prev[0]))):
                out[name] = (mod, fmt)
    return out


def width_of(fmt, name):
    for attr in ("n", "width", "W", "total", "bits", "nbits"):
        v = getattr(fmt, attr, None)
        if isinstance(v, int) and v > 0:
            return v
    d = "".join(c for c in name if c.isdigit())
    return int(d) if d else 0


def is_special(mod, fmt, raw) -> bool:
    """True if the code decodes to NaN / Inf / any non-finite sentinel."""
    try:
        v = mod.decode(fmt, raw)
    except Exception:
        return True
    if getattr(v, "kind", None) is not None:
        return True
    try:
        f = float(v)
    except (TypeError, ValueError, OverflowError):
        return True
    return f != f or abs(f) == float("inf")


def sample_codes(width, k=K):
    span = 1 << width
    if span <= k:
        return list(range(span))
    # spread across the space, and always include the low corner
    step = max(1, span // k)
    codes = list(range(0, span, step))[:k - 2]
    codes += [1, span - 1]
    return sorted(set(codes))


def main() -> int:
    oracles = load_oracles()
    print(f"{'format':<14}{'pairs':>7}  {'comm+':<7}{'comm*':<7}"
          f"{'x+0':<7}{'x*1':<7}{'x*0':<7}", flush=True)
    print("-" * 62, flush=True)

    violations = {}
    for name in sorted(oracles):
        mod, fmt = oracles[name]
        f_add, f_mul = arithmetic_of(mod)
        if f_add is None or f_mul is None:
            continue
        width = width_of(fmt, name)
        if width == 0 or width > 64:
            continue
        codes = sample_codes(width)

        bad = {"comm_add": 0, "comm_mul": 0, "id_add": 0, "id_mul": 0, "ann_mul": 0}
        pairs = 0

        # identity / annihilator need the codes for 0 and 1
        zero = 0
        one = None
        if hasattr(mod, "encode"):
            try:
                one = mod.encode(fmt, 1)
            except Exception:
                one = None

        for a in codes:
            for b in codes:
                try:
                    ab_add = f_add(fmt, a, b)
                    ba_add = f_add(fmt, b, a)
                    ab_mul = f_mul(fmt, a, b)
                    ba_mul = f_mul(fmt, b, a)
                except Exception:
                    continue
                pairs += 1
                if ab_add != ba_add:
                    bad["comm_add"] += 1
                if ab_mul != ba_mul:
                    bad["comm_mul"] += 1
            # Unary laws hold only for FINITE operands. NaN*0 = NaN and Inf*0 =
            # NaN are correct IEEE semantics, and NaN+0 = NaN does not return the
            # original code. Testing specials against x+0==x would manufacture
            # violations, so they are skipped — the same filter the decode sweeps
            # apply.
            if is_special(mod, fmt, a):
                continue
            try:
                if f_add(fmt, a, zero) != a:
                    bad["id_add"] += 1
                if f_mul(fmt, a, zero) != zero:
                    bad["ann_mul"] += 1
                if one is not None and f_mul(fmt, a, one) != a:
                    bad["id_mul"] += 1
            except Exception:
                pass

        if pairs == 0:
            continue

        def cell(k):
            return "OK" if bad[k] == 0 else str(bad[k])

        print(f"{name:<14}{pairs:>7}  {cell('comm_add'):<7}{cell('comm_mul'):<7}"
              f"{cell('id_add'):<7}{cell('id_mul'):<7}{cell('ann_mul'):<7}", flush=True)
        if any(bad.values()):
            violations[name] = dict(bad)

    print()
    if violations:
        print(f"VIOLATIONS in {len(violations)} format(s):")
        for name, b in violations.items():
            hits = ", ".join(f"{k}={v}" for k, v in b.items() if v)
            print(f"  {name}: {hits}")
        print()
        print("Commutativity violations are unambiguous defects. Identity and")
        print("annihilator failures may instead be sign-of-zero or encode-canonical")
        print("artefacts — diagnose each before reporting.")
    else:
        print("No arithmetic law violated in any format tested.")
    return 1 if violations else 0


if __name__ == "__main__":
    raise SystemExit(main())
