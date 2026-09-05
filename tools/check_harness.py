#!/usr/bin/env python3
"""Does a synthesis harness observe the whole output of the design under test?

Two confounds in three iterations, both in the harness rather than in any design
or claim, both invisible in the numbers because every run synthesised, routed and
reported plausible figures:

  1. A shared accumulator common to all candidates held the critical path, so
     delay differences bounded the shared block rather than the varying part.
  2. A harness observing four output bits pruned an unobserved 32-bit datapath to
     15% of itself, and pruned an unrelated 6-bit design barely at all -- an
     unequal cut that reversed a 2.34x conclusion.

Synthesis removes logic that does not reach an output. A harness must therefore
fold EVERY output bit of the design under test into what it observes, or the
comparison is between designs cut to different fractions of themselves.

This scans harness files for the two signatures: a partial slice of an
instantiated design's output driving the observed port, and an output port
narrower than the design's own outputs with no reduction in between.
"""
import re, sys, pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]

def analyse(p):
    src = p.read_text(errors="ignore")
    out = []
    # width of the module's own output port
    mo = re.search(r'output\s+wire\s+\[(\d+):0\]\s+(\w+)', src)
    if not mo: return out
    port_w, port = int(mo.group(1)) + 1, mo.group(2)
    # what drives it
    dr = re.search(r'assign\s+' + port + r'\s*=\s*([^;]+);', src)
    if not dr: return out
    expr = dr.group(1)
    # wires declared in the harness that carry a design output
    wires = {m.group(2): int(m.group(1)) + 1
             for m in re.finditer(r'wire\s+(?:signed\s+)?\[(\d+):0\]\s+(\w+)', src)}
    wires.update({m.group(2): int(m.group(1)) + 1
                  for m in re.finditer(r'reg\s+(?:signed\s+)?\[(\d+):0\]\s+(\w+)', src)})
    for name, w in wires.items():
        if name == port or w <= port_w: continue
        # is this wire referenced in the driving expression, and only in part?
        # A bare reference to the whole register observes every bit of it. A
        # reduction such as `^{q, 4'b0}` in a ternary condition does exactly
        # that, and counting only explicit slices reported it as observing 8 of
        # 23 bits. Checked by experiment before changing this: removing the
        # reduction pruned 30 flip-flops, so it was protecting the logic and the
        # report was a false positive.
        if re.search(r'\b' + re.escape(name) + r'\b(?!\s*\[)', expr):
            continue
        refs = re.findall(re.escape(name) + r'\s*\[(\d+):(\d+)\]', expr)
        if not refs: continue
        covered = set()
        for hi, lo in refs: covered |= set(range(int(lo), int(hi) + 1))
        if len(covered) < w:
            out.append(f"{p.relative_to(ROOT)}: observes {len(covered)} of {w} bits "
                       f"of `{name}` -- {100*(1-len(covered)/w):.0f}% of the logic "
                       f"feeding it can be pruned")
    return out

fails, checked = [], 0
# Scripts that GENERATE wrappers are read too. The wrappers behind several
# published numbers were written by a shell script, gitignored as scratch, and
# then deleted -- so the evidence for how those numbers were observed did not
# survive the measurement. A generator is permanent where its output is not.
for sh in sorted(ROOT.rglob("fpga/**/*.sh")):
    try: src = sh.read_text(errors="ignore")
    except Exception: continue
    # Comments are not code. This script's own header quotes the defective
    # harness it replaces -- "# assign led = ao[7:0] ^ am[7:0];" -- and reading
    # that as the wrapper reported a clean generator as a dirty one.
    code = "\n".join(l for l in src.split("\n") if not l.lstrip().startswith("#"))
    for m in re.finditer(r"assign\s+led\s*=\s*([^;]+);", code, re.S):
        expr = m.group(1)
        # a reduction over the whole register, ^{q...}, observes everything
        if "^{" in expr: continue
        bits = set()
        for r_ in re.finditer(r"\[\s*(\d+)\s*:\s*(\d+)\s*\]", expr):
            hi, lo = int(r_.group(1)), int(r_.group(2))
            bits |= set(range(min(hi, lo), max(hi, lo) + 1))
        decl = re.search(r"wire\s*\[\s*(\d+)\s*:\s*0\s*\]\s*all\b", code) \
            or re.search(r"reg\s*\[\s*(\d+)\s*:\s*0\s*\]\s*q\b", code)
        if decl and bits:
            width = int(decl.group(1)) + 1
            if len(bits) < width:
                fails.append(f"{sh.relative_to(ROOT)}: the wrapper it writes observes "
                             f"{len(bits)} of {width} bits -- "
                             f"{100*(width-len(bits))//width}% can be pruned")

for v in sorted(ROOT.rglob("fpga/**/*.v")):
    if not re.search(r'output\s+wire\s+\[\d+:0\]\s+led', v.read_text(errors="ignore")):
        continue
    checked += 1
    fails += analyse(v)

# Ratchet: the tree carries 83 known partial-observation harnesses, most of them
# one-off experiment files. Blocking every PR on that would make the gate useless
# until someone deleted them all. Fail only on NEW ones, and on baseline entries
# that stop reproducing so the file cannot rot into a permanent excuse.
import os
BASE = pathlib.Path(__file__).with_name("harness_baseline.txt")
print(f"harness files scanned: {checked}")
uniq = sorted(set(fails))
if "--update-baseline" in sys.argv:
    BASE.write_text("\n".join(uniq) + ("\n" if uniq else ""))
    print(f"baseline written: {len(uniq)} known"); sys.exit(0)
known = {l for l in BASE.read_text().splitlines() if l.strip()} if BASE.exists() else set()
new, gone = sorted(set(uniq) - known), sorted(known - set(uniq))
if gone:
    print(f"\n{len(gone)} baseline entry/entries no longer reproduce -- "
          f"run --update-baseline to shrink the ratchet")
if new:
    print(f"\nFAIL: {len(new)} NEW partial-observation harness(es)\n")
    for f in new: print(f"  {f}")
    sys.exit(1)
if gone: sys.exit(1)
print(f"OK: no new partial-observation harnesses ({len(known)} known)")
sys.exit(0)
if fails:
    print(f"\nFAIL: {len(fails)} partial-observation harness(es)\n")
    for f in sorted(set(fails)): print(f"  {f}")
    sys.exit(1)
print("OK: every harness observes the full width of the outputs it drives from")
