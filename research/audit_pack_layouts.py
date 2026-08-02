#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Do the published packs' catalogue entries describe layouts that can exist?

Pass 147 built this invariant and applied it to two tables inside this repository,
where it found two rows describing impossible layouts. It was never applied to the 83
published packs, which carry the same `bits`/`e`/`m` fields. This applies it there.

    1 + e + m == bits

**The result is clean, and getting to clean took the work.** Run naively the invariant
reports 8 disagreements out of 65 usable entries. Every one of the 8 is a format where
the invariant does not apply, and each is explained by the pack's own `format_notes`:

    double_double   "two IEEE-754 binary64 limbs" -- TWO sign bits, so the constant is
                    2, not 1: 2 + 22 + 104 = 128.
    quad_double     four limbs: 4 + 44 + 208 = 256.
    gfternary       "2-bit discrete set {-phi, 0, +phi}" -- a code table with no sign
                    field at all.
    nf4             "4-bit code indexes a fixed 16-entry quantile table" -- no
                    sign/exponent/mantissa decomposition exists to check.
    posit8/16/32/64 "es=2 ... tapered precision" -- `e` holds the es PARAMETER, not an
                    exponent field width, and `m` is not a field width either.

Publishing those 8 as findings would have been eight false reports, of exactly the kind
this campaign has produced before by pointing a tool at something it does not model. So
they are declared here with the reason and the arithmetic that does apply, rather than
suppressed or waved through.

    python3 research/audit_pack_layouts.py [--self-check]
"""
from __future__ import annotations

import base64
import json
import subprocess
import sys

T27 = "gHashTag/t27"

# Formats the plain invariant does not model. Each carries the reason and, where a
# corrected form exists, the arithmetic that does hold.
EXCEPTIONS = {
    "double_double": ("two IEEE-754 binary64 limbs, so there are TWO sign bits",
                      lambda b, e, m: 2 + e + m == b),
    "quad_double":   ("four binary64 limbs, so there are FOUR sign bits",
                      lambda b, e, m: 4 + e + m == b),
    "gfternary":     ("a 2-bit discrete set {-phi, 0, +phi}; no sign field exists",
                      None),
    "nf4":           ("a 4-bit index into a 16-entry quantile table; no S/E/M "
                      "decomposition exists", None),
    "posit8":        ("`e` holds the es parameter, not a field width", None),
    "posit16":       ("`e` holds the es parameter, not a field width", None),
    "posit32":       ("`e` holds the es parameter, not a field width", None),
    "posit64":       ("`e` holds the es parameter, not a field width", None),
}


def pack_names() -> list[str]:
    r = subprocess.run(
        ["gh", "api", f"repos/{T27}/contents/conformance/vectors",
         "--jq", ".[].name"], capture_output=True, text=True, timeout=180)
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip() or "gh failed")
    return sorted(n[: -len("_conformance_v0.json")]
                  for n in r.stdout.split()
                  if n.endswith("_conformance_v0.json"))


def catalog(name: str):
    r = subprocess.run(
        ["gh", "api", f"repos/{T27}/contents/conformance/vectors/"
         f"{name}_conformance_v0.json", "--jq", ".content"],
        capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        return None
    try:
        return json.loads(base64.b64decode(r.stdout)).get("catalog") or {}
    except Exception:
        return None


def self_check() -> int:
    """The invariant must reject a layout that cannot exist and accept one that can,
    and each exception's corrected arithmetic must hold on its own entry."""
    bad = 0
    for label, b, e, m, expect in (("a 24-bit format as 1+9+14", 24, 9, 14, True),
                                   ("the pass-147 gf24 defect", 24, 7, 17, False),
                                   ("the pass-147 gf4 defect", 4, 2, 2, False)):
        got = (1 + e + m == b)
        ok = got == expect
        bad += not ok
        print(f"  {label:<28} 1+{e}+{m}=={b} -> {got}, expected {expect}  "
              f"{'ok' if ok else 'MISSED'}")
    for name, (why, rule) in EXCEPTIONS.items():
        if rule is None:
            continue
        vals = {"double_double": (128, 22, 104), "quad_double": (256, 44, 208)}[name]
        ok = rule(*vals)
        bad += not ok
        print(f"  {name:<28} corrected arithmetic holds -> {ok}  "
              f"{'ok' if ok else 'WRONG'}")
    print(f"\nself-check: {'PASS' if bad == 0 else f'FAIL ({bad})'}")
    return bad


def main() -> int:
    if "--self-check" in sys.argv:
        return 1 if self_check() else 0

    try:
        names = pack_names()
    except Exception as e:
        print(f"could not list the packs: {e}")
        print("Nothing is assumed when the catalogue cannot be read.")
        return 2

    holds, excepted, unusable, broken = 0, [], 0, []
    for name in names:
        c = catalog(name)
        if c is None:
            unusable += 1
            continue
        b, e, m = c.get("bits"), c.get("e"), c.get("m")
        if not all(isinstance(x, int) for x in (b, e, m)) or (e == 0 and m == 0):
            unusable += 1
            continue
        if 1 + e + m == b:
            holds += 1
            continue
        if name in EXCEPTIONS:
            why, rule = EXCEPTIONS[name]
            excepted.append((name, b, e, m, why, rule(b, e, m) if rule else None))
            continue
        broken.append((name, b, e, m))

    print(f"packs in the catalogue                    : {len(names)}")
    print(f"  no S/E/M layout to check                : {unusable}")
    print(f"  1 + e + m == bits                       : {holds}")
    print(f"  declared exceptions                     : {len(excepted)}")
    print(f"  LAYOUTS THAT CANNOT EXIST               : {len(broken)}\n")

    for name, b, e, m, why, corrected in excepted:
        state = "" if corrected is None else \
            ("  corrected arithmetic HOLDS" if corrected
             else "  CORRECTED ARITHMETIC FAILS TOO")
        print(f"  exception  {name:<14} bits={b} e={e} m={m}{state}")
        print(f"             {why}")

    for name, b, e, m in broken:
        print(f"  BROKEN     {name:<14} bits={b} e={e} m={m} -> 1+e+m={1 + e + m}")

    print("""
Run without the exception table this reports 8 findings and every one is false. They are
declared with their reason, and where a corrected form exists -- the multi-limb formats,
which have one sign bit per limb -- the corrected arithmetic is checked rather than
assumed. An exception that nobody re-derives is a suppression.""")
    return 1 if broken else 0


if __name__ == "__main__":
    raise SystemExit(main())
