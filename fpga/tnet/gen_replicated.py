#!/usr/bin/env python3
"""W936: measure a decoder's LUT cost as the SLOPE of LUT(N), not as a difference.

The published comparison ranks formats whose cost over an empty harness is 0-2 LUT
against a one-LUT quantum. Replicating the decoder N times in a pipelined chain
multiplies the signal by N while the fixture stays fixed, so a least-squares fit of
LUT(N) = a + b*N recovers b (the per-decoder cost) with the fixture as the intercept
and an honest residual. No baseline subtraction is needed, and no shared-fixture
convention has to be argued about.

Chain, not fan-out: each replica consumes the previous replica's registered output,
so (a) inputs differ per stage and the synthesiser cannot common-subexpression them
away, (b) only the last stage needs folding into the LED, so the observation cost is
constant in N, and (c) the pipeline registers land in FF, not LUT.
"""
import re, sys, json, subprocess, pathlib

TNET = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else ".")
OUT = pathlib.Path(sys.argv[2] if len(sys.argv) > 2 else "/tmp/rep")
OUT.mkdir(parents=True, exist_ok=True)

INST = re.compile(
    r"^\s*([A-Za-z_]\w*)\s+(\w+)\s*\(\s*\.(\w+)\s*\(\s*lf\[(\d+):(\d+)\]\s*\)\s*,(.*?)\)\s*;",
    re.S | re.M)


def parse(wfile):
    """Return (decoder_module, in_port, width, rest_ports) or None."""
    src = wfile.read_text()
    m = INST.search(src)
    if not m:
        return None
    mod, _inst, port, hi, lo, rest = m.groups()
    width = int(hi) - int(lo) + 1
    extra = [p for p in re.findall(r"\.(\w+)\s*\(\s*\)", rest)]
    if "fp32_out" not in rest:
        return None
    return mod, port, width, extra


def emit(fmt, mod, port, width, extra, n):
    """One module: an LFSR, then n chained (decode -> register) stages."""
    extra_s = "".join(f", .{p}()" for p in extra)
    L = []
    L.append("`default_nettype none")
    L.append(f"module r_{fmt}_n{n} (input wire clk, input wire rst_n, output wire [3:0] led);")
    L.append("  reg [63:0] lf = 64'h1234_5678_9ABC_DEF0;")
    L.append("  always @(posedge clk) lf <= !rst_n ? 64'h1234_5678_9ABC_DEF0 :")
    L.append("                                       {lf[62:0], lf[63]^lf[62]^lf[60]^lf[59]};")
    L.append(f"  wire [31:0] o [0:{n - 1}];")
    L.append(f"  reg  [31:0] q [0:{n - 1}];")
    L.append("  genvar i;")
    L.append("  generate")
    L.append(f"    for (i = 0; i < {n}; i = i + 1) begin : rep")
    L.append(f"      wire [{width - 1}:0] din = (i == 0) ? lf[{width - 1}:0] : q[(i == 0) ? 0 : i - 1][{width - 1}:0];")
    L.append(f"      {mod} dec (.{port}(din), .fp32_out(o[i]){extra_s});")
    L.append("      always @(posedge clk) q[i] <= !rst_n ? 32'b0 : o[i];")
    L.append("    end")
    L.append("  endgenerate")
    last = f"q[{n - 1}]"
    L.append(f"  assign led = {last}[3:0] ^ {last}[7:4] ^ {last}[11:8] ^ {last}[15:12] ^")
    L.append(f"               {last}[19:16] ^ {last}[23:20] ^ {last}[27:24] ^ {last}[31:28];")
    L.append("endmodule")
    return "\n".join(L) + "\n"


def deps(mod):
    """Every .v in tnet that might define mod or its submodules -- yosys prunes the rest."""
    hits = [p for p in TNET.glob("*.v")
            if re.search(rf"^\s*module\s+{re.escape(mod)}\b", p.read_text(), re.M)]
    return hits


