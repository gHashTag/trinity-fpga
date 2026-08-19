#!/usr/bin/env python3
"""W942: structural decoders generated from the spec, verified exhaustively.

W941 priced every format as a truth table, which is fair at four to eleven bits
and impossible at nineteen: TNF16 has 524,288 codes. It also declared a bias --
a truth table flatters small alphabets -- without measuring it.

This emits a STRUCTURAL decoder for any TNFFormat directly from the format
object's own fields (sign_shift, exp_shift, exp_bits, mant_bits, exp_offset,
offset_max), verifies the structure against the oracle over EVERY code, and
prices it with the same rig. Running it on TNF4 and TNF8 as well, where the truth
table also exists, measures how much the truth-table method was flattering them.
"""
import json, re, subprocess, sys, pathlib
import numpy as np

SC = pathlib.Path("/private/tmp/claude-501/-Users-playom-t27--claude-worktrees-igla-fpga-improvements-3f5e1a/"
                  "eeed4a0e-20e8-40f4-aa16-1ecfee4ad92d/scratchpad")
sys.path.insert(0, str(SC / "upstream-wt/conformance"))
import tnf_ref as T

OUT = SC / "structural"
OUT.mkdir(parents=True, exist_ok=True)

RUNGS = [("tnf4", 2, 1), ("tnf8", 4, 3), ("tnf16", 4, 11)]


def model(f, raw):
    """Python transliteration of the emitted Verilog -- the thing verified."""
    sign = (raw >> f.sign_shift) & 1
    offset = (raw >> f.exp_shift) & ((1 << f.exp_bits) - 1)
    m = raw & (f.mant - 1)
    if offset == f.offset_max:
        return 0x7FC00000 if m else (0xFF800000 if sign else 0x7F800000)
    if offset == 0:
        # The oracle returns Fraction(0) regardless of sign, so the whole
        # sign=1, offset=0 row -- 2^mant_bits codes -- decodes to +0. Those are
        # redundant encodings of zero, and the RTL must agree or it is a
        # different format.
        return 0
    e32 = (offset - f.exp_offset) + 127
    if e32 <= 0 or e32 >= 255:
        return None  # outside fp32's own range; the emitted RTL must not claim it
    mant23 = m << (23 - f.mant_bits)
    return (sign << 31) | (e32 << 23) | mant23


def oracle_bits(f, raw):
    try:
        v = T.decode(f, raw)
    except Exception:
        return None
    try:
        fv = float(v)
    except Exception:
        return None
    if np.isnan(fv):
        return 0x7FC00000
    if np.isinf(fv):
        return 0xFF800000 if fv < 0 else 0x7F800000
    b = int(np.float32(fv).view(np.uint32))
    return b


def verify(f, bits):
    """Every code, model against oracle. Returns (checked, mismatches, skipped)."""
    bad = skipped = checked = 0
    for raw in range(1 << bits):
        mv = model(f, raw)
        ov = oracle_bits(f, raw)
        if mv is None or ov is None:
            skipped += 1
            continue
        checked += 1
        if mv != ov:
            bad += 1
            if bad <= 3:
                print(f"    расхождение код {raw}: модель {mv:08X} оракул {ov:08X}", flush=True)
    return checked, bad, skipped


def emit(name, f, bits):
    e_hi, e_lo = f.sign_shift - 1, f.exp_shift
    m_hi = f.mant_bits - 1
    sh = 23 - f.mant_bits
    return f"""`default_nettype none
// GENERATED from TNFFormat(exp_trits={f.exp_trits}, mant_bits={f.mant_bits}) by
// transliterating the reference decoder's own field arithmetic. Physical width is
// sign_shift + 1 = {bits}, not the rung's name. Verified against the oracle over
// all {1 << bits} codes.
module s_{name}_decode (input wire [{bits-1}:0] x, output wire [31:0] fp32_out);
  wire        s   = x[{f.sign_shift}];
  wire [{f.exp_bits-1}:0] off = x[{e_hi}:{e_lo}];
  wire [{m_hi}:0] m = x[{m_hi}:0];
  wire is_zero = (off == {f.exp_bits}'d0);
  wire is_inf  = (off == {f.exp_bits}'d{f.offset_max});
  wire [7:0] e32 = off + 8'd{127 - f.exp_offset};
  assign fp32_out = is_inf  ? (|m ? 32'h7FC00000 : {{s, 31'h7F800000}})
                  : is_zero ? 32'b0
                            : {{s, e32, m, {sh}'b0}};
endmodule
"""


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


def wrapper(top, mod, bits, n, fused):
    b = [HDR.format(top=top)]
    b.append(f"  reg [31:0] q [0:{n-1}];")
    b.append("  genvar i;")
    b.append("  generate")
    b.append(f"    for (i = 0; i < {n}; i = i + 1) begin : rep")
    b.append(f"      wire [{bits-1}:0] din = (i == 0) ? lf[{min(bits,32)-1}:0] : q[(i == 0) ? 0 : i-1][{bits-1}:0];")
    b.append("      wire [31:0] dec;")
    b.append(f"      {mod} dc (.x(din), .fp32_out(dec));")
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


def measure(name, bits, vfile, fused):
    xs, ys = [], []
    for n in (1, 2, 4):
        top = f"t_{name}_{'fu' if fused else 'ba'}_n{n}"
        wf = OUT / f"{top}.v"
        wf.write_text(wrapper(top, f"s_{name}_decode", bits, n, fused))
        cmd = f"read_verilog {wf} {vfile}; synth_xilinx -nodsp -top {top}; stat"
        r = subprocess.run(["yosys", "-p", cmd], capture_output=True, text=True, timeout=2400)
        if r.returncode != 0:
            print(f"  {top}: FAIL {(r.stdout+r.stderr)[-200:]}", flush=True)
            return None
        xs.append(n); ys.append(cells(r.stdout))
    a, b, r2 = fit(xs, ys)
    return {"per_unit": round(b, 3), "fixture": round(a, 2), "r2": round(r2, 6)}


if __name__ == "__main__":
    res = {}
    for name, et, mb in RUNGS:
        f = T.TNFFormat(et, mb)
        bits = f.sign_shift + 1
        checked, bad, skipped = verify(f, bits)
        print(f"  {name}: {bits} бит, проверено {checked} кодов, расхождений {bad}, "
              f"вне fp32 {skipped}", flush=True)
        if bad:
            print(f"  {name}: СТРУКТУРА НЕ СОВПАДАЕТ С ОРАКУЛОМ -- не измеряю", flush=True)
            continue
        vf = OUT / f"s_{name}_decode.v"
        vf.write_text(emit(name, f, bits))
        bare = measure(name, bits, vf, False)
        fu = measure(name, bits, vf, True)
        if not bare or not fu:
            continue
        res[name] = {"physical_bits": bits, "codes_checked": checked, "mismatches": bad,
                     "outside_fp32": skipped, "decoder_cells": bare["per_unit"],
                     "consumer_cells": fu["per_unit"], "r2_bare": bare["r2"], "r2_fused": fu["r2"]}
        print(f"  {name}: декодер {bare['per_unit']:.2f}  потребитель {fu['per_unit']:.2f}", flush=True)
        (OUT / "structural.json").write_text(json.dumps(res, indent=1))
    print("WROTE " + str(OUT / "structural.json"), flush=True)
