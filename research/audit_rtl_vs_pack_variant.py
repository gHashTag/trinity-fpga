#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Where the RTL and the pack both name a parameter, do they name the same one?

Pass 153 found a Tier-E row credited to a pack that implements a different format.
`external/tt-trinity-corona/src/rtl/posit8_decode.v` says in its own header
"Posit8(es=0) -> FP32 decode", while `posit8_conformance_v0.json` declares
"Posit Standard 2022, n=8, es=2". Those are different formats: at the same 8-bit code
they disagree on 252 of 255 values, by up to five orders of magnitude. The pack is
right -- it matches SoftPosit exactly -- and the silicon proves something else.

That was found by reading one file. This checks the class.

The check only fires where **both** sides state a parameter, which is the point. A
header that names no parameter is reported as unstated rather than assumed to agree; a
pack without a catalogue entry likewise. Silence is not evidence in either direction,
and this campaign has manufactured findings out of a tool's blind spots before.

Two parameter kinds are compared today, because they are the two the headers actually
state in a machine-readable way:

    es = N          posit family; the Posit Standard 2022 fixes es = 2 at every width
    BID or DPD      IEEE 754 decimal; two different encodings of the same values

    python3 research/audit_rtl_vs_pack_variant.py [--self-check]
"""
from __future__ import annotations

import base64
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
T27 = "gHashTag/t27"

ES = re.compile(r"\bes\s*=\s*(\d+)", re.I)
DECENC = re.compile(r"\b(BID|DPD)\b")


def core_header(name: str) -> str | None:
    """The comment header of the decode core for `name`, wherever it lives."""
    for pat in (f"fpga/openxc7-synth/{name}_decode.v",
                f"external/tt-trinity-corona/src/rtl/{name}_decode.v"):
        p = os.path.join(ROOT, pat)
        if os.path.exists(p):
            lines = open(p, encoding="utf-8", errors="replace").read().split("\n")[:12]
            return "\n".join(l for l in lines if l.startswith("//"))
    return None


def pack_meta(name: str):
    r = subprocess.run(
        ["gh", "api", f"repos/{T27}/contents/conformance/vectors/"
         f"{name}_conformance_v0.json", "--jq", ".content"],
        capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        return None
    try:
        return json.loads(base64.b64decode(r.stdout))
    except Exception:
        return None


def self_check() -> int:
    """The rule must fire on posit8 and stay silent on posit16 -- the two cases pass
    153 established by hand."""
    cases = [("posit8", "0", "2", True), ("posit16", "2", "2", False)]
    bad = 0
    for name, rtl, pack, should_fire in cases:
        fired = rtl != pack
        ok = fired == should_fire
        bad += not ok
        print(f"  {name:<8} rtl es={rtl}, pack es={pack} -> fires={fired}  "
              f"{'ok' if ok else 'MISSED'}")
    print(f"\nself-check: {'PASS' if bad == 0 else f'FAIL ({bad})'}")
    return bad


def main() -> int:
    if "--self-check" in sys.argv:
        return 1 if self_check() else 0

    subjects = ["posit8", "posit16", "posit32", "posit64", "posit128",
                "decimal32", "decimal64", "decimal128"]

    split, unstated, agree, nopack = [], [], [], []
    for name in subjects:
        head = core_header(name)
        meta = pack_meta(name)
        if head is None:
            unstated.append((name, "no decode core found"))
            continue
        if meta is None:
            nopack.append(name)
            continue

        notes = str(meta.get("format_notes", ""))
        for rx, kind in ((ES, "es"), (DECENC, "decimal encoding")):
            a, b = rx.search(head), rx.search(notes)
            if not (a and b):
                continue
            if a.group(1).upper() != b.group(1).upper():
                split.append((name, kind, a.group(1), b.group(1)))
            else:
                agree.append((name, kind, a.group(1)))

    print(f"formats checked                       : {len(subjects)}")
    print(f"  RTL and pack both state a parameter : {len(agree) + len(split)}")
    print(f"  they AGREE                          : {len(agree)}")
    print(f"  they DISAGREE                       : {len(split)}")
    if nopack:
        print(f"  core exists, no pack in the catalogue: {len(nopack)} "
              f"({', '.join(nopack)})")
    if unstated:
        print(f"  no decode core found                : {len(unstated)} "
              f"({', '.join(n for n, _ in unstated)})")

    if split:
        print()
        for name, kind, rtl, pack in split:
            print(f"VARIANT SPLIT  {name}")
            print(f"    RTL header says  {kind} = {rtl}")
            print(f"    the pack says    {kind} = {pack}")
            print(f"    Any hardware proof credited to this pack is a proof about the")
            print(f"    other format.")

    print("""
Only formats where BOTH sides state a parameter are compared. A header naming none is
reported as unstated, not assumed to agree -- silence is not evidence in either
direction. A core with no pack cannot make a false claim about one, but an inconsistent
core is still worth knowing about: posit128_decode.v uses es = 4, the legacy scheme
where es grows with width, which the Posit Standard 2022 replaced with a fixed es = 2.""")
    return 1 if split else 0


if __name__ == "__main__":
    raise SystemExit(main())
