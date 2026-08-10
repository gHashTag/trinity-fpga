#!/usr/bin/env python3
"""Does every artefact have code that produces it?

Two of the paper's six figures had no generator: the PDFs sat in the tree and
the code that drew them did not. They were also the only two still carrying the
format's name from two renames ago, and the two facts are one fact. **A file
nobody regenerates is a file nobody renames.**

So an orphaned artefact is not merely a reproducibility gap. It is where staleness
accumulates, because every sweep that updates the tree updates the code and
leaves the outputs alone.

This looks for artefacts -- figures, measured data, netlists -- that no script,
makefile or documented command names as an output.
"""
import re, pathlib, sys, collections

ROOT = pathlib.Path(__file__).resolve().parents[1]
# artefact kinds that are produced rather than written by hand
PATTERNS = ["research/**/*.pdf", "research/**/*.json", "research/**/*.png"]
SKIP_NAME = re.compile(r"(_paper|_baseline|cases|package(-lock)?)\.", re.I)
SKIP_DIR = {"node_modules", ".git", "__pycache__", "arxiv_submission"}

# everything a producer might be
producers = []
for pat in ("**/*.py", "**/*.sh", "**/Makefile", "**/*.mk", "**/*.md", "**/*.yml"):
    for f in ROOT.glob(pat):
        if any(p in SKIP_DIR for p in f.parts): continue
        try: producers.append((f, f.read_text(errors="ignore")))
        except Exception: pass

arts = []
for pat in PATTERNS:
    for f in ROOT.glob(pat):
        if any(p in SKIP_DIR for p in f.parts): continue
        if SKIP_NAME.search(f.name): continue
        arts.append(f)

def produced(a):
    """Literal name, or the f-string shape that writes it.

    A script writing f"scale_frontier_{TAG}.json" never contains the literal
    scale_frontier_smollm2.json, so matching only literals reports the whole
    parameterised family as orphaned. Match the stem before the last underscore
    plus the extension too."""
    if any(a.name in src for _, src in producers): return True
    stem, ext = a.stem, a.suffix
    for cut in range(len(stem) - 1, 0, -1):
        if stem[cut] != "_": continue
        pref = stem[:cut]
        needle = pref + '_{'
        if any(needle in src and ext in src for _, src in producers): return True
        break
    return False

orphans = [str(a.relative_to(ROOT)) for a in arts if not produced(a)]

BASE = pathlib.Path(__file__).with_name("orphan_artefacts_baseline.txt")
print(f"artefacts scanned: {len(arts)}   producers scanned: {len(producers)}")
uniq = sorted(set(orphans))
if "--update-baseline" in sys.argv:
    BASE.write_text("\n".join(uniq) + ("\n" if uniq else ""))
    print(f"baseline written: {len(uniq)} known"); sys.exit(0)
known = {l for l in BASE.read_text().splitlines() if l.strip()} if BASE.exists() else set()
new = sorted(set(uniq) - known)
if new:
    print(f"\nFAIL: {len(new)} artefact(s) that no code produces\n")
    for x in new: print(f"  {x}")
    print("\n  An artefact with no generator is where staleness accumulates.")
    sys.exit(1)
print(f"OK: no new orphaned artefacts ({len(known)} known)")
