#!/usr/bin/env python3
"""Synthesise the two decode paths the project's way and report LUT/FF/Fmax.

Method, taken from fpga/tnet/dec_full2.sh and the frontier notes it cites, not
invented here:

  * yosys synth_xilinx -flatten -nodsp, XC7A200T primitives, then nextpnr-xilinx
    against the real xc7a200tfbg484 chipdb.
  * FULL OBSERVATION. Every output bit folds into the four observed LEDs. A bit
    that reaches no output is pruned and measures nothing
    (DECODER_FULL_OBS_2026-08-10.md).
  * HARNESS SUBTRACTION with an invariant harness. Each arm is paired with a
    baseline that contains the same LFSR, the same register width and the same
    fold, and differs only by the unit under test
    (HARNESS_SUBTRACTION_2026-08-10.md). The 64-bit LFSR is a shift register, so
    every one of its bits is in the cone of any tap and it cannot be partly
    pruned -- that was the defect withdrawal 15 found with four independent LFSRs.
  * MEDIAN OF FIVE PLACEMENT SEEDS with the spread reported. Area is
    deterministic under seed; frequency is not (MEDIAN_SWEEP_2026-08-10.md).
  * Failures are detected by EXIT CODE, never by grepping for a warning string.

CAVEAT carried into every number below: bench.xdc's create_clock is not consumed
by nextpnr-xilinx, so "Fmax" is an UNCONSTRAINED post-route critical-path
estimate, not timing closure.
"""
import json, os, statistics, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
NP  = "/Users/ssdm4/Desktop/PROJECTS/CLAUDE/t27/target/nextpnr-xilinx/build/nextpnr-xilinx"
CDB = "/Users/ssdm4/Desktop/PROJECTS/CLAUDE/video-ax7203/build_lcd_diag2/chipdb/xc7a200tfbg484.bin"
XDC = os.path.join(HERE, "bench.xdc")
SEEDS = [1, 2, 3, 4, 5]

def fold(sig, W):
    """XOR every observed bit into the four LEDs. A part-select of a
    concatenation is not legal Verilog-2005, so the padded value gets its own
    wire rather than being sliced inline."""
    pad = (-W) % 4
    n = (W + pad) // 4
    decl = f"  wire [{W+pad-1}:0] fz_{sig} = " + (
        f"{{{pad}'b" + "0" * pad + f", {sig}}};" if pad else f"{sig};")
    expr = " ^ ".join(f"fz_{sig}[{4*k+3}:{4*k}]" for k in range(n))
    return decl, expr

def harness(name, W, body, reg_out=True):
    q = []
    q.append("`default_nettype none")
    q.append(f"module {name} (input wire clk, input wire rst_n, output wire [3:0] led);")
    q.append("  reg [63:0] lf = 64'h1234_5678_9ABC_DEF0;")
    q.append("  always @(posedge clk) lf <= !rst_n ? 64'h1234_5678_9ABC_DEF0 :"
             " {lf[62:0], lf[63]^lf[62]^lf[60]^lf[59]};")
    q.append(f"  wire [{W-1}:0] y;")
    q.append(body)
    if reg_out:
        q.append(f"  reg [{W-1}:0] q;")
        q.append(f"  always @(posedge clk) q <= !rst_n ? {W}'b0 : y;")
        d, e = fold("q", W)
    else:
        d, e = fold("y", W)
    q.append(d)
    q.append(f"  assign led = {e};")
    q.append("endmodule")
    q.append("`default_nettype wire")
    p = os.path.join(HERE, f"{name}.v")
    open(p, "w").write("\n".join(q) + "\n")
    return p

