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

A pipe into tee (`| tee`, `|& tee`, `| /usr/bin/tee`, through `sudo`,
`stdbuf`, `command`, `env`, `nice`, ..., also when the `|` ends one line and
tee starts the next) passes when it cannot hide a failure:

  - its effective shell has pipefail (`shell: bash`, or a `shell:` / job
    `defaults` / workflow `defaults` line that says pipefail);
  - the script turned pipefail on (`set -o pipefail`, `set -eo pipefail`, ...)
    BEFORE the pipe -- earlier on the same line counts, later does not -- and
    has not turned it off again. Only a `set` this shell runs counts: not one
    in a comment, in a string (a multi-line `bash -c "..."` too), in a
    subshell `( ... )` or `$( ... )`, or in a heredoc body;
  - the pipe's own line, or the line right after it, reads PIPESTATUS in code
    (it checks the left side itself). A PIPESTATUS further down reads some
    other pipe, and one in a comment reads nothing;
  - the command on the left is a bare echo/printf, which has no failure to
    hide -- not when the pipe follows a group, `(make; echo done) | tee`;
  - the pipeline ends in `|| true` / `|| :`, which declares the failure
    unimportant with or without pipefail;
  - the step says `continue-on-error: true`, so its verdict does not count.

A heredoc body is read as a script of its own that starts without pipefail:
the data of `cat > x <<EOF`, or what `bash <<EOF` runs in a fresh shell.

Known limits, on the conservative or the documented side: `{ ...; } | tee` is
flagged even when every command in the group is an echo, and so is a tee in a
string or a heredoc that is only data; a `set -o pipefail` inside a function
body counts from where it is written, not from where the function is called,
and one under `if false; then` counts as run.

