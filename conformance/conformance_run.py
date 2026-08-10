#!/usr/bin/env python3
"""Run a design against an independent reference model and report the bound.

This is the half the automated stage was missing. The five structural checks say
a design elaborates and synthesises; they compare it to nothing. Here the design
is simulated against vectors whose expected values came from a reference model
written from the operation, not from this RTL — so a defect shared between a
design and its own testbench does not survive.

The report prints N and the mismatch count, and then the thing that stops N from
being read as exhaustiveness: the bound N buys. Under Duran & Ntafos (IEEE TSE
SE-10(4), 1984), N passing independent vectors reject any per-vector failure
probability at or above 1 - (1-C)^(1/N) at confidence C.

Usage: conformance_run.py <pack.json> <rtl.v> <module> [more.v ...]
"""
import json
import re
import subprocess
import sys
from math import log
from pathlib import Path

WORK = Path("/tmp/conformance_runs")


def bound(n: int, c: float) -> float:
    """Upper bound on per-vector failure probability after n passes at confidence c."""
    return 1.0 - (1.0 - c) ** (1.0 / n)


def build_tb(module: str, width: int, vectors, tb_path: Path, vec_path: Path):
    """A testbench that reads the vectors from a file rather than embedding them.

    Embedding 100k vectors as Verilog literals makes iverilog spend minutes on
    parsing; $readmemh is the difference between a run and a coffee break.
    """
    with vec_path.open("w") as fh:
        for v in vectors:
            fh.write(f"{int(v['a'],16):0{width//4}x}{int(v['b'],16):0{width//4}x}{int(v['expected'],16):0{width//4}x}\n")
    n = len(vectors)
    tb_path.write_text(f"""
`timescale 1ns/1ps
module tb;
  localparam N = {n};
  localparam W = {width};
  reg  [3*W-1:0] mem [0:N-1];
  reg  [W-1:0] a, b;
  wire [W-1:0] result;
  reg  [W-1:0] expected;
  integer i, mismatches;

  {module} dut (.a(a), .b(b), .result(result));

  initial begin
    $readmemh("{vec_path.name}", mem);
    mismatches = 0;
    for (i = 0; i < N; i = i + 1) begin
      a        = mem[i][3*W-1 -: W];
      b        = mem[i][2*W-1 -: W];
      expected = mem[i][W-1 -: W];
      #1;
      if (result !== expected) begin
        if (mismatches < 5)
          $display("MISMATCH i=%0d a=%h b=%h got=%h want=%h", i, a, b, result, expected);
        mismatches = mismatches + 1;
      end
      #1;
    end
    $display("RESULT vectors=%0d mismatches=%0d", N, mismatches);
    $finish;
  end
endmodule
""", encoding="utf-8")


def main():
    if len(sys.argv) < 4:
        sys.exit(__doc__)
    pack_path, module = Path(sys.argv[1]), sys.argv[3]
    sources = [Path(p) for p in sys.argv[2:3] + sys.argv[4:]]
    pack = json.loads(pack_path.read_text())
    vectors = pack["vectors"]
    width = int(pack.get("width") or 16)

    WORK.mkdir(exist_ok=True)
    tb, vec = WORK / f"tb_{module}.v", WORK / f"vec_{module}.hex"
    build_tb(module, width, vectors, tb, vec)

    srcs = " ".join(f'"{s}"' for s in sources)
    out = WORK / f"{module}.vvp"
    rc = subprocess.run(f'iverilog -g2012 -o "{out}" {srcs} "{tb}"',
                        shell=True, capture_output=True, text=True)
    if rc.returncode:
        print("  COMPILE FAILED")
        print("   ", (rc.stdout + rc.stderr).strip().splitlines()[0][:200])
        return 1
    sim = subprocess.run(f'cd "{WORK}" && vvp "{out}"', shell=True,
                         capture_output=True, text=True, timeout=1800)
    log_txt = sim.stdout + sim.stderr
    m = re.search(r"RESULT vectors=(\d+) mismatches=(\d+)", log_txt)
    if not m:
        print("  NO RESULT LINE — the run did not complete")
        print("   ", log_txt.strip()[-300:])
        return 1
    n, bad = int(m.group(1)), int(m.group(2))

    print(f"  pack      : {pack_path.name}  ({pack['format']} {pack['operation']}, oracle {pack['oracle']})")
    print(f"  design    : {module} from {sources[0].name}")
    print(f"  vectors   : {n:,}")
    print(f"  mismatches: {bad:,}")
    if bad:
        for line in log_txt.splitlines():
            if line.startswith("MISMATCH"):
                print("   ", line)
    else:
        for c in (0.95, 0.99):
            b = bound(n, c)
            print(f"  bound     : per-vector failure probability < {b:.3e} "
                  f"at {int(c*100)}% confidence (about 1 in {1/b:,.0f})")
        print("  note      : a bound, not a zero — and it holds only for the "
              "distribution these vectors were drawn from")
    return 0 if bad == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
