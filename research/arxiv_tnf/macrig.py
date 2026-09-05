#!/usr/bin/env python3
"""W952: what does the RANGE cost in silicon?

Every cell census in this project priced a DECODER -- code in, format-encoded value
out -- and found TNF4 2 % dearer than a same-width float. That is not what an MX-style
datapath builds. There the decoded value is materialised in fixed point, multiplied,
and accumulated across the block, and the width of all three is set by the format's
DYNAMIC RANGE, which is the very thing this project claimed as its advantage.

Exact widths, computed from the grids (every grid value must be representable):

  TNF4      17 bits per value, 33 per product, 38-bit block-32 accumulator
  fp6 e3m2  10 / 19 / 24
  fp6 e2m3   7 / 13 / 18

So the unit under test is one MAC lane: decode a weight code and an activation code
to fixed point, multiply, accumulate at block-accumulator width. Cost is the SLOPE of
cells(N) = fixture + cost*N with the lane instantiated N times in a pipelined chain,
inputs differing per stage so nothing is shared away.
"""
import json, math, os, pathlib, re, subprocess, sys
from fractions import Fraction
import numpy as np

S = pathlib.Path(os.environ.get("T27_WORK") or pathlib.Path(__file__).resolve().parent)
sys.path.insert(0, os.environ.get("T27_CONFORMANCE") or str(S / "oracles"))
import tnf_ref as T, fp8_ref as F8

NS = [1, 2, 4, 8]
FMT = {"TNF4": (T, T.TNFFormat(2, 1), 6),
       "fp6e3m2": (F8, F8.FORMATS["fp6_e3m2"], 6),
       "fp6e2m3": (F8, F8.FORMATS["fp6_e2m3"], 6)}


def grid(mod, fmt, bits):
    out = {}
    for c in range(1 << bits):
        try:
            v = float(mod.decode(fmt, c))
        except Exception:
            continue
        if np.isfinite(v):
            out[c] = v
    return out


def widths(vals):
    fr = [Fraction(v).limit_denominator(1 << 40) for v in vals.values() if v != 0]
    e = 0
    while any((f * Fraction(2 ** e)).denominator != 1 for f in fr):
        e += 1
    u = Fraction(1, 2 ** e)
    mx = max(abs(f) for f in fr)
    w = math.ceil(math.log2(float(mx / u))) + 1
    return w, 2 * (w - 1) + 1, u


def lane_v(name, vals, bits, w, wp, acc):
    def q(v):
        return int(round(v / float(u)))
    def lit(v):
        # Verilog puts the sign BEFORE the size: -17'sd3, never 17'sd-3.
        i = q(v)
        return f"-{w}'sd{-i}" if i < 0 else f"{w}'sd{i}"
    rows = "\n".join(f"      {bits}'d{c}: d = {lit(v)};" for c, v in sorted(vals.items()))
    return f"""
module {name} (input clk, input [{bits-1}:0] wc, input [{bits-1}:0] ac,
               input signed [{acc-1}:0] ai, output reg signed [{acc-1}:0] ao);
  function signed [{w-1}:0] dec(input [{bits-1}:0] c);
    reg signed [{w-1}:0] d;
    begin
      case (c)
{rows}
        default: d = {w}'sd0;
      endcase
      dec = d;
    end
  endfunction
  wire signed [{w-1}:0] wv = dec(wc);
  wire signed [{w-1}:0] av = dec(ac);
  wire signed [{wp-1}:0] p = wv * av;
  always @(posedge clk) ao <= ai + {{{{{acc-wp}{{p[{wp-1}]}}}}, p}};
endmodule
"""


