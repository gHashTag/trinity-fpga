#!/usr/bin/env python3
"""Fail when a vector pack's declared special values contradict its own oracle.

The narrower gate next door compares an oracle against a .t27 spec, but only two
of the fifty-five specs declare special-value constants, so it reaches almost
nothing. This one needs no spec: every pack names the oracle that produced it and
most carry a `specials` block, so the pack can be checked against its own stated
source.

The failure this catches is the one that already happened. gf16's packs shipped
expected values built with a quiet NaN of 0x7E01 and gradual underflow, while
the spec declares 0xFE01 and flush-to-zero; the note mentioned neither, and
three separate copies of a spec-conformant multiplier each read as 110 defects.
A header that disagrees with the values underneath it is worse than no header:
it is believed.

Exit 0 when every pack agrees with its oracle, 1 otherwise.
"""
import json
import sys
from importlib import import_module
from pathlib import Path

HERE = Path(__file__).resolve().parents[1] / "conformance"
KEYS = ("pos_zero", "neg_zero", "pos_inf", "neg_inf", "quiet_nan", "nar")


def load_oracle(name: str):
    """Import an oracle by file name, once."""
    mod = name[:-3] if name.endswith(".py") else name
    try:
        return import_module(mod)
    except Exception:
        return None


def fmt_for(oracle, key: str):
    """Oracles expose their formats as a FORMATS dict keyed by format name."""
    table = getattr(oracle, "FORMATS", None)
    if not isinstance(table, dict):
        return None
    return table.get(key)


def main() -> int:
    sys.path.insert(0, str(HERE))
    packs = sorted((HERE / "vectors").glob("*.json"))
    if not packs:
        print("  no packs found — the path is wrong")
        return 1

    checked = compared = bad = 0
    no_oracle: set[str] = set()
    no_format: set[str] = set()
    problems: list[str] = []

    for p in packs:
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except Exception as e:
            problems.append(f"{p.name}: unreadable ({e})")
            bad += 1
            continue
        specials = d.get("specials") or {}
        oname, fname = d.get("oracle"), d.get("format")
        if not specials or not oname or not fname:
            continue
        checked += 1
        oracle = load_oracle(oname)
        if oracle is None:
            no_oracle.add(oname)
            continue
        fmt = fmt_for(oracle, fname)
        if fmt is None:
            no_format.add(f"{oname}:{fname}")
            continue
        for k in KEYS:
            if k not in specials:
                continue
            got = getattr(fmt, k, None)
            if got is None:
                continue
            compared += 1
            want = int(specials[k], 16) if isinstance(specials[k], str) else specials[k]
            if int(got) != want:
                problems.append(
                    f"{p.name}: declares {k}=0x{want:X} but {oname} produces 0x{int(got):X}"
                )
                bad += 1

    for line in problems[:40]:
        print(f"  MISMATCH  {line}")
    if no_oracle:
        print(f"  note: {len(no_oracle)} oracle(s) would not import: {', '.join(sorted(no_oracle))}")
    if no_format:
        print(f"  note: {len(no_format)} pack(s) name a format their oracle does not expose")
    print(f"  packs with a specials block: {checked}; special values compared: {compared}")
    if compared == 0:
        print("  nothing was compared — treat that as a failure, not a pass")
        return 1
    print("  OK" if not bad else f"  {bad} disagreement(s) between a pack and its own oracle")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
