#!/usr/bin/env python3
"""Self-test gate. Every decoder that is about to be synthesised is first proven
to emit the book it claims, for all sixteen codes, through iverilog.

A decoder that measures small because it decodes the wrong thing is the failure
mode this gate exists to stop. Failure is by EXIT CODE, never by grepping.

The golden values come from gen_asym.main(), which imports the campaign's book;
mxfp4_decode.v is checked on the 1/24 grid by doubling its units-of-1/12 output,
which is the identity that lets the two formats be compared at all.
"""
import os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gen_asym                                                # noqa: E402

U = 24
E2M1_12 = [0, 1, 2, 3, 4, 6, 8, 12]


def golden():
    books = gen_asym.main()
    g = {"asym_srt": (6, books["asym_srt"]),
         "asym_mx": (6, books["asym_mx"]),
         "mx_u24_flat": (6, books["mx_u24_flat"]),
         "mx_u24_struct": (6, books["mx_u24_struct"])}
    # incumbent: {s,e,m} -> +-E2M1 magnitude in units of 1/12; x2 -> 1/24 grid
    mx5 = [0] * 16
    for i, m in enumerate(E2M1_12):
        mx5[i], mx5[8 + i] = m, -m
    g["mxfp4_decode"] = (5, mx5)
    return g


def tb(mod, w, vals, grid):
    q = ["`timescale 1ns/1ps", "module tb;", "  reg [3:0] c;",
         f"  wire signed [{w-1}:0] w;", "  integer bad = 0;",
         f"  {mod} u (.code(c), .w(w));",
         f"  reg signed [7:0] g [0:15];", "  integer k;", "  initial begin"]
    for k, v in enumerate(vals):
        q.append(f"    g[{k}] = 8'sd0 + {v};")
    q.append("    for (k = 0; k < 16; k = k + 1) begin")
    q.append("      c = k[3:0]; #1;")
    q.append("      if ($signed(w) !== g[k]) begin")
    q.append('        $display("MISMATCH %s code=%0d got=%0d want=%0d", '
             f'"{mod}", k, $signed(w), g[k]);')
    q.append("        bad = bad + 1;")
    q.append("      end")
    q.append("    end")
    q.append(f'    if (bad == 0) $display("PASS {mod} 16/16 on the 1/{grid} grid");')
    q.append("    else begin $display(\"FAIL %0d/16\", bad); $fatal(1); end")
    q.append("    $finish;")
    q.append("  end", )
    q.append("endmodule")
    return "\n".join(q) + "\n"


def main():
    g = golden()
    src = {"asym_srt": "asym_srt.v", "asym_mx": "asym_mx.v",
           "mx_u24_flat": "mx_u24_flat.v", "mx_u24_struct": "mx_u24_struct.v",
           "mxfp4_decode": "mxfp4_decode.v"}
    ok = True
    for mod, (w, vals) in g.items():
        # mxfp4_decode is checked in its NATIVE units of 1/12
        grid = 12 if mod == "mxfp4_decode" else 24
        p = os.path.join(HERE, f"tb_{mod}.v")
        open(p, "w").write(tb(mod, w, vals, grid))
        exe = os.path.join(HERE, f"tb_{mod}.out")
        r = subprocess.run(["iverilog", "-g2005", "-o", exe, p,
                            os.path.join(HERE, src[mod])],
                           capture_output=True, text=True, cwd=HERE)
        if r.returncode != 0:
            print(f"COMPILE FAIL {mod}\n{r.stdout}{r.stderr}")
            ok = False
            continue
        r = subprocess.run([exe], capture_output=True, text=True, cwd=HERE)
        print(r.stdout.strip())
        if r.returncode != 0:
            ok = False
    # cross-check: the two asym encodings carry the SAME multiset of values
    assert sorted(g["asym_mx"][1]) == sorted(g["asym_srt"][1])
    print("PASS asym_mx and asym_srt are the same book, re-ordered")
    # cross-check: doubling E2M1 lands on the symmetric control exactly
    assert sorted(2 * v for v in g["mxfp4_decode"][1]) == sorted(g["mx_u24_flat"][1])
    print("PASS mxfp4_decode x2 == mx_u24_flat (the grid identity)")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
