"""Throwaway probe (exp/codegen-flake-ab, #851 W15): is vibee_gen deterministic?

Generates every spec REPEAT times into separate directories, compares the
output bytes, and ast-checks the variants of any spec whose output differs.
Also reproduces codegen_corpus's sample choice from the first repeat.
"""

import hashlib
import os
import subprocess
import sys
import time

REPEAT = int(os.environ.get("REPEAT", "5"))
BASELINE = "tools/codegen_corpus_baseline.txt"
SAMPLE = 24


def find_gen():
    r = subprocess.run(
        "find .zig-cache -name vibee_gen -type f -perm -u+x -printf '%T@ %p\\n' | sort -nr | head -1",
        shell=True, capture_output=True, text=True)
    parts = r.stdout.split()
    no_gen = len(parts) < 2
    if no_gen:
        sys.exit("vibee_gen not found under .zig-cache")
    return parts[1]


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
    needle = "Behaviors: "
    at = text.find(needle)
    missing = at < 0
    if missing:
        return 0
    i = at + len(needle)
    n = 0
    while i < len(text) and text[i].isdigit():
        n = n * 10 + int(text[i])
        i += 1
    return n


def gen_one(gen, spec, dest):
    p = subprocess.run([gen, "gen", spec, dest], capture_output=True, text=True, errors="replace")
    has_in_stderr = "Behaviors: " in p.stderr
    hay = p.stderr if has_in_stderr else p.stdout
    exists = os.path.exists(dest)
    digest = hashlib.sha256(open(dest, "rb").read()).hexdigest()[:12] if exists else "MISSING"
    return p.returncode, behaviours(hay), digest


def ast_clean(path):
    p = subprocess.run(["zig", "ast-check", path], capture_output=True, text=True, errors="replace")
    return ": error: " not in p.stderr


def main():
    gen = find_gen()
    specs = collect("specs")
    print(f"generator {gen}; {len(specs)} specs; repeat {REPEAT}")
    flat = {s: s.replace("/", "_") + ".zig" for s in specs}
    collisions = len(specs) - len(set(flat.values()))
    print(f"output-name collisions: {collisions}")

    t0 = time.time()
    rows = {}
    for s in specs:
        rows[s] = []
        for r in range(REPEAT):
            d = f"probe/r{r}"
            os.makedirs(d, exist_ok=True)
            rows[s].append(gen_one(gen, s, f"{d}/{flat[s]}"))
    print(f"generation: {time.time() - t0:.1f} s for {len(specs) * REPEAT} runs")

    differ = [s for s in specs if len(set(rows[s])) > 1]
    print(f"specs whose (rc, behaviours, digest) differ across {REPEAT} repeats: {len(differ)}")
    for s in differ[:40]:
        print(f"  DIFFER {s}: {rows[s]}")

    # The tool's clean list, from repeat 0 only, as one CI run would see it.
    clean0 = []
    for s in specs:
        has_beh = rows[s][0][1] > 0
        if has_beh and ast_clean(f"probe/r0/{flat[s]}"):
            clean0.append(s)
    base = [l.strip() for l in open(BASELINE) if l.strip()]
    extra = [s for s in clean0 if s not in set(base)]
    lost = [s for s in base if s not in set(clean0)]
    print(f"clean in repeat 0: {len(clean0)}; baseline {len(base)}; clean-not-baseline {len(extra)}; baseline-not-clean {len(lost)}")
    for s in extra:
        print(f"  EXTRA {s}")
    for s in lost:
        print(f"  LOST {s}")

    # Clean status of each variant, for the specs whose output differs.
    flips = 0
    for s in differ:
        status = []
        for r in range(REPEAT):
            has_beh = rows[s][r][1] > 0
            status.append(has_beh and ast_clean(f"probe/r{r}/{flat[s]}"))
        flipped = len(set(status)) > 1
        if flipped:
            flips += 1
            print(f"  FLIP {s}: {status}")
    print(f"clean-status flips: {flips}")

    # The sample codegen_corpus would compile from this clean list.
    sample = min(SAMPLE, len(clean0))
    stride = max(1, len(clean0) // sample) if sample else 1
    picked = clean0[::stride][:sample]
    target = "specs/tri/phi_utils_multi.tri"
    print(f"stride {stride}; {target} index {clean0.index(target) if target in clean0 else -1}; sampled {target in picked}")

    # Why the spec that reddens main does not compile.
    p = subprocess.run(
        ["zig", "test", "--cache-dir", ".zig-cache/probe-child", "--global-cache-dir", ".zig-cache/probe-global",
         f"probe/r0/{flat[target]}"], capture_output=True, text=True, errors="replace")
    print(f"zig test {target}: rc {p.returncode}")
    print("\n".join(p.stderr.splitlines()[:30]))

    # If everything differs, show what varies.
    if differ:
        s = differ[0]
        a = open(f"probe/r0/{flat[s]}", errors="replace").read().splitlines() if os.path.exists(f"probe/r0/{flat[s]}") else []
        b = open(f"probe/r1/{flat[s]}", errors="replace").read().splitlines() if os.path.exists(f"probe/r1/{flat[s]}") else []
        import difflib
        print(f"first differing spec {s}, r0 vs r1:")
        print("\n".join(list(difflib.unified_diff(a, b, lineterm=""))[:40]))


main()
