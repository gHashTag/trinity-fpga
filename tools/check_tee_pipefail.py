#!/usr/bin/env python3
"""Can a workflow step that pipes into tee still go red?

A step with no `shell:` runs as `bash -e {0}`: errexit, but NO pipefail. A
pipeline's status is then the status of its LAST command, so

    yosys -p synth.ys 2>&1 | tee synth.log

exits with tee's status -- 0 -- when yosys fails, and the step is green over a
synthesis that never happened. GitHub documents this (`shell: bash` alone means
`bash --noprofile --norc -eo pipefail {0}`; leaving it out does not), and two
workflows here already say so in prose and close it with
`defaults: run: shell: bash -eo pipefail {0}` (tnf-boundary-gate,
reachability-ratchet). The other workflows never heard. Neither actionlint nor
shellcheck flags it: the script is fine, the shell it runs under is not.

A step passes when the pipe cannot hide a failure:

  - its effective shell has pipefail (`shell: bash`, or a `shell:` / job
    `defaults` / workflow `defaults` line that says pipefail);
  - the script turns pipefail on (`set -o pipefail`, `set -eo pipefail`, ...)
    before the pipe, and has not turned it off again;
  - the script reads PIPESTATUS after the pipe (it checks the left side itself);
  - the left side is a bare echo/printf, which has no failure to hide;
  - the pipeline ends in `|| true` / `|| :`, which declares the failure
    unimportant with or without pipefail.

The steps found on the day this gate was written sit in
tools/tee_pipefail_baseline.txt. It is a ratchet in both directions, as in
check_doc_refs (#819): a step not in it fails, and an entry that no longer
reproduces fails too, because a stale entry is a pre-approved defect waiting to
come back. `--prune-baseline` writes baseline & current, so it can only remove;
there is no flag that adds.

Exit 0 clean, 1 a new or stale entry, 2 a workflow this parser could not read
(cannot tell is not clean).
"""
from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
BASE = pathlib.Path(__file__).with_name("tee_pipefail_baseline.txt")

# A single `|` (not `||`) followed by tee, or `|&` (stderr too) into tee.
TEE = re.compile(r"(?<!\|)\|&?(?!\|)\s*tee\b")
SET_ON = re.compile(r"^\s*set\b[^#]*?(-[A-Za-z]*o\s*pipefail\b|-o\s+pipefail\b)")
SET_OFF = re.compile(r"^\s*set\b[^#]*\+o\s+pipefail\b")
SWALLOWED = re.compile(r"\|\|\s*(true|:)\s*(;\s*)?$")
BARE_ECHO = re.compile(r"^\s*(echo|printf)\b[^|;&`]*$")
KEY = re.compile(r"^(\s*)(-\s+)?([A-Za-z0-9_.-]+)\s*:(\s*(.*))?$")


def shell_has_pipefail(shell: str | None) -> bool | None:
    """True/False for a declared shell, None when none is declared."""
    if shell is None:
        return None
    s = shell.strip().strip("'\"")
    # `shell: bash` is the one spelling GitHub expands WITH pipefail.
    return s == "bash" or "pipefail" in s


def unquote(v: str) -> str:
    v = v.strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in "'\"":
        return v[1:-1]
    return v


def block(lines: list[str], i: int, key_indent: int) -> tuple[list[str], int]:
    """The block scalar after line i: every following line indented deeper
    than its key, or blank. Returns (body, index of the first line after)."""
    body, j = [], i + 1
    while j < len(lines):
        ln = lines[j]
        if ln.strip() and len(ln) - len(ln.lstrip()) <= key_indent:
            break
        body.append(ln)
        j += 1
    while body and not body[-1].strip():
        body.pop()
    if body:
        cut = min(len(b) - len(b.lstrip()) for b in body if b.strip())
        body = [b[cut:] for b in body]
    return body, j


