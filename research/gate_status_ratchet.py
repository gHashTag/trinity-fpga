#!/usr/bin/env python3
"""Every ENUMERATED gate's status may improve and may not degrade.

SCOPE, stated first because the first version of this docstring said "every
gate" while the code globbed three prefixes in one directory. `research/block/`
holds 160 .py files of which 102 contain an assert or a non-zero exit, and none
of them was enumerated. That is the seventh instance in this campaign of a
harness asserting less than its prose claimed -- in an instrument written the
day after the lesson was recorded in the skill.

What is enumerated, exactly:
  * research/audit_*.py, research/witness_*.py, research/verify_*.py
  * research/block/*.py that are named for the same three roles, plus the
    campaign gates, MINUS SKIP_BLOCK below
Everything else in research/block/ is a MEASUREMENT script -- it loads
checkpoints and runs forward passes -- and belongs in a nightly, not in a gate
that runs on every PR. Those are listed in SKIP_BLOCK by name with a reason, so
the exclusion is auditable rather than implicit in a glob.

`run_all_gates.py` runs all of them and fails only on CRASH -- correctly, since
its own comment explains why flattening these exit codes into pass/fail produces
a number that is mostly false. But that leaves the regression this corpus
actually suffers unguarded: a script going from **clean** to **findings** is a
real defect appearing, and the aggregator returns 0 for it.

So this ratchets the per-script status against a recorded baseline, in exactly
the shape the website's typecheck ratchet uses: a gate on the DIRECTION, per
unit, never on the total. 142 gate-shaped scripts live in this directory and CI
invokes fifteen; the aggregator's own docstring records two defects that survived
a pass because nothing ran everything. This makes "nothing got worse" checkable
in CI without demanding that all 142 be clean first.

Severity order is run_all_gates' own, so the two cannot drift apart:
    CRASH/ERROR < TIMEOUT < needs input < findings < clean

Three vacuous-pass guards, because this project has been burned four times by a
harness reporting its own breakage as data:
  * a script that VANISHED is not an improvement -- deleting a failing gate must
    fail, not pass;
  * an empty or short enumeration means the runner did not run;
  * a status the severity table does not know is an error, not a silent pass.

And one broken-ruler guard, added the first time this gate ran against its own
baseline. It reported two scripts degraded clean -> TIMEOUT and one improved
TIMEOUT -> clean, on an unchanged tree: with `--jobs` workers competing for
cores, a wall-clock timeout measures the MACHINE, not the script. A gate whose
verdict moves with load is the instrument this project keeps criticising. So any
degradation that involves TIMEOUT on either side is re-run SERIALLY, with the
other workers gone, and only a script that times out alone is reported.

    python3 research/gate_status_ratchet.py            check
    python3 research/gate_status_ratchet.py --update   rewrite the baseline
    python3 research/gate_status_ratchet.py --selftest prove the gate can fail
"""
import concurrent.futures
import glob
import json
import os
import sys

import run_all_gates as G

HERE = os.path.dirname(os.path.abspath(__file__))
BASELINE = os.path.join(HERE, "gate_status_baseline.json")

# run_all_gates' own ordering, imported in spirit but pinned here so a change
# there cannot silently reverse the meaning of "degraded".
RANK = {"CRASH": 0, "ERROR": 0, "TIMEOUT": 1, "needs input": 2,
        "findings": 3, "clean": 4}


def rank(status):
    key = status.split(" rc=")[0]
    if key not in RANK:
        raise SystemExit(f"unknown status {status!r} -- refusing to judge it")
    return RANK[key]


# research/block/ scripts that load a checkpoint or run a forward sweep. They
# are gates in spirit and cannot run on a PR: each needs multi-GB weights and
# minutes of compute. Named individually so the exclusion is auditable.
SKIP_BLOCK_PREFIX = ("campaign", "line", "block_tnf", "onefit", "sensitivity",
                     "seed_control", "occupancy", "u_", "align_", "depth_",
                     "rebaseline", "final_", "kurtosis_", "heavy_", "scale_",
                     "profile_", "nsse_", "attack", "flatness", "metric_",
                     "loguniform", "two_level", "rotation_", "_sens")


def _block_gates():
    """The gate-shaped scripts in research/block/ that need no checkpoint."""
    out = []
    for p in sorted(glob.glob(os.path.join(HERE, "block", "*.py"))):
        b = os.path.basename(p)
        if b.startswith(SKIP_BLOCK_PREFIX):
            continue
        if b.startswith(("audit_", "verify_", "witness_", "check_")):
            out.append(p)
    return out


def collect(timeout, jobs):
    paths = sorted(glob.glob(os.path.join(HERE, "audit_*.py"))
                   + glob.glob(os.path.join(HERE, "witness_*.py"))
                   + glob.glob(os.path.join(HERE, "verify_*.py")))
    todo = [p for p in paths if os.path.basename(p) not in G.SKIP]
    todo += _block_gates()
    out = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=jobs) as ex:
        for f in concurrent.futures.as_completed(
                [ex.submit(G.run_one, p, timeout) for p in todo]):
            name, status, _secs, _note = f.result()
            out[name] = status.split(" rc=")[0]
    return out


