# 142 gate-shaped scripts, 15 invoked by CI — and the aggregator that would have run them was itself never run

The website side of this project found the same thing twice this week: a check
existed, nothing invoked it, and a later session wrote a second, weaker check for
the same problem. The research corpus was never audited the same way. It is
worse here.

| | count |
|---|---:|
| `audit_*` / `verify_*` / `witness_*` / `check_*` / `crossval_*` scripts in `research/` | **142** |
| referenced by any file in `.github/workflows/` | **15** |
| enumerated by `run_all_gates.py`, the aggregator | 89 |
| times `run_all_gates.py` itself appears in CI | **0** |

The aggregator's own docstring already argued the case, and had done for forty
passes:

> Forty passes have left 65 scripts here. Each was written to answer one question
> and then, mostly, never run again — and twice that cost something […] Both
> would have been caught the next day by running everything.

It then names the two: a regenerated pack whose specials legend was stale, and a
LUT parser that summed across a `stat` block boundary and **published a table of
deviations that did not exist**. The diagnosis, the remedy and the entry point
were all written down. Nothing called the entry point.

## What running the lot actually shows

89 scripts, 120 s limit — and the count depends on the worker count, which is
the finding two sections down:

| status | `--jobs 4` | `--jobs 2` |
|---|---:|---:|
| ran clean | 60 | **61** |
| ran, reported findings (several are inventories by design) | 17 | **18** |
| timed out | 8 | **6** |
| needs an argument, a URL or `gh` access — tools, not gates | 4 | 4 |
| **crashed** | **0** | **0** |

Same tree, same limit, two workers instead of four, and two scripts stop timing
out. The recorded baseline is the `--jobs 2` column.

No hard failure anywhere. The corpus is in better shape than "127 uninvoked
scripts" suggests — which is exactly why the gate can land now instead of after a
cleanup that would never happen.

## The gate, and why it is a ratchet

`run_all_gates.py` returns non-zero only on CRASH, and its comment explains why
that is right: these scripts use exit codes with meanings, and flattening them
into pass/fail produces a number that is mostly false. But it leaves the
regression this corpus actually suffers unguarded — **a script going from `clean`
to `findings` is a defect appearing, and the aggregator returns 0 for it.**

`gate_status_ratchet.py` records per-script status and fails when any script
degrades, on `run_all_gates`' own severity order so the two cannot drift:

    CRASH/ERROR  <  TIMEOUT  <  needs input  <  findings  <  clean

Per script, never on a total — the same shape as the website's typecheck ratchet,
for the same reason. A total lets one script's fix pay for another's regression.
The self-test carries that case by name and it must fail.

Four guards against the vacuous pass, three predicted and one learned:

* **a script that VANISHED is a failure, not a fix.** Deleting a failing gate is
  the cheapest way to make a ratchet green, so it is the first thing to forbid.
* **an enumeration shorter than 50 means the runner did not run**, and zero
  findings from a runner that did not run is not zero findings.
* **a status the severity table does not know is an error**, not a silent pass.
* **and the one that had to be learned by being caught out** — below.

## The gate's first act was to disagree with itself

Run against its own freshly-written baseline, on an unchanged tree, it reported:

```
DEGRADED: audit_header_vs_vectors.py  clean -> TIMEOUT
DEGRADED: audit_lut_table.py          clean -> TIMEOUT
improved: verify_tier_e_artifacts.py  TIMEOUT -> clean
```

Nothing had changed but how many workers were competing for cores. **A wall-clock
limit measures the machine, not the script**, and a gate whose verdict moves
without the tree moving is the broken ruler this project keeps writing rules
about — it would have been muted within a week, correctly, because it was lying.

Two fixes, both about treating the threshold as part of the measurement:

1. **The timeout lives in the baseline** and a check run reuses it. A script that
   is `TIMEOUT` at 90 s and `clean` at 300 s has not changed; comparing across two
   thresholds reports a fix or a regression that did not happen.
2. **Any disagreement with a timing-derived status on either side is re-run
   serially**, with the other workers gone. Only a script that exceeds the limit
   *alone* has regressed.

With that in place the same tree reports **zero degraded** — and turns up a
genuine improvement the noisy version had buried, `audit_rtl_parses.py`
`TIMEOUT → findings`.

**The transferable part:** a new gate's first act should be to disagree with
itself. Run it twice on an unchanged tree under *different* load. That costs one
command and it is the only evidence that the gate measures the code.

## What this does not claim

It does not claim the 17 `findings` are fine, or that the 8 timeouts are fast
enough, or that 60 `clean` scripts verify anything in particular — several are
inventories that always exit 0, and a check reporting clean with a coverage of
zero is the shape that reads as assurance and is not. `run_all_checks.py` in the
same directory already makes that distinction and deserves the same treatment.

What it claims is narrower and checkable: **from here, nothing gets quietly
worse.**

---

*Enumeration and statuses measured on this machine, 120 s limit, recorded in
`research/gate_status_baseline.json`. The CI job runs at `--jobs 2` and reads the
threshold from the baseline.*
