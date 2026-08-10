#!/usr/bin/env python3
"""Every oracle a test imports must exist, and the prefix-sharing families must
all survive.

Written after `rm -f specs/numeric/gft*.t27` in a sibling repository deleted
gfternary.t27 -- a 2-bit {-phi, 0, +phi} alphabet, a different object that merely
shares a prefix with the old GF-T names. The catalog row outlived the file and no
gate noticed. The same hazard lives here: `gft*` and `gf*` globs both swallow
gfternary_ref.py and gf_ref.py.

Exits non-zero on any failure.
"""
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent

# Three distinct families that share a prefix. Losing any one silently is the
# failure this gate exists to prevent.
NEIGHBOURS = {
    "gf_ref.py": "binary GoldenFloat ladder",
    "gfternary_ref.py": "2-bit {-phi, 0, +phi} alphabet",
    "tnf_ref.py": "ternary-exponent float ladder",
}


def main():
    problems = []

    for name, why in NEIGHBOURS.items():
        if not (HERE / name).exists():
            problems.append(f"MISSING   {name} ({why})")

    # Every `import X` inside this directory must resolve to a file here or to a
    # stdlib/site module. We only police local oracle imports.
    for py in sorted(HERE.glob("*.py")):
        text = py.read_text(encoding="utf-8", errors="replace")
        for mod in re.findall(r"^\s*import\s+([a-z0-9_]+_ref)\b", text, re.M):
            if not (HERE / f"{mod}.py").exists():
                problems.append(f"DANGLING  {py.name} imports {mod}, which is not here")

    if problems:
        for p in problems:
            print(p)
        print(f"FAIL: {len(problems)} problem(s)")
        return 1
    print(f"OK: {len(NEIGHBOURS)} prefix-sharing oracles present, all local _ref imports resolve")
    return 0


if __name__ == "__main__":
    sys.exit(main())
