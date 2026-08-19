#!/usr/bin/env python3
"""W940: the consumer's cost as a function of alphabet width, measured not asserted.

W939 found that an identical 12x8 multiply costs 382.4 cells behind a 16-bit input,
129.7 behind 8 bits and 4.1 behind a two-bit alphabet -- a 93x effect on the
CONSUMER against an 8-cell effect on the decoder. That comparison mixed widths, so
it is a width effect quoted as a format effect.

This sweeps every decoder in the tree, auto-discovering its input port and width,
and reports (alphabet bits) -> (decoder cells, consumer cells) so the effect becomes
a curve instead of three points. Joined afterwards with the five-seed accuracy runs,
it is a cost-quality frontier measured end to end on one substrate.
"""
import re, json, subprocess, pathlib

SC = pathlib.Path("/private/tmp/claude-501/-Users-playom-t27--claude-worktrees-igla-fpga-improvements-3f5e1a/"
                  "eeed4a0e-20e8-40f4-aa16-1ecfee4ad92d/scratchpad")
TNET = SC / "upstream-wt/fpga/tnet"
OUT = SC / "alpha"
OUT.mkdir(parents=True, exist_ok=True)

DECL = re.compile(
    r"^module\s+(\w*decode\w*)\s*\((.*?)\);", re.S | re.M)
IN_PORT = re.compile(r"input\s+wire\s*(?:\[\s*(\d+)\s*:\s*0\s*\])?\s*(\w+)")

SKIP = {"posit64_decode", "takum64_decode", "tnf64_decode", "tnf64s_decode",
        "posit32_decode", "binary32_decode", "tnf32_decode", "tnf32s_decode",
        "ibm_hfp32_decode"}  # 32b+ decoders dominate runtime; the curve is set by 2..16


def discover():
    """Every <x>_decode with a single vector input and an fp32_out."""
    found = {}
    for f in sorted(TNET.glob("*.v")):
        src = f.read_text(errors="ignore")
        for m in DECL.finditer(src):
            mod, ports = m.group(1), m.group(2)
            if mod in SKIP or "fp32_out" not in ports:
                continue
            ins = IN_PORT.findall(ports)
            ins = [(int(h) + 1 if h else 1, n) for h, n in ins]
            ins = [(w, n) for w, n in ins if w > 1]
            if len(ins) != 1:
                continue
            width, port = ins[0]
            found[mod] = (port, width, f)
    return found


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


def emit(top, mod, port, width, n, fused):
    src = min(width, 32)
    b = [HDR.format(top=top)]
    b.append(f"  reg [31:0] q [0:{n-1}];")
    b.append("  genvar i;")
    b.append("  generate")
    b.append(f"    for (i = 0; i < {n}; i = i + 1) begin : rep")
    b.append(f"      wire [{width-1}:0] din = (i == 0) ? lf[{src-1}:0] : q[(i == 0) ? 0 : i-1][{width-1}:0];")
    b.append("      wire [31:0] dec;")
    b.append(f"      {mod} dc (.{port}(din), .fp32_out(dec));")
    if fused:
        b.append("      wire [11:0] wq = dec[22:11];")
        b.append("      wire [7:0]  act = lf[39:32];")
        b.append("      wire [19:0] prod = wq * act;")
        b.append("      always @(posedge clk) q[i] <= !rst_n ? 32'b0 : {12'b0, prod};")
    else:
        b.append("      always @(posedge clk) q[i] <= !rst_n ? 32'b0 : dec;")
    b.append("    end")
    b.append("  endgenerate")
    b.append(f"  wire [31:0] acc = q[{n-1}];")
    b.append(FOOT)
    return "\n".join(b)


def cells(log):
    tail = log.rsplit("Printing statistics.", 1)[-1]
    lut = sum(int(m.group(1)) for m in re.finditer(r"^\s+(\d+)\s+LUT[1-6]\b", tail, re.M))
    cy = sum(int(m.group(1)) for m in re.finditer(r"^\s+(\d+)\s+CARRY4\b", tail, re.M))
    return lut + cy


def fit(xs, ys):
    n = len(xs); mx = sum(xs)/n; my = sum(ys)/n
    sxx = sum((x-mx)**2 for x in xs); sxy = sum((x-mx)*(y-my) for x, y in zip(xs, ys))
    bb = sxy/sxx; aa = my - bb*mx
    ssr = sum((y-(aa+bb*x))**2 for x, y in zip(xs, ys)); sst = sum((y-my)**2 for y in ys)
    return aa, bb, (1-ssr/sst if sst else 1.0)


def run(mod, port, width, f, fused):
    tag = f"a_{mod}_{'fu' if fused else 'ba'}"
    xs, ys = [], []
    for n in (1, 2, 4):
        top = f"{tag}_n{n}"
        vf = OUT / f"{top}.v"
        vf.write_text(emit(top, mod, port, width, n, fused))
        cmd = f"read_verilog {vf} {f}; synth_xilinx -nodsp -top {top}; stat"
        r = subprocess.run(["yosys", "-p", cmd], capture_output=True, text=True, timeout=1800)
        if r.returncode != 0:
            return None
        xs.append(n); ys.append(cells(r.stdout))
    a, b, r2 = fit(xs, ys)
    return {"per_unit": round(b, 3), "fixture": round(a, 2), "r2": round(r2, 6)}


if __name__ == "__main__":
    units = discover()
    print(f"  найдено декодеров: {len(units)}", flush=True)
    res = {}
    for mod, (port, width, f) in sorted(units.items(), key=lambda kv: kv[1][1]):
        bare = run(mod, port, width, f, False)
        fu = run(mod, port, width, f, True)
        if not bare or not fu:
            print(f"  {mod:22} ({width:2}b): FAIL", flush=True)
            continue
        res[mod] = {"alphabet_bits": width, "decoder_cells": bare["per_unit"],
                    "consumer_cells": fu["per_unit"],
                    "multiply_alone": round(fu["per_unit"] - bare["per_unit"], 3),
                    "r2_bare": bare["r2"], "r2_fused": fu["r2"]}
        print(f"  {mod:22} ({width:2}b): декодер {bare['per_unit']:8.2f}  "
              f"потребитель {fu['per_unit']:9.2f}  умножитель {res[mod]['multiply_alone']:9.2f}", flush=True)
        (OUT / "alphabet.json").write_text(json.dumps(res, indent=1))
    (OUT / "alphabet.json").write_text(json.dumps(res, indent=1))
    print("WROTE " + str(OUT / "alphabet.json"), flush=True)
