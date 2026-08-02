#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Registers narrower than what is put in them or compared against them.

Pass 145 found `reg led_mode_reg;` in trinity_v3_jtaguart.v -- one bit -- being
assigned `uart_rx_data[2:0]` and compared against `3'b000` .. `3'b011`. Two arms of
that ladder were unreachable: a single bit can only hold 0 or 1, so the Medium and
Fast blink modes were dead code. In the same sweep, vsa_10k_top.v declared
`reg signed a_val, b_val;` -- also one bit -- and assigned them 8-bit constants, which
collapsed +1 and -1 onto the same stored value.

Neither is reported by anything. Verilog widens both sides of a comparison silently and
truncates an oversized assignment silently; both are legal. Yosys is quiet, and the
`check` pass is quiet. Both were found by reading, which does not scale to 3,591 files.

This looks for the class mechanically. It reports two shapes:

  COMPARE   sig == N'b...   where the constant does not fit sig's declared width.
            Verilog truncates the literal at parse time, so the comparison silently
            tests a different value -- `led_counter == 24'd25000000` on a 24-bit
            register compares against 8,222,784. The code keeps working, wrongly.
  ASSIGN    sig <= expr[hi:lo]   where hi-lo+1 exceeds sig's width, so the high bits
            are dropped.

Only signals whose declared width is unambiguous in the same file are considered, and
only constants whose value actually exceeds the width are reported. A comparison like
`one_bit == 3'b001` is legal, reachable and correct, so it is not a finding -- the
defect is a constant that cannot fit, not a constant written wide.

    python3 research/audit_narrow_register.py [--root DIR] [--show N]
"""
from __future__ import annotations

import argparse
import os
import re

DECL = re.compile(
    r"\b(reg|wire|logic)\s+(?:signed\s+)?(?:\[\s*(\d+)\s*:\s*(\d+)\s*\]\s*)?"
    r"([A-Za-z_]\w*(?:\s*,\s*[A-Za-z_]\w*)*)\s*(?:=[^;]*)?;")

# `sig == 3'b010`, `sig != 8'd200`, either order.
CMP = re.compile(
    r"([A-Za-z_]\w*)\s*([=!]=)\s*(\d+)'([bdho])([0-9a-fA-FxXzZ_]+)")

# `sig <= other[7:0];` or `sig = other[7:0];`
ASSIGN_SLICE = re.compile(
    r"([A-Za-z_]\w*)\s*<?=\s*[A-Za-z_]\w*\s*\[\s*(\d+)\s*:\s*(\d+)\s*\]\s*;")

BASE = {"b": 2, "d": 10, "o": 8, "h": 16}

# Findings read and judged benign, so the gate can fail on anything new. Each entry
# needs the reason, not just the location -- an allowlist without one is a silence.
ACCEPTED = {
    ("fpga/vivado/gf6_clean_ax7203.v", "add_b"):
        "op_b[7:0] truncated to 6 bits keeps the low six, which is what this file's "
        "own header asks for ('low 6 bits of 16-bit protocol word'). The line above "
        "writes op_a[5:0] for the same thing; this is an inconsistency, not a fault.",
    ("fpga/vivado/gf6_mul_ax7203.v", "add_b"):
        "same as gf6_clean_ax7203.v.",
}


def widths(text: str) -> dict[str, int]:
    """Declared width of every signal we can resolve unambiguously in this file.

    A name declared twice with different widths is dropped rather than guessed at --
    the two could be in different modules, and this tool does not track scope.
    """
    seen: dict[str, int] = {}
    clash: set[str] = set()
    for m in DECL.finditer(text):
        hi, lo, names = m.group(2), m.group(3), m.group(4)
        w = (abs(int(hi) - int(lo)) + 1) if hi is not None else 1
        for name in (n.strip() for n in names.split(",")):
            if not name:
                continue
            if name in seen and seen[name] != w:
                clash.add(name)
            seen[name] = w
    for name in clash:
        seen.pop(name, None)
    return seen


def const_value(base: str, digits: str):
    """The constant's value, or None if it carries x/z and has no single value."""
    d = digits.replace("_", "")
    if not d or any(c in "xXzZ" for c in d):
        return None
    try:
        return int(d, BASE[base])
    except ValueError:
        return None


