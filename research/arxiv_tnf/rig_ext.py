#!/usr/bin/env python3
"""W937: run the W936 replication rig against a THIRD-PARTY reference implementation.

The manuscript's posit rows are the author's own structural models; the field's de
facto posit hardware baseline (PACoGen, Jaiswal & So, IEEE Access 2019) is cited
zero times in it. This measures both under one flow, one metric and one rig, so the
question "is the 6.1x a property of the format or of the comparator" gets a number.

Same method as W936: instantiate the unit N times in a pipelined chain, fit
cells(N) = fixture + cost*N over N in {1,2,4,8}, report the slope.
"""
import re, sys, json, subprocess, pathlib

SC = pathlib.Path("/private/tmp/claude-501/-Users-playom-t27--claude-worktrees-igla-fpga-improvements-3f5e1a/"
                  "eeed4a0e-20e8-40f4-aa16-1ecfee4ad92d/scratchpad")
PACO = SC / "ext/PACoGen-master"
TNET = SC / "upstream-wt/fpga/tnet"
OUT = SC / "ext/rig"
OUT.mkdir(parents=True, exist_ok=True)

HDR = """`default_nettype none
module {top} (input wire clk, input wire rst_n, output wire [3:0] led);
  reg [63:0] lf = 64'h1234_5678_9ABC_DEF0;
  always @(posedge clk) lf <= !rst_n ? 64'h1234_5678_9ABC_DEF0 :
                                       {{lf[62:0], lf[63]^lf[62]^lf[60]^lf[59]}};
"""
FOOT = """  assign led = acc[3:0] ^ acc[7:4] ^ acc[11:8] ^ acc[15:12] ^
               acc[19:16] ^ acc[23:20] ^ acc[27:24] ^ acc[31:28];
endmodule
"""


def w_extract(n, N=16, es=2, Bs=4):
    """PACoGen data_extract_v1: in -> (rc, regime, exp, mant). Chain on the packed outputs."""
    b = [HDR.format(top=f"x_paco_extract_n{n}")]
    b.append(f"  wire [{N-1}:0] din [0:{n-1}];")
    b.append(f"  reg  [{N-1}:0] q [0:{n-1}];")
    b.append("  genvar i;")
    b.append("  generate")
    b.append(f"    for (i = 0; i < {n}; i = i + 1) begin : rep")
    b.append(f"      wire rc; wire [{Bs-1}:0] rg; wire [{es-1}:0] ex; wire [{N-es-1}:0] mt;")
    b.append(f"      assign din[i] = (i == 0) ? lf[{N-1}:0] : q[(i == 0) ? 0 : i-1];")
    b.append(f"      data_extract_v1 #(.N({N}), .es({es})) dx (.in(din[i]), .rc(rc), .regime(rg), .exp(ex), .mant(mt));")
    b.append(f"      wire [{1+Bs+es+(N-es)-1}:0] packed = {{rc, rg, ex, mt}};")
    b.append(f"      always @(posedge clk) q[i] <= !rst_n ? {N}'b0 : packed[{N-1}:0];")
    b.append("    end")
    b.append("  endgenerate")
    b.append(f"  wire [31:0] acc = {{{32-N}'b0, q[{n-1}]}};")
    b.append(FOOT)
    return "\n".join(b)


def w_add(n, N=16):
    """PACoGen posit_add: chain out -> in1, second operand from the LFSR."""
    b = [HDR.format(top=f"x_paco_add_n{n}")]
    b.append(f"  wire [{N-1}:0] o [0:{n-1}];")
    b.append(f"  reg  [{N-1}:0] q [0:{n-1}];")
    b.append("  genvar i;")
    b.append("  generate")
    b.append(f"    for (i = 0; i < {n}; i = i + 1) begin : rep")
    b.append(f"      wire [{N-1}:0] a = (i == 0) ? lf[{N-1}:0] : q[(i == 0) ? 0 : i-1];")
    b.append(f"      wire [{N-1}:0] bb = lf[{2*N-1}:{N}] ^ {{{N}{{1'b0}}}};")
    b.append(f"      posit_add #(.N({N}), .es(2)) pa (.in1(a), .in2(bb), .start(1'b1), .out(o[i]), .inf(), .zero(), .done());")
    b.append(f"      always @(posedge clk) q[i] <= !rst_n ? {N}'b0 : o[i];")
    b.append("    end")
    b.append("  endgenerate")
    b.append(f"  wire [31:0] acc = {{{32-N}'b0, q[{n-1}]}};")
    b.append(FOOT)
    return "\n".join(b)


