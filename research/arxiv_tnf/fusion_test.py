#!/usr/bin/env python3
"""W939: does the decode cost survive fusion with the arithmetic that consumes it?

NeuraLUT's structural claim is that precision INSIDE a LUT partition is free --
only the partition boundary's bit-width sets area. If that applies here, the
2-vs-12 cell decode gap measured in W936 would vanish once the decoder is fused
with a multiply-accumulate, and the entire area argument of a format paper would
be an artefact of measuring the decoder alone.

So: measure each format twice under the identical rig.
  (a) decoder alone                      -- the W936 quantity
  (b) decoder + a fixed-width multiply   -- the smallest honest "consumer"
and compare the BETWEEN-FORMAT gap in each. If the gap survives (b), the format
choice is visible to the surrounding logic. If it collapses, the field is right
and the paper's framing has to change.
"""
import re, json, subprocess, pathlib

SC = pathlib.Path("/private/tmp/claude-501/-Users-playom-t27--claude-worktrees-igla-fpga-improvements-3f5e1a/"
                  "eeed4a0e-20e8-40f4-aa16-1ecfee4ad92d/scratchpad")
TNET = SC / "upstream-wt/fpga/tnet"
OUT = SC / "fusion"
OUT.mkdir(parents=True, exist_ok=True)

# (format key, decoder module, input port, input width, source file)
UNITS = [
    ("tnf16", "tnf16_decode", "x", 16, "bnf_decode.v"),
    ("bnf16", "bnf16_decode", "x", 16, "bnf_decode.v"),
    ("gfternary", "gfternary_decode", "gft_in", 2, "gfternary_decode.v"),
    ("fp8e4m3", "fp8_e4m3_decode", "x", 8, None),
    ("fp8e5m2", "fp8_e5m2_decode", "x", 8, None),
    ("posit16", "posit16_decode", "posit_in", 16, "posit16_decode.v"),
    ("int8", "int8_decode", "x", 8, None),
]

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
    b = [HDR.format(top=top)]
    b.append(f"  wire [31:0] o [0:{n-1}];")
    b.append(f"  reg  [31:0] q [0:{n-1}];")
    b.append("  genvar i;")
    b.append("  generate")
    b.append(f"    for (i = 0; i < {n}; i = i + 1) begin : rep")
    b.append(f"      wire [{width-1}:0] din = (i == 0) ? lf[{width-1}:0] : q[(i == 0) ? 0 : i-1][{width-1}:0];")
    b.append(f"      wire [31:0] dec;")
    b.append(f"      {mod} dc (.{port}(din), .fp32_out(dec));")
    if fused:
        # The smallest honest consumer: take a fixed 12-bit slice of the decoded
        # word and multiply it by an activation. Identical for every format, so
        # any between-format difference that survives is the decoder's.
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


def deps(mod):
    return [p for p in TNET.glob("*.v")
            if re.search(rf"^\s*module\s+{re.escape(mod)}\b", p.read_text(errors="ignore"), re.M)]


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


def run(key, mod, port, width, fused):
    tag = f"f_{key}_{'fused' if fused else 'bare'}"
    src = deps(mod)
    if not src:
        print(f"  {key}: модуль {mod} не найден", flush=True)
        return None
    xs, ys = [], []
    for n in (1, 2, 4, 8):
        top = f"{tag}_n{n}"
        f = OUT / f"{top}.v"
        f.write_text(emit(top, mod, port, width, n, fused))
        cmd = f"read_verilog {f} {' '.join(str(s) for s in src)}; synth_xilinx -nodsp -top {top}; stat"
        r = subprocess.run(["yosys", "-p", cmd], capture_output=True, text=True, timeout=1800)
        if r.returncode != 0:
            print(f"  {tag} N={n}: FAIL {(r.stdout+r.stderr)[-160:]}", flush=True)
            continue
        c = cells(r.stdout)
        xs.append(n); ys.append(c)
    if len(xs) < 3:
        return None
    a, b, r2 = fit(xs, ys)
    print(f"  {tag}: {b:.3f} ячеек/шт (арматура {a:.1f}, R2 {r2:.5f})", flush=True)
    return {"per_unit": round(b, 3), "fixture": round(a, 2), "r2": round(r2, 6),
            "points": dict(zip(xs, ys))}


if __name__ == "__main__":
    res = {}
    for key, mod, port, width, _f in UNITS:
        for fused in (False, True):
            got = run(key, mod, port, width, fused)
            if got:
                res.setdefault(key, {})["fused" if fused else "bare"] = got
    (OUT / "fusion.json").write_text(json.dumps(res, indent=1))
    print("\n  СВОДКА (ячеек на единицу):", flush=True)
    print(f"  {'формат':12} {'декодер':>9} {'слитый':>9} {'прирост':>9}", flush=True)
    for k, v in res.items():
        if "bare" in v and "fused" in v:
            print(f"  {k:12} {v['bare']['per_unit']:9.3f} {v['fused']['per_unit']:9.3f} "
                  f"{v['fused']['per_unit']-v['bare']['per_unit']:9.3f}", flush=True)
    print("WROTE " + str(OUT / "fusion.json"), flush=True)
