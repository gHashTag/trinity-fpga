#!/usr/bin/env python3
"""W952b: the part of the cost that no implementation can avoid.

The MAC-lane measurement prices ONE datapath -- decode to fixed point, multiply,
accumulate -- and that is the style most punishing to a wide-range format. A
float-style lane would multiply small mantissas and add exponents instead, so the
4.83x figure is not implementation-independent and must not be quoted as if it were.

What IS forced: to accumulate a block of 32 products without loss, the accumulator
must span 2*binades + log2(32) bits, whatever the multiplier looks like. That is
arithmetic, not design. So this measures the accumulator alone: an adder and a
register of the required width, replicated.

  TNF4 38 bits, fp6 e3m2 24, fp6 e2m3 18.
"""
import json, os, pathlib, re, subprocess
import numpy as np

S = pathlib.Path(os.environ.get("T27_WORK") or pathlib.Path(__file__).resolve().parent)
NS = [1, 2, 4, 8]
ACC = {"TNF4": 38, "fp6e3m2": 24, "fp6e2m3": 18}
CELL = re.compile(r"^\s+(\d+)\s+(LUT[1-6]|CARRY4|MUXF[78])\s*$")


def cells(src, work):
    work.write_text(src)
    r = subprocess.run(["yosys", "-p", f"read_verilog {work}; synth_xilinx -top top -nodsp; stat"],
                       capture_output=True, text=True, timeout=1200)
    if r.returncode != 0:
        raise RuntimeError(r.stderr[-400:])
    blocks = r.stdout.split("=== design hierarchy ===")
    lut = mux = 0
    for line in blocks[-1].splitlines():
        m = CELL.match(line)
        if m:
            if m.group(2).startswith("MUXF"):
                mux += int(m.group(1))
            else:
                lut += int(m.group(1))
    if lut == 0:
        raise RuntimeError("zero cells counted")
    return lut, mux


def acc_v(name, w, n):
    unit = (f"module {name} (input clk, input signed [{w-1}:0] d,"
            f" input signed [{w-1}:0] a, output reg signed [{w-1}:0] o);\n"
            f"  always @(posedge clk) o <= a + d;\nendmodule\n")
    ws = "\n".join(f"  wire signed [{w-1}:0] s{i};" for i in range(n))
    ins = "\n".join(
        f"  {name} u{i} (.clk(clk), .d(d ^ {w}'d{(i*2654435761) & ((1<<w)-1)}), "
        f".a({'a' if i == 0 else f's{i-1}'}), .o(s{i}));" for i in range(n))
    top = (f"module top (input clk, input signed [{w-1}:0] d, input signed [{w-1}:0] a,"
           f" output signed [{w-1}:0] o);\n{ws}\n{ins}\n  assign o = s{n-1};\nendmodule\n")
    return unit + top


out = {"metric": "LUT1-6 + CARRY4", "ns": NS, "acc_bits": ACC, "cost": {}}
for name, w in ACC.items():
    pts, mux = [], []
    for n in NS:
        c, m = cells(acc_v(f"acc_{name}", w, n), S / f"_acc_{name}_{n}.v")
        pts.append(c); mux.append(m)
        print(f"  {name:9} {w:2d} бит  N={n}: {c:5d} LUT+CARRY4", flush=True)
    A = np.vstack([np.array(NS), np.ones(len(NS))]).T
    slope, fix = np.linalg.lstsq(A, np.array(pts, float), rcond=None)[0]
    out["cost"][name] = {"per_acc": round(float(slope), 2), "fixture": round(float(fix), 2),
                         "points": pts}
    print(f"  -> {name}: {slope:.2f} ячеек на аккумулятор {w} бит\n", flush=True)
p = S / "acc_w952.json"
p.write_text(json.dumps(out, indent=1))
print("WROTE " + str(p), flush=True)
