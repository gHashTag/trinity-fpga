#!/usr/bin/env python3
"""W941: generate every decoder from its own reference oracle, exhaustively.

The frontier's one row where TNF wins -- four bits -- has no price, because no
4-bit TNF decoder exists in the tree. Hand-writing one would reintroduce exactly
the defect this project spent three waves criticising: a comparison in which every
baseline is the author's own implementation.

So generate them all the same way. For an alphabet of n bits there are 2^n codes;
enumerate them through the shipped conformance oracle, emit the result as a
Verilog case statement, and let the synthesiser do what it likes with the truth
table. Every format then gets identical treatment, the decoder is conformant by
construction (the enumeration IS the oracle), and no implementation-quality
difference can enter the comparison.

Cost of the method, stated up front: a truth-table decoder is not how a wide
format would be built in practice, so this is fair for small alphabets and
increasingly unfair to wide ones as n grows. Rows above ten bits are omitted for
that reason rather than for runtime.
"""
import json, re, subprocess, sys, pathlib
import numpy as np

SC = pathlib.Path(_envos.environ.get("T27_WORK") or pathlib.Path(__file__).resolve().parent)
import os
sys.path.insert(0, os.environ.get("T27_CONFORMANCE") or str(pathlib.Path(__file__).resolve().parent / "oracles"))
import tnf_ref as T, gf_ref as G, posit_ref as P, fp8_ref as F8

OUT = SC / "oracle_rtl"
OUT.mkdir(parents=True, exist_ok=True)

# (name, physical bits, encode/decode pair). Physical width, not the nominal name:
# TNF4 is E_t=2 trits -> 4 exponent cells + sign + 1 mantissa = 6 bits.
# W963: this list is the substitution itself. "tnf8" was bound to TNFFormat(4, 3) --
# 11 bits, 126.91 binades, TNF16's exponent field with a cut mantissa -- while the
# ladder defines the eighth rung as TNFFormat(3, 4): 10 bits, 30.95 binades. Every
# census figure published for TNF8 priced the substitute. Both are measured here,
# against floats of each one's own physical width, so the substitution has a number
# in this project's ORIGINAL metric rather than only in the MAC-lane one.
_Fx = F8.FPxFormat
UNITS = [
    ("tnf8_ladder_10b", 10, lambda: (T, T.TNFFormat(3, 4))),
    ("fp10_e5m4", 10, lambda: (F8, _Fx("fp10_e5m4", 5, 4, 15))),
    ("tnf8_as_measured_11b", 11, lambda: (T, T.TNFFormat(4, 3))),
    ("fp11_e6m4", 11, lambda: (F8, _Fx("fp11_e6m4", 6, 4, 31))),
]


def fp32_bits(x):
    if x is None:
        return 0
    try:
        f = float(x)
    except Exception:
        return 0
    if not np.isfinite(f):
        return 0x7F800000
    return int(np.float32(f).view(np.uint32))


def table(mod, fmt, bits):
    """Exhaustive code -> fp32 bit pattern, straight through the oracle."""
    rows = []
    seen_negative = False
    for code in range(1 << bits):
        try:
            v = mod.decode(fmt, code)
        except Exception:
            v = None
        rows.append(fp32_bits(v))
        try:
            seen_negative = seen_negative or float(v) < 0
        except Exception:
            pass
    assert seen_negative, "table has no negative values: the sign bit was not enumerated"
    return rows


def emit(name, bits, rows):
    L = ["`default_nettype none",
         f"// GENERATED from the conformance oracle by exhaustive enumeration of all",
         f"// {1 << bits} codes. Conformant by construction; no hand optimisation.",
         f"module o_{name}_decode (input wire [{bits-1}:0] x, output reg [31:0] fp32_out);",
         "  always @(*) case (x)"]
    for code, val in enumerate(rows):
        L.append(f"    {bits}'d{code}: fp32_out = 32'h{val:08X};")
    L.append("    default: fp32_out = 32'h00000000;")
    L.append("  endcase")
    L.append("endmodule")
    return "\n".join(L) + "\n"


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
    b.append(f"      wire [{bits-1}:0] din = (i == 0) ? lf[{bits-1}:0] : q[(i == 0) ? 0 : i-1][{bits-1}:0];")
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
    mod = f"o_{name}_decode"
    xs, ys = [], []
    for n in (1, 2, 4):
        top = f"m_{name}_{'fu' if fused else 'ba'}_n{n}"
        wf = OUT / f"{top}.v"
        wf.write_text(wrapper(top, mod, bits, n, fused))
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
    for name, bits, get in UNITS:
        mod, fmt = get()
        rows = table(mod, fmt, bits)
        distinct = len(set(rows))
        vf = OUT / f"o_{name}_decode.v"
        vf.write_text(emit(name, bits, rows))
        bare = measure(name, bits, vf, False)
        fu = measure(name, bits, vf, True)
        if not bare or not fu:
            continue
        res[name] = {"physical_bits": bits, "codes": 1 << bits, "distinct_values": distinct,
                     "decoder_cells": bare["per_unit"], "consumer_cells": fu["per_unit"],
                     "multiply_alone": round(fu["per_unit"] - bare["per_unit"], 3),
                     "r2_bare": bare["r2"], "r2_fused": fu["r2"]}
        print(f"  {name:10} {bits:2}b  различных значений {distinct:5}  "
              f"декодер {bare['per_unit']:8.2f}  потребитель {fu['per_unit']:9.2f}", flush=True)
        (OUT / "census_tnf8_w963.json").write_text(json.dumps(res, indent=1))
    print("WROTE " + str(OUT / "census_tnf8_w963.json"), flush=True)
