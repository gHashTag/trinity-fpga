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
import os
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

# Mutations are no longer confined to the paper: half the gates read Verilog or
# the conformance reference instead. Every touched file is snapshotted by bytes
# and restored by bytes, and the restore is verified before the next case runs.
SNAP = {}
def snapshot(paths):
    for q in paths:
        SNAP[q] = pathlib.Path(q).read_bytes()
def restore_all():
    """Restore by bytes AND purge bytecode.

    Restoring content is not enough. A .pyc records the source mtime it was
    compiled from, and a restore that lands in the SAME SECOND as the mutated
    compile leaves the cache looking valid -- so the next gate imports the
    MUTATION from cache while the source on disk is correct. That happened here:
    conformance/tnf_spec_ref.py read et=5 on disk and et=7 through import, and
    two gates failed on a clean tree afterwards.
    """
    for q, b in SNAP.items():
        f = pathlib.Path(q)
        f.write_bytes(b)
        for c in f.parent.glob("__pycache__/*.pyc"):
            c.unlink(missing_ok=True)
        os.utime(f, None)
    SNAP.clear()

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



import re as _re
def gates_at_all(name):
    s = (ROOT / "tools" / f"{name}.py").read_text()
    return bool(_re.search(r"sys\.exit\((?!0\))|sys\.exit\(main\(\)\)", s))

PAP = str(PAPER)
def find_one(pat, glob):
    """First file under ROOT matching glob that contains pat."""
    for q in sorted(ROOT.glob(glob)):
        if q.is_file() and pat in q.read_text(errors="ignore"):
            return str(q)
    return None

VERI = find_one("8'd127", "fpga/**/*.v")
SPEC = str(ROOT / "conformance" / "tnf_spec_ref.py")
INVF = str(ROOT / "conformance" / "tnf_ladder_invariants_test.py")