def run(name, W, body, deps, reg_out=True, nodsp=True):
    top = harness(name, W, body, reg_out)
    js  = os.path.join(HERE, f"{name}.json")
    if os.path.exists(js):
        os.remove(js)
    flags = "-flatten " + ("-nodsp " if nodsp else "")
    cmd = ["yosys", "-q", "-p",
           f"read_verilog {top} {' '.join(deps)}; "
           f"synth_xilinx {flags}-top {name} -json {js}"]
    r = subprocess.run(cmd, cwd=HERE, capture_output=True, text=True)
    if r.returncode != 0 or not os.path.exists(js):
        open(os.path.join(HERE, f"y_{name}.log"), "w").write(r.stdout + r.stderr)
        return {"name": name, "error": f"yosys exit {r.returncode}"}
    res = {"name": name, "W": W, "nodsp": nodsp, "f": []}
    for s in SEEDS:
        pr = subprocess.run([NP, "--chipdb", CDB, "--xdc", XDC, "--json", js,
                             "--seed", str(s), "--write", "/dev/null"],
                            cwd=HERE, capture_output=True, text=True)
        log = pr.stdout + pr.stderr
        open(os.path.join(HERE, f"s_{name}_{s}.log"), "w").write(log)
        if pr.returncode != 0:
            return {"name": name, "error": f"nextpnr exit {pr.returncode} seed {s}"}
        if s == SEEDS[0]:
            for key, tag in (("SLICE_LUTX", "lut"), ("SLICE_FFX", "ff"),
                             ("CARRY4", "carry"), ("DSP48E1", "dsp")):
                res[tag] = 0
                for line in log.splitlines():
                    if key + ":" in line:
                        res[tag] = int(line.split(key + ":")[1].split("/")[0].strip())
        # nextpnr prints "Max frequency for clock" TWICE per run: once after
        # placement and once after routing. Appending both and then slicing the
        # last len(SEEDS) values silently kept a mixture -- three post-route
        # figures and two post-placement ones, all from the last seeds only.
        # Post-placement is optimistic, so the median was drawn from two
        # different distributions. Take the LAST match in each seed's log, which
        # is the post-route estimate, and record exactly one value per seed.
        per_seed = [ln for ln in log.splitlines() if "Max frequency for clock" in ln]
        if per_seed:
            res["f"].append(float(per_seed[-1].split(":")[-1].split("MHz")[0].strip()))
    if len(res["f"]) != len(SEEDS):
        raise SystemExit(
            f"run_synth: {len(res['f'])} frequency values for {len(SEEDS)} seeds — "
            "one per seed is required, refusing to report a median over a mixture")
    if fs:
        res["fmed"] = statistics.median(fs)
        res["fspread"] = (max(fs) - min(fs)) / statistics.median(fs)
    return res


# ---------------------------------------------------------------------------
# The arms. Each is (name, observed width, harness body, extra sources,
# register-the-output?, allow DSP48?).
#
# Decoder arms are combinational, so the harness registers their output -- a
# combinational block has no clock and no Fmax, and quoting one for a block
# without a posedge is exactly the error that withdrew a 323 MHz claim.
# Lane and block arms register internally and are observed directly.
MX  = ["mxfp4_decode.v"]
LN  = ["mac_lane.v"]
BLK = ["blk32.v", "blk_scale.v"]

