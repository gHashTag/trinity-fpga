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
# `.gate_cache` holds files the gates write and rewrite for themselves. A cache
# has no generator by design and regenerates when deleted, so counting one as
# an artefact that "no code produces" is a category error, not a finding.
SKIP_DIR = {"node_modules", ".git", "__pycache__", "arxiv_submission", ".gate_cache"}

# A gate is not a producer. tools/check_*.py name files in order to CHECK them,
# and the harness that proves each gate can fail (check_gates_can_fail.py)
# names the very orphan it plants. Counting the gates as producers made this
# gate pass its own defect the first day it was green: the planted file was
# "produced" by the line that planted it.
GATE = re.compile(r"^check_.*\.py$")

# everything a producer might be
producers = []
for pat in ("**/*.py", "**/*.sh", "**/Makefile", "**/*.mk", "**/*.md", "**/*.yml"):
    for f in ROOT.glob(pat):
        if any(p in SKIP_DIR for p in f.parts): continue
        if f.parent == ROOT / "tools" and GATE.match(f.name): continue
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
    # An f-string names the file in pieces. Two shapes occur here:
    #   f"scale_frontier_{TAG}.json"                       -> prefix + "_{"
    #   f"zphi_acc_width{'_row' if ROWMODE else ''}.json"  -> prefix + "{"
    # so try every prefix of the stem, longest first, against both shapes. A
    # prefix shorter than three characters is too weak to mean anything -- and
    # six was too strict: awq_test.py writes f"awq_{TAG}.json" and the whole
    # family read as orphaned. The extension must appear in the same file too,
    # which is what keeps a three-letter prefix from matching anything.
    #
    # The prefix must START a name. Matched as a bare substring, "gate_{" was
    # found inside f"lineD_actgate_{MDIR}.json", so that one script "produced"
    # every gate_*.json in the tree -- including the orphan that
    # check_gates_can_fail plants to prove this gate can fail. The substring
    # test stays as a cheap filter; the boundary is checked only on a hit.
    for cut in range(len(stem), 2, -1):
        pref = stem[:cut]
        for needle in (pref + "{", pref + "_{"):
            at_start = re.compile(r"(?<![A-Za-z0-9_])" + re.escape(needle))
            if any(needle in src and ext in src and at_start.search(src)
                   for _, src in producers):
                return True
    return False

# A DRAWN figure has no generator by nature: an illustration plate is made, not
# computed, and no script will ever name it as an output. Counting such plates as
# orphans kept eighty of them in the failure list for weeks, where they buried
# the thirteen measurement records that were a real question. They are not
# waved through silently either: a directory opts out only by DECLARING it, in a
# README.md beside the files carrying the marker below, and every run prints how
# many artefacts rely on a declaration. Only figures can be declared -- a .json
# is data, and data that no code produces is never "drawn".
DRAWN_MARK = "<!-- orphan-artefacts: drawn-not-computed -->"
DRAWN_KINDS = (".png", ".pdf", ".svg")
_drawn_dirs = {}
def declared_drawn(a):
    if a.suffix not in DRAWN_KINDS: return False
    if a.parent not in _drawn_dirs:
        rd = a.parent / "README.md"
        _drawn_dirs[a.parent] = rd.exists() and declares(rd.read_text(errors="ignore"))
    return _drawn_dirs[a.parent]

# The marker DECLARES only on a line of its own, outside a code fence. Matched
# anywhere in the text, a README that merely quoted it -- to explain the gate,
# or inline in a sentence -- exempted its whole directory without meaning to.
#
# "Outside a code fence" means every way Markdown quotes a line: ``` and ~~~
# fences, a fence closed only by its own character at least as long as the one
# that opened it (so ```` can quote ```), and a line indented four columns or
# more, which is an indented code block. Toggling on ``` alone let a ~~~ fence,
# an indented block, or a ``` nested in ```` declare the directory after all.
# A fence line is indented at most three columns. Four or more is an indented
# code line, never a fence -- so it can neither open one nor close one. Let it
# close one and a marker quoted after it, still inside the block, declared.
# Tabs are expanded before matching, so a tab counts as four columns.
FENCE = re.compile(r" {0,3}(`{3,}|~{3,})(.*)$")
def declares(text):
    fence = None
    # A UTF-8 byte-order mark is not part of the first line; left in, it made a
    # marker on line one fail to equal DRAWN_MARK.
    #
    # Markdown ends a line only at \n, \r\n or \r. str.splitlines() also breaks
    # at \f, \v, \x1c-\x1e, \x85, U+2028 and U+2029, so a ``` glued to quoted
    # text by one of those closed the fence here while the renderer kept it
    # open, and a marker quoted below it declared the directory.
    text = text.lstrip("\ufeff").replace("\r\n", "\n").replace("\r", "\n")
    for line in text.split("\n"):
        line = line.expandtabs(4)
        m = FENCE.match(line)
        if m and m.group(1)[0] == "`" and "`" in m.group(2):
            m = None  # ```x``` is inline code, not a fence
        if fence:
            if (m and m.group(1)[0] == fence[0] and len(m.group(1)) >= len(fence)
                    and not m.group(2).strip()):
                fence = None
        elif m:
            fence = m.group(1)
        elif len(line) - len(line.lstrip()) < 4 and line.strip() == DRAWN_MARK:
            return True
    return False

unproduced = [a for a in arts if not produced(a)]
drawn = [a for a in unproduced if declared_drawn(a)]
orphans = [str(a.relative_to(ROOT)) for a in unproduced if not declared_drawn(a)]

BASE = pathlib.Path(__file__).with_name("orphan_artefacts_baseline.txt")
print(f"artefacts scanned: {len(arts)}   producers scanned: {len(producers)}")
for d in sorted({a.parent for a in drawn}):
    n = sum(1 for a in drawn if a.parent == d)
    print(f"declared drawn, not computed: {n} in {d.relative_to(ROOT)}/ (see its README.md)")
uniq = sorted(set(orphans))
if "--update-baseline" in sys.argv:
    BASE.write_text("\n".join(uniq) + ("\n" if uniq else ""))
    print(f"baseline written: {len(uniq)} known"); sys.exit(0)
known = {l for l in BASE.read_text().splitlines() if l.strip()} if BASE.exists() else set()
new = sorted(set(uniq) - known)
# One flat list of ninety-odd paths reads as a wall and gets skipped. These are
# not one problem: a directory of plates awaiting a decision, a handful of
# measurement records written by hand, and whatever else. Group them so the
# question each group asks is visible, and print the groups largest first.
def group_of(path):
    if "/canon/" in path:        return "canon plates -- figures with no generator"
    if "/measurements/" in path: return "measurement records written without a script"
    if path.endswith((".png", ".pdf", ".svg")): return "other figures"
    return "other artefacts"

if new:
    print(f"\nFAIL: {len(new)} artefact(s) that no code produces\n")
    groups = {}
    for x in new: groups.setdefault(group_of(x), []).append(x)
    for name, items in sorted(groups.items(), key=lambda kv: -len(kv[1])):
        print(f"  {len(items)}x  {name}")
        for x in items[:6]: print(f"        {x}")
        if len(items) > 6: print(f"        ... and {len(items) - 6} more")
        print()
    print("  An artefact with no generator is where staleness accumulates.")
    print("  These groups ask different questions; answering them together is")
    print("  why the count has stood for weeks.")
    sys.exit(1)
print(f"OK: no new orphaned artefacts ({len(known)} known)")
