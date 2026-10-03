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

A pipe into tee (`| tee`, `|& tee`, `| sudo tee`, `| /usr/bin/tee`, also when
the `|` ends one line and tee starts the next) passes when it cannot hide a
failure:

  - its effective shell has pipefail (`shell: bash`, or a `shell:` / job
    `defaults` / workflow `defaults` line that says pipefail);
  - the script turned pipefail on (`set -o pipefail`, `set -eo pipefail`, ...)
    BEFORE the pipe -- earlier on the same line counts, later does not -- and
    has not turned it off again;
  - the pipe's own line, or the line right after it, reads PIPESTATUS (it
    checks the left side itself). A PIPESTATUS further down reads some other
    pipe, so it does not count;
  - the command on the left is a bare echo/printf, which has no failure to
    hide;
  - the pipeline ends in `|| true` / `|| :`, which declares the failure
    unimportant with or without pipefail;
  - the step says `continue-on-error: true`, so its verdict does not count.

Known limits, on the conservative or the documented side: `{ ...; } | tee` is
flagged even when every command in the group is an echo; a `set -o pipefail`
inside a function body counts from where it is written, not from where the
function is called.

The steps found on the day this gate was written sit in
tools/tee_pipefail_baseline.txt as `<workflow> :: <job> :: <step>`. A step's
name is not unique in a job, so the second step of a name is `<name> #2`, the
third `<name> #3`, counted over all steps of the job; otherwise a second unsafe
`Yosys` would hide behind the first one's entry. The baseline is a ratchet in
both directions, as in check_doc_refs (#819): a step not in it fails, and an
entry that no longer reproduces fails too, because a stale entry is a
pre-approved defect waiting to come back. `--prune-baseline` writes
baseline & current, so it can only remove; there is no flag that adds.

This reads YAML by hand. So that a file it misreads cannot pass as clean, it
also counts the `run:` keys in each workflow as text and compares that count
with the run keys the walk reached; a difference -- a quoted key, a flow-style
step, a job laid out in a way the walk did not follow -- is "cannot tell", and
so is a merge key (`<<:`). tools/test_check_tee_pipefail.py plants every case
above.

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

# A single `|` (not `||`), or `|&` (stderr too), into tee -- also through sudo
# (`sudo -E tee`) or by path (`/usr/bin/tee`).
TEE = re.compile(r"(?<!\|)\|&?(?!\|)\s*(?:sudo\s+(?:-\S+\s+)*)?(?:\S*/)?tee(?![\w.-])")
# A `set` command at the start of a command: line start, or after ; & ( { or a
# shell keyword. Its arguments run to the next separator.
SET_CMD = re.compile(r"(?:^|[;&({]|\b(?:then|do|else)\b)\s*set\s+([^;&|#)}]*)")
PF_ON = re.compile(r"(?:^|\s)-[A-Za-z]*o\s*pipefail\b")
PF_OFF = re.compile(r"(?:^|\s)\+[A-Za-z]*o\s*pipefail\b")
SWALLOWED = re.compile(r"\|\|\s*(true|:)\s*$")
BARE_ECHO = re.compile(r"^\s*(echo|printf)\b[^|;&`]*$")
KEY = re.compile(r"^(\s*)(-\s+)?([A-Za-z0-9_.-]+)\s*:(\s*(.*))?$")
# What the walk is checked against: every `run:` key as text, block or flow.
RUN_TEXT = re.compile(r"""^\s*(?:-\s+)?["']?run["']?\s*:(?:\s|$)""")
FLOW_RUN = re.compile(r"""[{,]\s*["']?run["']?\s*:""")
MERGE = re.compile(r"""^\s*(?:-\s+)?["']?<<["']?\s*:""")


def shell_has_pipefail(shell: str | None) -> bool | None:
    """True/False for a declared shell, None when none is declared."""
    if shell is None:
        return None
    s = unquote(shell)
    # `shell: bash` is the one spelling GitHub expands WITH pipefail.
    return s == "bash" or "pipefail" in s


def unquote(v: str) -> str:
    """A one-line YAML scalar's value: quotes off, a trailing comment off."""
    v = v.strip()
    m = re.match(r"""^(["'])(.*)\1\s*(#.*)?$""", v)
    if m:
        return m.group(2)
    return re.sub(r"(^|\s+)#.*$", "", v).strip()


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
    """Lines bash reads as one: a trailing backslash, or a trailing `|` / `|&`
    (bash goes on reading the pipeline on the next line). (first physical
    index, text)."""
    out, buf, start = [], "", 0
    for k, ln in enumerate(script):
        if not buf:
            start = k
        r = ln.rstrip()
        if r.endswith("\\"):
            buf += r[:-1] + " "
            continue
        if not r.lstrip().startswith("#") and re.search(r"(?<!\|)\|&?$", r):
            buf += r + " "
            continue
        out.append((start, buf + ln))
        buf = ""
    if buf:
        out.append((start, buf))
    return out


def flatten(s: str) -> str:
    """$(...) and `...` replaced by a word: what fails inside them is lost to
    the command around them, pipefail or not."""
    while True:
        flat = re.sub(r"\$\([^()]*\)|`[^`]*`", "S", s)
        if flat == s:
            return s
        s = flat


def unsafe_pipes(script: list[str], pipefail: bool) -> list[int]:
    """Indexes (into script) of tee pipes that can hide a failure."""
    hits = []
    logical = logical_lines(script)
    for n, (k, text) in enumerate(logical):
        if text.strip().startswith("#"):
            continue
        events = []
        for m in SET_CMD.finditer(text):
            if PF_OFF.search(" " + m.group(1)):
                events.append((m.start(), "off", m))
            elif PF_ON.search(" " + m.group(1)):
                events.append((m.start(), "on", m))
        for m in TEE.finditer(text):
            events.append((m.start(), "tee", m))
        for _, kind, m in sorted(events, key=lambda e: e[0]):
            if kind == "on":
                pipefail = True
                continue
            if kind == "off":
                pipefail = False
                continue
            if pipefail:
                continue
            # This pipeline's own end: up to the next ; or && after tee.
            rest = re.split(r";|&&", text[m.end():], maxsplit=1)[0]
            if SWALLOWED.search(rest.strip()):
                continue
            # The command on the left, after the last ; && || of the line.
            left = re.split(r";|&&|\|\|", flatten(text[: m.start()]))[-1]
            if BARE_ECHO.match(left):
                continue
            # PIPESTATUS is overwritten by the next pipeline, so it must be
            # read on the pipe's own line or the very next one.
            after = text[m.end():]
            nxt = logical[n + 1][1] if n + 1 < len(logical) else ""
            if "PIPESTATUS" in after or "PIPESTATUS" in nxt:
                continue
            hits.append(k)
            break
    return hits


def indent(ln: str) -> int:
    return len(ln) - len(ln.lstrip())


def text_runs(lines: list[str]) -> int:
    """`run:` keys whose value is a script, counted as text outside block
    scalars and comments. Not a script: a list or a mapping -- a matrix axis
    called `run` (`run: [1, 2]`), or the `run:` of a `defaults:`, whose next
    line is a key."""
    n, i = 0, 0
    while i < len(lines):
        ln = lines[i]
        s = ln.strip()
        if not s or s.startswith("#"):
            i += 1
            continue
        if RUN_TEXT.match(ln):
            val = unquote(ln.split(":", 1)[1])
            if val[:1] not in ("[", "{"):
                if val:
                    n += 1
                else:
                    nx = next((x for x in lines[i + 1:] if x.strip()
                               and not x.lstrip().startswith("#")), "")
                    if indent(nx) > indent(ln) and not nx.lstrip().startswith("-") \
                            and not KEY.match(nx):
                        n += 1
        else:
            n += len(FLOW_RUN.findall(ln))
        m = KEY.match(ln)
        if m and (m.group(5) or "").strip()[:1] in ("|", ">"):
            _, i = block(lines, i, len(m.group(1)) + len(m.group(2) or ""))
            continue
        i += 1
    return n


def scan(path: pathlib.Path) -> tuple[list[tuple[str, int]], str | None]:
    """[(key, line number)] of unsafe steps, or an error message."""
    try:
        rel = path.relative_to(ROOT).as_posix()
    except ValueError:
        rel = path.name
    lines = path.read_text().splitlines()
    wf_shell: str | None = None
    found: list[tuple[str, int]] = []
    seen = {"runs": 0}

    if any(MERGE.match(ln) for ln in lines):
        return [], f"{rel}: a YAML merge key (`<<:`) -- cannot tell what it brings in"

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
        jobs_at = next(i for i, ln in enumerate(lines) if re.match(r"^jobs:\s*(#.*)?$", ln))
    except StopIteration:
        return [], f"{rel}: no top-level `jobs:` -- cannot read it"

    i, job, job_indent, child = jobs_at + 1, None, None, None
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
            job, job_shell, child = m.group(3), None, None
            i += 1
            continue
        # The job's own keys sit at the indent of its first key, whatever it is.
        if child is None and ind > job_indent:
            child = ind
        if m.group(3) == "defaults" and ind == child and not m.group(2):
            for ln2 in lines[i + 1:]:
                if ln2.strip() and indent(ln2) <= ind:
                    break
                s = re.match(r"^\s+shell:\s*(.+?)\s*$", ln2)
                if s:
                    job_shell = s.group(1)
            i += 1
            continue
        if m.group(3) == "steps" and ind == child and not m.group(2):
            i = steps(lines, i, ind, rel, job, wf_shell, job_shell, found, seen)
            continue
        i += 1

    counted = text_runs(lines)
    if counted != seen["runs"]:
        return found, (f"{rel}: {counted} `run:` key(s) as text, {seen['runs']} reached "
                       f"by the walk -- cannot tell (quoted key, flow style or layout)")
    return found, None


def steps(lines, i, steps_indent, rel, job, wf_shell, job_shell, found, seen) -> int:
    """Walk one `steps:` list; append unsafe steps to found; return next index."""
    j, n, step, item_indent = i + 1, 0, None, None
    every: list[dict] = []

    while j < len(lines):
        ln = lines[j]
        if ln.strip() and indent(ln) <= steps_indent and not ln.lstrip().startswith("- "):
            break
        if ln.strip() and indent(ln) < steps_indent:
            break
        m = KEY.match(ln)
        if not m or ln.lstrip().startswith("#"):
            j += 1
            continue
        if item_indent is None and m.group(2):
            item_indent = len(m.group(1))
        if m.group(2) and len(m.group(1)) == item_indent:  # `- key:` starts a step
            n += 1
            key_indent = len(m.group(1)) + len(m.group(2))
            step = {"n": n, "run": None, "ki": key_indent}
            every.append(step)
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
            seen["runs"] += 1
            v = val.strip()
            if v[:1] in ("|", ">"):
                body, nxt = block(lines, j, key_indent)
                if v[:1] == ">":
                    body = [" ".join(b.strip() for b in body)]
                step["run"], step["run_line"] = body, j
                j = nxt
                continue
            # A flow scalar may go on over the next, deeper lines; YAML folds
            # them into one line.
            parts, k = [v], j + 1
            quoted = v[:1] in ("'", '"')
            closed = quoted and re.match(r"""^(["']).*\1\s*(#.*)?$""", v)
            while k < len(lines) and not closed:
                nx = lines[k]
                if not nx.strip():
                    k += 1
                    continue
                if indent(nx) <= key_indent or (not quoted and nx.lstrip().startswith("#")):
                    break
                parts.append(nx.strip())
                if quoted and nx.rstrip().endswith(v[0]):
                    break
                k += 1
            joined = " ".join(parts)
            step["run"], step["run_line"] = [unquote(joined) if (quoted or "#" in joined)
                                             else joined], j - 1
        elif key == "name":
            step["name"] = unquote(val)
        elif key == "shell":
            step["shell"] = val
        elif key == "continue-on-error":
            step["coe"] = unquote(val)
        j += 1

    count: dict[str, int] = {}
    for st in every:
        name = st.get("name")
        if name:
            count[name] = count.get(name, 0) + 1
            label = name if count[name] == 1 else f"{name} #{count[name]}"
        else:
            label = f"step {st['n']}"
        if st.get("run") is None:
            continue
        if (st.get("coe") or "").lower() == "true":
            continue  # declared non-blocking: a hidden failure changes no verdict
        declared = shell_has_pipefail(st.get("shell"))
        if declared is None:
            declared = shell_has_pipefail(job_shell)
        if declared is None:
            declared = shell_has_pipefail(wf_shell)
        hits = unsafe_pipes(st["run"], bool(declared))
        if hits:
            found.append((f"{rel} :: {job} :: {label}", st["run_line"] + 1 + hits[0] + 1))
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