def counts(log):
    tail = log.rsplit("Printing statistics.", 1)[-1]
    lut = sum(int(m.group(1)) for m in re.finditer(r"^\s+(\d+)\s+LUT[1-6]\b", tail, re.M))
    cy = sum(int(m.group(1)) for m in re.finditer(r"^\s+(\d+)\s+CARRY4\b", tail, re.M))
    mux = sum(int(m.group(1)) for m in re.finditer(r"^\s+(\d+)\s+MUXF[78]\b", tail, re.M))
    ff = sum(int(m.group(1)) for m in re.finditer(r"^\s+(\d+)\s+FD[RS]E\b", tail, re.M))
    return lut, cy, mux, ff


def fit(xs, ys):
    n = len(xs); mx = sum(xs)/n; my = sum(ys)/n
    sxx = sum((x-mx)**2 for x in xs); sxy = sum((x-mx)*(y-my) for x, y in zip(xs, ys))
    b = sxy/sxx; a = my - b*mx
    ssr = sum((y-(a+b*x))**2 for x, y in zip(xs, ys)); sst = sum((y-my)**2 for y in ys)
    return a, b, (1-ssr/sst if sst else 1.0)


def run(name, gen, srcs, ns=(1, 2, 4, 8)):
    xs, ys, pts = [], [], {}
    for n in ns:
        f = OUT / f"{name}_n{n}.v"
        f.write_text(gen(n))
        cmd = f"read_verilog {f} {' '.join(str(s) for s in srcs)}; synth_xilinx -nodsp -top {name}_n{n}; stat"
        r = subprocess.run(["yosys", "-p", cmd], capture_output=True, text=True, timeout=1800)
        if r.returncode != 0:
            pts[n] = {"error": (r.stdout + r.stderr)[-500:]}
            print(f"{name} N={n}: FAIL", flush=True)
            print((r.stdout + r.stderr)[-500:], flush=True)
            continue
        lut, cy, mux, ff = counts(r.stdout)
        xs.append(n); ys.append(lut + cy)
        pts[n] = {"lut": lut, "carry4": cy, "muxf": mux, "ff": ff, "cells": lut + cy}
        print(f"{name} N={n}: lut={lut} carry4={cy} cells={lut+cy}", flush=True)
    if len(xs) >= 3:
        a, b, r2 = fit(xs, ys)
        print(f"  -> {name}: {b:.3f} cells/unit, fixture {a:.1f}, R2 {r2:.5f}", flush=True)
        return {"cells_per_unit": round(b, 3), "fixture": round(a, 2), "r2": round(r2, 6), "points": pts}
    return {"status": "failed", "points": pts}


def w_tnf_add(n, W=16, top="tnf_cost_e4m8_add_top"):
    """TNF adder arm at 16 physical cells: chain out_y -> in_a, in_b from the LFSR."""
    b = [HDR.format(top=f"x_tnf_add_n{n}")]
    b.append(f"  wire [{W-1}:0] o [0:{n-1}];")
    b.append(f"  reg  [{W-1}:0] q [0:{n-1}];")
    b.append("  genvar i;")
    b.append("  generate")
    b.append(f"    for (i = 0; i < {n}; i = i + 1) begin : rep")
    b.append(f"      wire [{W-1}:0] a = (i == 0) ? lf[{W-1}:0] : q[(i == 0) ? 0 : i-1];")
    b.append(f"      wire [{W-1}:0] bb = lf[{2*W-1}:{W}];")
    b.append(f"      {top} u (.clk(clk), .rst(~rst_n), .in_valid(1'b1), .in_a(a), .in_b(bb),")
    b.append("               .in_ready(), .out_valid(), .out_y(o[i]), .out_ready(1'b1));")
    b.append(f"      always @(posedge clk) q[i] <= !rst_n ? {W}'b0 : o[i];")
    b.append("    end")
    b.append("  endgenerate")
    b.append(f"  wire [31:0] acc = {{{32-W}'b0, q[{n-1}]}};")
    b.append(FOOT)
    return "\n".join(b)


if __name__ == "__main__":
    res = {}
    add_v = PACO / "add/posit_add.v"
    res["pacogen_data_extract_n16_es2"] = run("x_paco_extract", w_extract, [add_v])
    res["pacogen_posit_add_n16_es2"] = run("x_paco_add", w_add, [add_v])
    cost = SC / "upstream-wt/fpga/openxc7-synth/tnf_cost"
    synthdir = SC / "upstream-wt/fpga/openxc7-synth"
    core = [synthdir / "gf_adder_param.v", synthdir / "gf_decode_param.v"]
    core = [c for c in core if c.exists()]
    res["tnf_e4m8_add_16cells"] = run("x_tnf_add", w_tnf_add, [cost / "tnf_cost_e4m8_add_top.v"] + core)
    (OUT / "ext_fit.json").write_text(json.dumps(res, indent=1))
    print("WROTE " + str(OUT / "ext_fit.json"), flush=True)
