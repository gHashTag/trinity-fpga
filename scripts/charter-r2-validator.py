#!/usr/bin/env python3
"""charter-r2-validator · S-174 · G-82

Enforces R2 of the TRI NET constitution: NO HW multiplier symbol `*`
in synthesizable Verilog/SystemVerilog (`.v`, `.sv`) outside of comments
and string literals.

Maps LANG→SI: R2 constitutional rule → repo-layer gate.
Falsification predicate (G-82): a hand-injected `*` in synthesizable RTL
must trigger exit-1.

Anchor: phi^2 + phi^-2 = 3 · DOI 10.5281/zenodo.19227877
"""
from __future__ import annotations
import argparse
import os
import re
import sys
from pathlib import Path

SYNTH_EXTS = {".v", ".sv"}
EXCLUDE_DIRS = {".git", "node_modules", "build", "target", "dist", "vendor",
                "third_party", "sim", "tb", "test", "tests"}

# Line-comment OR block-comment OR string literal — stripped before scan
COMMENT_RE = re.compile(r"//[^\n]*|/\*.*?\*/|\"(?:\\.|[^\"\\])*\"", re.DOTALL)
STAR_RE = re.compile(r"\*")


def strip_noise(src: str) -> str:
    return COMMENT_RE.sub("", src)


def scan_file(p: Path) -> list[tuple[int, str]]:
    try:
        src = p.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return []
    stripped = strip_noise(src)
    # Walk original lines but check against stripped equivalent
    bad: list[tuple[int, str]] = []
    # Compute per-line stripped versions
    for i, line in enumerate(src.splitlines(), 1):
        l_strip = COMMENT_RE.sub("", line)
        if "*" in l_strip:
            # Exclude pointer-style or attribute syntax false positives:
            # In synthesizable Verilog `*` only legitimately appears in
            # comments or `(* ... *)` attributes — strip those too.
            l_strip = re.sub(r"\(\*.*?\*\)", "", l_strip)
            if "*" in l_strip:
                bad.append((i, line.rstrip()))
    return bad


def walk(root: Path) -> list[Path]:
    out: list[Path] = []
    for dp, dns, fns in os.walk(root):
        dns[:] = [d for d in dns if d not in EXCLUDE_DIRS and not d.startswith(".")]
        for fn in fns:
            p = Path(dp) / fn
            if p.suffix.lower() in SYNTH_EXTS:
                out.append(p)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="*", default=["."])
    ap.add_argument("--manifest", default=None,
                    help="Optional JSON manifest of explicit file paths")
    args = ap.parse_args()

    files: list[Path] = []
    for raw in args.paths:
        p = Path(raw)
        if p.is_dir():
            files.extend(walk(p))
        elif p.is_file() and p.suffix.lower() in SYNTH_EXTS:
            files.append(p)

    violations: list[tuple[Path, int, str]] = []
    for f in files:
        for ln, txt in scan_file(f):
            violations.append((f, ln, txt))

    print(f"[charter-r2-validator] scanned {len(files)} synthesizable files")
    if violations:
        print("::error::R2 violation — `*` found in synthesizable RTL:")
        for f, ln, txt in violations:
            print(f"  {f}:{ln}: {txt}")
        print(f"\nTotal R2 violations: {len(violations)}")
        print("Anchor: phi^2 + phi^-2 = 3 · charter R2 NOT-PASS")
        return 1
    print("R2 PASS · charter:r2-pass · phi^2+phi^-2=3")
    return 0


if __name__ == "__main__":
    sys.exit(main())
