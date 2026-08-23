#!/usr/bin/env python3
"""Does the manuscript still describe the records it cites?

The TNF paper package passes every pre-flight check in SUBMISSION.md -- it
builds, every figure resolves, the bibliography is inline -- and on 2026-08-24 it
described a state of knowledge three days and twenty waves old. `tnf_paper.tex`
was last written 2026-08-20; `measurements/` had been written through 08-23. In
between: the first silicon numbers (W973, Fmax 80.35 MHz), a defect the die found
that simulation had passed (W975-W978), and W991, which shows TNF holding fewer
values and a coarser step than posit at matched physical width.

None of it was in the paper. Not a single occurrence of `80.35`, `BSCAN`,
`on-die`, `516096` or `524286`. A package that compiles is not a package that is
current, and nothing here was checking the difference: every existing gate asks
whether the paper is internally consistent, which it can be while being stale.

So this asks the one question none of them ask -- is the newest record newer than
the manuscript, and are there records the manuscript never mentions?

Exit 0 when the manuscript is at least as new as the records. Exit 1 when it is
behind, with the gap named. Exit 2 when the subject is missing, because a gate
that cannot find what it audits has not passed.
"""
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAPER = os.path.join(ROOT, "research", "arxiv_tnf", "tnf_paper.tex")
RECORDS = os.path.join(ROOT, "research", "arxiv_tnf", "measurements")


def last_commit_date(path):
    """Committed date, not mtime: a checkout rewrites every mtime to now."""
    try:
        out = subprocess.run(
            ["git", "log", "-1", "--format=%cI", "--", path],
            cwd=ROOT, capture_output=True, text=True, timeout=60)
        return out.stdout.strip() or None
    except Exception:
        return None


def main():
    if not os.path.exists(PAPER):
        print(f"nothing to audit: {PAPER} is not here")
        return 2
    if not os.path.isdir(RECORDS):
        print(f"nothing to audit against: {RECORDS} is not here")
        return 2

    paper_date = last_commit_date(PAPER)
    if paper_date is None:
        print("cannot date the manuscript: no git history for it here")
        return 2

    newest, newest_date = None, ""
    for name in sorted(os.listdir(RECORDS)):
        if not name.endswith(".json"):
            continue
        d = last_commit_date(os.path.join(RECORDS, name))
        if d and d > newest_date:
            newest, newest_date = name, d

    if newest is None:
        print("no dated records to compare against")
        return 2

    tex = open(PAPER, encoding="utf-8", errors="replace").read()

    # A wave is unreflected when the paper names neither its number nor any
    # distinctive figure from it. Checking the wave label alone would pass on a
    # citation that says "W991" and nothing it found, so the numbers are checked
    # too -- integers of five digits or more, which are specific enough to be
    # evidence rather than coincidence.
    unreflected = []
    for name in sorted(os.listdir(RECORDS)):
        if not name.endswith(".json"):
            continue
        if last_commit_date(os.path.join(RECORDS, name)) <= paper_date:
            continue
        try:
            doc = json.load(open(os.path.join(RECORDS, name), encoding="utf-8"))
        except Exception:
            continue
        blob = json.dumps(doc)
        # not every record is an object: a few are bare arrays of readings
        wave = (doc.get("wave") or "").strip() if isinstance(doc, dict) else ""
        figures = set(re.findall(r"\b\d{5,}\b", blob))
        cited = (wave and wave in tex) or any(f in tex for f in figures)
        if not cited:
            unreflected.append((name, wave))


    print(f"manuscript last written  {paper_date[:10]}  ({os.path.relpath(PAPER, ROOT)})")
    print(f"newest record written    {newest_date[:10]}  ({newest})")

    if newest_date[:10] <= paper_date[:10] and not unreflected:
        print("\nthe manuscript is at least as new as the records it cites")
        return 0

    # Two groups, because they carry different weight. A record that names its
    # own wave and whose label appears nowhere in the manuscript is a gap you can
    # point at. A record with no wave field is only a suspicion: the check falls
    # back to five-digit figures, and a record whose numbers are all small or all
    # shared with its neighbours will look unreflected whether it is or not.
    labelled = [(n, w) for n, w in unreflected if w]
    unlabelled = [n for n, w in unreflected if not w]

    print(f"\n{len(labelled)} wave(s) newer than the manuscript, named nowhere in it:")
    for name, wave in sorted(labelled, key=lambda x: x[1]):
        print(f"  {wave:<6} {name}")
    if unlabelled:
        print(f"\n{len(unlabelled)} further record(s) carry no wave label, so this")
        print("  cannot tell an omission from a coincidence of figures:")
        for name in unlabelled[:8]:
            print(f"         {name}")
        if len(unlabelled) > 8:
            print(f"         ... and {len(unlabelled) - 8} more")
    print("\nThe package can build, pass every pre-flight and still be stale;")
    print("this reports the gap, it does not judge whether it matters. A record")
    print("deliberately left out of the paper is a decision -- make it visible by")
    print("naming the wave in the text, even to say it is excluded.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
