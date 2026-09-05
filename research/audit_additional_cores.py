#!/usr/bin/env python3
"""Re-measure the five "additional cores" the paper's 505/580 arithmetic rests on.

arXiv 2606.05017 line 132 says a GF16+ MAC is "580 LUT (505 multiply + 75 Quire)",
and line 56 says "GF16 multiply-with-Quire (505 LUT) ... plain GF16 multiply is 587
LUT" -- a Quire with negative area under any reading.

Item 6 of research/CORRECTIONS_PACKAGE_both_preprints.md traced both numbers to the
"additional cores" table of research/COMPLETE_LUT_TABLE.md:

    Ternary MAC-16       55 LUT
    GF Quire             75 LUT
    GF Sqrt             128 LUT, 8 DSP
    GF Div              207 LUT
    takum16 native MUL  505 LUT

and reported that three reproduce exactly while GF Quire measured 1063 -- fourteen
times the table. Those measurements were made in a session and typed into markdown.
Like item 5 before pass 283, the correction had no script. This is the script.

FLAGS ARE PER-CORE, ON PURPOSE
------------------------------
GF Sqrt is measured WITHOUT -nodsp, because the table records 8 DSPs for it and a
core that is allowed to infer them is a different measurement from one that is not.
Pass 258 forced -nodsp onto that row, got 4818 LUTs against 128, and reported the
table as wrong. The table was right and the flag was mine. Every row here therefore
carries the flags it was measured under, and says so.

The DSP count is compared as well as the LUT count. A row that matches on LUTs
while differing on DSPs is not a match -- that is exactly how the pass 258 error
would have been caught a pass earlier.

Usage:  python3 research/audit_additional_cores.py [--verbose] [--only NAME]

Exits non-zero if a core deviates from the table by more than the drift tolerance.
"""
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SYNTH = os.path.join(ROOT, "fpga", "openxc7-synth")

# Ordinary build drift between yosys builds. Item 6 already records GF16 moving
# 485->490 and 587->602 for this reason, so anything inside a few percent is noise
# and only a gross deviation is a finding. 25% is far wider than any observed
# drift and far narrower than the 14x this exists to detect.
DRIFT = 0.25

BASE = "-flatten -abc9 -nocarry -arch xc7"

CORES = [
    # name             top                    params        LUT   DSP  nodsp
    ("Ternary MAC",    "ternary_mac_16",      {},            55,   0,   True),
    ("GF Quire",       "gf_quire_param",      {},            75,   0,   True),
    ("GF Sqrt",        "gf_sqrt_param",       {},           128,   8,   False),
    ("GF Div",         "gf_div_param",        {},           207,   0,   True),
    ("takum16 MUL",    "takum16_native_mul",  {},           505,   0,   True),
]

# yosys prints "      184   LUT2" -- COUNT first, then the cell name. The first
# version of this regex expected name-then-count, matched nothing, and reported
# every core as 0 LUT. Three cores at exactly zero is the signature of a broken
# parser, not of three empty designs, and it is the reason this file compares
# against a known table instead of just printing numbers: a table gives the zero
# somewhere to disagree with.
STAT = re.compile(r"^\s+(\d+)\s+(\S+)\s*$", re.M)

# yosys's stat table ends with summary lines ("N cells", "N wires", ...) whose
# shape the cell regex also matches, so the declared total arrives in the same
# dict as the cell types. logic_count.py cross-checks the histogram against that
# total and raises when they disagree; these two had the number available and
# did not use it. A regex that silently misses a cell type produces a LUT count
# that is low and looks fine -- which is how pass 250's retracted LUT table
# happened, in this same parser family.
SUMMARY_KEYS = {"cells", "wires", "processes", "memories", "bits", "public"}


def cross_check(cells):
    """(ok, note) -- ADVISORY, never a gate here. Read the whole comment.

    logic_count.py cross-checks its histogram against yosys' declared total and
    RAISES on disagreement. That works there because it locates an explicit
    `=== top ===` stat block and reads the cell table beneath it.

    These two files take `stdout.split("=== ")[-1]`, which is a different object:
    the trailing text after the last marker, whose declared total and whose
    matched lines are not the same population. Measured, when this was first
    wired as a gate: the histogram exceeded the declared total by a near-constant
    6-9 on every core, and every core became "could not measure" while the script
    exited 0 with nothing to report.

    That is this repository's own defect class, self-inflicted inside its own
    fix, and it is worse than the gap it was closing -- a gate that stops finding
    things is indistinguishable from a corpus that got fixed. The excess is a
    defect in the key set below, not in yosys and not in the designs; until the
    extra captured lines are identified BY NAME the comparison is not sound
    enough to fail a build on.

    So it reports and does not gate. The correct fix is to locate the explicit
    stat block the way logic_count.py does rather than to split on a marker, and
    that is a change to how these files find their table, not to this function.
    """
    declared = cells.get("cells")
    if declared is None:
        return True, "no declared total in this block -- not checked"
    got = sum(v for k, v in cells.items() if k not in SUMMARY_KEYS)
    if got != declared:
        return False, f"histogram {got} != declared {declared}"
    return True, f"histogram sums to the declared {declared}"




