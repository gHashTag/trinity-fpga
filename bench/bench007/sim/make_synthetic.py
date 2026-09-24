#!/usr/bin/env python3
"""Synthetic captures with KNOWN answers, to check b7_analyze.py end to end.

    python3 make_synthetic.py OUTDIR [--delta-mw 45] [--break-instrument]
"""
import argparse
import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "host"))
from b7_format import make_b7  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("out")
ap.add_argument("--f-hz", type=float, default=68_812_345.0)
ap.add_argument("--delta-mw", type=float, default=45.0)
ap.add_argument("--break-instrument", action="store_true")
a = ap.parse_args()
os.makedirs(a.out, exist_ok=True)
rnd = random.Random(7)

# probe UART: 61 windows, window 0 partial, one corrupted line, one lost line
t0 = 1_758_700_000_000_000_000
with open(os.path.join(a.out, "uart_probe_synth.log"), "w") as f:
    f.write("# synthetic\n")
    for seq in range(62):
        if seq == 30:
            continue                                   # a lost line -> one gap
        c = rnd.randint(1_000, 5_000_000) if seq == 0 else int(a.f_hz) + rnd.choice((0, 1))
        p = c // 1024 + (7 if a.break_instrument and seq == 10 else 0)
        line = make_b7(seq, c, p)
        if seq == 20:
            line = line[:-2] + ("00" if not line.endswith("00") else "11")   # corrupted checksum
        f.write(f"{t0 + seq * 1_000_000_000}\t{line}\n")

# host-counted steps: 25 per second for 60 s
with open(os.path.join(a.out, "uart_active_synth.log"), "w") as f:
    for n in range(1501):
        f.write(f"{t0 + n * 40_000_000}\ty=0.{n % 1000:03d}\n")

# power: idle 3.200 W, active 3.200 W + delta; 10 Hz, 70 s, sd 5 mW; two file schemas
for cond, base in (("idle", 3.200), ("active", 3.200 + a.delta_mw / 1000)):
    for r in (1, 2, 3):
        path = os.path.join(a.out, f"p_{cond}_r{r}.csv")
        with open(path, "w") as f:
            if r == 2:   # FNB58-logger style: whitespace, V and I columns
                f.write("timestamp sample_in_packet voltage_V current_A\n")
                for k in range(700):
                    p = base + rnd.gauss(0, 0.005)
                    f.write(f"{1758700000 + k / 10:.3f} {k % 4} 12.000 {p / 12.0:.7f}\n")
            else:
                f.write("time,power\n")
                for k in range(700):
                    f.write(f"{k / 10:.1f},{base + rnd.gauss(0, 0.005):.6f}\n")
print("synthetic captures in", a.out)
