#!/usr/bin/env python3
"""Does any decoder produce an undefined output?

A module whose output is X synthesises beautifully: the logic feeding an
unobservable value is pruned, so the module comes out small and fast while
producing nothing. That is not a hypothetical. A TNF8 decoder generated here had
a signed exponent wire seven bits wide with `e[7:0]` sliced from it; 960 of its
1,024 codes produced X, and it entered the throughput table at rank three at
10% less area and 22% more frequency than the working module.

The oracle caught it, but an oracle is expensive and three of our formats do not
have one. This is the cheap check that needs none: sweep the module and fail on
a single X. A correct module may be wrong; an X module is not even a module.
"""
import re, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
SWEEPS = sorted((ROOT / "fpga" / "tnet").glob("cf_*.txt"))

fails, checked = [], 0
for f in SWEEPS:
    tag = f.stem[3:]
    bad, total = 0, 0
    first = None
    for line in f.read_text(errors="ignore").splitlines():
        p = line.split()
        if len(p) != 2 or not p[0].isdigit(): continue
        total += 1
        if re.search(r"[xXzZ]", p[1]):
            bad += 1
            if first is None: first = (p[0], p[1])
    if total == 0:
        fails.append(f"{f.name}: swept nothing -- an empty sweep is not a clean one")
        continue
    checked += 1
    if bad:
        pct = 100 * bad // total
        fails.append(f"{tag}: {bad} of {total} codes undefined ({pct}%), "
                     f"first at code {first[0]} = {first[1]}")

print(f"sweeps checked: {checked}")
if not SWEEPS:
    print("\nFAIL: no sweeps found -- run fpga/tnet/conform.sh first")
    sys.exit(1)
if fails:
    print(f"\nFAIL: {len(fails)} module(s) with undefined output\n")
    for x in fails: print(f"  {x}")
    print("\n  A module whose output is X synthesises small because the logic "
          "feeding it is pruned.")
    sys.exit(1)
print("OK: every swept module is defined on every code")
