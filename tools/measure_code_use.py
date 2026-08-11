#!/usr/bin/env python3
"""Code utilisation: how many distinct values a format's codes actually name.

A throughput metric rewards a format for discarding code space -- a decoder
whose image is smaller needs less logic, and logic observing that image may
specialise to it (Proposition, output-space pruning). So MHz/LUT alone is not a
ranking of format quality, and every row needs this number beside it.

Utilisation is |distinct decoder outputs| / |codes|, measured on the RTL's own
32-bit output so there is no rounding question: the output IS the value.

Exhaustive up to 2^18 codes; uniformly sampled above, with the sample size
printed so a partial sweep never reads as a complete one.
"""
import json, pathlib, random, subprocess, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
TNET = ROOT / "fpga" / "tnet"
SCRATCH = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp")

# format -> (module, sources, input port, width, extra port text)
JOBS = {
    "GFTernary": ("gfternary_decode", ["gfternary_decode.v"], "gft_in", 2, ""),
    "binary32":  ("binary32_decode", ["binary32_decode.v"], "binary32_in", 32, ""),
    "binary16":  ("binary16_decode", ["binary16_decode.v"], "b16_in", 16, ""),
    "GF10":      ("gf10_decode", ["gf10_decode.v"], "gf10_in", 10, ""),
    "GF14":      ("gf14_decode", ["gf14_decode.v"], "gf14_in", 14, ""),
    "fp8 e4m3":  ("fp8_e4m3_decode", ["fp8_decode.v"], "x", 8, ""),
    "fp8 e5m2":  ("fp8_e5m2_decode", ["fp8_decode.v"], "x", 8, ""),
    "minifloat": ("minifloat_decode", ["minifloat_decode.v"], "mf_in", 8, ""),
    "BNF16":     ("bnf16s_decode", ["tnf_spec_decode.v"], "x", 17, ""),
    "TNF16":     ("tnf17_decode", ["tnf17_decode.v"], "x", 17, ""),
    "TNF16a":    ("tnf16a_decode", ["tnf16_rungs.v"], "x", 16, ""),
    "TNF16b":    ("tnf16b_decode", ["tnf16_rungs.v"], "x", 16, ""),
    "TNF8":      ("tnf8s_decode", ["tnf_spec_decode.v"], "x", 10, ""),
    "TNF32":     ("tnf32s_decode", ["tnf_spec_decode.v"], "x", 36, ""),
    "TNF64":     ("tnf64s_decode", ["tnf_spec_decode.v"], "x", 65, ""),
    "VAX F":     ("vax_f_decode", ["vax_f_decode.v"], "vax_in", 32, ", .is_zero()"),
    "IBM hex32": ("ibm_hfp32_decode", ["ibm_hfp32_decode.v"], "ibm_in", 32, ", .is_zero()"),
    "posit8":    ("posit8_es2_decode", ["posit8_es2_decode.v", "posit16_decode.v"],
                  "posit_in", 8, ", .is_zero(), .is_nar()"),
    "posit16":   ("posit16_decode", ["posit16_decode.v"], "posit_in", 16, ", .is_zero(), .is_nar()"),
    "posit32":   ("posit32_decode", ["posit32_decode.v"], "posit_in", 32, ", .is_zero(), .is_nar()"),
    "LNS16":     ("lns16_decode", ["lns16_decode.v"], "lns_in", 16, ""),
    "GF+8":      ("gfplus8_a_decode", ["gfplus8_a_decode.v"], "word_in", 10, ""),
    # takum16's decoder is a clocked block-memory table, so its sweep needs a
    # clock and one cycle of latency; CLOCKED lists the modules that do.
    "takum16":   ("takum16_decode", ["takum16_decode.v"], "takum16_in", 16, ""),
}
CLOCKED = {"takum16_decode"}
EXHAUSTIVE = 1 << 18
SAMPLE = 200_000

def sweep(name, mod, srcs, port, width, extra):
    total = 1 << width
    if total <= EXHAUSTIVE:
        codes, exact = list(range(total)), True
    else:
        random.seed(7)
        codes, exact = [random.getrandbits(width) for _ in range(SAMPLE)], False
    hexw = (width + 3) // 4
    hexf = SCRATCH / f"cu_{mod}.hex"
    hexf.write_text("\n".join(f"{c:0{hexw}x}" for c in codes) + "\n")
    # GF+A takes its two selector bits on a separate port
    drive = (f".word_in(c[7:0]), .pocket(c[9:8]), .fp32_out(o), .is_zero()"
             if mod == "gfplus8_a_decode" else
             (f".clk(clk), .{port}(c), .fp32_out(o){extra}" if mod in CLOCKED
              else f".{port}(c), .fp32_out(o){extra}"))
    clk_decl = "reg clk = 0; always #5 clk = ~clk;\n  " if mod in CLOCKED else ""
    step = "@(posedge clk); @(posedge clk);" if mod in CLOCKED else "#1;"
    tb = f"""`timescale 1ns/1ps
module tb;
  reg [{width-1}:0] mem [0:{len(codes)-1}]; integer i, fo; reg [{width-1}:0] c; wire [31:0] o;
  {clk_decl}
  {mod} u({drive});
  initial begin
    $readmemh("{hexf}", mem); fo=$fopen("{SCRATCH}/cu_{mod}.out","w");
    for(i=0;i<{len(codes)};i=i+1) begin c=mem[i]; {step} $fwrite(fo,"%08x\\n", o); end
    $fclose(fo); $finish; end
endmodule"""
    tbf = SCRATCH / f"cu_tb_{mod}.v"; tbf.write_text(tb)
    r = subprocess.run(["iverilog", "-o", str(SCRATCH / f"cu_{mod}.vvp"), str(tbf)]
                       + [str(TNET / s) for s in srcs], capture_output=True, text=True)
    if r.returncode:
        return None, r.stderr.strip().splitlines()[-1][:80] if r.stderr else "build failed"
    subprocess.run([str(SCRATCH / f"cu_{mod}.vvp")], capture_output=True)
    vals = {l.strip() for l in open(SCRATCH / f"cu_{mod}.out") if l.strip()}
    return (len(vals), len(codes), exact), None

if __name__ == "__main__":
    out = {}
    for name, (mod, srcs, port, width, extra) in JOBS.items():
        res, err = sweep(name, mod, srcs, port, width, extra)
        if err:
            print(f"  {name:12s} FAILED: {err}"); continue
        distinct, n, exact = res
        u = distinct / n
        out[name] = {"distinct": distinct, "codes": n, "exhaustive": exact, "use": u}
        tag = "exhaustive" if exact else f"sampled {n:,}"
        print(f"  {name:12s} {distinct:7,} / {n:7,} = {u*100:5.1f}%   ({tag})")
    (ROOT / "research" / "arxiv_tnf" / "code_use.json").write_text(json.dumps(out, indent=1))
    print(f"\n  written: research/arxiv_tnf/code_use.json ({len(out)} formats)")