def luts(logtext):
    """LUT and MUXF counts from the final `stat` block."""
    tail = logtext.rsplit("Printing statistics.", 1)[-1]
    n_lut = sum(int(m.group(1)) for m in re.finditer(r"^\s+(\d+)\s+LUT[1-6]\b", tail, re.M))
    n_mux = sum(int(m.group(1)) for m in re.finditer(r"^\s+(\d+)\s+MUXF[78]\b", tail, re.M))
    n_ff = sum(int(m.group(1)) for m in re.finditer(r"^\s+(\d+)\s+FD[RS]E\b", tail, re.M))
    # CARRY4 is not a LUT but it is area, and a constant-add decoder lands entirely
    # in it: counting LUTs alone reported such a decoder as costing zero.
    n_cy = sum(int(m.group(1)) for m in re.finditer(r"^\s+(\d+)\s+CARRY4\b", tail, re.M))
    return n_lut, n_mux, n_ff, n_cy


def synth(fmt, mod, n, vfile):
    srcs = " ".join(str(p) for p in [vfile] + deps(mod))
    top = f"r_{fmt}_n{n}"
    cmd = f"read_verilog {srcs}; synth_xilinx -nodsp -top {top}; stat"
    r = subprocess.run(["yosys", "-p", cmd], capture_output=True, text=True, timeout=900)
    if r.returncode != 0:
        return None, (r.stdout + r.stderr)[-400:]
    return luts(r.stdout), None


def fit(xs, ys):
    """Least squares y = a + b x; returns (a, b, r2, max_abs_residual)."""
    n = len(xs)
    mx = sum(xs) / n
    my = sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    b = sxy / sxx
    a = my - b * mx
    ss_res = sum((y - (a + b * x)) ** 2 for x, y in zip(xs, ys))
    ss_tot = sum((y - my) ** 2 for y in ys)
    r2 = 1 - ss_res / ss_tot if ss_tot else 1.0
    resid = max(abs(y - (a + b * x)) for x, y in zip(xs, ys))
    return a, b, r2, resid


def main():
    ns = [int(x) for x in (sys.argv[3].split(",") if len(sys.argv) > 3 else "1,2,4,8".split(","))]
    only = sys.argv[4].split(",") if len(sys.argv) > 4 else None
    results = {}
    for wfile in sorted(TNET.glob("w_*.v")):
        fmt = wfile.stem[2:]
        if fmt == "baseline":
            continue
        if only and fmt not in only:
            continue
        p = parse(wfile)
        if not p:
            results[fmt] = {"status": "unparsed"}
            print(f"{fmt}: UNPARSED", flush=True)
            continue
        mod, port, width, extra = p
        xs, ys, raw = [], [], {}
        for n in ns:
            vf = OUT / f"r_{fmt}_n{n}.v"
            vf.write_text(emit(fmt, mod, port, width, extra, n))
            got, err = synth(fmt, mod, n, vf)
            if got is None:
                raw[n] = {"error": err}
                print(f"{fmt} N={n}: FAIL {err[:100]}", flush=True)
                continue
            lut, mux, ff, cy = got
            xs.append(n); ys.append(lut + cy)
            raw[n] = {"lut": lut, "muxf": mux, "ff": ff, "carry4": cy, "lut_plus_carry": lut + cy}
            print(f"{fmt} N={n}: lut={lut} carry4={cy} muxf={mux} ff={ff}", flush=True)
        if len(xs) >= 3:
            a, b, r2, resid = fit(xs, ys)
            results[fmt] = {"status": "fitted", "module": mod, "in_width": width,
                            "fixture_luts": round(a, 2), "lut_plus_carry_per_decoder": round(b, 3),
                            "r2": round(r2, 6), "max_residual_luts": round(resid, 2), "points": raw}
            print(f"  -> {fmt}: {b:.3f} (LUT+CARRY4)/decoder, fixture {a:.1f}, R2 {r2:.5f}", flush=True)
        else:
            results[fmt] = {"status": "insufficient", "points": raw}
    (OUT / "fit.json").write_text(json.dumps(results, indent=1))
    print("WROTE " + str(OUT / "fit.json"), flush=True)


if __name__ == "__main__":
    main()
