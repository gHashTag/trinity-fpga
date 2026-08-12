#!/usr/bin/env python3
"""Exhaustive functional gate for the Campaign-B decoders.

Before any area number is quoted, every decoder is simulated over all 16 codes
and compared against the book object it claims to implement. A decoder that
does not decode is not a measurement of anything.
"""
import os, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gen_asym as G

near0 = G.near0_units()
e2m1  = G.e2m1_units()

mx = [0]*16
for i, m in enumerate(e2m1):
    mx[i] = m; mx[8+i] = -m
mx[8] = 1
fl = [0]*16
for i, m in enumerate(e2m1):
    fl[i] = m; fl[8+i] = -m

# mxfp4_decode is on the 1/12 grid; every other arm is on 1/24.
mx12 = [0]*16
for i, m in enumerate([0,1,2,3,4,6,8,12]):
    mx12[i] = m; mx12[8+i] = -m

ARMS = {
    "mx_u12_flat":   (mx12,        5, "mx_u12_flat.v"),
    "asym_srt":      (list(near0), 6, "asym_srt.v"),
    "asym_mx":       (mx,          6, "asym_mx.v"),
    "mx_u24_flat":   (fl,          6, "mx_u24_flat.v"),
    "mx_u24_struct": (fl,          6, "mx_u24_struct.v"),
    "mxfp4_decode":  (mx12,        5, "mxfp4_decode.v"),
}

ok = True
for name, (exp, W, src) in ARMS.items():
    tb = os.path.join(HERE, f"_fc_{name}.v")
    open(tb, "w").write(f"""
`timescale 1ns/1ps
module tb;
  reg [3:0] c; wire signed [{W-1}:0] w;
  {name} u (.code(c), .w(w));
  integer k;
  initial begin
    for (k = 0; k < 16; k = k + 1) begin
      c = k[3:0]; #1; $display("%0d %0d", k, w);
    end
    $finish;
  end
endmodule
""")
    exe = os.path.join(HERE, f"_fc_{name}.out")
    r = subprocess.run(["iverilog", "-g2005", "-o", exe, tb, os.path.join(HERE, src)],
                       capture_output=True, text=True)
    if r.returncode != 0:
        print(f"{name}: COMPILE FAIL\n{r.stderr}"); ok = False; continue
    r = subprocess.run([exe], capture_output=True, text=True)
    got = {}
    for line in r.stdout.splitlines():
        p = line.split()
        if len(p) == 2:
            got[int(p[0])] = int(p[1])
    bad = [(k, got.get(k), exp[k]) for k in range(16) if got.get(k) != exp[k]]
    print(f"{name:14s} {'PASS' if not bad else 'FAIL'}  16/16 codes"
          if not bad else f"{name:14s} FAIL {bad}")
    if bad: ok = False
    os.remove(tb); os.remove(exe)

# T38 on both tails, in the integer grid, per arm. The grid is a property of
# the arm, not of its name -- mx_u12_flat is E2M1 on the 1/12 grid too.
GRID = {"mxfp4_decode": 12, "mx_u12_flat": 12,
        "asym_srt": 24, "asym_mx": 24, "mx_u24_flat": 24, "mx_u24_struct": 24}
for name, (exp, W, _) in ARMS.items():
    U = GRID[name]
    assert max(exp) == U and min(exp) == -U, ("T38 fail", name, max(exp), min(exp))
    assert all(-(1 << (W-1)) <= v < (1 << (W-1)) for v in exp), ("width", name)
print("T38 max|level|=1.0 on BOTH tails: asserted for all 5 arms")
print("distinct values: NEAR0 =", len(set(near0)), " E2M1-flat =", len(set(fl)))
sys.exit(0 if ok else 1)
