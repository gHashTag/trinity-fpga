#!/usr/bin/env python3
r"""Can a workflow step that pipes into tee still go red?

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

The script is NOT parsed. Five reviews of #828 each found one more way a
hand model of bash quotes, heredocs and comments let an unsafe step through,
and review 6 measured that the model bought nothing: on this tree it flagged
the same 78 steps as the plain text rules below, and only added misses. So
the gate reads text and narrows what it accepts:

  - a step is a candidate when one of its lines has the WORD tee (`| tee`,
    `| /usr/bin/tee`, `| "tee"`, `| sudo tee`, `| {` with tee on the next
    line) and one has a pipe, `|` or `|&` but not `||`. Every line is read,
    a `#` line too: inside a quoted string over several lines
    (`python3 -c "`, `{ false; echo "`) it is data, not a comment, and its
    `| tee` runs (review 7);
  - a candidate passes when it has pipefail and no shell of its own. Pipefail
    is its effective shell's (`shell: bash`, or a `shell:` / job / workflow
    `defaults` that says pipefail), or the script's leading run of plain
    `set` lines (`set -euo pipefail`; blank lines and comments between them
    allowed; each line nothing but a set of options -- no `;`, no comment,
    no quotes). Anything that may turn it off voids both, wherever it stands:
    a `+` word with an `o` or a `$` in it (`set +o pipefail`,
    `set +"o" pipefail`, `set ${PFOPT:-+o} pipefail`, `set +$O pipefail`)
    and any `shopt`;
  - a shell of its own is an option cluster with c of any case and length
    (`bash -c`, `sh -ec`, `bash -Ec`, `bash -euxvfc`, `docker run ... bash
    -c`), a heredoc or here-string (`<<`), a process substitution (`<(`,
    `>(`), or a shell named as a word anywhere (`| bash`, `bash x.sh`,
    `ssh host '...'`; `x.sh` and `shell` are no such word): a tee there runs
    without the step's pipefail. A step under pipefail whose tee is not in
    that shell says so, with the reason, in the comment block its script
    opens with (blank, `#` and plain `set` lines, before anything else --
    where nothing is quoted yet, so the marker is not a line of a heredoc):
        # tee-pipefail: the heredoc feeds python, not a shell
    The marker is a claim about every shell of its own in the step, and a
    reviewer reads it as one. A step without pipefail has no such way out;
  - the step says `continue-on-error: true`, so its verdict does not count.

No left-hand command and no `|| true` is an exemption: the gate does not read
intent. An earlier version let a bare echo/printf pass, "it has no failure to
hide": `echo "${X:?}"` and `printf '%d' abc` both fail, and review 5 showed
the step green behind tee. PIPESTATUS is no exemption either: reading it says
nothing about whether the value is acted on, nor which pipe it belongs to.

`shell:` is read as words up to `{0}` (the script's path; what follows are its
arguments): `bash` alone has pipefail, and so does a bash whose options turn it
on last (`-eo pipefail`, `-o pipefail`); `+o pipefail` turns it off again.

Known limits. On the conservative side, all fixed by `shell: bash` or a
leading `set -o pipefail` line: `echo hi | tee x` is flagged, and so is a tee
that is only an argument (`| grep tee`) or only data, a `#` comment after
code, `set -o pipefail; make | tee x` on one line, and any `shopt` or
`+...o`, `+...$` or `` +...` `` word. Under pipefail, a `grep -c`, a `<<` that feeds
python, or a comment that names bash flags until the step's marker names why. Misses, which text cannot close: a tee
named through a variable (`| $TEE x`) or an alias; a shell named through any
variable but `$SHELL` and `$BASH`; a script given by an
expression (`run: ${{ matrix.cmd }}`); pipefail turned off by a sourced file,
an `eval`, a Makefile or a script file the step runs; a shell started by
another language's code (`perl -e 'system("make | tee x")'`, `node -e`)
under a name the shell-word rule does not know; a marker whose reason is
wrong, or true of one shell of its own and not of another; and
`continue-on-error: true` taken as "this verdict does not count" without
checking that no later step reads `steps.<id>.outcome`.

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
import shlex
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
BASE = pathlib.Path(__file__).with_name("tee_pipefail_baseline.txt")

# Every rule below reads the step's script as RAW TEXT. Six reviews of #828
# each found one more way a model of bash quotes, heredocs and comments got a
# line wrong -- `'"'` inside "$(...)", a heredoc opened on a line ending in
# `|`, a `#` inside ${...} -- and on the tree of the day that model flagged
# exactly the 78 steps the raw text flags: it bought nothing but its misses.

# A pipe: `|` or `|&`, but not `||`.
PIPE = re.compile(r"(?<!\|)\|(?!\|)")
# The word tee anywhere: `| tee`, `| /usr/bin/tee`, `| "tee"`, `| sudo tee`,
# `| {` and tee on the next line.
TEE = re.compile(r"(?<![\w.-])tee(?![\w.-])")
# Anything that may turn pipefail off: a `+` word with an `o`, a `$` or a
# backtick in it (`set +o pipefail`, `set +eo pipefail`, `set +"o" pipefail`,
# `set ${PFOPT:-+o} pipefail`, `set +$O pipefail`, `` set +`printf o` pipefail ``,
# review 8 of #828), and any shopt. A `+` glued to a word or to another `+`
# is no option (`c++o`, `g++ -o`).
PF_OFF = re.compile(r"(?<![\w+])\+\S*[o$`]|\bshopt\b")
# A shell of its own, which the step's pipefail does not reach: an option
# cluster with c, any case and length (`bash -c`, `sh -ec`, `bash -Ec`,
# `bash -euxvfc`, `docker run ... bash -c`), a heredoc or here-string
# (`bash <<EOF`), a process substitution (`bash <(echo ...)`), or a shell
# named as a word anywhere, by its path too (`echo '...' | bash`,
# `| /bin/sh`, `ssh host '...'`, `bash tools/x.sh`), or through the variables
# that hold one (`| "$BASH"`, `${SHELL}`). Review 7 of #828 walked four of
# these past the old lower-case, at-most-four-letters pattern; review 8 the
# path and the variable.
OWN_SHELL = re.compile(
    r"(?<![\w-])-[A-Za-z]*c[A-Za-z]*(?![\w=-])"
    r"|<<|[<>]\("
    r"|(?<![\w.-])(?:ba|da|z|k|a|s)?sh(?![\w.-])"
    r"|\$\{?(?:SHELL|BASH)\b"
)
# A step under pipefail that has a shell of its own AND a tee, where the tee
# is not in it, says so in its script, with the reason:
#   # tee-pipefail: the tee is in this shell, the heredoc only feeds python
# It silences that one rule, and only in the comment block the script opens
# with (with the leading `set` lines): there nothing is quoted yet, so the
# marker is this shell's, not a line of a heredoc or of a `bash -c '...'`.
# It is a claim about EVERY shell of its own in the step. A step without
# pipefail has no such way out.
ACCEPTED = re.compile(r"#[ \t]*tee-pipefail:[ \t]*\S")


def set_options(words: list[str]) -> bool | None:
    """What a run of bash option words (`-eo pipefail`, `-e -o pipefail`,
    `+o pipefail`) leaves pipefail at: True, False, or None when they do not
    touch it. None also when a word is not an option -- the caller then does
    not trust the line."""
    on, i = None, 0
    while i < len(words):
        w = words[i]
        if not re.fullmatch(r"[-+][A-Za-z]+", w):
            return None
        if w.endswith("o"):
            if i + 1 >= len(words):
                return None
            if words[i + 1] == "pipefail":
                on = w[0] == "-"
            i += 2
            continue
        i += 1
    return on


def shell_has_pipefail(shell: str | None) -> bool | None:
    """True/False for a declared shell, None when none is declared."""
    if shell is None:
        return None
    # `shell: bash` is the one spelling GitHub expands WITH pipefail.
    if shell.strip() == "bash":
        return True
    try:
        words = shlex.split(shell)
    except ValueError:
        return False
    if not words or pathlib.PurePosixPath(words[0]).name != "bash" or "{0}" not in words:
        return False
    # Up to {0}: after it come the script's own arguments, not bash's. The two
    # long options are the ones GitHub's own expansion of `shell: bash` has.
    opts = [w for w in words[1:words.index("{0}")] if w not in ("--noprofile", "--norc")]
    return set_options(opts) is True


def leading_pipefail(script: list[str]) -> bool:
    """Does the run of `set` lines the script opens with (blank lines and `#`
    comments between them allowed) turn pipefail on (`set -euo pipefail`)?
    Each line exactly a plain set of options and nothing after it: no `;`, no
    comment, no quotes. The first other line ends the run. Turning it off is
    PF_OFF's to see, anywhere in the step."""
    on = False
    for ln in script:
        line = ln.strip()
        if not line or line.startswith("#"):
            continue
        if not re.fullmatch(r"set(?:\s+(?:[-+][A-Za-z]+|[a-z]+))+", line):
            break
        on = on or set_options(line.split()[1:]) is True
    return on


