"""Throwaway probe 2 (exp/codegen-flake-ab, #851 W15).

1. One generation of every spec: which specs report behaviours but leave no
   output (missing or empty file, or a non-zero exit)? codegen_corpus counts
   those as ast-check clean, because `zig ast-check` on a missing file prints
   "error: unable to open file", which lacks the ": error: " it looks for.
2. REPEAT generations of every spec, four at a time: does any outcome vary?
3. `zig test` on every baseline output, four at a time: how many of the 788
   "clean" outputs compile?
"""

import collections
import concurrent.futures as cf
import hashlib
import os
import subprocess
import sys
import tempfile
import time

REPEAT = int(os.environ.get("REPEAT", "60"))
WORKERS = int(os.environ.get("WORKERS", "4"))
BASELINE = "tools/codegen_corpus_baseline.txt"


def find_gen():
    r = subprocess.run(
        "find .zig-cache -name vibee_gen -type f -perm -u+x -printf '%T@ %p\\n' | sort -nr | head -1",
        shell=True, capture_output=True, text=True)
    parts = r.stdout.split()
    no_gen = len(parts) < 2
    if no_gen:
        sys.exit("vibee_gen not found under .zig-cache")
    return os.path.abspath(parts[1])


def collect(root):
    acc = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not d.startswith(".")]
        for f in filenames:
            hidden = f.startswith(".")
            is_spec = f.endswith(".tri") or f.endswith(".vibee")
            if is_spec and not hidden:
                acc.append(os.path.join(dirpath, f))
    return sorted(acc)


def behaviours(text):
    at = text.find("Behaviors: ")
    missing = at < 0
    if missing:
        return 0
    i = at + len("Behaviors: ")
    n = 0
    while i < len(text) and text[i].isdigit():
        n = n * 10 + int(text[i])
        i += 1
    return n


def gen_once(gen, spec, dest):
    if os.path.exists(dest):
        os.remove(dest)
    p = subprocess.run([gen, "gen", spec, dest], capture_output=True, text=True, errors="replace")
    has_in_stderr = "Behaviors: " in p.stderr
    hay = p.stderr if has_in_stderr else p.stdout
    exists = os.path.exists(dest)
    if not exists:
        state = "MISSING"
    else:
        data = open(dest, "rb").read()
        state = "EMPTY" if len(data) == 0 else hashlib.sha256(data).hexdigest()[:12]
    return (p.returncode, behaviours(hay), state)


def repeat_task(gen, spec, workdir):
    dest = os.path.join(workdir, spec.replace("/", "_") + ".zig")
    outcomes = collections.Counter(gen_once(gen, spec, dest) for _ in range(REPEAT))
    return spec, outcomes


def compile_task(path, wid):
    p = subprocess.run(
        ["zig", "test", "--cache-dir", f".zig-cache/probe-child-{wid}", "--global-cache-dir",
         ".zig-cache/probe-global", path], capture_output=True, text=True, errors="replace")
    first = ""
    for line in p.stderr.splitlines():
        is_error = ": error: " in line
        if is_error:
            first = line.split(": error: ", 1)[1][:80]
            break
    return path, p.returncode, first


def main():
    gen = find_gen()
    specs = collect("specs")
    base = [l.strip() for l in open(BASELINE) if l.strip()]
    base_set = set(base)
    print(f"generator {gen}; {len(specs)} specs; baseline {len(base)}; repeat {REPEAT}; workers {WORKERS}")

    # 1. One generation each, kept on disk for step 3.
    os.makedirs("probe2/one", exist_ok=True)
    one = {}
    for s in specs:
        one[s] = gen_once(gen, s, f"probe2/one/{s.replace('/', '_')}.zig")
    no_output = [s for s in specs if one[s][1] > 0 and (one[s][2] in ("MISSING", "EMPTY") or one[s][0] != 0)]
    print(f"behaviours > 0 but rc != 0 or no output: {len(no_output)}; of those in the baseline: {sum(s in base_set for s in no_output)}")
    for s in no_output:
        print(f"  NO-OUTPUT {s} rc={one[s][0]} beh={one[s][1]} file={one[s][2]} baseline={s in base_set}")

    # 2. Repeats, in parallel, each spec in its own temp dir per worker.
    t0 = time.time()
    varied = []
    with cf.ThreadPoolExecutor(WORKERS) as ex:
        dirs = [tempfile.mkdtemp(prefix=f"rep{i}-", dir=".") for i in range(len(specs))]
        futs = [ex.submit(repeat_task, gen, s, d) for s, d in zip(specs, dirs)]
        for f in cf.as_completed(futs):
            spec, outcomes = f.result()
            varies = len(outcomes) > 1
            if varies:
                varied.append((spec, outcomes))
    print(f"repeats: {time.time() - t0:.1f} s for {len(specs) * REPEAT} generations")
    print(f"specs whose outcome varies over {REPEAT} runs: {len(varied)}")
    for spec, outcomes in sorted(varied):
        print(f"  VARIES {spec} baseline={spec in base_set}: {dict(outcomes)}")

    # 3. Compile every baseline output.
    t0 = time.time()
    fails = []
    with cf.ThreadPoolExecutor(WORKERS) as ex:
        futs = [ex.submit(compile_task, f"probe2/one/{s.replace('/', '_')}.zig", i % WORKERS) for i, s in enumerate(base)]
        for f in cf.as_completed(futs):
            path, rc, first = f.result()
            failed = rc != 0
            if failed:
                fails.append((path, first))
    print(f"compile: {time.time() - t0:.1f} s; {len(base) - len(fails)} of {len(base)} baseline outputs pass zig test")
    hist = collections.Counter(first for _, first in fails)
    for msg, n in hist.most_common(15):
        print(f"  {n:4d}  {msg}")
    for path, first in sorted(fails)[:60]:
        print(f"  FAIL {path}: {first}")


main()
