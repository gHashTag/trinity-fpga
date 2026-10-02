#!/usr/bin/env python3
"""Does ANY comment in issue #199 carry a complete Tier-E chain for GF64?

Item 1 of research/CORRECTIONS_PACKAGE_both_preprints.md says arXiv 2606.05017's
GF64 figure -- 70.1%, 359/512 -- sits inside a passage ending "Each ships with a
full evidence chain", and that no single GF64 comment carries all four Tier-E
links. That conclusion came from reading seventeen comments. It is the last major
item in the package with no script behind it.

research/verify_tier_e.py answers the general question and its cell list does not
contain gf64. That is suggestive and not sufficient: it groups by a cell name
parsed out of each comment, and comments whose name it cannot parse land in a "?"
bucket. A GF64 comment hiding there would make the absence an artefact of the
parser rather than a fact about the issue. Silence from an aggregate is not
evidence.

So this goes at it directly: take every comment that MENTIONS GF64 at all, by any
spelling, and count the four links in each one individually.

    1. a public CI run URL
    2. a bitstream SHA-256
    3. a UART "HW RESULT: N/N bit-exact" line
    4. the IDCODE (0x13636093, or its version-0 variant 0x03636093)

The claim under test is an existential one -- "there is no such comment" -- so a
single counterexample settles it, and the script exits non-zero if it finds one.

WHAT THIS CANNOT DO
-------------------
Re-run the CI, re-hash the bitstream or re-read the UART. It checks that the four
links are PRESENT in one comment, which is what Tier-E's own definition asks for.
A comment could carry four well-formed links that describe a different build.

Usage:  python3 research/audit_gf64_chain.py [--verbose]
"""
import json
import re
import subprocess
import sys

ISSUE = ("repos/gHashTag/trinity-fpga/issues/199/comments"
         "?per_page=100&page={page}")

# Every spelling seen in the corpus. gf_64 and GF-64 included because a mechanical
# check that misses a naming variant reproduces the very failure it is testing for.
MENTIONS = re.compile(r"\bgf[\s_-]?64\b", re.I)

LINKS = {
    "CI url":   re.compile(r"github\.com/[^\s)]*/(?:actions/runs|runs)/\d+", re.I),
    "sha256":   re.compile(r"\b[0-9a-f]{64}\b", re.I),
    "UART log": re.compile(r"HW RESULT:\s*\d+/\d+\s*bit-exact", re.I),
    "IDCODE":   re.compile(r"0x[01]3636093", re.I),
}

# A board reading that is NOT a conformance count. Comment 4958733671 carries
#
#     HW RESULT: GF64 ADD smoke 0+0=0x0000000000000000 @160000 IDCODE=0x13636093
#
# which is a genuine line off the board at the right baud with the right IDCODE --
# and a ONE-VECTOR smoke test, not an N/N bit-exact run. The strict pattern above
# rightly excludes it, but reporting that comment as simply "no UART log" would
# understate what is there, and this distinction is the whole substance of item 1.
# Reported as its own category rather than folded into either side.
SMOKE = re.compile(r"HW RESULT:(?![^\n]*\d+/\d+\s*bit-exact)[^\n]*", re.I)

SCORE = re.compile(r"\b(\d+)\s*/\s*(\d+)\b")


def fetch():
    out, page = [], 1
    while True:
        r = subprocess.run(["gh", "api", ISSUE.format(page=page)],
                           capture_output=True, text=True, timeout=180)
        if r.returncode != 0:
            return None, (r.stderr or "gh api failed").strip().splitlines()[-1][:120]
        batch = json.loads(r.stdout)
        if not batch:
            break
        out += batch
        if len(batch) < 100:
            break
        page += 1
    return out, None


def main():
    verbose = "--verbose" in sys.argv
    comments, err = fetch()
    if comments is None:
        print("could not fetch issue #199: %s" % err)
        print("Without the comments there is nothing to check -- not guessing.")
        return 2

    hits = [c for c in comments if MENTIONS.search(c.get("body") or "")]
    print("comments in issue #199        : %d" % len(comments))
    print("comments mentioning GF64      : %d" % len(hits))
    print()

    complete, partial, smokes = [], [], []
    print("%-10s %-8s %-8s %-9s %-8s  %s"
          % ("comment", "CI url", "sha256", "UART log", "IDCODE", "score seen"))
    for c in hits:
        body = c.get("body") or ""
        got = dict((k, bool(rx.search(body))) for k, rx in LINKS.items())
        n = sum(got.values())
        smoke = None
        if not got["UART log"]:
            m = SMOKE.search(body)
            if m and "|" not in m.group(0)[:20]:   # not a table header
                smoke = m.group(0).strip()[:70]
                smokes.append((c, smoke))
        scores = SCORE.findall(body)
        best = max((int(a) / int(b), "%s/%s" % (a, b))
                   for a, b in scores if int(b)) if scores else (0, "-")
        row = ("#%d" % c["id"])[-9:]
        print("%-10s %-8s %-8s %-9s %-8s  %s"
              % (row,
                 "yes" if got["CI url"] else ".",
                 "yes" if got["sha256"] else ".",
                 "yes" if got["UART log"] else ".",
                 "yes" if got["IDCODE"] else ".",
                 best[1]))
        (complete if n == 4 else partial).append((c, n, best[1]))

    print()
    print("GF64 comments with ALL FOUR links : %d" % len(complete))
    print("GF64 comments with one to three   : %d" % len(partial))
    print("of those, carrying a board reading that is NOT an N/N count : %d"
          % len(smokes))
    for c, line in smokes:
        print("    %s" % c["html_url"])
        print("      %s" % line)
    print()
    if complete:
        print("A COMPLETE GF64 CHAIN EXISTS. Item 1 of the corrections package")
        print("says there is none and must be withdrawn or narrowed:")
        for c, _, s in complete:
            print("    %s   score %s" % (c["html_url"], s))
        return 1

    print("No GF64 comment carries all four links. Item 1 stands, now mechanically")
    print("rather than by reading.")
    print()
    print("This checks PRESENCE of the four links in one comment, which is what")
    print("Tier-E's definition asks. It cannot re-run the CI, re-hash the bitstream")
    print("or re-read the UART -- those need the board.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
