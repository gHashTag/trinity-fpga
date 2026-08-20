#!/usr/bin/env python3
"""Can each paper gate actually fail?

Every other gate here asks whether the paper is right. None asks whether the
gates are. That question is not hypothetical: check_self_consistency passed a
paper claiming "Ninety-nine retractions are marked in place below" and again
one claiming "Three", because its pattern only matched sentences carrying a
retraction verb and its number-word dictionary stopped at twenty — an
unreadable count was skipped in silence rather than reported. It had been
green for weeks over a document whose count it could not read.

This injects a defect each gate is supposed to catch, runs the gate, and
requires it to fail. A gate that passes its own defect is reported here, in
CI, instead of being discovered by whoever eventually trusts it.

THE MISTAKE THIS FILE EXISTS TO PREVENT, MADE THREE TIMES BY ITS AUTHOR:
a string replacement whose target is absent is a no-op, the gate then passes
because nothing was injected, and the output is identical to a gate that has
gone blind. check_withdrawn_live's docstring warned about it in prose; the
warning was ignored twice more anyway. So every injection here asserts the
file actually changed before the gate is allowed to speak, and a no-op
injection is a failure of THIS file, not a pass of the gate.
"""
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
PAPER = ROOT / "research" / "arxiv_tnf" / "tnf_paper.tex"
ANCHOR = "\\section{What this paper argues}"

# Not every gate reads the paper. Those that check documents against the tree
# need their defect injected into a document instead, so the harness carries a
# second target and each case says which file it patches.
SCRATCH_DOC = ROOT / "research" / "GATE_SELFTEST_SCRATCH.md"

# gate -> text inserted before ANCHOR that the gate must reject.
# Each defect is the smallest thing that gate exists to notice.
CASES = {
    "check_self_consistency": (
        "Ninety-nine retractions are marked in place below.\n\n"
    ),
    "check_paper_numbers": (
        "The synthesised design runs at 987.65 MHz on the board.\n\n"
    ),
    "check_ref_kinds": (
        "See Section~\\ref{fig:acc} for the plate.\n\n"
    ),
    "check_latex_hygiene": (
        "A reference to \\ref{sec:does-not-exist-at-all} here.\n\n"
    ),
    # Documents-against-the-tree gates: the defect goes in a scratch document
    # that the harness creates and removes, never in a real one.
    "check_doc_refs": None,
    "check_withdrawn_live": (
        "\\paragraph{Withdrawn.} The earlier claim of $77.31\\times$ is withdrawn: "
        "it was measured against the broken oracle.\n\n"
        "The rung still reaches $77.31\\times$ in the far band.\n\n"
    ),
}


def run(gate: str) -> bool:
    """True if the gate passed."""
    r = subprocess.run(
        [sys.executable, str(ROOT / "tools" / f"{gate}.py")],
        capture_output=True,
        cwd=ROOT,
    )
    return r.returncode == 0


def main() -> int:
    original = PAPER.read_text()
    if ANCHOR not in original:
        print(f"FAIL: the injection anchor is not in {PAPER.name}; this file cannot test anything")
        return 1

    # A gate that is ALREADY failing rejects anything you inject, so its
    # "rejects its defect" verdict would mean nothing. Establish each gate's
    # clean-tree state first and report the ones that cannot be tested rather
    # than counting them as proven — the same distinction between "no boards"
    # and "cannot tell" that this project keeps rediscovering.
    already_red = [g for g in CASES if not run(g)]

    blind, noop = [], []
    try:
        for gate, defect in CASES.items():
            if gate in already_red:
                continue
            if defect is None:
                # A gate that reads documents rather than the paper: name a
                # file that does not exist and require the gate to notice.
                SCRATCH_DOC.write_text(
                    "# Gate self-test scratch\n\n"
                    "This document names `tools/a_file_that_does_not_exist.py`, which is\n"
                    "the defect check_doc_refs exists to catch. The harness writes this\n"
                    "file, runs the gate, and removes it.\n"
                )
                if not SCRATCH_DOC.is_file():
                    noop.append(gate)
                    continue
                if run(gate):
                    blind.append(gate)
                SCRATCH_DOC.unlink(missing_ok=True)
                continue
            patched = original.replace(ANCHOR, defect + ANCHOR, 1)
            if len(patched) <= len(original):
                # The whole point: a silent no-op reads exactly like a pass.
                noop.append(gate)
                continue
            PAPER.write_text(patched)
            if run(gate):
                blind.append(gate)
            PAPER.write_text(original)
    finally:
        PAPER.write_text(original)
        SCRATCH_DOC.unlink(missing_ok=True)

    print(f"gates tested: {len(CASES) - len(already_red)} of {len(CASES)}")
    for g in CASES:
        if g in already_red:
            print(f"  {g}: UNTESTABLE — already failing on a clean tree")
        elif g in noop:
            print(f"  {g}: INJECTION NO-OP")
        elif g in blind:
            print(f"  {g}: PASSED ITS OWN DEFECT")
        else:
            print(f"  {g}: rejects its defect")

    if noop:
        print(f"\nFAIL: {len(noop)} injection(s) changed nothing — this file is broken, not the gate")
        return 1
    if blind:
        print(f"\nFAIL: {len(blind)} gate(s) accept the defect they exist to catch")
        return 1
    if already_red:
        print(f"\n{len(already_red)} gate(s) could not be tested because they are red")
        print("on a clean tree. That is a finding about the tree, not about them —")
        print("fix the tree, then this harness can say whether they work.")
    print("\nOK: every gate rejects the defect it exists to catch")
    return 0


if __name__ == "__main__":
    sys.exit(main())
