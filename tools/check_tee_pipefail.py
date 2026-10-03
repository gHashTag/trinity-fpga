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

A pipe into tee is a `|` or `|&` into a command with the WORD tee anywhere in
it, up to its end: `| tee`, `| /usr/bin/tee`, `| "tee"`, `| sudo -u ci tee`,
`| timeout 60 tee`, `| { tee x; }`, also when the `|` ends one line and the
rest is on the next. Not a list of the commands that run the next one: review
5 of #828 found three that such a list did not have. It passes when it cannot
hide a failure:

  - its effective shell has pipefail (`shell: bash`, or a `shell:` / job
    `defaults` / workflow `defaults` line that says pipefail);
  - the script turns pipefail on FIRST: its leading commands, before
    anything else runs, are plain `set` lines (`set -o pipefail`,
    `set -eo pipefail`, `set -e -o pipefail`), one of them with pipefail --
    the last may go on after a `;` (`set -o pipefail; yosys | tee y.log`).
    Every script that does it on the day of this gate does it that way. A
    `set` anywhere else -- after a command, under `&&` or `if`, in a
    subshell, a loop, a function, a heredoc -- is not read: whether it runs
    in this shell before the pipe is bash's to know, and four reviews each
    found one more way a hand parser got it wrong (#828);
  - with either of these, nothing in the script may turn pipefail off: any
    `+...o` option word (`set +o pipefail`, `set +o "pipe"fail`,
    `set +eo $opt`) and any `shopt`, wherever they stand, void both;
  - the pipeline ends in `|| true` / `|| :`, which declares the failure
    unimportant with or without pipefail;
  - the step says `continue-on-error: true`, so its verdict does not count.

A heredoc body (`<<EOF`, `<<-EOF`, `<<'EOF'`, `<<"EOF"`, `<<\EOF`) is read as
a script of its own that starts without pipefail: the data of `cat > x <<EOF`,
or what `bash <<EOF` runs in a fresh shell. So is a tee inside a string
(`bash -c "make | tee x"` runs in a shell of its own) -- also when the step's
shell or the script has pipefail. A comment ends at the end of its line,
whatever it ends with: `# old \` does not swallow the next line. Quotes are
followed across lines, `$'...'` with its backslash escapes included; a heredoc
body is never read as this shell's code, so an `it's` in one opens no quote.

No left-hand command is an exemption. An earlier version let a bare
echo/printf pass, "it has no failure to hide": `echo "${X:?}"` and
`printf '%d' abc` both fail, and review 5 of #828 showed the step green behind
tee. PIPESTATUS is not one either: reading it says nothing about whether the
value is acted on, nor which pipe it belongs to, and no step here relies on it.

`shell:` is read as words up to `{0}` (the script's path; what follows are its
arguments): `bash` alone has pipefail, and so does a bash whose options turn it
on last (`-eo pipefail`, `-o pipefail`); `+o pipefail` turns it off again.

Known limits. On the conservative side: `echo hi | tee x` is flagged, and so
is a word tee that is only an argument (`| grep tee`), a tee in a string or a
heredoc that is only data, a script that turns pipefail on after a first
command (`cd x; set -o pipefail` -- move the `set` up, or say `shell: bash`),
and any `shopt` or `+...o` word, even one that leaves pipefail alone. Misses,
which no hand parser can close: a tee named through a variable (`| $TEE x`)
or an alias; and `continue-on-error: true` is taken as "this verdict does not
count" without checking that no later step reads `steps.<id>.outcome`.

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

# A single `|` (not `||`), or `|&` (stderr too), into a command that has the
# word tee anywhere before its end (`;` `&` `|` or the line's end): `| tee`,
# `| /usr/bin/tee`, `| "tee"`, `| sudo -u ci tee`, `| timeout 60 tee`,
# `| { tee x; }`. Not a list of the commands that run the next one -- review
# 5 of #828 found three a list did not have.
TEE = re.compile(r"(?<!\|)\|&?(?!\|)[^|;&]*?(?<![\w.-])(?:\S*/)?['\"]?tee['\"]?(?![\w.-])")
# Anything that may turn pipefail off, read as raw text: a `+...o` option word
# whatever follows it (`set +o pipefail`, `set +o "pipe"fail`, `set +o $opt`),
# and any shopt (`shopt -uo pipefail`).
PF_OFF = re.compile(r"(?<![\w+-])\+[A-Za-z]*o(?![\w-])|\bshopt\b")
SWALLOWED = re.compile(r"\|\|\s*(true|:)\s*$")
# `<<EOF`, `<<-EOF`, `<< 'EOF'`, `<<"EOF"`, `<<\EOF` -- not `<<<` (a
# here-string).
HEREDOC = re.compile(r"(?<!<)<<(-?)\s*\\?(['\"]?)([A-Za-z_][\w.-]*)\2")


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


def heredocs(code: str, masked: str) -> list[tuple[bool, str]]:
    """The heredocs a line opens, in order: (strip tabs, end word). The `<<`
    must stand outside quotes; matched in code, where a quoted 'EOF' keeps its
    word."""
    return [(d.group(1) == "-", d.group(3)) for d in HEREDOC.finditer(code)
            if masked[d.start()] == "<"]


def body_end(script: list[str], first: int, strip_tabs: bool, word: str) -> int:
    """Index of a heredoc's end line (len(script) when it never comes)."""
    for j in range(first, len(script)):
        if (script[j].lstrip("\t") if strip_tabs else script[j]) == word:
            return j
    return len(script)


def logical_lines(script: list[str]) -> list[tuple[int, str, list[tuple[int, int]]]]:
    """Lines bash reads as one: a trailing backslash, or a trailing `|` / `|&`
    (bash goes on reading the pipeline on the next line) -- in CODE: a comment
    ends at its newline whatever it ends with, so `# old flag \\` or
    `make  # pipe it |` leaves the next line a command of its own (#828).
    The bodies of the heredocs a line opens are not code and are skipped: an
    `it's` in one opened a quote that hid the next pipe (review 5 of #828).
    (first physical index, text, [(body first, body end) ...])."""
    out, buf, start, quote, k = [], "", 0, "", 0
    while k < len(script):
        ln = script[k]
        if not buf:
            start, opened = k, quote
        code, _, after = shell_view(ln, quote)
        r = code.rstrip()
        # Only outside quotes: inside one the string simply goes on.
        if not after and r.endswith("\\") and not r.endswith("\\\\"):
            buf += r[:-1] + " "
            k += 1
            continue
        if not after and re.search(r"(?<!\|)\|&?$", r):
            buf += r + " "
            k += 1
            continue
        text = buf + ln
        bodies, nxt = [], k + 1
        for strip_tabs, word in heredocs(*shell_view(text, opened)[:2]):
            end = body_end(script, nxt, strip_tabs, word)
            bodies.append((nxt, end))
            nxt = end + 1
        out.append((start, text, bodies))
        buf, quote, k = "", after, nxt
    if buf:
        out.append((start, buf, []))
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
            # In "..." and in $'...' a backslash escapes the next character.
            if quote in ('"', "$'") and c == "\\" and i + 1 < len(text):
                code.append(text[i:i + 2])
                masked.append("__")
                i += 2
                continue
            if c == quote[-1]:
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
        if c == "$" and text[i + 1:i + 2] == "'":
            code.append("$'")
            masked.append("$'")
            quote = "$'"
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


def leading_pipefail(logical: list[tuple[int, str, list[tuple[int, int]]]]) -> bool:
    """Does the script open with plain `set` lines that turn pipefail on?
    Only the leading commands count (see the docstring): the first line that
    is anything else ends the search."""
    on, quote = False, ""
    for _, text, _ in logical:
        code, _, quote = shell_view(text, quote)
        line = code.strip()
        if not line:
            continue
        # `set -o pipefail; yosys | tee x` on the first line runs the set
        # first too; whatever follows the `;` ends the leading commands.
        head, sep, _ = line.partition(";")
        head = head.strip()
        # Options only, unquoted: not `set -- -o pipefail` (arguments), not
        # `set -o pipefail &` (a background job), not `false && set ...`, not
        # a command that merely starts with the letters `set`.
        if not re.fullmatch(r"set(?:\s+(?:[-+][A-Za-z]+|[a-z]+))*", head):
            return on
        got = set_options(head.split()[1:])
        if got is not None:
            on = got
        if sep:
            return on
    return on


def unsafe_pipes(script: list[str], pipefail: bool) -> list[int]:
    """Indexes (into script) of tee pipes that can hide a failure. pipefail:
    the step's shell turns it on."""
    logical = logical_lines(script)
    text = "\n".join(script)
    if PF_OFF.search(text):
        pipefail = False  # turned off somewhere: neither the shell nor a set counts
    else:
        pipefail = pipefail or leading_pipefail(logical)
    hits, quote = [], ""
    for k, line, bodies in logical:
        code, masked, quote = shell_view(line, quote)
        for m in TEE.finditer(code):
            # A tee in a string runs, if at all, in a shell of its own.
            if pipefail and masked[m.start()] == "|":
                continue
            # This pipeline's own end: up to the next ; or && after tee, read
            # outside quotes, so a `"; x || true"` argument is not its end.
            rest = re.split(r";|&&", masked[m.end():], maxsplit=1)[0]
            if SWALLOWED.search(rest.strip()):
                continue
            hits.append(k)
            break
        # A heredoc body is not this shell's script: data, or a script some
        # other command runs from a fresh state. Read it as its own script,
        # starting without pipefail.
        for first, end in bodies:
            hits += [first + h for h in unsafe_pipes(script[first:end], False)]
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
