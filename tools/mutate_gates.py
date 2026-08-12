#!/usr/bin/env python3
"""Mutation-test the gates: inject the defect each one exists to catch.

A gate that passes its own regression is only known to catch the ONE phrasing
its author happened to write. Iteration 113 found the self-consistency gate
counting only the passive voice, so three retractions written "we withdraw it"
were invisible and the paper's self-reported count drifted below the truth while
the gate stayed green. That is not an adversary routing around a check; it is an
author writing English.

This injects each defect twice: once in the phrasing the gate was written
against (a CONTROL -- it must FAIL, or the harness is broken and proves nothing)
and once in an equally ordinary alternative (the TEST -- if it PASSES, the hole
is real).

The paper is restored from a backup after every mutation, and the restore is
verified by byte comparison before the next one runs.
"""
import hashlib
import pathlib
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
PAPER = ROOT / "research" / "arxiv_tnf" / "tnf_paper.tex"
BAK = pathlib.Path("/tmp/tnf_paper_mutation_backup.tex")
ORIG = PAPER.read_bytes()
DIGEST = hashlib.sha256(ORIG).hexdigest()
shutil.copy2(PAPER, BAK)

BODY = r"\section{The format}"
ABSTRACT_END = r"\end{abstract}"


def mutate(anchor, text, before=False):
    t = PAPER.read_text()
    i = t.index(anchor)
    return t[:i] + text + t[i:] if before else t[:i + len(anchor)] + text + t[i + len(anchor):]


def restore():
    PAPER.write_bytes(ORIG)
    assert hashlib.sha256(PAPER.read_bytes()).hexdigest() == DIGEST, "ВОССТАНОВЛЕНИЕ НЕ УДАЛОСЬ"


def run(gate):
    r = subprocess.run([sys.executable, str(ROOT / "tools" / f"{gate}.py")],
                       cwd=ROOT, capture_output=True, timeout=900)
    return r.returncode == 0            # True = gate passed


# A tool that ends in an unconditional sys.exit(0) cannot fail, so mutating the
# paper against it proves nothing. check_paper_numbers and
# check_scoped_superlatives are REPORTS, not gates, and were being counted among
# "gates green" for thirteen iterations. Probe rather than assume.
import re as _re
def gates_at_all(name):
    s = (ROOT / "tools" / f"{name}.py").read_text()
    return bool(_re.search(r"sys\.exit\((?!0\))|sys\.exit\(main\(\)\)", s))

# The withdrawal and the live assertion must land in DIFFERENT paragraphs: the
# gate deliberately ignores a number that appears inside the withdrawal's own
# paragraph, since a replacement value lives there. The first harness put both in
# one insertion, so its control could not fail -- which is what the control was
# for.
WD_ANCHOR = r"\section{The format}"
LIVE_ANCHOR = r"\section{Hardware}"
CASES = [
    ("снятие СТРАДАТЕЛЬНЫМ залогом", "check_withdrawn_live",
     [(WD_ANCHOR, "\n\nThe $77.77\\%$ figure is withdrawn.\n\n"),
      (LIVE_ANCHOR, "\n\nThe rung measures $77.77\\%$ throughput per LUT.\n\n")], True),
    ("снятие ДЕЙСТВИТЕЛЬНЫМ залогом", "check_withdrawn_live",
     [(WD_ANCHOR, "\n\nWe withdraw the $77.77\\%$ figure.\n\n"),
      (LIVE_ANCHOR, "\n\nThe rung measures $77.77\\%$ throughput per LUT.\n\n")], False),
    ("дубль \\label", "check_latex_hygiene",
     [(WD_ANCHOR, "\n\n\\label{sec:format}\n\n")], True),
    ("ссылка \\ref без \\label", "check_latex_hygiene",
     [(WD_ANCHOR, "\n\nSee Section~\\ref{sec:nonexistent-xyz}.\n\n")], True),
]

def apply_all(edits):
    t = ORIG.decode()
    for anchor, text in sorted(edits, key=lambda e: -t.index(e[0])):
        i = t.index(anchor) + len(anchor)
        t = t[:i] + text + t[i:]
    return t

print(f"  статья: {len(ORIG):,} байт, sha256 {DIGEST[:12]}\n")
print(f"  {'мутация':34s} {'гейт':24s} {'роль':9s} итог")
holes, broken = [], []
for label, gate, edits, ctrl in CASES:
    if not gates_at_all(gate):
        print(f"  {label:34s} {gate:24s} {'—':9s} ⚠ НЕ ГЕЙТ (безусловный exit 0)")
        broken.append(gate); continue
    try:
        PAPER.write_text(apply_all(edits))
        passed = run(gate)
    finally:
        restore()
    role = "контроль" if ctrl else "тест"
    if passed:
        print(f"  {label:34s} {gate:24s} {role:9s} "
              f"{'❗СТЕНД СЛОМАН' if ctrl else '🕳 ДЫРА'}")
        (broken if ctrl else holes).append(gate)
    else:
        print(f"  {label:34s} {gate:24s} {role:9s} ✓ поймал")

restore()
print(f"\n  восстановлено, sha256 {hashlib.sha256(PAPER.read_bytes()).hexdigest()[:12]}")
print(f"  дыр: {len(holes)}   сломанных контролей/не-гейтов: {len(broken)}")