def chain_v(name, n, bits, acc):
    inst, wires = [], []
    for i in range(n):
        wires.append(f"  wire signed [{acc-1}:0] s{i};")
        src = "ai" if i == 0 else f"s{i-1}"
        inst.append(f"  {name} u{i} (.clk(clk), .wc(wc ^ {bits}'d{i*7 & ((1<<bits)-1)}), "
                    f".ac(ac ^ {bits}'d{i*13 & ((1<<bits)-1)}), .ai({src}), .ao(s{i}));")
    return ("module top (input clk, input [%d:0] wc, input [%d:0] ac,\n"
            "            input signed [%d:0] ai, output signed [%d:0] ao);\n%s\n%s\n"
            "  assign ao = s%d;\nendmodule\n"
            % (bits - 1, bits - 1, acc - 1, acc - 1,
               "\n".join(wires), "\n".join(inst), n - 1))


# W952: yosys -q suppresses the stat output, and the rig read the silence as
# 0.000 cells at R2 = 1.00000 -- the same signature that lesson 1407 recorded when
# a LUT-only census reported TNF decoders at zero. Two rules encoded here: never
# run the tool quiet when the tool's output IS the measurement, and refuse a
# reading of zero instead of fitting a line through it.
CELL = re.compile(r"^\s+(\d+)\s+(LUT[1-6]|CARRY4|MUXF[78])\s*$")


def cells(vsrc, work):
    """Return (LUT1-6 + CARRY4, MUXF7 + MUXF8) from the LAST design-hierarchy block."""
    work.write_text(vsrc)
    r = subprocess.run(["yosys", "-p",
                        f"read_verilog {work}; synth_xilinx -top top -nodsp; stat"],
                       capture_output=True, text=True, timeout=1800)
    if r.returncode != 0:
        raise RuntimeError(r.stderr[-500:])
    blocks = r.stdout.split("=== design hierarchy ===")
    if len(blocks) < 2:
        raise RuntimeError("no design hierarchy block in yosys output")
    lut = mux = 0
    for line in blocks[-1].splitlines():
        m = CELL.match(line)
        if m:
            if m.group(2).startswith("MUXF"):
                mux += int(m.group(1))
            else:
                lut += int(m.group(1))
    if lut == 0:
        raise RuntimeError("counted zero consumer cells -- the parser missed the stat block")
    return lut, mux


out = {"metric": "LUT1-6 + CARRY4", "ns": NS, "widths": {}, "cost": {}}
for name, spec in FMT.items():
    vals = grid(*spec)
    bits = spec[2]
    w, wp, u = widths(vals)
    acc = wp + 5
    out["widths"][name] = {"value": w, "product": wp, "acc32": acc}
    pts, muxes = [], []
    for n in NS:
        src = lane_v(f"lane_{name}", vals, bits, w, wp, acc) + chain_v(f"lane_{name}", n, bits, acc)
        c, mx_ = cells(src, S / f"_mac_{name}_{n}.v")
        pts.append(c); muxes.append(mx_)
        print(f"  {name:9} N={n}: {c:7d} LUT+CARRY4, {mx_:5d} MUXF7/8", flush=True)
    A = np.vstack([np.array(NS), np.ones(len(NS))]).T
    slope, fix = np.linalg.lstsq(A, np.array(pts, float), rcond=None)[0]
    pred = A @ np.array([slope, fix])
    ss = 1 - ((np.array(pts) - pred) ** 2).sum() / max(((np.array(pts) - np.mean(pts)) ** 2).sum(), 1e-9)
    ms = np.linalg.lstsq(A, np.array(muxes, float), rcond=None)[0][0]
    out["cost"][name] = {"per_lane": round(float(slope), 2), "fixture": round(float(fix), 2),
                         "r2": round(float(ss), 5), "points": pts,
                         "mux_per_lane": round(float(ms), 2), "mux_points": muxes}
    print(f"  -> {name}: {slope:.2f} LUT+CARRY4 на полосу (+{ms:.2f} MUXF), "
          f"фикстура {fix:.1f}, R²={ss:.5f}\n", flush=True)

p = S / "mac_w952.json"
p.write_text(json.dumps(out, indent=1))
print("WROTE " + str(p), flush=True)