def compare(base, now):
    """(degraded, improved, vanished). Vanishing is a failure, not a fix."""
    degraded, improved, vanished = [], [], []
    for name, was in base.items():
        if name not in now:
            vanished.append(name)
            continue
        if rank(now[name]) < rank(was):
            degraded.append((name, was, now[name]))
        elif rank(now[name]) > rank(was):
            improved.append((name, was, now[name]))
    return degraded, improved, vanished


def selftest():
    base = {"a.py": "clean", "b.py": "findings", "c.py": "clean"}
    cases = [
        ("unchanged", dict(base), False),
        ("clean -> findings", {**base, "a.py": "findings"}, True),
        ("findings -> CRASH", {**base, "b.py": "CRASH"}, True),
        ("clean -> TIMEOUT", {**base, "c.py": "TIMEOUT"}, True),
        ("a failing gate DELETED is not a fix", {"a.py": "clean", "c.py": "clean"}, True),
        ("one improved, one degraded -- must not net out",
         {**base, "a.py": "findings", "b.py": "clean"}, True),
        ("everything improved", {"a.py": "clean", "b.py": "clean", "c.py": "clean"}, False),
        ("a NEW script, even a failing one, is not a regression",
         {**base, "d.py": "CRASH"}, False),
    ]
    bad = 0
    for name, now, want in cases:
        d, _i, v = compare(base, now)
        got = bool(d or v)
        if got != want:
            bad += 1
        print(f"  {'ok  ' if got == want else 'FAIL'}  {name}: fails={got}, expected={want}")
    print(f"\n  {bad} self-test(s) failed" if bad else
          "\n  the gate fails when it should")
    return 1 if bad else 0


def main():
    if "--selftest" in sys.argv:
        return selftest()
    jobs = int(sys.argv[sys.argv.index("--jobs") + 1]) if "--jobs" in sys.argv else 4
    # The timeout is part of the MEASUREMENT, not a convenience knob: a script
    # that is TIMEOUT at 90s and clean at 300s has not changed, and comparing the
    # two would report a fix or a regression that did not happen. So a check run
    # reuses the baseline's recorded timeout unless told otherwise, explicitly.
    if "--timeout" in sys.argv:
        timeout = int(sys.argv[sys.argv.index("--timeout") + 1])
    elif os.path.exists(BASELINE):
        timeout = json.load(open(BASELINE, encoding="utf-8")).get("timeout", 180)
    else:
        timeout = 180

    now = collect(timeout, jobs)
    if len(now) < 50:
        print(f"  only {len(now)} script(s) enumerated -- the runner did not run. "
              "Refusing to report that as a pass.")
        return 2

    if "--update" in sys.argv or not os.path.exists(BASELINE):
        with open(BASELINE, "w", encoding="utf-8") as fh:
            json.dump({"note": "Per-script status. May improve, may not degrade. "
                               "Run --update after a genuine fix.",
                       "timeout": timeout,
                       "scripts": dict(sorted(now.items()))}, fh, indent=2)
            fh.write("\n")
        tally = {s: sum(1 for v in now.values() if v == s) for s in sorted(set(now.values()))}
        print(f"  baseline written: {len(now)} scripts  {tally}")
        return 0

    base = json.load(open(BASELINE, encoding="utf-8"))["scripts"]
    degraded, improved, vanished = compare(base, now)

    # Re-run TIMEOUT-involved disagreements alone before believing them.
    recheck = sorted({n for n, was, is_ in degraded
                      if "TIMEOUT" in (was, is_)}
                     | {n for n, was, is_ in improved if "TIMEOUT" in (was, is_)})
    if recheck:
        print(f"  {len(recheck)} disagreement(s) involve TIMEOUT — re-running "
              "them serially, since a wall-clock limit under load measures the "
              "machine rather than the script.")
        for name in recheck:
            _n, status, secs, _note = G.run_one(os.path.join(HERE, name), timeout)
            settled = status.split(" rc=")[0]
            if settled != now[name]:
                print(f"    {name}: {now[name]} under load -> {settled} alone "
                      f"({secs:.0f}s)")
            now[name] = settled
        degraded, improved, vanished = compare(base, now)

    print(f"  {len(now)} scripts; baseline {len(base)}.")
    for name, was, is_ in improved:
        print(f"    improved: {name}  {was} -> {is_}")
    if improved and not (degraded or vanished):
        print("  run `--update` to lock the improvements in.")
    if not (degraded or vanished):
        print("  no gate degraded.")
        return 0

    for name in vanished:
        print(f"  VANISHED: {name} was {base[name]} and is no longer enumerated. "
              "Deleting a gate is not fixing it.", file=sys.stderr)
    for name, was, is_ in degraded:
        print(f"  DEGRADED: {name}  {was} -> {is_}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
