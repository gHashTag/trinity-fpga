#!/usr/bin/env python3
"""Do the Tier-E CI runs actually exist and actually pass?

Passes 91-94 established that 74 comments carry all four required links. That checks
the evidence was PUBLISHED. It does not check that the evidence is SOUND: a URL can
be pasted, and a run can be red.

The first link is directly checkable. Each comment cites a GitHub Actions run; the
API reports its conclusion and its artifacts. This resolves every cited run and
reports the conclusion, so "Tier-E holds" stops resting on the presence of a link.

    python3 research/verify_tier_e_artifacts.py
"""
from __future__ import annotations

import collections
import json
import re
import subprocess

RUN = re.compile(r"github\.com/([\w.-]+/[\w.-]+)/actions/runs/(\d+)", re.I)
LINKS = [
    re.compile(r"github\.com/[^\s)]*/(?:actions/runs|runs)/\d+", re.I),
    re.compile(r"\b[0-9a-f]{64}\b", re.I),
    re.compile(r"HW RESULT:\s*\d+/\d+\s*bit-exact", re.I),
    re.compile(r"0x[01]3636093", re.I),
]


def tier_e_runs():
    """(cell heading, repo, run id) for every complete-chain comment."""
    out = []
    for page in range(1, 6):
        raw = subprocess.run(
            ["gh", "api", "repos/gHashTag/trinity-fpga/issues/199/comments"
             f"?per_page=100&page={page}"], capture_output=True, text=True).stdout
        try:
            chunk = json.loads(raw)
        except json.JSONDecodeError:
            break
        if not chunk:
            break
        for c in chunk:
            b = c.get("body") or ""
            if not all(p.search(b) for p in LINKS):
                continue
            head = " ".join((b.strip().splitlines() or [""])[0].split())[:70]
            m = RUN.search(b)
            if m:
                out.append((head, m.group(1), m.group(2)))
    return out


def run_status(repo, rid):
    r = subprocess.run(
        ["gh", "api", f"repos/{repo}/actions/runs/{rid}",
         "--jq", '"\\(.conclusion // .status)\\t\\(.name)\\t\\(.created_at[0:10])"'],
        capture_output=True, text=True)
    if r.returncode != 0:
        return ("UNRESOLVABLE", "", "")
    parts = (r.stdout.strip() or "\t\t").split("\t")
    return tuple(parts + [""] * (3 - len(parts)))


def main() -> int:
    runs = tier_e_runs()
    print(f"complete-chain comments citing a CI run: {len(runs)}\n")

    tally = collections.Counter()
    bad = []
    seen = {}
    for head, repo, rid in runs:
        if rid in seen:
            concl = seen[rid]
        else:
            concl, name, when = run_status(repo, rid)
            seen[rid] = concl
        tally[concl] += 1
        if concl not in ("success",):
            bad.append((head, repo, rid, concl))

    print("CI run conclusions:")
    for k, v in tally.most_common():
        print(f"  {k:<14} {v}")

    if bad:
        print(f"\nruns that are NOT success ({len(bad)}):")
        for head, repo, rid, concl in bad[:15]:
            print(f"  {concl:<14} {repo}#{rid}")
            print(f"      {head}")
    else:
        print("\nEvery cited run resolves and reports success.")

    print(f"\ndistinct runs checked: {len(seen)}")
    print("""
This verifies link 1 of the four: the CI run exists and passed. Links 2-4 -- the
bitstream hash, the UART log and the IDCODE -- were produced on hardware and cannot
be re-derived without the board. What can be said is that the CI half of the chain
is not merely cited but real.""")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
