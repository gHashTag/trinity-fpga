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

# Lines that state how much a check looked at. Deliberately loose: the point is to
# surface a number the reader can judge, not to parse every phrasing perfectly.
COVERAGE = re.compile(
    r"^\s*(?:.*?[:=]\s*)?([\d,]{2,})\s*(?:of|/)\s*([\d,]{2,})\b"
    r"|(\b[\d,]{3,})\s+(?:codes|pairs|vectors|formats|packs|wrappers|files|comments)\b",
    re.I | re.M)


def coverage_of(text: str) -> str:
    best = 0
    shown = ""
    for m in COVERAGE.finditer(text):
        a = m.group(1) or m.group(3)
        if not a:
            continue
        try:
            n = int(a.replace(",", ""))
        except ValueError:
            continue
        if n > best:
            best = n
            shown = m.group(0).strip()[:46]
    return shown


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
            cov = coverage_of(out)
            if r.returncode == 0:
                buckets["HOLDS"].append((name, cov))
                if not cov:
                    blind.append(name)
            elif r.returncode == 1:
                buckets["FINDINGS"].append((name, cov))
            elif r.returncode == 2:
                buckets["NO INPUT"].append((name, cov))
            else:
                buckets["BROKE"].append((name, f"exit {r.returncode}"))
        except subprocess.TimeoutExpired:
            buckets["SLOW"].append((name, f">{args.timeout}s"))
        except Exception as e:                                   # pragma: no cover
            buckets["BROKE"].append((name, type(e).__name__))

    print(f"checks in research/ : {len(scripts)}\n")
    for k in ("HOLDS", "FINDINGS", "NO INPUT", "SLOW", "BROKE"):
        print(f"  {k:<9} {len(buckets[k])}")

    for k in ("FINDINGS", "NO INPUT", "SLOW", "BROKE"):
        if not buckets[k]:
            continue
        print(f"\n{k}")
        for name, note in buckets[k]:
            print(f"    {name:<40} {note}")

    print("\nHOLDS, with what each one looked at")
    for name, cov in buckets["HOLDS"]:
        print(f"    {name:<40} {cov or '-- no coverage figure printed'}")

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