# Each case: (label, gate, [(file, old, new)], is_control)
# A control uses the phrasing the gate was written against and MUST fail.
# A test uses an equally ordinary alternative; if it passes, the hole is real.
CASES = [
    ("снятие СТРАДАТЕЛЬНЫМ залогом", "check_withdrawn_live",
     [(PAP, r"\section{The format}",
       "\\section{The format}\n\nThe $77.77\\%$ figure is withdrawn.\n"),
      (PAP, r"\section{Hardware}",
       "\\section{Hardware}\n\nThe rung measures $77.77\\%$ per LUT.\n")], True),
    ("снятие ДЕЙСТВИТЕЛЬНЫМ залогом", "check_withdrawn_live",
     [(PAP, r"\section{The format}",
       "\\section{The format}\n\nWe withdraw the $77.77\\%$ figure.\n"),
      (PAP, r"\section{Hardware}",
       "\\section{Hardware}\n\nThe rung measures $77.77\\%$ per LUT.\n")], False),
    ("дубль \\label", "check_latex_hygiene",
     [(PAP, r"\section{Hardware}", "\\section{Hardware}\\label{sec:format}")], True),
    ("\\ref без \\label", "check_latex_hygiene",
     [(PAP, r"\section{Hardware}",
       "\\section{Hardware} See Section~\\ref{sec:nope-xyz}.")], True),
    ("счёт снятий, ЗНАКОМАЯ форма", "check_self_consistency",
     [(PAP, "Sixteen retractions are marked in place below.",
       "Twelve retractions are marked in place below.")], True),
    ("счёт снятий, ДРУГАЯ форма", "check_self_consistency",
     [(PAP, r"\section{Hardware}",
       "\\section{Hardware}\n\nWe have retracted twelve claims in this document.\n")], False),
    # The gate keys on the phrase "in-specification codes exact" within 130
    # characters, so the mutation must hit THAT occurrence, not the first one in
    # the file. The first harness changed an unrelated 62{,}208 and its control
    # could not fail.
    ("счёт соответствия, С РАЗДЕЛИТЕЛЕМ", "check_conformance_counts",
     [(PAP, "$62{,}208$ of $62{,}208$ in-specification codes exact",
            "$62{,}209$ of $62{,}209$ in-specification codes exact")], True),
    ("счёт соответствия, БЕЗ РАЗДЕЛИТЕЛЯ", "check_conformance_counts",
     [(PAP, "$62{,}208$ of $62{,}208$ in-specification codes exact",
            "$62209$ of $62209$ in-specification codes exact")], False),
    # check_exponent_window reads the LADDER, not any Verilog: it checks the
    # exponent span arithmetically from conformance/tnf_spec_ref.py. Mutating a
    # .v file proved nothing about it, which is why that control passed.
    ("окно экспоненты, E_t за предел", "check_exponent_window",
     [(SPEC, "et=5", "et=7")], True),

    # check_overfull greps the build log for "Overfull \\hbox". Its docstring
    # asks whether anything runs off the page; a vertical overflow does exactly
    # that and matches no pattern it holds.
    ("переполнение ГОРИЗОНТАЛЬНОЕ", "check_overfull",
     [(PAP, r"\section{Hardware}",
       "\\section{Hardware}\n\n\\noindent "
       "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA\n")], True),
    ("переполнение ВЕРТИКАЛЬНОЕ", "check_overfull",
     [(PAP, r"\section{Hardware}",
       "\\section{Hardware}\n\n\\begin{minipage}[t][2pt]{\\linewidth}\n"
       "One two three four five six seven eight nine ten eleven twelve thirteen "
       "fourteen fifteen sixteen seventeen eighteen nineteen twenty.\n"
       "\\end{minipage}\n")], False),

    # UNIT is read from one file by IMPORT and from the other by scanning for a
    # line that STARTS with "UNIT". An ordinary annotated declaration does not.
    ("рассогласование единиц, знакомая запись", "check_ladder_units",
     [(INVF, 'UNIT = "positions"', 'UNIT = "stored bits"')], True),
    ("объявление UNIT с аннотацией типа", "check_ladder_units",
     [(INVF, 'UNIT = "positions"', 'UNIT: str = "positions"')], False),

    # This gate FAILS only on MARKED claims -- an unmarked percentage is
    # counted and printed, never failed, by design. The first control here
    # asserted an unmarked claim and so could not fail: my aim, not the gate.
    ("размеченное utilisation, знакомая запись", "check_codespace_claims",
     [(PAP, "\\codeuse{TNF16a}{98.4}", "\\codeuse{TNF16a}{62.5}")], True),
    ("размеченное utilisation, ПРОБЕЛЫ в аргументе", "check_codespace_claims",
     [(PAP, "\\codeuse{TNF16a}{98.4}", "\\codeuse{TNF16a}{ 62.5 }")], False),
]

def apply_edits(edits):
    snapshot({f for f, _, _ in edits})
    for f, old, new in edits:
        q = pathlib.Path(f); s = q.read_text()
        if old not in s:
            raise LookupError(f"{pathlib.Path(f).name}: не найдено {old[:40]!r}")
        q.write_text(s.replace(old, new, 1))

print(f"  {'мутация':40s} {'гейт':26s} {'роль':9s} итог")
holes, broken, skipped = [], [], []
for label, gate, edits, ctrl in CASES:
    if not gates_at_all(gate):
        print(f"  {label:40s} {gate:26s} {'—':9s} ⚠ НЕ ГЕЙТ"); broken.append(gate); continue
    try:
        apply_edits(edits)
    except LookupError as e:
        restore_all(); print(f"  {label:40s} {gate:26s} {'—':9s} ⚠ {e}")
        skipped.append(gate); continue
    try:
        passed = run(gate)
    finally:
        restore_all()
    role = "контроль" if ctrl else "тест"
    if passed:
        print(f"  {label:40s} {gate:26s} {role:9s} "
              f"{'❗СТЕНД СЛОМАН' if ctrl else '🕳 ДЫРА'}")
        (broken if ctrl else holes).append(gate)
    else:
        print(f"  {label:40s} {gate:26s} {role:9s} ✓ поймал")

restore()
print(f"\n  статья цела: sha256 {hashlib.sha256(PAPER.read_bytes()).hexdigest()[:12]}")
print(f"  дыр: {len(holes)}   сломано/не-гейт: {len(broken)}   пропущено: {len(skipped)}")