def logical_lines(script: list[str]) -> list[tuple[int, str]]:
    """Backslash-continued lines joined; (first physical index, text)."""
    out, buf, start = [], "", 0
    for k, ln in enumerate(script):
        if not buf:
            start = k
        if ln.rstrip().endswith("\\"):
            buf += ln.rstrip()[:-1] + " "
            continue
        out.append((start, buf + ln))
        buf = ""
    if buf:
        out.append((start, buf))
    return out


def unsafe_pipes(script: list[str], pipefail: bool) -> list[int]:
    """Indexes (into script) of tee pipes that can hide a failure."""
    hits = []
    logical = logical_lines(script)
    for n, (k, text) in enumerate(logical):
        stripped = text.strip()
        if stripped.startswith("#"):
            continue
        if SET_OFF.search(text):
            pipefail = False
            continue
        if SET_ON.search(text):
            pipefail = True
            continue
        m = TEE.search(text)
        if not m or pipefail:
            continue
        if SWALLOWED.search(stripped):
            continue
        # A failure inside echo's $(...) is lost to echo itself, pipefail or
        # not, so only the echo's own pipes count.
        left = text[: m.start()]
        while True:
            flat = re.sub(r"\$\([^()]*\)|`[^`]*`", "S", left)
            if flat == left:
                break
            left = flat
        if BARE_ECHO.match(left):
            continue
        if any("PIPESTATUS" in t for _, t in logical[n:]):
            continue
        hits.append(k)
    return hits


def scan(path: pathlib.Path) -> tuple[list[tuple[str, int]], str | None]:
    """[(key, line number)] of unsafe steps, or an error message."""
    rel = path.relative_to(ROOT).as_posix()
    lines = path.read_text().splitlines()
    wf_shell: str | None = None
    found: list[tuple[str, int]] = []

    # Workflow-level defaults.run.shell: `defaults:` at column 0.
    for i, ln in enumerate(lines):
        if ln.startswith("defaults:"):
            for ln2 in lines[i + 1:]:
                if ln2.strip() and not ln2.startswith(" "):
                    break
                m = re.match(r"^\s+shell:\s*(.+?)\s*$", ln2)
                if m:
                    wf_shell = m.group(1)

    try:
        jobs_at = next(i for i, ln in enumerate(lines) if re.match(r"^jobs:\s*$", ln))
    except StopIteration:
        return [], f"{rel}: no top-level `jobs:` -- cannot read it"

    i, job, job_indent = jobs_at + 1, None, None
    job_shell: str | None = None
    while i < len(lines):
        ln = lines[i]
        if ln.strip() and not ln.startswith((" ", "#")):
            break  # left the jobs mapping
        m = KEY.match(ln)
        if not m or ln.lstrip().startswith("#"):
            i += 1
            continue
        ind = len(m.group(1))
        if job_indent is None:
            job_indent = ind
        if ind == job_indent and not m.group(2):
            job, job_shell = m.group(3), None
            i += 1
            continue
        if m.group(3) == "defaults" and ind == job_indent + 2:
            for ln2 in lines[i + 1:]:
                if ln2.strip() and len(ln2) - len(ln2.lstrip()) <= ind:
                    break
                s = re.match(r"^\s+shell:\s*(.+?)\s*$", ln2)
                if s:
                    job_shell = s.group(1)
            i += 1
            continue
        if m.group(3) == "steps" and ind == job_indent + 2:
            i = steps(lines, i, ind, rel, job, wf_shell, job_shell, found)
            continue
        i += 1
    return found, None


