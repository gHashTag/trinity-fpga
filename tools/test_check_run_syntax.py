#!/usr/bin/env python3
"""Self-test for tools/check_run_syntax.py: every case is a one-file tree."""
from __future__ import annotations

import contextlib
import importlib.util
import io
import pathlib
import subprocess
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("crs", HERE / "check_run_syntax.py")
crs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(crs)

H = "on: push\njobs:\n  j:\n    runs-on: ubuntu-latest\n"


def git_show(rev_path: str) -> str | None:
    r = subprocess.run(["git", "-C", str(HERE), "show", rev_path], capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else None


# (name, expected rc, workflow text)
CASES: list[tuple[str, int, str]] = [
    ("a clean step", 0, H + "    steps:\n      - run: echo ok\n"),
    ("an apostrophe in a comment inside bash -c '...'", 1, H +
     "    steps:\n      - run: |\n          docker run img bash -c '\n"
     "            # this does not matter, it doesn't\n            make\n          '\n"),
    ("'\\'' outside single quotes leaves one open", 1, H +
     "    steps:\n      - run: |\n          norm() { grep -oE '\\''A.+'\\'' \"$1\"; }\n"),
    ("'\\'' inside single quotes is a quote", 0, H +
     "    steps:\n      - run: |\n          bash -c 'grep -oE '\\''A.+'\\'' x'\n"),
    ("an unclosed if", 1, H + "    steps:\n      - run: |\n          if true; then\n            echo x\n"),
    ("${{ }} is left as written", 0, H +
     "    steps:\n      - run: echo \"${{ github.sha }}\"\n"),
    # `cat <(echo x)` parses in bash and not in sh (dash, or bash in POSIX
    # mode as macOS's /bin/sh), so these two tell the interpreters apart.
    ("shell: sh is checked with sh", 1, H +
     "    steps:\n      - shell: sh\n        run: cat <(echo x)\n"),
    ("shell: bash is checked with bash", 0, H +
     "    steps:\n      - shell: bash\n        run: cat <(echo x)\n"),
    ("no shell is bash", 0, H + "    steps:\n      - run: cat <(echo x)\n"),
    ("a container job with no shell must parse in sh too", 1, H +
     "    container: alpine:3\n    steps:\n      - run: cat <(echo x)\n"),
    ("a container job with no shell must parse in bash too", 1, H +
     "    container: alpine:3\n    steps:\n      - run: 'echo \"x'\n"),
    ("a container job with shell: bash is bash", 0, H +
     "    container: alpine:3\n    steps:\n      - shell: bash\n        run: cat <(echo x)\n"),
    ("a container job with a job default shell: bash is bash", 0, H +
     "    container: alpine:3\n    defaults:\n      run:\n        shell: bash\n"
     "    steps:\n      - run: cat <(echo x)\n"),
    ("shell: /usr/bin/env bash {0} is bash", 1, H +
     "    steps:\n      - shell: /usr/bin/env bash {0}\n        run: 'echo \"x'\n"),
    ("shell: env -i PATH=/bin sh {0} is sh", 1, H +
     "    steps:\n      - shell: env -i PATH=/bin sh {0}\n        run: cat <(echo x)\n"),
    ("shell: env -S 'sh -e {0}' is sh", 1, H +
     "    steps:\n      - shell: env -S 'sh -e {0}'\n        run: cat <(echo x)\n"),
    ("shell: env -S'sh -e {0}' (attached) is sh", 1, H +
     "    steps:\n      - shell: env -S'sh -e {0}'\n        run: cat <(echo x)\n"),
    ("shell: env --split-string='sh -e {0}' is sh", 1, H +
     "    steps:\n      - shell: env --split-string='sh -e {0}'\n        run: cat <(echo x)\n"),
    ("shell: env -u FOO sh {0} is sh, not FOO", 1, H +
     "    steps:\n      - shell: env -u FOO sh {0}\n        run: cat <(echo x)\n"),
    ("shell: env -C /tmp sh {0} is sh, not /tmp", 1, H +
     "    steps:\n      - shell: env -C /tmp sh {0}\n        run: cat <(echo x)\n"),
    ("an expression shell = cannot tell", 2, H +
     "    strategy:\n      matrix:\n        shell: [bash]\n"
     "    defaults:\n      run:\n        shell: ${{ matrix.shell }} {0}\n"
     "    steps:\n      - run: 'echo \"x'\n"),
    ("a runs-on expression that may pick windows = cannot tell", 2,
     "on: workflow_dispatch\njobs:\n  j:\n"
     "    runs-on: ${{ inputs.win && 'windows-latest' || 'ubuntu-latest' }}\n"
     "    steps:\n      - run: 'echo \"x'\n"),
    ("runs-on: ${{ matrix.os }} without windows is bash", 1,
     "on: push\njobs:\n  j:\n    strategy:\n      matrix:\n        os: [ubuntu-latest]\n"
     "    runs-on: ${{ matrix.os }}\n"
     "    steps:\n      - run: 'echo \"x'\n"),
    ("defaults that is not a mapping = cannot tell", 2, H +
     "    defaults: bash\n    steps:\n      - run: echo ok\n"),
    ("shell: env python {0} is skipped", 0, H +
     "    steps:\n      - shell: env python {0}\n        run: print('it doesn')\n"),
    ("a shell line with an open quote = cannot tell", 2, H +
     "    steps:\n      - shell: bash -c 'x {0}\n        run: echo ok\n"),
    ("shell: bash -eo pipefail {0} is bash", 1, H +
     "    steps:\n      - shell: bash -eo pipefail {0}\n        run: 'echo \"x'\n"),
    ("job defaults shell: python is skipped", 0, H +
     "    defaults:\n      run:\n        shell: python\n    steps:\n      - run: print('it doesn')\n"),
    ("workflow defaults shell: pwsh is skipped", 0,
     "on: push\ndefaults:\n  run:\n    shell: pwsh\njobs:\n  j:\n    runs-on: ubuntu-latest\n"
     "    steps:\n      - run: Write-Host \"it's\n"),
    ("the step's shell beats the job's", 1, H +
     "    defaults:\n      run:\n        shell: python\n    steps:\n      - shell: bash\n        run: 'echo \"x'\n"),
    ("a windows runner with no shell is skipped", 0,
     "on: push\njobs:\n  j:\n    runs-on: windows-latest\n    steps:\n      - run: echo \"it's\n"),
    ("a step with no run is skipped", 0, H + "    steps:\n      - uses: actions/checkout@v4\n"),
    ("not YAML = cannot tell", 2, "on: [\n"),
    ("no jobs = cannot tell", 2, "on: push\n"),
    ("a step that is not a mapping = cannot tell", 2, H + "    steps:\n      - echo\n"),
]

# The two defects this gate was written for, as they stood on main.
for name, path in (("main's build-matrix.yml before the fix", ".github/workflows/build-matrix.yml"),
                   ("main's iddr-golden-diff.yml before the fix", ".github/workflows/iddr-golden-diff.yml")):
    # A missing commit (a shallow clone) is an empty file, rc 2, so the case
    # goes BAD instead of quietly dropping out.
    CASES.append((name, 1, git_show(f"e6eac090:{path}") or ""))


# Direct answers where no script can tell the interpreters apart portably:
# on macOS /bin/sh is bash, so "must parse in bash too" cannot be shown by a
# script that only bash rejects. (name, got, want)
DIRECT = [
    ("a container job is checked with bash and sh",
     lambda: crs.shell_of({}, {"container": "alpine:3"}, {}), ("bash", "sh")),
    ("a plain job is checked with bash", lambda: crs.shell_of({}, {}, {}), ("bash",)),
    ("WINDOWS-latest is skipped (case-blind)",
     lambda: crs.shell_of({}, {"runs-on": "WINDOWS-latest"}, {}), ()),
]


def run_case(text: str) -> tuple[int, str]:
    with tempfile.TemporaryDirectory() as d:
        root = pathlib.Path(d)
        wf = root / ".github" / "workflows"
        wf.mkdir(parents=True)
        (wf / "t.yml").write_text(text)
        crs.ROOT, crs.WORKFLOWS = root, wf
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = crs.main()
        return rc, out.getvalue()


def main() -> int:
    good = 0
    for name, want, text in CASES:
        rc, out = run_case(text)
        if rc == want:
            good += 1
            print(f"ok   {name} (rc {rc})")
        else:
            print(f"BAD  {name}: want rc {want}, got {rc}\n{out}")
    for name, got, want in DIRECT:
        g = got()
        if g == want:
            good += 1
            print(f"ok   {name} ({g})")
        else:
            print(f"BAD  {name}: want {want}, got {g}")
    total = len(CASES) + len(DIRECT)
    print(f"\n{good} of {total} cases as expected")
    return 0 if good == total else 1


if __name__ == "__main__":
    sys.exit(main())
