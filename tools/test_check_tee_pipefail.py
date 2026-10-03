#!/usr/bin/env python3
"""Plants every case tools/check_tee_pipefail.py claims to decide, and checks
its exit code: 0 clean, 1 a new or stale entry, 2 cannot tell.

"This turns red when X" is a claim to test by planting X (#819). Each case
writes one workflow into an empty tree with its own baseline and runs the
checker's main() on it. Cases 25-28 are the four misses the review of #828
reproduced: a second same-named step behind the first one's entry, a job body
indented 4, a PIPESTATUS read far below the pipe, and a `|` that ends a line
with tee on the next.

Exit 0 when every case gives its expected code, 1 otherwise.
"""
from __future__ import annotations

import contextlib
import importlib.util
import io
import pathlib
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("ctp", HERE / "check_tee_pipefail.py")
ctp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ctp)

H = "on: push\njobs:\n  j:\n    runs-on: ubuntu-latest\n"
PF = "    defaults:\n      run:\n        shell: bash -eo pipefail {0}\n"
WF = ".github/workflows/t.yml"

# (name, expected rc, workflow text, baseline entries)
CASES: list[tuple[str, int, str, list[str]]] = [
    ("default shell", 1, H + "    steps:\n      - name: Synth\n        run: |\n"
     "          yosys -p x 2>&1 | tee y.log\n", []),
    ("shell: bash", 0, H + "    steps:\n      - name: Synth\n        shell: bash\n"
     "        run: |\n          yosys -p x 2>&1 | tee y.log\n", []),
    ("workflow defaults", 0, "on: push\ndefaults:\n  run:\n    shell: bash -eo pipefail {0}\n"
     "jobs:\n  j:\n    runs-on: ubuntu-latest\n    steps:\n      - run: yosys | tee y.log\n", []),
    ("job defaults", 0, H + PF + "    steps:\n      - run: yosys | tee y.log\n", []),
    ("set -euo pipefail", 0, H + "    steps:\n      - run: |\n          set -euo pipefail\n"
     "          yosys | tee y.log\n", []),
    ("pipefail turned off", 1, H + "    steps:\n      - run: |\n          set -o pipefail\n"
     "          set +o pipefail\n          yosys | tee y.log\n", []),
    ("PIPESTATUS on the next line", 0, H + "    steps:\n      - run: |\n"
     "          yosys | tee y.log\n          exit ${PIPESTATUS[0]}\n", []),
    ("|| true", 0, H + "    steps:\n      - run: |\n          yosys | tee y.log || true\n", []),
    ("echo", 0, H + "    steps:\n      - run: |\n"
     "          echo \"n=$(nproc | wc -l)\" | tee -a $GITHUB_STEP_SUMMARY\n", []),
    ("continue-on-error", 0, H + "    steps:\n      - name: soft\n"
     "        continue-on-error: true\n        run: |\n          yosys | tee y.log\n", []),
    ("shell sh", 1, H + "    steps:\n      - shell: sh -e {0}\n        run: yosys | tee y.log\n", []),
    ("explicit bash -e", 1, H + "    steps:\n      - shell: bash -e {0}\n"
     "        run: yosys | tee y.log\n", []),
    ("step sh overrides job pipefail", 1, H + PF + "    steps:\n      - shell: sh -e {0}\n"
     "        run: yosys | tee y.log\n", []),
    ("|& tee", 1, H + "    steps:\n      - run: |\n          yosys |& tee y.log\n", []),
    ("folded scalar", 1, H + "    steps:\n      - run: >\n          yosys -p x\n"
     "          | tee y.log\n", []),
    ("backslash continuation", 1, H + "    steps:\n      - run: |\n          yosys -p x \\\n"
     "            -q | tee y.log\n", []),
    ("with: name is not the step name", 1, H + "    steps:\n"
     "      - uses: actions/upload-artifact@v4\n        with:\n          name: logs\n"
     "      - run: yosys | tee y.log\n", []),
    ("zero-indent list", 1, "on: push\njobs:\n  j:\n    runs-on: ubuntu-latest\n    steps:\n"
     "    - name: Synth\n      run: yosys | tee y.log\n", []),
    ("two jobs, second unsafe", 1, H + PF + "    steps:\n      - run: yosys | tee y.log\n"
     "  k:\n    runs-on: ubuntu-latest\n    steps:\n      - run: nextpnr | tee p.log\n", []),
    ("|| is not a pipe", 0, H + "    steps:\n      - run: |\n          yosys || tee y.log\n", []),
    ("commented pipe", 0, H + "    steps:\n      - run: |\n          # yosys | tee y.log\n"
     "          true\n", []),
    ("no jobs = cannot tell", 2, "on: push\n", []),
    ("known entry", 0, H + "    steps:\n      - name: Synth\n        run: yosys | tee y.log\n",
     [f"{WF} :: j :: Synth"]),
    ("stale entry", 1, H + "    steps:\n      - name: Synth\n        run: yosys | tee y.log\n",
     [f"{WF} :: j :: Synth", f"{WF} :: j :: Gone"]),
    # -- the four misses of the #828 review --
    ("second same-named step is not covered by the first's entry", 1,
     H + "    steps:\n      - name: Yosys\n        run: yosys a | tee a.log\n"
     "      - name: Yosys\n        run: yosys b | tee b.log\n",
     [f"{WF} :: j :: Yosys"]),
    ("fixing one of two same-named steps stales its entry", 1,
     H + "    steps:\n      - name: Yosys\n        run: yosys a | tee a.log\n"
     "      - name: Yosys\n        shell: bash\n        run: yosys b | tee b.log\n",
     [f"{WF} :: j :: Yosys", f"{WF} :: j :: Yosys #2"]),
    ("job body indented 4", 1, "on: push\njobs:\n  j:\n      runs-on: ubuntu-latest\n"
     "      steps:\n        - run: yosys | tee y.log\n", []),
    ("PIPESTATUS far below reads another pipe", 1, H + "    steps:\n      - run: |\n"
     "          yosys | tee y.log\n          nextpnr | cat\n          ls\n"
     "          echo ${PIPESTATUS[0]}\n", []),
    ("trailing | with tee on the next line", 1, H + "    steps:\n      - run: |\n"
     "          yosys 2>&1 |\n            tee y.log\n", []),
    # -- the rest of the review's list --
    ("set pipefail AFTER the pipe on the same line", 1, H + "    steps:\n      - run: |\n"
     "          set -x; yosys | tee y.log; set -o pipefail\n", []),
    ("set pipefail BEFORE the pipe on the same line", 0, H + "    steps:\n      - run: |\n"
     "          set -o pipefail; yosys | tee y.log\n", []),
    ("| sudo tee", 1, H + "    steps:\n      - run: yosys | sudo -E tee /var/y.log\n", []),
    ("| /usr/bin/tee", 1, H + "    steps:\n      - run: yosys | /usr/bin/tee y.log\n", []),
    ("tee-like name is not tee", 0, H + "    steps:\n      - run: yosys | teeth\n", []),
    ("comment after the name is not the name", 0, H + "    steps:\n"
     "      - name: Synth  # the slow one\n        run: yosys | tee y.log\n",
     [f"{WF} :: j :: Synth"]),
    ("comment after `shell: bash` keeps pipefail", 0, H + "    steps:\n"
     "      - shell: bash  # the default\n        run: yosys | tee y.log\n", []),
    ("quoted run key = cannot tell", 2, H + "    steps:\n      - \"run\": yosys | tee y.log\n", []),
    ("flow-style step = cannot tell", 2, H + "    steps:\n      - { run: yosys | tee y.log }\n", []),
    ("merge key = cannot tell", 2, "on: push\njobs:\n  j:\n    <<: *base\n"
     "    steps:\n      - run: yosys | tee y.log\n", []),
    ("multi-line plain run", 1, H + "    steps:\n      - run: yosys -p x 2>&1\n"
     "          | tee y.log\n", []),
    ("multi-line double-quoted run", 1, H + "    steps:\n      - run: \"yosys -p x\n"
     "          | tee y.log\"\n", []),
    ("matrix axis named run is not a step", 0, H + "    strategy:\n      matrix:\n"
     "        run: [1, 2, 3]\n    steps:\n      - run: echo ok\n", []),
    ("echo after ; is still a bare echo", 0, H + "    steps:\n      - run: |\n"
     "          cd x; echo hi | tee -a log\n", []),
    ("make before ; and || true on another pipeline", 1, H + "    steps:\n      - run: |\n"
     "          yosys | tee y.log; ls || true\n", []),
]


