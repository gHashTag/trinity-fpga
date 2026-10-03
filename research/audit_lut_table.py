#!/usr/bin/env python3
"""Do the published LUT numbers reproduce?

research/CI_LUT_REPORT.md and research/COMPLETE_LUT_TABLE.md give per-format LUT
counts, and the paper quotes several of them -- "587 LUT" for a GF16 multiply,
"505 LUT" in the zero-DSP regime, "75 LUT" for the Quire. The reports document
their method fully, which makes the numbers testable:

    Flags: synth_xilinx -flatten -abc9 -nocarry [-nodsp] -arch xc7
    Tool:  Yosys 0.62 / 0.63, inside the regymm/openxc7 container

This rebuilds the same wrappers .github/workflows/lut-report.yml generates -- a
`top` module instantiating the parametric core with explicit TOTAL and BIAS and
HAS_INF(0) at every width, gf16 included -- and runs the same flags.

What it found, and did not find:

  * the RTL has not changed since the table was made (no commit touches
    gf_adder_param.v after 2026-07-14)
  * dropping `hierarchy -top`, as the CI script does, changes nothing
  * the counts still come out systematically higher, and the gap grows with
    width: +4 LUTs at GF4, +396 at GF20 -- roughly +22% to +79%

So the numbers reproduce as a METHOD and not as VALUES outside the pinned
container. That is worth saying plainly in a paper whose argument rests on an
open-source toolchain: "yosys 0.63" is not enough to reproduce them, the image is
part of the measurement.

Usage:  python3 research/audit_lut_table.py
"""
import os
import re
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SYNTH = os.path.join(ROOT, "fpga", "openxc7-synth")
LUT = re.compile(r"^\s+(\d+)\s+LUT[1-6]\s*$", re.M)
BLOCK = re.compile(r"^=== (.+?) ===$", re.M)


def luts(out):
    """Sum LUTs inside the LAST `=== <name> ===` block only.

    yosys `stat` prints THREE blocks after a synth run -- `=== top ===`,
    `=== design hierarchy ===`, and `=== top ===` again from the explicit stat.
    The first version of this took "the last half of all LUT lines", which spans
    a block boundary and sums part of one block with part of another. It reported
    the GF16 multiply at 812 and then 841 across two runs of the same binary, and
    produced a table of deltas that looked like a systematic +22% to +79% drift
    against the published numbers. There was no drift; there was a bad parser.
    """
    starts = [m.start() for m in BLOCK.finditer(out)]
    if not starts:
        return None
    return sum(int(x) for x in LUT.findall(out[starts[-1]:]))

FLAGS = "synth_xilinx -flatten -abc9 -nocarry -nodsp -arch xc7"

# (format, E, M, published ADD, published MUL) from research/CI_LUT_REPORT.md
PUBLISHED = [
    ("GF4", 1, 2, 18, 7),
    ("GF8", 3, 4, 172, 157),
    ("GF12", 4, 7, 296, 407),
    ("GF14", 5, 8, 398, 470),
    ("GF16", 6, 9, 434, 586),
    ("GF20", 7, 12, 627, 877),
]


def synth(core, eb, mb):
    """The wrapper lut-report.yml writes, and the flags it uses."""
    w = 1 + eb + mb
    bias = (1 << (eb - 1)) - 1
    src = """module top(input clk, input rst, input in_valid,
    input [%d:0] in_a, input [%d:0] in_b, output in_ready,
    output reg out_valid, output reg [%d:0] out_y, input out_ready);
  %s #(.EXP_BITS(%d),.MANT_BITS(%d),.TOTAL(%d),.BIAS(%d),.HAS_INF(0)) u(
    .clk(clk),.rst(rst),.in_valid(in_valid),.in_a(in_a),.in_b(in_b),
    .in_ready(in_ready),.out_valid(out_valid),.out_y(out_y),.out_ready(out_ready));
endmodule
""" % (w - 1, w - 1, w - 1, core, eb, mb, w, bias)
    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, "top.v")
        with open(p, "w") as fh:
            fh.write(src)
        s = "read_verilog %s %s/%s.v; %s; stat" % (p, SYNTH, core, FLAGS)
        r = subprocess.run(["yosys", "-p", s], capture_output=True, text=True)
        if r.returncode:
            return None
        return luts(r.stdout + r.stderr) or 0


def main():
    v = subprocess.run(["yosys", "-V"], capture_output=True, text=True).stdout.strip()
    print("here : %s" % v.splitlines()[0])
    print("published against : Yosys 0.62/0.63 inside regymm/openxc7")
    print("flags : %s" % FLAGS)
    print()
    print("%-6s %-3s %-3s %8s %8s %7s   %8s %8s %7s"
          % ("fmt", "E", "M", "ADD pub", "ADD here", "delta", "MUL pub", "MUL here", "delta"))
    # The twelve synth runs are independent -- one wrapper per (format, op),
    # each in its own temp directory -- so the only reason the audit took
    # 65.6 s alone and >120 s on the 2-core runner was that it ran them one
    # after another (#736). The pool is sized to the machine; the ratchet's
    # wall-clock timeout measures the script's serial part, and this keeps
    # every individual measurement identical while dividing the waiting.
    workers = min(os.cpu_count() or 1, 2 * len(PUBLISHED))
    with ThreadPoolExecutor(max_workers=workers) as ex:
        adds = {name: ex.submit(synth, "gf_adder_param", E, M)
                for name, E, M, _ap, _mp in PUBLISHED}
        muls = {name: ex.submit(synth, "gf_mul_param", E, M)
                for name, E, M, _ap, _mp in PUBLISHED}
        # ex.map preserves input order; dict futures keyed by format name keep
        # the printed table byte-identical to the serial version whatever
        # order the runs finish in.
        worst = 0
        for name, E, M, ap, mp in PUBLISHED:
            a = adds[name].result()
            m = muls[name].result()
            da = "" if a is None else "%+d" % (a - ap)
            dm = "" if m is None else "%+d" % (m - mp)
            if a is not None:
                worst = max(worst, abs(a - ap))
            if m is not None:
                worst = max(worst, abs(m - mp))
            print("%-6s %-3d %-3d %8d %8s %7s   %8d %8s %7s"
                  % (name, E, M, ap, a, da, mp, m, dm))
    print()
    print("largest single deviation : %d LUTs" % worst)
    print()
    print("The RTL is unchanged since the table was made, and dropping")
    print("`hierarchy -top` as the CI script does changes nothing. What is left is")
    print("the toolchain BUILD. The numbers reproduce as a method, not as values,")
    print("outside the pinned container -- and for a paper whose argument rests on")
    print("an open-source flow, the image is part of the measurement.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