def scan(path: str):
    text = open(path, encoding="utf-8", errors="replace").read()
    w = widths(text)
    out = []

    for m in CMP.finditer(text):
        sig, op, declared_lit, base, digits = m.groups()
        if sig not in w:
            continue
        val = const_value(base, digits)
        if val is None:
            continue
        # The defect is a constant that cannot fit, not one merely written wide.
        if val < (1 << w[sig]):
            continue
        line = text[:m.start()].count("\n") + 1
        # NOT "always false". Verilog truncates a sized literal to its declared width
        # at parse time, so the comparison is against a DIFFERENT, reachable value --
        # which is worse, because the code goes on looking as though it works.
        actual = val & ((1 << w[sig]) - 1)
        out.append(("COMPARE", line, sig, w[sig],
                    f"{sig} {op} {declared_lit}'{base}{digits}  ->  the literal is "
                    f"truncated to {actual}, so this compares against {actual}, "
                    f"not {val}"))

    for m in ASSIGN_SLICE.finditer(text):
        sig, hi, lo = m.group(1), int(m.group(2)), int(m.group(3))
        if sig not in w:
            continue
        span = abs(hi - lo) + 1
        if span <= w[sig]:
            continue
        line = text[:m.start()].count("\n") + 1
        out.append(("ASSIGN", line, sig, w[sig],
                    f"{sig} is {w[sig]} bit(s), assigned a {span}-bit slice  ->  "
                    f"top {span - w[sig]} bit(s) dropped"))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default="fpga")
    ap.add_argument("--show", type=int, default=40)
    args = ap.parse_args()

    files = []
    for root, dirs, fs in os.walk(args.root):
        dirs[:] = [d for d in dirs if d not in (".git", "__pycache__")]
        files += [os.path.join(root, f) for f in fs if f.endswith(".v")]
    files.sort()

    findings, accepted = [], []
    for p in files:
        for f in scan(p):
            (accepted if (p, f[2]) in ACCEPTED else findings).append((p,) + f)

    print(f"verilog files scanned              : {len(files)}")
    print(f"  registers narrower than their use: {len(findings)}")
    print(f"  read and accepted as benign      : {len(accepted)}\n")
    for p, kind, line, sig, w, _ in accepted:
        print(f"  accepted  {p}:{line}  {sig}")
        print(f"            {ACCEPTED[(p, sig)]}")
    if accepted:
        print()

    by_kind: dict[str, int] = {}
    for f in findings:
        by_kind[f[1]] = by_kind.get(f[1], 0) + 1
    for k, n in sorted(by_kind.items()):
        print(f"  {k:<8} {n}")

    if findings:
        print()
        for p, kind, line, sig, w, msg in findings[:args.show]:
            print(f"  {kind}  {p}:{line}")
            print(f"          {msg}")
        if len(findings) > args.show:
            print(f"\n  ... and {len(findings) - args.show} more")

    print("""
Both shapes are legal Verilog and neither is reported by yosys -- checked, not assumed:
trinity_v1_morse.v carried a 25-bit register compared against 1,500,000,000 and yosys
emitted zero warnings on it. That is why they survive.

Read every finding before acting on it. A COMPARE means the comparison silently tests a
different number than the one written. An ASSIGN means bits are dropped on the way in --
and that is NOT always a defect: `wire [5:0] add_b = op_b[7:0]` keeps the low six bits,
which is exactly what the file it lives in says it wants. Truncation that preserves the
intended low bits is an inconsistency, not a fault. This tool cannot tell the two apart,
and does not try to.""")
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