def arms():
    A = []
    # ---- 1. the decode paths alone, each against a bare wire of its width ----
    A.append(("d_wire5", 5, "  assign y = lf[4:0];", [], True, True))
    A.append(("d_mxfp4", 5, "  mxfp4_decode u (.code(lf[3:0]), .w(y));", MX, True, True))
    for B in (6, 8, 10):
        W = B + 2
        A.append((f"d_wire{W}", W, f"  assign y = lf[{W-1}:0];", [], True, True))
        A.append((f"d_cb{B}", W, f"  cb4_decode_b{B} u (.code(lf[3:0]), .w(y));",
                  [f"cb4_decode_b{B}.v"], True, True))
    # ---- 2. one decoder feeding one MAC lane -------------------------------
    for nodsp in (True, False):
        t = "n" if nodsp else "d"
        A.append((f"l{t}_h32", 32, "  assign y = lf[31:0];", [], True, nodsp))
        for WW in (5, 8, 12):
            A.append((f"l{t}_raw{WW}", 32,
                f"  mac_lane #(.WW({WW}),.AW(8),.ACC(32)) u (.clk(clk),.rst_n(rst_n),"
                f".w(lf[{WW-1}:0]),.a(lf[23:16]),.acc(y));", LN, False, nodsp))
        A.append((f"l{t}_mxfp4", 32,
            "  wire signed [4:0] wv;\n"
            "  mxfp4_decode d (.code(lf[3:0]), .w(wv));\n"
            "  mac_lane #(.WW(5),.AW(8),.ACC(32)) u (.clk(clk),.rst_n(rst_n),"
            ".w(wv),.a(lf[23:16]),.acc(y));", MX + LN, False, nodsp))
        for B in (6, 10):
            W = B + 2
            A.append((f"l{t}_cb{B}", 32,
                f"  wire signed [{W-1}:0] wv;\n"
                f"  cb4_decode_b{B} d (.code(lf[3:0]), .w(wv));\n"
                f"  mac_lane #(.WW({W}),.AW(8),.ACC(32)) u (.clk(clk),.rst_n(rst_n),"
                f".w(wv),.a(lf[23:16]),.acc(y));",
                [f"cb4_decode_b{B}.v"] + LN, False, nodsp))
    # ---- 3. a whole 32-element block, to settle amortisation ---------------
    SP = ("  wire [127:0] cds = {lf[63:0], lf[63:0]} ^ {64'h0F0F_0F0F_0F0F_0F0F, lf[31:0], lf[63:32]};\n"
          "  wire [255:0] act = {cds, cds} ^ {128'h0, lf[63:0], lf[63:0]};\n")
    A.append(("b_scale", 40,
        "  reg signed [31:0] bv; always @(posedge clk) bv <= !rst_n ? 32'b0 : lf[31:0];\n"
        "  blk_scale #(.ACC(32),.OUT(40)) u (.clk(clk),.rst_n(rst_n),.blk(bv),"
        ".e8m0(lf[39:32]),.emax(lf[47:40]),.y(y));", ["blk_scale.v"], False, True))
    A.append(("b_mxfp4", 40, SP +
        "  blk32_mxfp4 u (.clk(clk),.rst_n(rst_n),.codes(cds),.acts(act),"
        ".e8m0(lf[39:32]),.emax(lf[47:40]),.y(y));",
        BLK + MX + ["cb4_decode_b10.v"], False, True))
    A.append(("b_cb10", 40, SP +
        "  blk32_cb #(.WW(12)) u (.clk(clk),.rst_n(rst_n),.codes(cds),.acts(act),"
        ".e8m0(lf[39:32]),.emax(lf[47:40]),.y(y));",
        BLK + MX + ["cb4_decode_b10.v"], False, True))
    for WW in (5, 12):
        A.append((f"b_raw{WW}", 40,
            f"  wire [{32*WW-1}:0] wss = {{{(32*WW)//64 + 1}{{lf[63:0]}}}};\n" + SP +
            f"  blk32_raw #(.WW({WW})) u (.clk(clk),.rst_n(rst_n),.ws(wss),.acts(act),"
            ".e8m0(lf[39:32]),.emax(lf[47:40]),.y(y));",
            BLK + MX + ["cb4_decode_b10.v"], False, True))
    return A

if __name__ == "__main__":
    import concurrent.futures as cf
    only = sys.argv[1] if len(sys.argv) > 1 else ""
    A = [a for a in arms() if not only or a[0].startswith(only)]
    print(f"{len(A)} arms, 5 seeds each", flush=True)
    res = {}
    with cf.ThreadPoolExecutor(max_workers=5) as ex:
        futs = {ex.submit(run, *a): a[0] for a in A}
        for fu in cf.as_completed(futs):
            r = fu.result()
            res[r["name"]] = r
            if "error" in r:
                print(f"{r['name']:12s} ERROR {r['error']}", flush=True)
            else:
                print(f"{r['name']:12s} LUT={r.get('lut',0):5d} FF={r.get('ff',0):5d} "
                      f"CARRY={r.get('carry',0):4d} DSP={r.get('dsp',0):3d} "
                      f"Fmed={r.get('fmed',0):8.2f} spread={100*r.get('fspread',0):5.1f}%",
                      flush=True)
            json.dump(res, open(os.path.join(HERE, "results.json"), "w"), indent=1)
