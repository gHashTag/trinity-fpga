#!/usr/bin/env python3
"""THROWAWAY (exp/corpus-ab-*): set up one arm of the #885 A/B.

Each arm puts the tree into one situation, then the workflow runs
`zig build codegen-corpus` with whichever tool the branch carries. Both exp
branches run this same file, so main's tool and the fixed tool see the same
tree.

  extra        copy baseline entry 0 to specs/tri/a_s42_extra<ext>: one more
               clean spec, sorting before specs/tri/phi_utils_multi.tri
  unextra      remove it
  nonbase-dir  the first spec before phi_utils_multi that reports behaviours
               and is not in the baseline: put a directory where its output
               goes, so the generator cannot write it
  base-dir     baseline entry 1 (never sampled -- the slots are multiples of
               the stride): put a directory where its output goes
  clear-dirs   remove every directory this script made

Output paths are made for both tools: main's flattens '/' to '_', the fixed
one mirrors the spec path. Each tool ignores the other's.
"""
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile

BASELINE = pathlib.Path("tools/codegen_corpus_baseline.txt")
OUT = ".zig-cache/codegen-corpus"
PHI = "specs/tri/phi_utils_multi.tri"
MADE = pathlib.Path(".zig-cache/ab-pick-dirs.txt")
EXTRA_STEM = "specs/tri/a_s42_extra"


def say(msg):
    print(f"ab-pick: {msg}", flush=True)


def baseline():
    return [l.strip() for l in BASELINE.read_text().splitlines() if l.strip()]


def specs():
    """The tool's own walk: no dot-entries, regular files only, byte order."""
    acc = []

    def walk(p):
        for e in os.scandir(p):
            hidden = e.name.startswith(".")
            if hidden:
                continue
            is_dir = e.is_dir(follow_symlinks=False)
            if is_dir:
                walk(os.path.join(p, e.name))
                continue
            is_spec = e.is_file(follow_symlinks=False) and e.name.endswith((".tri", ".vibee"))
            if is_spec:
                acc.append(os.path.join(p, e.name))

    walk("specs")
    return sorted(acc)


def dests(spec):
    return [f"{OUT}/{spec.replace('/', '_')}.zig", f"{OUT}/{spec}.zig"]


def vibee_gen():
    found = []
    for root, _, files in os.walk(".zig-cache"):
        for f in files:
            p = os.path.join(root, f)
            usable = f == "vibee_gen" and os.access(p, os.X_OK)
            if usable:
                found.append(p)
    none = not found
    if none:
        sys.exit("ab-pick: no vibee_gen under .zig-cache -- run zig build codegen-corpus first")
    return max(found, key=os.path.getmtime)


def behaviours(text):
    needle = "Behaviors: "
    i = text.find(needle)
    absent = i < 0
    if absent:
        return 0
    digits = ""
    for ch in text[i + len(needle):]:
        is_digit = ch.isdigit()
        if not is_digit:
            break
        digits += ch
    return int(digits or "0")


def probe(gen, spec):
    """Generate to a scratch file: (behaviours, gen rc, ast-check rc, ': error: ' seen)."""
    with tempfile.TemporaryDirectory() as d:
        dest = os.path.join(d, "out.zig")
        r = subprocess.run([gen, "gen", spec, dest], capture_output=True, text=True)
        n = behaviours(r.stderr) or behaviours(r.stdout)
        a = subprocess.run(["zig", "ast-check", dest], capture_output=True, text=True)
        return n, r.returncode, a.returncode, ": error: " in a.stderr


def block(spec):
    made = []
    for p in dests(spec):
        is_file = os.path.isfile(p)
        if is_file:
            os.remove(p)
        os.makedirs(p, exist_ok=True)
        made.append(p)
    with MADE.open("a") as f:
        for p in made:
            f.write(p + "\n")
    say(f"directory at {' and '.join(made)}")


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    base = baseline()
    say(f"{cmd}: baseline {len(base)}, specs {len(specs())}")

    if cmd == "extra":
        src = base[0]
        dst = EXTRA_STEM + os.path.splitext(src)[1]
        shutil.copyfile(src, dst)
        n, grc, arc, err = probe(vibee_gen(), dst)
        say(f"extra {dst} copied from {src}: behaviours={n} gen_rc={grc} astcheck_rc={arc} error_line={err}")
        say(f"extra sorts before {PHI}: {dst < PHI}")
    elif cmd == "unextra":
        for ext in (".tri", ".vibee"):
            p = EXTRA_STEM + ext
            present = os.path.exists(p)
            if present:
                os.remove(p)
                say(f"removed {p}")
    elif cmd == "nonbase-dir":
        gen = vibee_gen()
        in_base = set(base)
        for s in specs():
            past_phi = s >= PHI
            if past_phi:
                sys.exit("ab-pick: no non-baseline spec with behaviours sorts before " + PHI)
            recorded = s in in_base
            if recorded:
                continue
            n, grc, arc, err = probe(gen, s)
            silent = n == 0
            if silent:
                continue
            say(f"nonbase {s}: behaviours={n} gen_rc={grc} astcheck_rc={arc} error_line={err}")
            block(s)
            return
    elif cmd == "base-dir":
        s = base[1]
        say(f"base {s} (baseline index 1)")
        block(s)
    elif cmd == "clear-dirs":
        made = MADE.read_text().splitlines() if MADE.exists() else []
        for p in made:
            shutil.rmtree(p, ignore_errors=True)
            say(f"removed {p}")
        MADE.unlink(missing_ok=True)
    else:
        sys.exit("usage: codegen_ab_pick.py extra|unextra|nonbase-dir|base-dir|clear-dirs")


if __name__ == "__main__":
    main()
