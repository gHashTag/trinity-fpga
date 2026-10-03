#!/usr/bin/env python3
"""Plants every case tools/check_tee_pipefail.py claims to decide, and checks
its exit code: 0 clean, 1 a new or stale entry, 2 cannot tell.

"This turns red when X" is a claim to test by planting X (#819). Each case
writes one workflow into an empty tree with its own baseline and runs the
checker's main() on it. Cases 25-28 are the four misses the review of #828
reproduced: a second same-named step behind the first one's entry, a job body
indented 4, a PIPESTATUS read far below the pipe, and a `|` that ends a line
with tee on the next. The second review's three -- a quoted job key, a step
not opened by `- key:`, an aliased steps list -- each walked an unsafe step
past a hand-read YAML layout; the checker now reads YAML with PyYAML, and they
stay planted here. Review 5 found the bare echo/printf exemption false
(`echo "${X:?}"`, `printf '%d' abc` fail), a heredoc body read as code, `$'`
quotes, shopt, `+o "pipe"fail` and tee behind `timeout` or a group: each one
was green behind tee in real `bash -e`, and is planted here.

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
# A first step that passes, for a second one to be misread into.
A = "    steps:\n      - name: safe\n        shell: bash\n        run: echo ok\n"

# (name, expected rc, workflow text, baseline entries)
R = "    steps:\n      - run: |\n"
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
    ("PIPESTATUS is no exemption: nothing says it is acted on (#828)", 1, H + "    steps:\n      - run: |\n"
     "          yosys | tee y.log\n          exit ${PIPESTATUS[0]}\n", []),
    ("|| true is no exemption: the gate does not read intent", 1, H + "    steps:\n      - run: |\n          yosys | tee y.log || true\n", []),
    ("echo is no exemption: it fails too", 1, H + "    steps:\n      - run: |\n"
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
    ("commented pipe is read: a # line may be inside a quoted string (review 7)", 1,
     H + "    steps:\n      - run: |\n          # yosys | tee y.log\n          true\n", []),
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
    ("set pipefail; and a pipe on one line: not a plain set line", 1, H + "    steps:\n      - run: |\n"
     "          set -o pipefail; yosys | tee y.log\n", []),
    ("| sudo tee", 1, H + "    steps:\n      - run: yosys | sudo -E tee /var/y.log\n", []),
    ("| /usr/bin/tee", 1, H + "    steps:\n      - run: yosys | /usr/bin/tee y.log\n", []),
    ("tee-like name is not tee", 0, H + "    steps:\n      - run: yosys | teeth\n", []),
    ("comment after the name is not the name", 0, H + "    steps:\n"
     "      - name: Synth  # the slow one\n        run: yosys | tee y.log\n",
     [f"{WF} :: j :: Synth"]),
    ("comment after `shell: bash` keeps pipefail", 0, H + "    steps:\n"
     "      - shell: bash  # the default\n        run: yosys | tee y.log\n", []),
    ("quoted run key is a run key", 1, H + "    steps:\n      - \"run\": yosys | tee y.log\n", []),
    ("flow-style step is a step", 1, H + "    steps:\n      - { run: yosys | tee y.log }\n", []),
    ("merge key = cannot tell", 2, "on: push\nbase: &b\n  defaults:\n    run:\n"
     "      shell: bash\njobs:\n  j:\n    <<: *b\n    runs-on: ubuntu-latest\n"
     "    steps:\n      - run: yosys | tee y.log\n", []),
    ("multi-line plain run", 1, H + "    steps:\n      - run: yosys -p x 2>&1\n"
     "          | tee y.log\n", []),
    ("multi-line double-quoted run", 1, H + "    steps:\n      - run: \"yosys -p x\n"
     "          | tee y.log\"\n", []),
    ("matrix axis named run is not a step", 0, H + "    strategy:\n      matrix:\n"
     "        run: [1, 2, 3]\n    steps:\n      - run: echo ok\n", []),
    ("echo after ; is no exemption", 1, H + "    steps:\n      - run: |\n"
     "          cd x; echo hi | tee -a log\n", []),
    ("make before ; and || true on another pipeline", 1, H + "    steps:\n      - run: |\n"
     "          yosys | tee y.log; ls || true\n", []),
    # -- the three of the second review: a hand-read layout walked them past --
    ("quoted job key is a job, not the job above's steps", 1,
     "on: push\njobs:\n  a:\n    runs-on: ubuntu-latest\n    steps:\n      - name: Yosys\n"
     "        run: yosys a | tee a.log\n  \"evil\":\n    runs-on: ubuntu-latest\n    steps:\n"
     "      - name: Yosys\n        run: yosys b | tee b.log\n",
     [f"{WF} :: a :: Yosys"]),
    ("anchored step `- &s` is its own step", 1, H + A + "      - &s\n"
     "        run: yosys | tee y.log\n", []),
    ("bare `-` step is its own step", 1, H + A + "      -\n        run: yosys | tee y.log\n", []),
    ("`- # comment` step is its own step", 1, H + A + "      - # slow\n"
     "        run: yosys | tee y.log\n", []),
    ("aliased steps list is read for the second job too", 1,
     "on: push\njobs:\n  a:\n    runs-on: ubuntu-latest\n    defaults:\n      run:\n"
     "        shell: bash -eo pipefail {0}\n    steps: &st\n      - run: yosys | tee y.log\n"
     "  b:\n    runs-on: ubuntu-latest\n    steps: *st\n", []),
    ("aliased step `- *s` is read", 1, H + "    steps:\n      - &s\n        shell: bash\n"
     "        run: echo ok\n      - *s\n      - run: yosys | tee y.log\n", []),
    ("key given twice = cannot tell", 2, H + "    steps:\n      - shell: bash\n"
     "        run: yosys | tee y.log\n        shell: sh -e {0}\n", []),
    ("steps not a list = cannot tell", 2, H + "    steps: yosys | tee y.log\n", []),
    ("step not a mapping = cannot tell", 2, H + "    steps:\n      - yosys | tee y.log\n", []),
    ("not YAML = cannot tell", 2, H + "    steps:\n      - run: [yosys | tee\n", []),
    # -- its script-level list: a set this shell never runs --
    ("set in a heredoc body is not this shell's", 1, H + "    steps:\n      - run: |\n"
     "          cat > x.sh <<'EOF'\n          set -euo pipefail\n          EOF\n"
     "          yosys | tee y.log\n", []),
    ("a heredoc script is not read: its own pipefail does not count", 1, H + "    steps:\n      - run: |\n"
     "          bash <<'EOF'\n          set -o pipefail\n          yosys | tee y.log\n"
     "          EOF\n", []),
    ("tee in a heredoc script without pipefail", 1, H + "    steps:\n      - run: |\n"
     "          bash <<EOF\n          yosys | tee y.log\n          EOF\n", []),
    ("set in a multi-line bash -c string", 1, H + "    steps:\n      - run: |\n"
     "          bash -c \"\n            set -eo pipefail\n            make\n          \"\n"
     "          yosys | tee y.log\n", []),
    ("set in a subshell", 1, H + "    steps:\n      - run: |\n"
     "          ( set -o pipefail; true )\n          yosys | tee y.log\n", []),
    ("set in a string", 1, H + "    steps:\n      - run: |\n"
     "          echo \"x; set -o pipefail\"\n          yosys | tee y.log\n", []),
    ("set in a trailing comment", 1, H + "    steps:\n      - run: |\n"
     "          true  # ; set -o pipefail\n          yosys | tee y.log\n", []),
    ("echo closing a subshell group", 1, H + "    steps:\n      - run: |\n"
     "          (yosys; echo done) | tee y.log\n", []),
    ("echo closing a brace group", 1, H + "    steps:\n      - run: |\n"
     "          { yosys; echo done; } | tee y.log\n", []),
    ("echo of ${VAR} is no exemption", 1, H + "    steps:\n      - run: |\n"
     "          echo \"${GITHUB_SHA}\" | tee -a sha.txt\n", []),
    ("| stdbuf -oL tee", 1, H + "    steps:\n      - run: yosys | stdbuf -oL tee y.log\n", []),
    ("| command tee", 1, H + "    steps:\n      - run: yosys | command tee y.log\n", []),
    ("| env A=1 tee", 1, H + "    steps:\n      - run: yosys | env A=1 tee y.log\n", []),
    ("| nice -n 5 tee", 1, H + "    steps:\n      - run: yosys | nice -n 5 tee y.log\n", []),
    ("PIPESTATUS only in a comment", 1, H + "    steps:\n      - run: |\n"
     "          yosys | tee y.log\n          true  # PIPESTATUS\n", []),
    ("PIPESTATUS in double quotes is no exemption either", 1, H + "    steps:\n      - run: |\n"
     "          yosys | tee y.log\n          exit \"${PIPESTATUS[0]}\"\n", []),
    ("a trailing comment is read as code: tee there flags", 1, H + "    steps:\n      - run: |\n"
     "          make  # then | tee it\n", []),
    # Review 4 of #828: each of these ended green under bash -e with `false`
    # on the left of the pipe, and the checker said safe.
    ("comment ending in a backslash does not swallow the next line", 1, H + R +
     "          # old flag \\\n          yosys | tee y.log\n", []),
    ("comment ending in a pipe does not swallow the next line", 1, H + R +
     "          make  # pipe it |\n          yosys | tee y.log\n", []),
    ("set in a multi-line subshell does not count", 1, H + R +
     "          (\n            set -o pipefail\n          )\n          yosys | tee y.log\n", []),
    ("set in a multi-line $( ) does not count", 1, H + R +
     "          x=$(\n            set -o pipefail\n          )\n          yosys | tee y.log\n", []),
    ("set in a <<\\EOF heredoc does not count", 1, H + R +
     "          cat > x.sh <<\\EOF\n          set -euo pipefail\n          EOF\n"
     "          yosys | tee y.log\n", []),
    ("PIPESTATUS after another pipeline", 1, H + R +
     "          yosys | tee y.log; ls | wc -l; exit ${PIPESTATUS[0]}\n", []),
    ("shell: +o pipefail turns it off", 1, H + "    steps:\n      - shell: bash -e +o pipefail {0}\n"
     "        run: yosys | tee y.log\n", []),
    ("shell: pipefail after {0} is an argument", 1, H + "    steps:\n"
     "      - shell: 'bash -e {0} pipefail'\n        run: yosys | tee y.log\n", []),
    ("shell: bash -o pipefail {0} has it", 0, H + "    steps:\n      - shell: bash -o pipefail {0}\n"
     "        run: yosys | tee y.log\n", []),
    ("set under && does not count", 1, H + R +
     "          false && set -o pipefail\n          yosys | tee y.log\n", []),
    ("set in the background does not count", 1, H + R +
     "          set -o pipefail &\n          yosys | tee y.log\n", []),
    ("set -- sets arguments", 1, H + R +
     "          set -- -o pipefail\n          yosys | tee y.log\n", []),
    ("set as an echo argument", 1, H + R +
     "          echo do set -o pipefail\n          yosys | tee y.log\n", []),
    ("set after a first command is not read", 1, H + R +
     "          cd /tmp\n          set -o pipefail\n          yosys | tee y.log\n", []),
    ("set lines first, comments between", 0, H + R +
     "          # strict\n          set -e\n\n          set -o pipefail\n          yosys | tee y.log\n", []),
    ("set pipefail; command on the first line: not a plain set line", 1, H + R +
     "          set -o pipefail; yosys | tee y.log\n          make | tee m.log\n", []),
    ("+o pipefail anywhere voids the leading set", 1, H + R +
     "          set -eo pipefail\n          f() { set +o pipefail; }\n          yosys | tee y.log\n", []),
    ("+o pipefail voids the shell too", 1, H + PF + R +
     "          set +o pipefail\n          yosys | tee y.log\n", []),
    ("tee in bash -c runs without the outer pipefail", 1, H + "    steps:\n      - shell: bash\n"
     "        run: bash -c \"yosys | tee y.log\"\n", []),
    ("tee before a set on the first line is not covered by it", 1, H + R +
     "          set -e; yosys | tee y.log\n          set -o pipefail\n", []),
    ("a command named setx is not set", 1, H + R +
     "          setx -o pipefail\n          yosys | tee y.log\n", []),
    ("a string with a backslash line keeps the next pipe's continuation", 1, H + R +
     "          echo \"a \\\n          b\"\n          yosys |\n            tee y.log\n", []),
    ("a backslash ending a line inside a string is not a continuation", 0, H + R +
     "          set -o pipefail\n          echo \"a \\\n          b\"; yosys | tee y.log\n", []),
    # Review 5 of #828: each was "0 new" before, and exits 0 in `bash -e`
    # with tee and 1 without.
    ("an apostrophe in a heredoc body does not hide the next pipe", 1, H + R +
     "          cat > n.txt <<EOF\n          it's data\n          EOF\n"
     "          false |\n            tee x.log\n", []),
    ("two heredocs on a line: both bodies skipped as code", 1, H + R +
     "          cat <<A <<B\n          it's\n          A\n          it's\n          B\n"
     "          false |\n            tee x.log\n", []),
    ("echo ${X:?} fails, so it is no exemption", 1, H + R +
     "          echo \"${X:?}\" | tee -a out\n", []),
    ("printf of a bad number fails, so it is no exemption", 1, H + R +
     "          printf '%d' abc | tee -a out\n", []),
    ("a ; inside a quoted argument is not the left command's start", 1, H + R +
     "          false \"x; echo off\" | tee y\n", []),
    ("shopt -uo pipefail voids shell: bash", 1, H + "    steps:\n      - shell: bash\n"
     "        run: |\n          shopt -uo pipefail\n          false | tee x\n", []),
    ("shopt -uo pipefail voids a leading set", 1, H + R +
     "          set -eo pipefail\n          shopt -uo pipefail\n          false | tee x\n", []),
    ("set +eo pipefail (a bundle) voids shell: bash", 1, H + "    steps:\n      - shell: bash\n"
     "        run: |\n          set +eo pipefail\n          false | tee x\n", []),
    ("set +o with a quoted option name voids a leading set", 1, H + R +
     "          set -eo pipefail\n          set +o \"pipe\"fail\n          false | tee x\n", []),
    ("$'it\\'s' does not end its string early", 1, H + "    steps:\n      - shell: bash\n"
     "        run: |\n          echo $'it\\'s'; bash -c 'false | tee x'\n", []),
    ('tee in quotes: | "tee"', 1, H + R + "          false | \"tee\" x\n", []),
    ("tee under timeout", 1, H + R + "          false | timeout 60 tee x\n", []),
    ("tee in a brace group", 1, H + R + "          false | { tee x; }\n", []),
    ("tee under sudo -u user", 1, H + R + "          false | sudo -u ci tee x\n", []),
    ("GitHub's own expansion of shell: bash has pipefail", 0, H + "    steps:\n"
     "      - shell: bash --noprofile --norc -eo pipefail {0}\n"
     "        run: yosys | tee y.log\n", []),
    ("a word that ends in tee is not tee", 0, H + R + "          make | grep -c committee\n", []),
    ("+o in a word is not an option", 0, H + "    steps:\n      - shell: bash\n"
     "        run: |\n          echo c++o\n          yosys | tee y.log\n", []),
    # Review 6 of #828: the bash model missed each of these; the raw-text
    # rules do not model quotes, heredocs or expansions, so none can hide.
    ("nested quotes in \"$(...)\" do not hide the pipe", 1, H + R +
     "          echo \"$(echo \"a\")\" ; yosys | tee y.log\n", []),
    ("a heredoc on a line ending in |", 1, H + R +
     "          cat <<'EOF' |\n          x\n          EOF\n          tee y.log\n", []),
    ("# inside ${...} is no comment", 1, H + R +
     "          echo ${X#*/} | tee y.log\n", []),
    ("set +\"o\" pipefail voids shell: bash", 1, H + "    steps:\n      - shell: bash\n"
     "        run: |\n          set +\"o\" pipefail\n          yosys | tee y.log\n", []),
    ("${PFOPT:-+o} voids shell: bash", 1, H + "    steps:\n      - shell: bash\n"
     "        run: |\n          set ${PFOPT:-+o} pipefail\n          yosys | tee y.log\n", []),
    ("| { with tee on the next line", 1, H + R +
     "          yosys | {\n            tee y.log\n          }\n", []),
    ("set lines then a comment then a set: the run holds", 0, H + R +
     "          set -e\n          # and\n          set -o pipefail\n          yosys | tee y.log\n", []),
    ("a command between ends the set run", 1, H + R +
     "          set -e\n          cd x\n          set -o pipefail\n          yosys | tee y.log\n", []),
    # A shell of its own under pipefail: flagged, unless the step names why
    # its tee is not in it.
    ("pipefail + bash -c + tee: flagged", 1, H + PF +
     "    steps:\n      - run: |\n          bash -c 'yosys | tee y.log'\n", []),
    ("pipefail + heredoc + tee: flagged", 1, H + PF +
     "    steps:\n      - run: |\n          python3 - <<'PY' | tee y.txt\n          print(1)\n          PY\n", []),
    ("pipefail + heredoc + tee + a reasoned marker", 0, H + PF +
     "    steps:\n      - run: |\n          # tee-pipefail: the heredoc feeds python\n"
     "          python3 - <<'PY' | tee y.txt\n          print(1)\n          PY\n", []),
    ("a marker with no reason is no marker", 1, H + PF +
     "    steps:\n      - run: |\n          # tee-pipefail:\n          bash -c 'yosys | tee y.log'\n", []),
    ("a marker does not lend pipefail to a step without it", 1, H +
     "    steps:\n      - run: |\n          # tee-pipefail: trust me\n          yosys | tee y.log\n", []),
    ("-Dci is no shell of its own", 0, H + PF +
     "    steps:\n      - run: zig build -Dci=true 2>&1 | tee b.log\n", []),
    ("grep -c in a comment is read like code (review 7)", 1, H + PF +
     "    steps:\n      - run: |\n          # count with grep -c later\n          make | tee m.log\n", []),
    ("... and the opening marker answers it", 0, H + PF +
     "    steps:\n      - run: |\n          # tee-pipefail: grep -c is only in a comment\n"
     "          # count with grep -c later\n          make | tee m.log\n", []),
    ("grep -c in code is a shell as far as the gate knows", 1, H + PF +
     "    steps:\n      - run: |\n          make | tee m.log\n          grep -c ok m.log\n", []),
    ("g++ -o is no +o", 0, H + PF +
     "    steps:\n      - run: |\n          g++ -o a a.cc 2>&1 | tee c.log\n", []),
    ("|| between tee and make is no pipe", 0, H +
     "    steps:\n      - run: make || tee fail.log\n", []),
    # -- review 7 of #828 --
    ("# line inside a group's string hides no tee", 1, H +
     "    steps:\n      - run: |\n          { false; echo \"\n          ## Totals\"; } | tee -a x.log\n", []),
    ("# line inside python -c hides no tee", 1, H +
     "    steps:\n      - run: |\n          python3 -c \"\n          # end\" 2>&1 | tee report.log\n", []),
    ("# line inside a string under pipefail hides no shell", 1, H + PF +
     "    steps:\n      - run: |\n          make | tee m.log\n          x=\"\n          # \"; bash -c 'false | tee x.log'\n", []),
    ("piped into bash is a shell of its own", 1, H + PF +
     "    steps:\n      - run: |\n          echo 'false | tee x.log' | bash\n", []),
    ("bash <(...) is a shell of its own", 1, H + PF +
     "    steps:\n      - run: |\n          bash <(echo 'false | tee x.log')\n", []),
    ("bash -Ec is a shell of its own", 1, H + PF +
     "    steps:\n      - run: |\n          bash -Ec 'false | tee x.log'\n", []),
    ("bash -euxvfc is a shell of its own", 1, H + PF +
     "    steps:\n      - run: |\n          bash -euxvfc 'false | tee x.log'\n", []),
    ("\"$SHELL\" -Ec is a shell of its own: the cluster alone, no shell word", 1, H + PF +
     "    steps:\n      - run: |\n          \"$SHELL\" -Ec 'false | tee x.log'\n", []),
    ("\"$SHELL\" <(...) is a shell of its own: the substitution alone", 1, H + PF +
     "    steps:\n      - run: |\n          \"$SHELL\" <(echo 'false | tee x.log')\n", []),
    ("ssh is a shell of its own", 1, H + PF +
     "    steps:\n      - run: |\n          ssh host 'make | tee x.log'\n", []),
    ("a .sh file name is no shell word", 0, H + PF +
     "    steps:\n      - run: |\n          ./build.sh 2>&1 | tee b.log\n", []),
    ("set +$O pipefail turns it off", 1, H + PF +
     "    steps:\n      - run: |\n          O=o\n          set +$O pipefail\n          false | tee x.log\n", []),
    ("set +e alone leaves pipefail on", 0, H + PF +
     "    steps:\n      - run: |\n          set +e\n          make | tee x.log\n", []),
    ("a marker inside a heredoc does not count", 1, H + PF +
     "    steps:\n      - run: |\n          python3 - <<'PY' | tee r.txt\n"
     "          # tee-pipefail: says the heredoc\n          print(1)\n          PY\n", []),
    ("a marker after the first command does not count", 1, H + PF +
     "    steps:\n      - run: |\n          make | tee m.log\n"
     "          # tee-pipefail: too late\n          bash -c 'false | tee x.log'\n", []),
    ("a marker after the leading set run counts", 0, H +
     "    steps:\n      - run: |\n          set -euo pipefail\n"
     "          # tee-pipefail: the heredoc feeds python\n          python3 - <<'PY' | tee r.txt\n"
     "          print(1)\n          PY\n", []),
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

    # --base-baseline: an entry the base branch's copy does not have is added
    # by hand, so it fails even though the step it names is unsafe today.
    one = H + "    steps:\n      - name: A\n        run: yosys | tee a.log\n"
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
        f.write("# base\n")
    extra = 0
    for label, want, argv in (
        ("--base-baseline: an entry added by hand", 1, ["--base-baseline", f.name]),
        ("--base-baseline: no file = cannot tell", 2, ["--base-baseline", f.name + ".gone"]),
    ):
        rc, out, _ = run_case(one, [f"{WF} :: j :: A"], argv)
        extra += 1
        if rc == want:
            print(f"ok   {label} (rc {rc})")
        else:
            bad += 1
            print(f"BAD  {label}: want rc {want}, got {rc}\n     {out.strip()}")
    pathlib.Path(f.name).write_text(f"# base\n{WF} :: j :: A\n")
    rc, out, _ = run_case(one, [f"{WF} :: j :: A"], ["--base-baseline", f.name])
    extra += 1
    if rc == 0:
        print("ok   --base-baseline: the same list passes (rc 0)")
    else:
        bad += 1
        print(f"BAD  --base-baseline same list: want rc 0, got {rc}\n     {out.strip()}")
    pathlib.Path(f.name).unlink()

    # Without PyYAML nothing is read, and nothing read is not clean.
    saved = sys.modules.get("yaml")
    sys.modules["yaml"] = None  # `import yaml` now raises ImportError
    try:
        rc, out, _ = run_case(one, [f"{WF} :: j :: A"])
    finally:
        if saved is None:
            del sys.modules["yaml"]
        else:
            sys.modules["yaml"] = saved
    extra += 1
    if rc == 2:
        print("ok   no PyYAML = cannot tell (rc 2)")
    else:
        bad += 1
        print(f"BAD  no PyYAML: want rc 2, got {rc}\n     {out.strip()}")

    # An unread file's entries are not stale, and prune leaves them alone.
    rc, out, after = run_case(H + "    steps: [\n", [f"{WF} :: j :: A"], ["--prune-baseline"])
    extra += 1
    if rc == 2 and f"{WF} :: j :: A" in after:
        print("ok   --prune-baseline on an unread file = cannot tell, entry kept (rc 2)")
    else:
        bad += 1
        print(f"BAD  --prune-baseline on an unread file: rc {rc}, baseline now {after!r}")

    total = len(CASES) + 1 + extra
    print(f"\n{total - bad} of {total} cases as expected")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
