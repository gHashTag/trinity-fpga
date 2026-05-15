#!/usr/bin/env python3
"""ci/check_1to1_mapping.py — R19 QUANTUM-BRAIN-1TO1 enforcer.

Vector: enforcement of R19 (introduced TT v22).
Mapping: LANG -> SI.
Anchor: phi^2 + phi^-2 = 3 · DOI 10.5281/zenodo.19227877

Every RTL block (module … endmodule in .v / .sv / .vh / .svh) MUST carry a
`// MAPPING: {PHYS->SI|BIO->SI|LANG->SI}` tag inside the first 10 lines after
the `module` declaration. PRs are rejected if any module is missing or
ambiguous (more than one tag) or uses an unknown domain.

Usage:
  python3 ci/check_1to1_mapping.py [<path> [<path> ...]]
  (default: rtl/)

Exit codes:
  0 — all RTL modules tagged
  1 — at least one violation (prints offenders, then exits non-zero)
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Iterable

VALID_DOMAINS = {"PHYS->SI", "BIO->SI", "LANG->SI"}
RTL_EXTS = {".v", ".sv", ".vh", ".svh"}
MODULE_RE = re.compile(r"^\s*module\s+([A-Za-z_][A-Za-z0-9_]*)\b")
MAPPING_RE = re.compile(r"//\s*MAPPING:\s*([A-Z]+->SI)")


def iter_rtl(roots: Iterable[Path]) -> Iterable[Path]:
    for root in roots:
        if root.is_file() and root.suffix in RTL_EXTS:
            yield root
            continue
        if root.is_dir():
            for p in sorted(root.rglob("*")):
                if p.is_file() and p.suffix in RTL_EXTS:
                    yield p


def check_file(path: Path) -> list[str]:
    """Return list of violations in this file."""
    violations: list[str] = []
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError as e:
        return [f"{path}: cannot read ({e})"]

    i = 0
    while i < len(lines):
        m = MODULE_RE.match(lines[i])
        if not m:
            i += 1
            continue
        mod_name = m.group(1)
        # look in next 10 non-blank lines for a MAPPING tag
        window = lines[i : i + 12]
        tags = MAPPING_RE.findall("\n".join(window))
        if not tags:
            violations.append(
                f"{path}:{i+1}: module '{mod_name}' missing // MAPPING: tag (R19)"
            )
        elif len(tags) > 1:
            violations.append(
                f"{path}:{i+1}: module '{mod_name}' has {len(tags)} MAPPING tags "
                f"(ambiguous, R19): {tags}"
            )
        else:
            tag = tags[0]
            if tag not in VALID_DOMAINS:
                violations.append(
                    f"{path}:{i+1}: module '{mod_name}' invalid MAPPING domain "
                    f"'{tag}' (allowed: {sorted(VALID_DOMAINS)})"
                )
        i += 1

    return violations


def main(argv: list[str]) -> int:
    roots = [Path(a) for a in argv[1:]] or [Path("rtl")]
    existing = [r for r in roots if r.exists()]
    if not existing:
        print(
            "ci/check_1to1_mapping.py: no RTL paths found "
            f"(checked {[str(r) for r in roots]}); "
            "treating as PASS (project pre-RTL).",
            file=sys.stderr,
        )
        return 0

    all_violations: list[str] = []
    file_count = 0
    module_count = 0
    for f in iter_rtl(existing):
        file_count += 1
        with f.open() as fh:
            text = fh.read()
        module_count += len(MODULE_RE.findall(text))
        all_violations.extend(check_file(f))

    if all_violations:
        print(
            f"R19 QUANTUM-BRAIN-1TO1 violations "
            f"({len(all_violations)} in {file_count} files):",
            file=sys.stderr,
        )
        for v in all_violations:
            print(f"  ✗ {v}", file=sys.stderr)
        print(
            "\nFix: add `// MAPPING: PHYS->SI` (or BIO->SI / LANG->SI) inside "
            "the first 10 lines of each module body.",
            file=sys.stderr,
        )
        return 1

    print(
        f"R19 OK: {module_count} module(s) across {file_count} file(s) "
        "tagged correctly."
    )
    print("phi^2 + phi^-2 = 3 · QUANTUM BRAIN 1:1 SILICON")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