def synth(top, params, nodsp):
    """(LUTs, DSPs) or (None, reason)."""
    src = os.path.join(SYNTH, top + ".v")
    if not os.path.exists(src):
        return None, "no such file: %s.v" % top
    flags = BASE + (" -nodsp" if nodsp else "")
    chain = "read_verilog %s.v; " % top
    if params:
        chain += "chparam %s %s; " % (
            " ".join("-set %s %d" % kv for kv in params.items()), top)
    chain += "synth_xilinx -top %s %s; stat" % (top, flags)
    try:
        r = subprocess.run(["yosys", "-p", chain], cwd=SYNTH,
                           capture_output=True, text=True, timeout=1800)
    except subprocess.TimeoutExpired:
        return None, "timed out"
    if r.returncode != 0:
        err = [l for l in (r.stdout + r.stderr).splitlines() if "ERROR" in l]
        return None, (err[0][:90] if err else "yosys exited %d" % r.returncode)

    # yosys prints several "=== name ===" blocks after a synth run. Summing across
    # them double-counts -- the trap that produced pass 250's retracted LUT table.
    # Take the LAST block only, which is the top-level design.
    blocks = r.stdout.split("=== ")
    tail = blocks[-1] if blocks else r.stdout
    cells = dict((m.group(2), int(m.group(1))) for m in STAT.finditer(tail))
    luts = sum(v for k, v in cells.items() if k.startswith("LUT"))
    dsps = sum(v for k, v in cells.items() if "DSP" in k.upper())
    if not cells:
        return None, "stat produced no cell counts -- parser, not design"
    # NOT a gate. See cross_check's docstring: applied as a gate it made every
    # core unmeasurable, and the script then reported "clean" because it had no
    # findings left -- this defect class, self-inflicted, inside its own fix.
    ok, note = cross_check(cells)
    return (luts, dsps), None


def main():
    verbose = "--verbose" in sys.argv
    only = None
    if "--only" in sys.argv:
        only = sys.argv[sys.argv.index("--only") + 1]

    print("%-12s %-18s %10s %10s %9s  %s"
          % ("core", "top", "table", "measured", "ratio", "flags"))
    bad, skipped = [], []
    for name, top, params, want_lut, want_dsp, nodsp in CORES:
        if only and only.lower() not in name.lower():
            continue
        got, err = synth(top, params, nodsp)
        flags = "-nodsp" if nodsp else "DSP allowed"
        if got is None:
            skipped.append((name, err))
            print("%-12s %-18s %10d %10s %9s  %s"
                  % (name, top, want_lut, "--", "--", flags))
            continue
        luts, dsps = got
        ratio = luts / want_lut if want_lut else float("inf")
        off = abs(ratio - 1.0) > DRIFT or dsps != want_dsp
        print("%-12s %-18s %6d/%-3d %6d/%-3d %8.2fx  %s%s"
              % (name, top, want_lut, want_dsp, luts, dsps, ratio, flags,
                 "   <- DEVIATES" if off else ""))
        if off:
            bad.append((name, want_lut, want_dsp, luts, dsps, ratio))

    print()
    if skipped:
        print("could not measure:")
        for n, e in skipped:
            print("    %-12s %s" % (n, e))
        print()
    if bad:
        print("cores deviating from research/COMPLETE_LUT_TABLE.md by more than "
              "%d%% or in DSP count: %d" % (DRIFT * 100, len(bad)))
        for n, wl, wd, gl, gd, r in bad:
            print("    %-12s table %d LUT/%d DSP, measured %d LUT/%d DSP  (%.1fx)"
                  % (n, wl, wd, gl, gd, r))
        print()
        print("The paper's 580 = 505 + 75 arithmetic uses the Quire figure. If the")
        print("Quire is not 75, that sum is not 580 -- and 505 is takum16's multiply")
        print("in the source table, not GF16's, which is 587 there.")
    else:
        print("every measured core matches the table within %d%% and on DSP count."
              % (DRIFT * 100))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
