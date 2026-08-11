#!/usr/bin/env python3
"""Is the linear path exact in the silicon, not only in the proof?

The paper's central claim is that a ternary layer's entire linear path -- every
weight application and every accumulation, to arbitrary fan-in -- is computed
without rounding error of any kind, because Z[phi] is closed under both. That is
a theorem and it is machine-checked in Coq.

What had never been checked is the module. A proof about a lattice says nothing
about whether the RTL implements the lattice, and this project has now found six
modules that did not implement the format they were labelled with.

Here the accumulator pair is compared against exact integer arithmetic in Z[phi].
No float appears anywhere in the comparison: the datapath's (a, b) is checked
against the reference's (a, b) as integers, modulo the accumulator width.
"""
import importlib.util, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("z", ROOT / "conformance" / "zphi_exact.py")
z = importlib.util.module_from_spec(spec); spec.loader.exec_module(z)

CASES = [(8, 16, "exact_sweep.txt"), (16, 20, "exact_sweep16.txt"),
         (32, 24, "exact_sweep32.txt")]
s8 = lambda v: v - 256 if v >= 128 else v

fails, total = [], 0
for N, ACC, fn in CASES:
    p = ROOT / "fpga" / "phiscale" / fn
    if not p.exists():
        fails.append(f"{fn}: missing -- run fpga/phiscale/tb_exact benches first")
        continue
    bad = tot = 0
    for line in p.read_text().splitlines():
        q = line.split()
        if len(q) != 4: continue
        X, Wd, ga, gb = int(q[0], 16), int(q[1], 16), int(q[2]), int(q[3])
        xs = [s8((X >> (j * 8)) & 0xFF) for j in range(N)]
        cs = [(Wd >> (j * 2)) & 0b11 for j in range(N)]
        ea, eb = z.layer(xs, cs); m = 1 << ACC
        tot += 1
        if not (((ea - ga) % m == 0) and ((eb - gb) % m == 0)): bad += 1
    total += tot
    if tot == 0:
        fails.append(f"{fn}: swept nothing -- an empty sweep is not a clean one")
    elif bad:
        fails.append(f"fan-in {N}: {bad} of {tot} vectors disagree with exact Z[phi]")
    else:
        print(f"  fan-in {N:2}: {tot} vectors, 0 mismatches")

print(f"\nvectors compared exactly: {total}")
if total == 0:
    print("\nFAIL: nothing was compared"); sys.exit(1)
if fails:
    print(f"\nFAIL: {len(fails)}\n")
    for f in fails: print(f"  {f}")
    sys.exit(1)
print("OK: the linear path is exact in the silicon, at every fan-in swept")
