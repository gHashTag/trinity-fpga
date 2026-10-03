#!/usr/bin/env python3
r"""Does every workflow step's shell script parse?

A `run:` script with a syntax error does not fail at review time, it fails
when it runs -- and two steps here only run on `workflow_dispatch`, so their
errors sat unseen:

  - build-matrix.yml "Full bitstream build": a `doesn't` in a comment inside
    `bash -c '...'` closed the single-quoted script, and the rest of it was
    read as the outer shell's;
  - iddr-golden-diff.yml "Build the same design with openXC7 and diff the
    ILOGIC config": the `'\''` idiom, which only means "a quote" INSIDE single
    quotes, was used on a line outside them and left one quote open.

Both steps failed on parse every time they were dispatched. This gate runs
`bash -n` (or `sh -n` for `shell: sh`) on every step whose effective shell is
a POSIX one -- the step's `shell:`, else the job's, else the workflow's
`defaults.run.shell`, read through `/usr/bin/env [-opts] [VAR=x]`. With no
`shell:` anywhere it is bash; pwsh on a `windows` runner, which is skipped;
and in a `container:` job, bash only if the image has it and `sh` if not -- so
there the script is checked with BOTH, and a bashism needs an explicit
`shell: bash`. `${{ ... }}` is left as written: `bash -n` does not expand it.
A `shell:` line that does not split into words is "cannot tell".

`bash -n` reads syntax only: a script inside a quoted `bash -c '...'` argument
is one string to it, so an error INSIDE that string is not seen -- unless, as
in both cases above, it breaks the quoting of the outer script.

Exit 0 clean, 1 a step that does not parse, 2 a workflow this could not read
(cannot tell is not clean). tools/test_check_run_syntax.py plants every case.
"""
from __future__ import annotations

import pathlib
import shlex
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"


class CannotTell(Exception):
    pass


POSIX = ("bash", "sh")


def command_word(words: list[str]) -> str:
    """The program a `shell:` line runs, looking through `env [-opts] [VAR=x]`."""
    while words:
        word, words = words[0], words[1:]
        if pathlib.PurePosixPath(word).name != "env":
            return word
        while words and (words[0].startswith("-") or "=" in words[0]):
            opt, words = words[0], words[1:]
            if opt in ("-S", "--split-string") and words:
                words = shlex.split(words[0]) + words[1:]
            elif opt.startswith("-S") and len(opt) > 2:
                words = shlex.split(opt[2:]) + words
            elif opt.startswith("--split-string="):
                words = shlex.split(opt.split("=", 1)[1]) + words
    return ""


def shell_of(step: dict, job: dict, wf: dict) -> tuple[str, ...]:
    """The interpreters to check the script with; empty to skip it."""
    for node in (step, (job.get("defaults") or {}).get("run") or {}, (wf.get("defaults") or {}).get("run") or {}):
        sh = node.get("shell")
        if sh:
            break
    else:
        runs_on = str(job.get("runs-on", ""))
        if "windows" in runs_on.lower():
            return ()
        # In a `container:` job the default is bash only if the image has it,
        # and `sh` otherwise -- so the script has to parse in both.
        return POSIX if job.get("container") else ("bash",)
    try:
        name = pathlib.PurePosixPath(command_word(shlex.split(str(sh)))).name
    except ValueError as e:
        raise CannotTell(f"shell: {sh!r} does not split ({e})")
    if name in POSIX:
        return (name,)
    return ()  # pwsh, python, cmd, a custom shell: not ours to parse


def check(path: pathlib.Path) -> tuple[list[str], str | None]:
    import yaml  # inside: a missing PyYAML is "cannot tell", not a crash
    try:
        wf = yaml.safe_load(path.read_text())
    except yaml.YAMLError as e:
        return [], f"{path.name}: not YAML ({e.__class__.__name__})"
    if not isinstance(wf, dict) or not isinstance(wf.get("jobs"), dict):
        return [], f"{path.name}: no jobs mapping"
    bad = []
    for jn, job in wf["jobs"].items():
        if not isinstance(job, dict):
            return [], f"{path.name} :: {jn}: job is not a mapping"
        for k, step in enumerate(job.get("steps") or [], 1):
            if not isinstance(step, dict):
                return [], f"{path.name} :: {jn}: step {k} is not a mapping"
            if "run" not in step:
                continue
            try:
                shells = shell_of(step, job, wf)
            except CannotTell as e:
                return [], f"{path.name} :: {jn} :: step {k}: {e}"
            for sh in shells:
                r = subprocess.run([sh, "-n"], input=str(step["run"]), capture_output=True, text=True)
                if r.returncode:
                    err = " ".join(r.stderr.split())[:240]
                    bad.append(f"{path.relative_to(ROOT)} :: {jn} :: {step.get('name') or f'step {k}'}"
                               f" [{sh} -n]\n    {err}")
                    break
    return bad, None


def main() -> int:
    try:
        import yaml  # noqa: F401
    except ImportError:
        print("cannot tell: PyYAML is not installed")
        return 2
    for sh in POSIX:
        if not shutil.which(sh):
            print(f"cannot tell: no {sh} on PATH")
            return 2
    files = sorted(list(WORKFLOWS.glob("*.yml")) + list(WORKFLOWS.glob("*.yaml")))
    bad, unread = [], []
    for f in files:
        b, err = check(f)
        bad += b
        if err:
            unread.append(err)
    print(f"workflows read: {len(files) - len(unread)} of {len(files)}; steps that do not parse: {len(bad)}")
    for b in bad:
        print("  " + b)
    for u in unread:
        print("  cannot read: " + u)
    if bad:
        print("\nFAIL: these steps fail on parse every time they run. A quote inside a")
        print("single-quoted `bash -c '...'` (an apostrophe in a comment counts) ends it.")
        return 1
    return 2 if unread else 0


if __name__ == "__main__":
    sys.exit(main())