def unsafe_pipes(script: list[str], pipefail: bool) -> list[int]:
    """Indexes (into script) of the lines with the word tee, when the step can
    hide a failure behind it; empty when it cannot. pipefail: the step's
    shell turns it on."""
    text = "\n".join(script)
    # Every line is read, `#` or not: inside a quoted string that runs over
    # several lines (`python3 -c "`, `{ false; echo "`) a line starting with
    # # is data, and its `| tee` runs. Review 7 of #828 hid a pipe that way.
    tees = [k for k, ln in enumerate(script) if TEE.search(ln)]
    if not tees or not any(PIPE.search(ln) for ln in script):
        return []
    if PF_OFF.search(text):
        pipefail = False  # turned off somewhere: neither the shell nor a set counts
    else:
        pipefail = pipefail or leading_pipefail(script)
    if pipefail and (not any(OWN_SHELL.search(ln) for ln in script) or marked(script)):
        return []
    return tees


def marked(script: list[str]) -> bool:
    """Is there a `# tee-pipefail: <reason>` line in the block the script
    opens with: blank lines, comment lines and plain `set` lines, up to the
    first other line? Nothing can be quoted there yet."""
    for ln in script:
        line = ln.strip()
        if not line or re.fullmatch(r"set(?:\s+(?:[-+][A-Za-z]+|[a-z]+))+", line):
            continue
        if not line.startswith("#"):
            return False
        if ACCEPTED.match(line):
            return True
    return False


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
