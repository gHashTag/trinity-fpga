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
    ("shell: sh is checked with sh", 1, H +
     "    steps:\n      - shell: sh\n        run: |\n          if true; then\n"),
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
    print(f"\n{good} of {len(CASES)} cases as expected")
    return 0 if good == len(CASES) else 1


if __name__ == "__main__":
    sys.exit(main())