The steps found on the day this gate was written sit in
tools/tee_pipefail_baseline.txt as `<workflow> :: <job> :: <step>`. A step's
name is not unique in a job, so the second step of a name is `<name> #2`, the
third `<name> #3`, counted over all steps of the job; otherwise a second unsafe
`Yosys` would hide behind the first one's entry. The baseline is a ratchet in
both directions, as in check_doc_refs (#819): a step not in it fails, and an
entry that no longer reproduces fails too, because a stale entry is a
pre-approved defect waiting to come back. `--prune-baseline` writes
baseline & current, so it can only remove; there is no flag that adds, and
`--base-baseline FILE` (the base branch's copy, on a pull request) fails an
entry added by hand.

The workflows are read with PyYAML (`yaml.compose`), as the runner reads them:
a quoted key, an anchored or bare `-` step, an aliased `steps: *list` are what
they are, not a layout to recognise. Two earlier versions read YAML by hand,
and each review found a layout that walked an unsafe step past them. What the
walk cannot decide is "cannot tell": a merge key (`<<:`), a key given twice,
a step that is not a mapping, a file that is not YAML, PyYAML missing.
tools/test_check_tee_pipefail.py plants every case above.

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

# A single `|` (not `||`), or `|&` (stderr too), into tee -- also through a
# command that runs the next one (`sudo -E tee`, `stdbuf -oL tee`, `command
# tee`, `env A=1 tee`, `nice -n 5 tee`) or by path (`/usr/bin/tee`).
RUNS_NEXT = r"(?:(?:sudo|command|stdbuf|env|nice|nohup|time|ionice|unbuffer|exec)" \
    r"(?:\s+(?:-\S+(?:\s+\d+)?|[A-Za-z_]\w*=\S*))*\s+)*"
TEE = re.compile(r"(?<!\|)\|&?(?!\|)\s*" + RUNS_NEXT + r"(?:\S*/)?tee(?![\w.-])")
# A `set` command at the start of a command in THIS shell: line start, or
# after ; & { or a shell keyword. Not after `(`: a set in a subshell or in
# $(...) ends with it.
SET_CMD = re.compile(r"(?:^|[;&{]|\b(?:then|do|else)\b)\s*set\s+([^;&|#)}]*)")
PF_ON = re.compile(r"(?:^|\s)-[A-Za-z]*o\s*pipefail\b")
PF_OFF = re.compile(r"(?:^|\s)\+[A-Za-z]*o\s*pipefail\b")
SWALLOWED = re.compile(r"\|\|\s*(true|:)\s*$")
BARE_ECHO = re.compile(r"^\s*(echo|printf)\b[^|;&`]*$")
# `<<EOF`, `<<-EOF`, `<< 'EOF'`, `<<"EOF"` -- not `<<<` (a here-string).
HEREDOC = re.compile(r"(?<!<)<<(-?)\s*(['\"]?)([A-Za-z_][\w.-]*)\2")


def shell_has_pipefail(shell: str | None) -> bool | None:
    """True/False for a declared shell, None when none is declared."""
    if shell is None:
        return None
    s = shell.strip()
    # `shell: bash` is the one spelling GitHub expands WITH pipefail.
    return s == "bash" or "pipefail" in s


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


def shell_view(text: str, quote: str) -> tuple[str, str, str]:
    """(code, masked, quote after): code is text without its comment; masked is
    code with what is inside quotes blanked, so a `set` in a string or in a
    `bash -c "..."` running on from an earlier line is not this shell's. quote
    is the quote still open at the end of the line ('' when none)."""
    code, masked, i = [], [], 0
    while i < len(text):
        c = text[i]
        if quote:
            if quote == '"' and c == "\\" and i + 1 < len(text):
                code.append(text[i:i + 2])
                masked.append("__")
                i += 2
                continue
            if c == quote:
                quote = ""
            code.append(c)
            masked.append(c if not quote else "_")
            i += 1
            continue
        if c == "\\" and i + 1 < len(text):
            code.append(text[i:i + 2])
            masked.append("__")
            i += 2
            continue
        if c in ("'", '"'):
            quote = c
        elif c == "#" and (i == 0 or text[i - 1] in " \t;&|()"):
            break  # a word that starts with # starts a comment
        code.append(c)
        masked.append(c)
        i += 1
    return "".join(code), "".join(masked), quote


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
    n, quote = 0, ""
    while n < len(logical):
        k, text = logical[n]
        code, masked, quote = shell_view(text, quote)
        # A heredoc body is not this shell's script: data, or a script some
        # other command runs from a fresh state. Read it as its own script,
        # starting without pipefail, and let nothing in it change this one.
        # (Matched in code, where a quoted 'EOF' keeps its word; the `<<` must
        # stand outside quotes.)
        doc = next((d for d in HEREDOC.finditer(code) if masked[d.start()] == "<"), None)
        events = []
        for m in SET_CMD.finditer(masked):
            if PF_OFF.search(" " + m.group(1)):
                events.append((m.start(), "off", m))
            elif PF_ON.search(" " + m.group(1)):
                events.append((m.start(), "on", m))
        for m in TEE.finditer(code):
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
            rest = re.split(r";|&&", code[m.end():], maxsplit=1)[0]
            if SWALLOWED.search(rest.strip()):
                continue
            # The command on the left, after the last ; && || of the line --
            # unless the pipe follows a group, `(...) | tee` or `{ ...; } | tee`,
            # whose last command says nothing about the ones before it.
            before = re.sub(r"\$\{[^{}]*\}", "S", flatten(code[: m.start()])).rstrip()
            left = re.split(r";|&&|\|\|", before)[-1]
            if BARE_ECHO.match(left) and not before.endswith((")", "}")):
                continue
            # PIPESTATUS is overwritten by the next pipeline, so it must be
            # read on the pipe's own line or the very next one -- in code, not
            # in a comment.
            nxt = shell_view(logical[n + 1][1], quote)[0] if n + 1 < len(logical) else ""
            if "PIPESTATUS" in code[m.end():] or "PIPESTATUS" in nxt:
                continue
            hits.append(k)
            break
        n += 1
        if doc:
            strip_tabs, word = doc.group(1) == "-", doc.group(3)
            first = logical[n][0] if n < len(logical) else len(script)
            end = len(script)
            for j in range(first, len(script)):
                if (script[j].lstrip("\t") if strip_tabs else script[j]) == word:
                    end = j
                    break
            hits += [first + h for h in unsafe_pipes(script[first:end], False)]
            while n < len(logical) and logical[n][0] <= end:
                n += 1
    return hits


class CannotTell(Exception):
    """A workflow this checker cannot read the way the runner does."""


MERGE_TAG = "tag:yaml.org,2002:merge"


def mapping(node, where: str) -> dict:
    """A mapping node as {key: value node}. A key that is not a plain string,
    a key given twice or a merge key (`<<:`) is "cannot tell": which value the
    runner takes is then not ours to guess."""
    import yaml

    if not isinstance(node, yaml.MappingNode):
        raise CannotTell(f"{where} is not a mapping")
    out: dict = {}
    for k, v in node.value:
        if k.tag == MERGE_TAG:
            raise CannotTell(f"{where}: a YAML merge key (`<<:`) -- cannot tell what it brings in")
        if not isinstance(k, yaml.ScalarNode):
            raise CannotTell(f"{where}: a key that is not a string")
        if k.value in out:
            raise CannotTell(f"{where}: key `{k.value}` given twice")
        out[k.value] = v
    return out


def scalar(node, where: str) -> str:
    import yaml

    if not isinstance(node, yaml.ScalarNode):
        raise CannotTell(f"{where} is not a string")
    return node.value


def defaults_shell(node, where: str) -> str | None:
    """`defaults: run: shell:` of a workflow or a job, None when not set."""
    if node is None:
        return None
    run = mapping(node, f"{where} defaults").get("run")
    if run is None:
        return None
    shell = mapping(run, f"{where} defaults.run").get("shell")
    return None if shell is None else scalar(shell, f"{where} defaults.run.shell")


def script_line(node, k: int) -> int:
    """1-based file line of line k of a run script. A block literal keeps its
    lines; folded and flow scalars do not, so they point at the first one."""
    first = node.start_mark.line + 1
    if node.style == "|":
        return first + 1 + k
    return first + (1 if node.style == ">" else 0)


def relpath(path: pathlib.Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.name


def scan(path: pathlib.Path) -> tuple[list[tuple[str, int]], str | None]:
    """[(key, line number)] of unsafe steps, or an error message."""
    rel = relpath(path)
    try:
        import yaml
    except ImportError:
        return [], f"{rel}: PyYAML is not installed -- cannot read it"
    found: list[tuple[str, int]] = []
    try:
        # compose, not load: the nodes keep their line numbers, and an alias
        # (`steps: *common`) is the very node its anchor names, as the runner
        # reads it.
        root = yaml.compose(path.read_text(), Loader=yaml.SafeLoader)
        top = mapping(root, "the workflow")
        wf_shell = defaults_shell(top.get("defaults"), "workflow")
        if "jobs" not in top:
            raise CannotTell("no top-level `jobs:`")
        for job, body in mapping(top["jobs"], "jobs").items():
            jb = mapping(body, f"job {job}")
            job_shell = defaults_shell(jb.get("defaults"), f"job {job}")
            if "steps" not in jb:
                continue  # a reusable-workflow call has no steps of its own
            found += steps(jb["steps"], rel, job, wf_shell, job_shell)
    except yaml.YAMLError as e:
        return [], f"{rel}: not readable as YAML -- {str(e).splitlines()[0]}"
    except CannotTell as e:
        return [], f"{rel}: {e}"
    return found, None


def steps(node, rel, job, wf_shell, job_shell) -> list[tuple[str, int]]:
    """Unsafe steps of one job's `steps:` list."""
    import yaml

    if not isinstance(node, yaml.SequenceNode):
        raise CannotTell(f"job {job}: `steps:` is not a list")
    found: list[tuple[str, int]] = []
    count: dict[str, int] = {}
    for n, item in enumerate(node.value, 1):
        st = mapping(item, f"job {job} step {n}")
        name = scalar(st["name"], f"job {job} step {n} name") if "name" in st else None
        if name:
            count[name] = count.get(name, 0) + 1
            label = name if count[name] == 1 else f"{name} #{count[name]}"
        else:
            label = f"step {n}"
        if "run" not in st:
            continue
        run = st["run"]
        script = scalar(run, f"job {job} {label} run").split("\n")
        coe = st.get("continue-on-error")
        if coe is not None and scalar(coe, f"job {job} {label} continue-on-error").lower() == "true":
            continue  # declared non-blocking: a hidden failure changes no verdict
        shell = scalar(st["shell"], f"job {job} {label} shell") if "shell" in st else None
        declared = shell_has_pipefail(shell)
        if declared is None:
            declared = shell_has_pipefail(job_shell)
        if declared is None:
            declared = shell_has_pipefail(wf_shell)
        hits = unsafe_pipes(script, bool(declared))
        if hits:
            found.append((f"{rel} :: {job} :: {label}", script_line(run, hits[0])))
    return found


def entries(path: pathlib.Path) -> set[str]:
    if not path.is_file():
        return set()
    return {l for l in path.read_text().splitlines() if l.strip() and not l.startswith("#")}


def main() -> int:
    current: dict[str, int] = {}
    unread, unread_files = [], set()
    files = sorted(list(WORKFLOWS.glob("*.yml")) + list(WORKFLOWS.glob("*.yaml")))
    for wf in files:
        found, err = scan(wf)
        if err:
            unread.append(err)
            unread_files.add(relpath(wf))
        for key, line in found:
            current.setdefault(key, line)

    base = entries(BASE)

    if "--prune-baseline" in sys.argv:
        if unread:
            # An unread file's entries would look stale and be pruned.
            print(f"CANNOT TELL: {len(unread)} workflow(s) not read -- baseline left as it is:")
            for e in unread:
                print(f"  {e}")
            return 2
        kept = sorted(base & set(current))
        header = [l for l in BASE.read_text().splitlines() if l.startswith("#")] if BASE.is_file() else []
        BASE.write_text("\n".join(header + kept) + "\n")
        print(f"baseline pruned: {len(base) - len(kept)} removed, {len(kept)} kept")
        return 0

    new = sorted(set(current) - base)
    # An entry of a file that was not read is not known to be stale.
    stale = sorted(k for k in base - set(current) if k.split(" :: ")[0] not in unread_files)
    print(f"workflows read: {len(files) - len(unread)} of {len(files)}; "
          f"steps piping into tee without pipefail: {len(current)} "
          f"({len(current) - len(new)} known, {len(new)} new)")

    rc = 0
    # The baseline may only shrink, also by hand: given the base branch's copy
    # (`--base-baseline FILE`, on a pull request), an entry it does not have
    # is a defect written into the list instead of fixed.
    if "--base-baseline" in sys.argv:
        arg = sys.argv.index("--base-baseline") + 1
        if arg >= len(sys.argv) or not pathlib.Path(sys.argv[arg]).is_file():
            print("\nCANNOT TELL: --base-baseline needs the base branch's baseline file")
            return 2
        grown = sorted(base - entries(pathlib.Path(sys.argv[arg])))
        if grown:
            print(f"\nFAIL: {len(grown)} baseline entry/entries added -- the list only shrinks;")
            print("fix the step instead:\n")
            for k in grown:
                print(f"  {k}")
            rc = 1
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
