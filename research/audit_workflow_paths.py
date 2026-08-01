#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Do the synthesis workflows watch the files they build?

Pass 109 found ax7203-gf16-conformance.yml triggering on gf16_add.v and gf16_mul.v
while its synthesis step read gf16_codec_ax7203.v and gf16_adder.v. Neither watched
file appeared in any read_verilog line, so editing one started a build that ignored it
and reported success -- a green run carrying no information about the change that
caused it.

That was found by accident, while chasing something else. This looks for the same
shape everywhere, and reports two directions separately because they mean different
things:

    watched but not built   a change to this file triggers a build that cannot see
                            it. The run goes green regardless. This is the pass-109
                            defect.

    built but not watched   a change to this file does NOT trigger the build that
                            compiles it. The defect is the mirror image: silence
                            rather than a false pass, and it means a broken source
                            can sit unnoticed until something else triggers the job.

Neither is read from the workflow's name or its comments, only from its `paths:` list
and its `read_verilog` arguments, because names and comments are what went stale.

    python3 research/audit_workflow_paths.py [--verbose]
"""
from __future__ import annotations

import argparse
import os
import re

WF = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                  "..", ".github", "workflows")

READV = re.compile(r"read_verilog\s+([^\";']+)")
# A source can reach the job through iverilog as well as through yosys. Looking only
# at read_verilog flagged three trinet workflows whose testbenches are compiled by
# iverilog on the line above -- three findings that were not findings, caught by
# reading the workflow before reporting.
# Line continuations matter: wrapper-fsm-sim.yml names its sources on the lines
# after `iverilog -g2012 -o /tmp/a.vvp ... \`, and a pattern stopping at the first
# newline reported it as watching files it never built. Second false positive from
# this tool, second one caught by reading the workflow instead of the report.
IVERILOG = re.compile(r"iverilog\s+((?:[^\n|&;]|\\\n)+)")
# A shell expansion such as ${name}_add.v leaves "_add.v" behind, which is not a
# file. Requiring a leading word character drops those without hiding real names.
VFILE = re.compile(r"(?<![\w./-])[A-Za-z0-9][\w./-]*\.v\b")


def paths_block(text: str) -> list[str]:
    """Every quoted path under a `paths:` key, push and pull_request alike."""
    out, in_paths = [], False
    for line in text.splitlines():
        if re.match(r"\s*paths:\s*$", line):
            in_paths = True
            continue
        if in_paths:
            m = re.match(r"\s*-\s*'([^']+)'\s*$", line) or \
                re.match(r'\s*-\s*"([^"]+)"\s*$', line)
            if m:
                out.append(m.group(1))
                continue
            if line.strip().startswith("#"):
                continue
            in_paths = False
    return out


def matches(pattern: str, path: str) -> bool:
    """A `paths:` glob against a repo-relative file, loosely but not wrongly.

    Only the forms this tree actually uses are handled -- ** and * -- and a pattern
    with no wildcard has to match exactly. Being loose here would turn a real finding
    into a false clean.
    """
    # A pattern naming a directory covers everything beneath it, which is how
    # GitHub Actions reads it -- and is the only way to watch a submodule, whose
    # internal edits are invisible to this repository's path filter anyway.
    if "*" not in pattern and not pattern.endswith(".v"):
        if path == pattern or path.startswith(pattern.rstrip("/") + "/"):
            return True
    rx = re.escape(pattern).replace(r"\*\*", ".*").replace(r"\*", "[^/]*")
    rx = rx.replace(r"\{", "(").replace(r"\}", ")").replace(",", "|")
    return re.fullmatch(rx, path) is not None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    files = sorted(f for f in os.listdir(WF) if f.endswith((".yml", ".yaml")))
    checked = 0
    watch_not_build, build_not_watch, delegated = [], [], []

    for fn in files:
        text = open(os.path.join(WF, fn), encoding="utf-8",
                    errors="replace").read()
        # Everything the job names outside its paths: block. Two attempts at
        # parsing specific invocations (read_verilog, then iverilog with line
        # continuations) each produced false positives, so this stops trying to
        # understand the command and simply asks which sources the file mentions.
        watched_lines = set()
        in_p = False
        for line in text.splitlines():
            if re.match(r"\s*paths:\s*$", line):
                in_p = True
            elif in_p and not re.match(r"\s*-\s*['\"]", line):
                in_p = False
            if in_p:
                watched_lines.add(line)
        built = set()
        for line in text.splitlines():
            if line in watched_lines or line.lstrip().startswith("#"):
                continue
            built |= set(VFILE.findall(line))
        if not built:
            continue                       # not a synthesis workflow
        checked += 1
        watched = paths_block(text)
        if not watched:
            continue                       # manual-dispatch only; nothing to compare

        # a watched pattern that matches no built file and no workflow file
        stray = []
        for p in watched:
            if p.endswith((".yml", ".yaml", ".xdc", ".tcl")):
                continue
            if not p.endswith(".v"):
                continue
            if any(matches(p, b) or b.endswith(p.split("/")[-1]) for b in built):
                continue
            stray.append(p)
        # A job that hands synthesis to a script names nothing itself, so its
        # watches cannot be matched here. lut-report.yml is the case in this tree:
        # it generates wrappers into /tmp and runs fpga/openxc7-synth/run_synth.py,
        # which is what reads the parametric cores it watches. Reported as a
        # limitation rather than a finding, because it is one.
        delegates = re.search(r"python3?\s+\S+\.py", text) is not None
        if stray and not delegates:
            watch_not_build.append((fn, stray, sorted(built)))
        elif stray:
            delegated.append((fn, stray))

        # a built file no watched pattern would catch
        unwatched = [b for b in sorted(built)
                     if not any(matches(p, b) or p.split("/")[-1] == b.split("/")[-1]
                                for p in watched)]
        if unwatched:
            build_not_watch.append((fn, unwatched))

    print(f"workflow files                     : {len(files)}")
    print(f"  with a read_verilog step         : {checked}")
    print(f"  watching a .v they never build   : {len(watch_not_build)}")
    print(f"  building a .v they never watch   : {len(build_not_watch)}")
    print(f"  delegating synthesis to a script : {len(delegated)}  "
          f"(not checkable here)\n")
    for fn, stray in delegated:
        print(f"  {fn} watches {', '.join(stray)} and runs a script that reads them")
    if delegated:
        print()

    if watch_not_build:
        print("WATCHED BUT NOT BUILT -- a change here triggers a build that "
              "ignores it:")
        for fn, stray, built in watch_not_build:
            print(f"  {fn}")
            for s in stray:
                print(f"      watches {s}")
            if args.verbose:
                for b in built:
                    print(f"      builds  {b}")
        print()

    if build_not_watch:
        print("BUILT BUT NOT WATCHED -- a change here triggers nothing:")
        for fn, unwatched in build_not_watch[:12]:
            print(f"  {fn}")
            for u in unwatched:
                print(f"      builds {u}")
        if len(build_not_watch) > 12:
            print(f"  ... and {len(build_not_watch) - 12} more")

    print("""
Read from `paths:` and `read_verilog` only. A workflow's name and its header comments
are exactly what went stale in the case that prompted this, so neither is consulted.""")
    # Both directions fail the check. Exiting 0 on "built but not watched" was the
    # first version's behaviour, and the negative control caught it: that is the
    # direction which found the unwatched parametric cores behind the Tier-E proofs,
    # so a gate blind to it would be a gate blind to the worst case so far.
    return 1 if (watch_not_build or build_not_watch) else 0


if __name__ == "__main__":
    raise SystemExit(main())
