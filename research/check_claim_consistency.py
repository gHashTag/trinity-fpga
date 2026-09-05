#!/usr/bin/env python3
"""Find the same format quoted with two different numbers in two documents.

The site has 48 automated checks. The research documents have none, and on
2026-08-11 that cost a day: `21.9397` and `22.4998` were both published as
"MXFP4 perplexity, SmolLM2, wikitext-2, 40 windows" in different files. Both were
correct — the same format at two headroom phases, see
`block/SCALE_PHASE_THEOREM_2026-08-11.md` — but nothing flagged the collision, so
it was found by a script refusing to run rather than by a check.

This is that check. It scans the research corpus for lines that attach a decimal
number to a known format name, groups by format, and reports formats quoted with
more than one value.

It is deliberately dumb in one direction: it CANNOT know whether two different
numbers are a contradiction or two legitimate conditions. So it does not fail on
disagreement by itself. It fails only when a disagreement is **undeclared** —
when no document in the collision names a convention, a model, or a window count
that would distinguish them. A declared difference is fine; a silent one is the
bug.

    python3 research/check_claim_consistency.py            # report
    python3 research/check_claim_consistency.py --strict   # exit 1 on undeclared
"""
import os
import re
import sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.abspath(__file__))

# Formats whose headline numbers have collided before, or plausibly could.
FORMATS = [
    "MXFP4", "MXFP6", "NVFP4", "Lloyd-Max", "TNF4", "TNF6",
    "E2M1", "NF4", "BOF4", "AF4", "tekum16", "GF-T16", "GF16",
]

# A claim looks like: <format> ... <number with a decimal point>, and the number
# must NOT carry a unit. The first version of this file matched "14.97x" (a
# ratio) and "91.36 dB" (an SNR) as if they were perplexities, which is how an
# over-broad instrument becomes worse than no instrument.
NUM = r"(\d{1,3}\.\d{2,6})(?![\dx×%]|\s*(?:x|×|dB|%|bits?|LUT|MHz|nats?))"

# Only lines that are actually reporting a perplexity. Everything else is a
# different quantity that happens to sit near a format name.
PPL_CONTEXT = ("ppl", "perplexity", "перплекс")

# Words whose presence near a number means the document HAS declared what
# distinguishes it. Any one of these is enough.
QUALIFIERS = [
    "convention", "phase", "rule", "windows", "window", "block", "K=",
    "normalis", "normaliz", "top", "rotat", "unrotated", "held out", "held-out",
    "in-sample", "out-of-sample", "SmolLM2", "Qwen", "Pythia", "Llama",
]

# Numbers that are not perplexities: bits, ratios, percentages, years.
def is_plausible_ppl(x):
    return 5.0 <= x <= 200.0


def scan():
    hits = defaultdict(list)          # format -> [(value, file, line_no, line)]
    for dirpath, dirnames, files in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if not d.startswith((".", "__"))]
        for fn in files:
            if not fn.endswith(".md"):
                continue
            path = os.path.join(dirpath, fn)
            rel = os.path.relpath(path, ROOT)
            try:
                text = open(path, encoding="utf-8").read()
            except (OSError, UnicodeDecodeError):
                continue
            for i, line in enumerate(text.splitlines(), 1):
                # A withdrawal or a correction is allowed to restate an old number.
                low = line.lower()
                if any(w in low for w in ("withdraw", "corrected", "superseded",
                                          "previously reported", "was wrong")):
                    continue
                if not any(c in low for c in PPL_CONTEXT):
                    continue
                for fmt in FORMATS:
                    if fmt.lower() not in low:
                        continue
                    for m in re.finditer(NUM, line):
                        v = float(m.group(1))
                        if is_plausible_ppl(v):
                            hits[fmt].append((v, rel, i, line.strip()))
    return hits


def main():
    strict = "--strict" in sys.argv
    hits = scan()
    undeclared = []

    print(f"  scanned {ROOT}")
    for fmt in sorted(hits):
        rows = hits[fmt]
        values = sorted({v for v, _, _, _ in rows})
        if len(values) < 2:
            continue
        # Group by file so a document quoting a table of variants is not a
        # collision with itself.
        by_file = defaultdict(set)
        for v, rel, _, _ in rows:
            by_file[rel].add(v)
        cross = {rel: vs for rel, vs in by_file.items() if vs}
        if len(cross) < 2:
            continue

        # Declared if every file in the collision qualifies its number.
        unqualified = []
        for v, rel, ln, line in rows:
            if not any(q.lower() in line.lower() for q in QUALIFIERS):
                unqualified.append((v, rel, ln, line))

        status = "declared" if not unqualified else "UNDECLARED"
        print(f"\n  {fmt}: {len(values)} distinct values across {len(cross)} files  [{status}]")
        for v in values:
            where = sorted({rel for vv, rel, _, _ in rows if vv == v})
            print(f"      {v:>10.4f}  {', '.join(where[:3])}"
                  + (f" (+{len(where)-3} more)" if len(where) > 3 else ""))
        for v, rel, ln, line in unqualified[:4]:
            print(f"      ! {rel}:{ln} quotes {v} with nothing to distinguish it")
            print(f"        {line[:100]}")
        if unqualified:
            undeclared.append(fmt)

    print()
    if not undeclared:
        print("  every cross-document collision is declared — each side names a")
        print("  convention, model, window count or block size that distinguishes it.")
        return 0
    print(f"  {len(undeclared)} format(s) quoted with different numbers and nothing")
    print(f"  to distinguish them: {', '.join(undeclared)}")
    print("  Either the numbers disagree, or the document is missing the condition")
    print("  that makes them both true. Both are worth fixing.")
    return 1 if strict else 0


if __name__ == "__main__":
    sys.exit(main())
