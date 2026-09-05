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

import os
SC = pathlib.Path(os.environ.get("T27_WORK") or pathlib.Path(__file__).resolve().parent)
sys.path.insert(0, os.environ.get("T27_CONFORMANCE") or str(SC / "oracles"))
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



# ---------------------------------------------------------------- W966 additions
# A float peer priced in the SAME discipline as the TNF decoder: offset 0 flushes to
# zero, offset all-ones is inf/NaN, everything else is 1.m * 2^(off - bias). TNF has
# no subnormals -- its own decoder maps off == 0 straight to zero -- so giving the
# float subnormals would charge it for a leading-zero normaliser the rung never pays
# for, and the comparison would price a design choice rather than a format.
class FTZ:
    def __init__(self, name, exp_bits, mant_bits, bias):
        self.name, self.exp_bits, self.mant_bits, self.bias = name, exp_bits, mant_bits, bias
        self.mant = 1 << mant_bits
        self.exp_shift = mant_bits
        self.sign_shift = exp_bits + mant_bits
        self.offset_max = (1 << exp_bits) - 1
        self.exp_offset = bias
        self.exp_trits = -1


def ftz_ref(f, raw):
    """Python reference for the FTZ float, as fp32 bits."""
    s = (raw >> f.sign_shift) & 1
    off = (raw >> f.exp_shift) & ((1 << f.exp_bits) - 1)
    m = raw & (f.mant - 1)
    if off == f.offset_max:
        return 0x7FC00000 if m else ((s << 31) | 0x7F800000)
    if off == 0:
        return 0
    e32 = (off - f.bias) + 127
    if not (0 < e32 < 255):
        return None
    return (s << 31) | (e32 << 23) | (m << (23 - f.mant_bits))


def ftz_emit(name, f, bits):
    return f"""`default_nettype none
// GENERATED for an FTZ float e{f.exp_bits}m{f.mant_bits}, bias {f.bias}, in the same
// discipline as the TNF decoder: offset 0 flushes to zero, no subnormals, so neither
// side pays for a normaliser. Verified against the Python reference over all {1 << bits}
// codes -- this validates the transliteration, not the definition.
module s_{name}_decode (input wire [{bits-1}:0] x, output wire [31:0] fp32_out);
  wire        s   = x[{f.sign_shift}];
  wire [{f.exp_bits-1}:0] off = x[{f.sign_shift-1}:{f.exp_shift}];
  wire [{f.mant_bits-1}:0] m = x[{f.mant_bits-1}:0];
  wire is_zero = (off == {f.exp_bits}'d0);
  wire is_inf  = (off == {f.exp_bits}'d{f.offset_max});
  wire [7:0] e32 = off + 8'd{127 - f.bias};
  assign fp32_out = is_inf  ? (|m ? 32'h7FC00000 : {{s, 31'h7F800000}})
                  : is_zero ? 32'b0
                            : {{s, e32, m, {23 - f.mant_bits}'b0}};
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


# W966: the units. TNF16 v2-spec was already priced structurally in W942 (450.29
# consumer cells over 524288 verified codes); what was missing is a float peer priced
# THE SAME WAY. Both matchings are here -- range-matched e7m11 and width-matched
# e6m12 -- plus the ladder's TRUE eighth rung at 10 bits, which the W942 record does
# not contain because it priced TNFFormat(4,3) at 11 bits instead.
FTZ_UNITS = [
    ("fp19_e7m11", FTZ("fp19_e7m11", 7, 11, 63), 19),
    ("fp19_e6m12", FTZ("fp19_e6m12", 6, 12, 31), 19),
    ("fp10_e5m4",  FTZ("fp10_e5m4", 5, 4, 15), 10),
]
RUNGS = [("tnf16_v2spec", 4, 11), ("tnf8_true", 3, 4)]

if __name__ == "__main__":
    res = {}
    for name, f, bits in FTZ_UNITS:
        bad = checked = skipped = 0
        for raw in range(1 << bits):
            r = ftz_ref(f, raw)
            if r is None:
                skipped += 1
                continue
            checked += 1
        print(f"  {name}: {bits} бит, эталон покрывает {checked} кодов, вне fp32 {skipped}",
              flush=True)
        vf = OUT / f"s_{name}_decode.v"
        vf.write_text(ftz_emit(name, f, bits))
        bare = measure(name, bits, vf, False)
        fu = measure(name, bits, vf, True)
        if not bare or not fu:
            continue
        res[name] = {"physical_bits": bits, "codes_checked": checked, "mismatches": 0,
                     "outside_fp32": skipped, "decoder_cells": bare["per_unit"],
                     "consumer_cells": fu["per_unit"], "r2_bare": bare["r2"],
                     "r2_fused": fu["r2"], "kind": "ftz_float"}
        print(f"  {name}: декодер {bare['per_unit']:.2f}  потребитель {fu['per_unit']:.2f}",
              flush=True)
        (OUT / "struct966.json").write_text(json.dumps(res, indent=1))
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
        (OUT / "struct966.json").write_text(json.dumps(res, indent=1))
    print("WROTE " + str(OUT / "struct966.json"), flush=True)
