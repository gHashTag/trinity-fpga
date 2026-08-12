#!/usr/bin/env python3
"""Count LOGIC CELLS on the mapped netlist, not LUT-BEL occupancy.

CODEBOOK_SILICON_2026-08-11.md records the trap this file exists to avoid:
nextpnr-xilinx's SLICE_LUTX line is BEL OCCUPANCY. A LUT1 buffer and a fully
used LUT6 each occupy one SLICE_LUTX, so subtracting a differently-packed
baseline compares packing, not arithmetic. The first version of that
measurement was wrong for exactly this reason.

So: run yosys to the mapped netlist and count the cells it instantiated.

Two parsing hazards, both hit while writing this file and both fixed here:
  * `yosys -q` suppresses the stat block, yielding an empty histogram and a
    confident zero rather than an error.
  * yosys 0.65 prints the "Local Count" table, not the older
    "Number of cells:" block. A parser written for the old format silently
    matches nothing.
The self-test at the bottom exists so neither can recur undetected.
"""
import os, re, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__))

LUTS = ("LUT1", "LUT2", "LUT3", "LUT4", "LUT5", "LUT6", "LUT6_2")
FFS  = ("FDRE", "FDSE", "FDCE", "FDPE", "FDRE_1")
# IBUF/OBUF are pads, not logic, and are excluded everywhere below.
PADS = ("IBUF", "OBUF", "BUFG", "OBUFT", "IOBUF")
# $scopeinfo is yosys hierarchy METADATA emitted by -flatten. It is not a cell
# on the die. Listed explicitly so the unknown-cell guard stays strict.
META = ("$scopeinfo",)


def raw(srcs, top, nodsp=True, flatten=True):
    flags = ("-flatten " if flatten else "") + ("-nodsp " if nodsp else "")
    cmd = ["yosys", "-p",
           f"read_verilog {' '.join(srcs)}; synth_xilinx {flags}-top {top}; stat"]
    r = subprocess.run(cmd, cwd=HERE, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"yosys exit {r.returncode} for {top}\n{r.stdout[-3000:]}\n{r.stderr[-3000:]}")
    return r.stdout + r.stderr


def parse(out, top):
    """Cell histogram of module `top` from a yosys 0.65 stat table.

    synth_xilinx prints an INTERNAL stat partway through, where CARRY4 is still
    a submodule rather than a mapped cell, followed by a '=== design hierarchy
    ===' roll-up. Only the FINAL explicit `stat` describes the netlist that
    actually ships, so that is the block taken. The declared cell total is
    cross-checked against the histogram sum: a parser that silently reads the
    wrong block, or stops early, fails loudly instead of returning a number.
    """
    lines = out.splitlines()
    idx = [k for k, l in enumerate(lines) if l.strip() == f"=== {top} ==="]
    if not idx:
        raise RuntimeError(f"stat block for '{top}' not found")
    i = idx[-1]                                   # the final, post-map stat
    j = next((k for k in range(i + 1, len(lines))
              if re.match(r"^\s+\d+\s+cells\s*$", lines[k])), None)
    if j is None:
        raise RuntimeError(f"cell table for '{top}' not found")
    total = int(re.match(r"^\s+(\d+)\s+cells\s*$", lines[j]).group(1))
    cells = {}
    for l in lines[j + 1:]:
        if re.match(r"^\s+\d+\s+submodules\s*$", l):
            # -flatten should leave none; if one appears the count is not flat
            # and the comparison would be against a different object.
            raise RuntimeError(f"unflattened submodule in final stat for {top}")
        m = re.match(r"^\s+(\d+)\s+(\S+)\s*$", l)
        if not m:
            break
        cells[m.group(2)] = cells.get(m.group(2), 0) + int(m.group(1))
    got = sum(cells.values())
    if got != total:
        raise RuntimeError(f"histogram {got} != declared {total} for {top}")
    return cells


def summarise(cells):
    known = set(LUTS) | set(FFS) | set(PADS) | set(META) | {"CARRY4", "DSP48E1", "MUXF7",
                                                "MUXF8", "RAM32X1D", "RAM64X1D",
                                                "RAM32M", "RAM64M", "SRL16E",
                                                "SRLC32E", "RAMB18E1", "RAMB36E1",
                                                "INV", "BUFGCTRL"}
    unknown = {k: v for k, v in cells.items() if k not in known}
    return {
        "lut":   sum(cells.get(k, 0) for k in LUTS),
        "carry": cells.get("CARRY4", 0),
        "ff":    sum(cells.get(k, 0) for k in FFS),
        "dsp":   cells.get("DSP48E1", 0),
        "muxf":  cells.get("MUXF7", 0) + cells.get("MUXF8", 0),
        "unknown": unknown,
        "cells": {k: v for k, v in sorted(cells.items())
                  if k not in PADS and k not in META},
    }


def logic(srcs, top, nodsp=True, flatten=True):
    return summarise(parse(raw(srcs, top, nodsp, flatten), top))


if __name__ == "__main__":
    # SELF-TEST: the parser must reproduce the published corrected figures.
    exp = {"mxfp4_decode": (9, 2, 0), "cb4_decode_b6": (15, 2, 0),
           "cb4_decode_b10": (22, 3, 0)}
    ok = True
    for top, e in exp.items():
        src = top + ".v"
        r = logic([src], top)
        got = (r["lut"], r["carry"], r["ff"])
        good = got == e
        ok &= good
        print(f"{top:16s} LUT={r['lut']:3d} CARRY4={r['carry']:2d} FF={r['ff']:2d}"
              f"   published {e}  {'MATCH' if good else 'MISMATCH'}")
        print(f"{'':16s} {r['cells']}")
        if r["unknown"]:
            print(f"{'':16s} UNKNOWN CELLS {r['unknown']}")
    print("PUBLISHED-BASELINE REPRODUCTION:", "PASS" if ok else "FAIL")
    sys.exit(0 if ok else 1)