def steps(lines, i, steps_indent, rel, job, wf_shell, job_shell, found) -> int:
    """Walk one `steps:` list; append unsafe steps to found; return next index."""
    j, n, step, item_indent = i + 1, 0, None, None

    def finish(st):
        if st is None or st.get("run") is None:
            return
        if (st.get("coe") or "").lower() == "true":
            return  # declared non-blocking: a hidden failure changes no verdict
        declared = shell_has_pipefail(st.get("shell"))
        if declared is None:
            declared = shell_has_pipefail(job_shell)
        if declared is None:
            declared = shell_has_pipefail(wf_shell)
        hits = unsafe_pipes(st["run"], bool(declared))
        if hits:
            label = st.get("name") or f"step {st['n']}"
            found.append((f"{rel} :: {job} :: {label}", st["run_line"] + 1 + hits[0] + 1))

    while j < len(lines):
        ln = lines[j]
        if ln.strip() and len(ln) - len(ln.lstrip()) <= steps_indent and not ln.lstrip().startswith("- "):
            break
        if ln.strip() and len(ln) - len(ln.lstrip()) < steps_indent:
            break
        m = KEY.match(ln)
        if not m or ln.lstrip().startswith("#"):
            j += 1
            continue
        if item_indent is None and m.group(2):
            item_indent = len(m.group(1))
        if m.group(2) and len(m.group(1)) == item_indent:  # `- key:` starts a step
            finish(step)
            n += 1
            key_indent = len(m.group(1)) + len(m.group(2))
            step = {"n": n, "run": None, "ki": key_indent}
        elif step is None:
            j += 1
            continue
        else:
            key_indent = len(m.group(1))
            if m.group(2) or key_indent != step["ki"]:
                # a key of `with:` / `env:` (with's own `name:` is not the
                # step's), or a list inside one
                if key_indent > step["ki"]:
                    j += 1
                    continue
        key, val = m.group(3), (m.group(5) or "")
        if key == "run":
            if val.strip()[:1] in ("|", ">"):
                body, nxt = block(lines, j, key_indent)
                if val.strip()[:1] == ">":
                    body = [" ".join(b.strip() for b in body)]
                step["run"], step["run_line"] = body, j
                j = nxt
                continue
            step["run"], step["run_line"] = [unquote(val)], j - 1
        elif key == "name":
            step["name"] = unquote(val)
        elif key == "shell":
            step["shell"] = val
        elif key == "continue-on-error":
            step["coe"] = val.strip()
        j += 1
    finish(step)
    return j


def main() -> int:
    current: dict[str, int] = {}
    unread = []
    files = sorted(list(WORKFLOWS.glob("*.yml")) + list(WORKFLOWS.glob("*.yaml")))
    for wf in files:
        found, err = scan(wf)
        if err:
            unread.append(err)
        for key, line in found:
            current.setdefault(key, line)

    base = set()
    if BASE.is_file():
        base = {l for l in BASE.read_text().splitlines() if l.strip() and not l.startswith("#")}

    if "--prune-baseline" in sys.argv:
        kept = sorted(base & set(current))
        header = [l for l in BASE.read_text().splitlines() if l.startswith("#")] if BASE.is_file() else []
        BASE.write_text("\n".join(header + kept) + "\n")
        print(f"baseline pruned: {len(base) - len(kept)} removed, {len(kept)} kept")
        return 0

    new = sorted(set(current) - base)
    stale = sorted(base - set(current))
    print(f"workflows read: {len(files) - len(unread)} of {len(files)}; "
          f"steps piping into tee without pipefail: {len(current)} "
          f"({len(current) - len(new)} known, {len(new)} new)")

    rc = 0
    if new:
        print(f"\nFAIL: {len(new)} step(s) pipe into tee under a shell with no pipefail --")
        print("a failure on the left of the pipe ends green. Add")
        print("  defaults:\n    run:\n      shell: bash -eo pipefail {0}")
        print("to the workflow (or `shell: bash` to the step):\n")
        for k in new:
            path = k.split(" :: ")[0]
            print(f"  {path}:{current[k]}  {k}")
        rc = 1
    if stale:
        print(f"\nFAIL: {len(stale)} baseline entry/entries no longer reproduce -- run with")
        print("--prune-baseline and commit tools/tee_pipefail_baseline.txt:\n")
        for k in stale:
            print(f"  {k}")
        rc = 1
    if unread:
        print(f"\nCANNOT TELL: {len(unread)} workflow(s) not read:")
        for e in unread:
            print(f"  {e}")
        rc = rc or 2
    if rc == 0:
        print("OK: no new step can hide a failure behind tee")
    return rc


if __name__ == "__main__":
    sys.exit(main())
