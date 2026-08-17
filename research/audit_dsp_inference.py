#!/usr/bin/env python3
"""Does the flag rule really leave DSP48E1 inferable on 915 targets?

arXiv 2606.09686 says DSP48E1 is used "only when explicitly instantiated". Item 4
of research/CORRECTIONS_PACKAGE_both_preprints.md answers in two parts:

  4a  the cited example does not use one. gf_mul_dsp_param.v instantiates DSP48E1
      and no wrapper instantiates gf_mul_dsp_param.

  4b  .github/workflows/build-matrix.yml adds -nodsp ONLY when the op is mul, so
      sqrt, fma and alu are synthesised with DSP inference left on. "915 of the
      3,203 compute targets have an op ending in sqrt, fma or alu, and every one
      of them would infer DSP48E1 on dispatch."

Two claims of very different strength. The count is arithmetic on filenames. The
"every one" was generalised from measuring THREE gf16 targets, and this campaign
has been burned by exactly that shape before -- pass 250 published a LUT drift
from one mis-parsed block, pass 258 condemned a table row from one wrong flag.

So the count is verified exactly and the generalisation is SAMPLED, across widths
rather than at one of them, because DSP inference is a function of operand width:
a multiplier narrow enough is cheaper in LUTs and yosys will not map it.

WHAT A TIMEOUT MEANS HERE
-------------------------
Not "no DSP". Wide formats take minutes under synth_xilinx and a target that did
not finish was not measured. Counting it as zero would bias the answer toward the
comfortable direction, so it is reported apart.

Usage:  python3 research/audit_dsp_inference.py [--per-op N] [--timeout S]

Exits non-zero if any sampled target infers a DSP -- i.e. if the paper's sentence
is contradicted, which is item 4's claim and the state this expects to find.
"""
import glob
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SYNTH = os.path.join(ROOT, "fpga", "openxc7-synth")
WF = os.path.join(ROOT, ".github", "workflows", "build-matrix.yml")

NAME = re.compile(r"^corona_compute_(?P<fmt>.+?)_(?P<op>[a-z0-9]+)_ax7203\.v$")
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
    """(ok, note). Only checks when yosys actually printed a total."""
    declared = cells.get("cells")
    if declared is None:
        return True, "no declared total in this block -- not checked"
    got = sum(v for k, v in cells.items() if k not in SUMMARY_KEYS)
    if got != declared:
        return False, f"histogram {got} != declared {declared}"
    return True, f"histogram sums to the declared {declared}"


READS_LINE = re.compile(r'READS="([^"]*)\$\{DESIGN\}\.v"')

# The ops the workflow does NOT protect with -nodsp, other than the trivial ones.
UNPROTECTED = ("sqrt", "fma", "alu")


def workflow_reads():
    try:
        m = READS_LINE.search(open(WF, encoding="utf-8").read())
    except OSError:
        return None
    return m.group(1).strip() if m else None


def nodsp_rule():
    """Confirm from the workflow itself that -nodsp is mul-only, rather than
    trusting item 4's reading of it."""
    try:
        src = open(WF, encoding="utf-8").read()
    except OSError:
        return None
    # Shell test syntax: [ "$OP" = "mul" ]. The first version of this looked for
    # `op == "mul"`, matched nothing, and printed "NO -- re-read the workflow"
    # against a workflow that says exactly what item 4 says it does. A detector
    # that cries wolf about its own regex is worse than no detector.
    if "-nodsp" not in src:
        return False
    return re.search(r'\[\s*"\$\{?OP\}?"\s*=\s*"?mul"?\s*\]', src) is not None