def run_case(text: str, base: list[str], argv: list[str] | None = None) -> tuple[int, str, str]:
    with tempfile.TemporaryDirectory() as d:
        root = pathlib.Path(d)
        wf = root / WF
        wf.parent.mkdir(parents=True)
        wf.write_text(text)
        bl = root / "baseline.txt"
        bl.write_text("# header\n" + "".join(b + "\n" for b in base))
        ctp.ROOT, ctp.WORKFLOWS, ctp.BASE = root, wf.parent, bl
        old, sys.argv = sys.argv, ["check_tee_pipefail.py"] + (argv or [])
        out = io.StringIO()
        try:
            with contextlib.redirect_stdout(out):
                rc = ctp.main()
        finally:
            sys.argv = old
        return rc, out.getvalue(), bl.read_text()


def main() -> int:
    bad = 0
    for name, want, text, base in CASES:
        rc, out, _ = run_case(text, base)
        if rc == want:
            print(f"ok   {name} (rc {rc})")
        else:
            bad += 1
            print(f"BAD  {name}: want rc {want}, got {rc}")
            print("     " + out.strip().replace("\n", "\n     "))

    # --prune-baseline only removes: a stale entry goes, a new step is not added.
    text = H + "    steps:\n      - name: A\n        run: yosys | tee a.log\n" \
        "      - name: B\n        run: nextpnr | tee b.log\n"
    rc, _, after = run_case(text, [f"{WF} :: j :: A", f"{WF} :: j :: Gone"], ["--prune-baseline"])
    want = f"# header\n{WF} :: j :: A\n"
    if rc == 0 and after == want:
        print("ok   --prune-baseline removes the stale entry and adds nothing")
    else:
        bad += 1
        print(f"BAD  --prune-baseline: rc {rc}, baseline now {after!r}")

    total = len(CASES) + 1
    print(f"\n{total - bad} of {total} cases as expected")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
