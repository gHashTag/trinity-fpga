#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Run every check in research/ and report what each one actually covers.

Fifteen passes have added checks one at a time, and the coverage picture is now spread
across fifteen reports. This is the single place to ask the question that matters:
**what is verified, and what is merely not refuted?**

The distinction is not rhetorical. A check that exits 0 because it found nothing and a
check that exits 0 because it could not read its input look identical from the outside,
and this campaign has been misled by that before. So the categories here are:

    HOLDS        ran, examined something, found nothing wrong
    FINDINGS     ran and reported something
    NO INPUT     could not read what it needs (network, board, an artefact) -- exit 2
    SLOW         did not finish inside the time limit
    BROKE        raised

A check reporting HOLDS with a coverage of zero is called out separately, because that
is the shape that reads as assurance and is not.

    python3 research/run_all_checks.py [--timeout N] [--quick]
"""
from __future__ import annotations

import argparse
import glob
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

PREFIXES = ("audit_", "crossval_", "measure_", "verify_", "witness_")

# How much a check looked at. Two routes, and the runner says which it used.
#
# Pass 158 corrected an earlier claim from this file. It reported that 26 checks printed
# no coverage figure; they printed one, and the regex here could not see it -- exactly
# the shape this campaign keeps catching in other tools. The heuristic below is wider
# now, and the declared route exists so that guessing is never the only option.
#
# A check declares coverage by printing one line:
#
#     COVERAGE: 83 packs
#
# Anything else is guessed from "label : number" and "number unit" shapes, and marked
# as guessed, because a guessed figure and a stated one are not the same evidence.

DECLARED = re.compile(r"^COVERAGE:\s*([\d,]+)\s*(.*)$", re.M)

GUESSES = (
    re.compile(r"^\s*([A-Za-z][\w /()+*=-]{4,44}?)\s*:\s*([\d,]{2,})\s*$", re.M),
    re.compile(r"\b(codes|pairs|vectors|formats|packs|wrappers|files|comments|"
               r"cells|rows|scripts|loaders|oracles)\s*=?\s*([\d,]{2,})\b", re.I),
    re.compile(r"\b([\d,]{2,})\s+(codes|pairs|vectors|formats|packs|wrappers|files|"
               r"comments|cells|rows|scripts|loaders|oracles)\b", re.I),
)


def coverage_of(text: str) -> tuple[str, str]:
    """(figure, how) -- how is 'declared', 'guessed' or 'none'."""
    m = DECLARED.search(text)
    if m:
        return (f"{m.group(1)} {m.group(2)}".strip()[:46], "declared")

    best, shown = 0, ""
    for rx in GUESSES:
        for g in rx.finditer(text):
            parts = [p for p in g.groups() if p]
            num = next((p for p in parts if p.replace(",", "").isdigit()), None)
            if not num:
                continue
            try:
                n = int(num.replace(",", ""))
            except ValueError:
                continue
            if n > best:
                best, shown = n, " ".join(g.group(0).split())[:46]
    return (shown, "guessed" if shown else "none")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--timeout", type=int, default=180)
    ap.add_argument("--quick", action="store_true",
                    help="skip checks that need the network")
    args = ap.parse_args()

    scripts = sorted(
        p for pre in PREFIXES for p in glob.glob(os.path.join(HERE, pre + "*.py")))

    buckets: dict[str, list] = {k: [] for k in
                                ("HOLDS", "FINDINGS", "NO INPUT", "SLOW", "BROKE")}
    blind = []

    for path in scripts:
        name = os.path.basename(path)
        try:
            r = subprocess.run([sys.executable, path], capture_output=True,
                               text=True, timeout=args.timeout, cwd=ROOT)
            out = (r.stdout or "") + (r.stderr or "")
            cov, how = coverage_of(out)
            if r.returncode == 0:
                buckets["HOLDS"].append((name, cov, how))
                if how == "none":
                    blind.append(name)
            elif r.returncode == 1:
                buckets["FINDINGS"].append((name, cov, how))
            elif r.returncode == 2:
                buckets["NO INPUT"].append((name, cov, how))
            else:
                buckets["BROKE"].append((name, f"exit {r.returncode}", "none"))
        except subprocess.TimeoutExpired:
            buckets["SLOW"].append((name, f">{args.timeout}s", "none"))
        except Exception as e:                                   # pragma: no cover
            buckets["BROKE"].append((name, type(e).__name__, "none"))

    print(f"checks in research/ : {len(scripts)}\n")
    for k in ("HOLDS", "FINDINGS", "NO INPUT", "SLOW", "BROKE"):
        print(f"  {k:<9} {len(buckets[k])}")

    for k in ("FINDINGS", "NO INPUT", "SLOW", "BROKE"):
        if not buckets[k]:
            continue
        print(f"\n{k}")
        for name, note, _ in buckets[k]:
            print(f"    {name:<40} {note}")

    print("\nHOLDS, with what each one looked at")
    decl = sum(1 for _, _, h in buckets["HOLDS"] if h == "declared")
    print(f"    ({decl} declare a COVERAGE line; the rest are guessed from output)\n")
    for name, cov, how in buckets["HOLDS"]:
        mark = {"declared": "  ", "guessed": " ~", "none": " ?"}[how]
        print(f"   {mark}{name:<40} {cov or '-- nothing found'}")

    if blind:
        print(f"""
{len(blind)} checks exit 0 without printing how much they examined. That is the shape
that reads as assurance and is not: an empty scan and a clean scan look identical from
outside. They are listed above with a dash, and each should either print a count or say
why it cannot.""")

    print("""
Exit 0 here means every check ran; it does NOT mean the corpus is verified. NO INPUT is
the honest category -- those checks need a network, a board, or an artefact that is not
present, and reporting them as passing would be the exact failure this whole set exists
to prevent.""")
    return 1 if buckets["BROKE"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