def measure(base, reads, timeout):
    """(luts, dsps) or (None, reason). Flags exactly as the workflow sets them."""
    op = NAME.search(base).group("op")
    flags = "-flatten -abc9 -nocarry -arch xc7"
    if op == "mul":
        flags += " -nodsp"
    script = "read_verilog %s %s; synth_xilinx %s; stat" % (reads, base, flags)
    try:
        r = subprocess.run(["yosys", "-p", script], cwd=SYNTH,
                           capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return None, "timed out at %ds -- NOT measured, not zero" % timeout
    if r.returncode != 0:
        errs = [l for l in (r.stdout + r.stderr).splitlines() if "ERROR" in l]
        return None, (errs[0][:80] if errs else "yosys exited %d" % r.returncode)
    tail = r.stdout.split("=== ")[-1]
    cells = dict((m.group(2), int(m.group(1))) for m in STAT.finditer(tail))
    if not cells:
        return None, "stat produced no cell counts -- parser, not design"
    ok, note = cross_check(cells)
    if not ok:
        return None, f"stat parse disagrees with yosys: {note}"
    luts = sum(v for k, v in cells.items() if k.startswith("LUT"))
    dsps = sum(v for k, v in cells.items() if "DSP" in k.upper())
    return (luts, dsps), None


def main():
    per_op = 5
    timeout = 420
    if "--per-op" in sys.argv:
        per_op = int(sys.argv[sys.argv.index("--per-op") + 1])
    if "--timeout" in sys.argv:
        timeout = int(sys.argv[sys.argv.index("--timeout") + 1])

    files = sorted(os.path.basename(p) for p in
                   glob.glob(os.path.join(SYNTH, "corona_compute_*_ax7203.v")))
    by_op = {}
    for b in files:
        m = NAME.search(b)
        if m:
            by_op.setdefault(m.group("op"), []).append(b)

    unprotected = sum(len(by_op.get(op, [])) for op in UNPROTECTED)
    print("compute targets                       : %d" % len(files))
    for op in UNPROTECTED:
        print("   op = %-5s                          : %d" % (op, len(by_op.get(op, []))))
    print("   TOTAL synthesised without -nodsp   : %d" % unprotected)
    print("   item 4 claims                      : 915  %s"
          % ("<- matches" if unprotected == 915 else "<- DIFFERS"))
    rule = nodsp_rule()
    print("   workflow applies -nodsp to mul only: %s"
          % {True: "yes", False: "NO -- re-read the workflow", None: "?"}[rule])
    print()

    reads = workflow_reads()
    if reads is None:
        print("cannot read the READS list from build-matrix.yml")
        return 2

    # Stratified by width, not by convenience: DSP inference depends on operand
    # width, so sampling five narrow formats would answer a different question.
    print("sampled %d per op, spread across the width range:" % per_op)
    print("%-46s %8s %6s" % ("target", "LUT", "DSP"))
    infer, clean, unmeasured = [], [], []
    for op in UNPROTECTED:
        pool = by_op.get(op, [])
        if not pool:
            continue
        step = max(1, len(pool) // per_op)
        for b in pool[::step][:per_op]:
            got, err = measure(b, reads, timeout)
            if got is None:
                unmeasured.append((b, err))
                print("%-46s %8s %6s   %s" % (b[:46], "--", "--", err))
                continue
            luts, dsps = got
            (infer if dsps else clean).append((b, luts, dsps))
            print("%-46s %8d %6d%s"
                  % (b[:46], luts, dsps, "   <- infers DSP" if dsps else ""))

    print()
    print("sampled and measured : %d" % (len(infer) + len(clean)))
    print("   inferred a DSP48E1 : %d" % len(infer))
    print("   inferred none      : %d" % len(clean))
    print("   not measured       : %d  (timeout or error -- NOT counted as zero)"
          % len(unmeasured))
    print()
    if infer and clean:
        print("The count of 915 is exact, but 'every one of them would infer")
        print("DSP48E1' is not what the sample shows: %d of %d measured targets"
              % (len(infer), len(infer) + len(clean)))
        print("inferred one. The rule leaves DSPs POSSIBLE on 915 targets, which is")
        print("the defensible form of item 4b -- whether a given target takes one")
        print("depends on its operand width.")
    elif infer:
        print("Every measured target inferred a DSP, consistent with item 4b as")
        print("written. A sample cannot establish 'every one' over 915; it can only")
        print("fail to contradict it, which is what happened.")
    else:
        print("No sampled target inferred a DSP. Item 4b's generalisation from three")
        print("gf16 targets does not hold at other widths and should be restated.")
    return 1 if infer else 0


if __name__ == "__main__":
    sys.exit(main())
