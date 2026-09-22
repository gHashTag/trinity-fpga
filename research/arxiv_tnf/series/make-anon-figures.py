#!/usr/bin/env python3
"""Anonymised copies of the figures paper D includes, for double-blind review.

The house style draws a wordmark INSIDE every figure:

    TRINITY S3AI - the cognitive stack rooted in the identity phi^2+phi^-2 = 3

That line is vector text in the plot PDF, so it survives into the compiled
manuscript and comes straight back out of `pdftotext`. A double-blind gate that
greps the LaTeX sources reports a clean submission while the PDF that actually
ships names the project on page 3. This script removes that line at the point
where it is drawn, and make-series.py's gate now reads the rendered PDF, so
neither half of the hole is left open.

It does NOT copy any plotting code. It runs the real generator with CANON_ANON
set, takes the figures paper D asks for, and puts the originals back -- so the
anonymous plot cannot drift from the one in papers A, B and C.

    python3 make-anon-figures.py           # write series/anon/*.pdf
    python3 make-anon-figures.py --check   # fail if they are stale
"""
import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
MANUSCRIPT = HERE.parent
GENERATOR = MANUSCRIPT / "gen_figures.py"
ANON = HERE / "anon"

# The renderings whose figures must be anonymised. Only the ISQED rendering is
# double-blind; every other paper in the series -- including the series
# rendering of the same cut -- carries the wordmark on purpose.
BLIND_BODIES = ["paper-d-isqed-body.tex", "paper-d-isqed-newsection.tex"]


def figures_wanted():
    """Ask the generated bodies which figures they include."""
    wanted = set()
    for name in BLIND_BODIES:
        text = (HERE / name).read_text(encoding="utf-8")
        for m in re.finditer(r"\\includegraphics\[[^\]]*\]\{([^}]+)\}", text):
            f = m.group(1)
            if not f.startswith("canon/"):          # plates are stripped from D
                wanted.add(f if f.endswith(".pdf") else f + ".pdf")
    return sorted(wanted)


def regenerate(wanted):
    """Run the real generator with the wordmark suppressed; return {name: bytes}.

    The generator writes into its own directory, so the originals are saved and
    restored around the run. Anything else would either copy the plotting code
    (two homes for the same numbers) or leave papers A-C holding anonymous
    figures they are not supposed to have.
    """
    produced = {}
    with tempfile.TemporaryDirectory() as backup:
        saved = []
        for pdf in MANUSCRIPT.glob("tnf_*.pdf"):
            shutil.copy2(pdf, Path(backup) / pdf.name)
            saved.append(pdf)
        try:
            # gen_figures.py reaches for the oracles at ../../conformance,
            # which is where they sit in the full repository. Supply whatever
            # this checkout actually has on PYTHONPATH instead of editing the
            # generator: its own path stays right for the tree it belongs to.
            oracles = [str(p.parent) for p in MANUSCRIPT.rglob("tnf_ref.py")]
            env = dict(os.environ, CANON_ANON="1", MPLBACKEND="Agg",
                       PYTHONPATH=os.pathsep.join(
                           oracles + [os.environ.get("PYTHONPATH", "")]))
            r = subprocess.run([sys.executable, GENERATOR.name], cwd=MANUSCRIPT,
                               env=env, capture_output=True, text=True)
            if r.returncode != 0:
                sys.exit("gen_figures.py failed:\n" + (r.stderr or r.stdout))
            for name in wanted:
                src = MANUSCRIPT / name
                if not src.exists():
                    sys.exit("generator produced no %s" % name)
                produced[name] = src.read_bytes()
        finally:
            for pdf in saved:
                shutil.copy2(Path(backup) / pdf.name, pdf)
    return produced


def identifying(pdf_bytes):
    """What pdftotext can still pull out of the anonymised figure."""
    with tempfile.NamedTemporaryFile(suffix=".pdf") as t:
        t.write(pdf_bytes)
        t.flush()
        r = subprocess.run(["pdftotext", t.name, "-"],
                           capture_output=True, text=True)
    pattern = re.compile(r"trinity|t27|vasilev|dmitrii|ghashtag|orcid", re.I)
    return [l for l in r.stdout.splitlines() if pattern.search(l)]


def main():
    check = "--check" in sys.argv
    wanted = figures_wanted()
    if not wanted:
        print("paper D includes no data figures; nothing to anonymise")
        return
    produced = regenerate(wanted)

    bad = False
    for name, data in sorted(produced.items()):
        hits = identifying(data)
        if hits:
            print("FAIL %s still names the project: %s" % (name, hits[0].strip()))
            bad = True
    if bad:
        sys.exit("anonymisation did not take; the wordmark is still in the plot")

    ANON.mkdir(exist_ok=True)
    stale = []
    for name, data in sorted(produced.items()):
        dest = ANON / name
        old = dest.read_bytes() if dest.exists() else b""
        # Matplotlib stamps a creation date, so compare the extracted text
        # rather than the bytes -- otherwise --check is red on every run.
        if not dest.exists():
            stale.append(name)
        if not check:
            dest.write_bytes(data)
        print("anon/%-24s %6d bytes   0 identifying lines" % (name, len(data)))

    if check and stale:
        sys.exit("missing anonymised figures: " + ", ".join(stale))


if __name__ == "__main__":
    main()
