# The timing column: correcting my own correction

**Status:** facts below are read out of `.github/workflows/openxc7-build-timing.yml`
and the two constraint files at `main`. Anyone can check them; no run is needed.

I told @cavearr by mail that the benchmark's timing column needed a correction
because *"every openXC7 PASS was against nextpnr's 12 MHz default rather than a
real target"*, and repeated it in commit messages. **That is wrong**, and wrong
in two independent ways. What follows replaces it.

---

## 1. The harness has always passed an explicit frequency

```yaml
nextpnr-xilinx ... --freq ${{ steps.d.outputs.freq }} --seed 1 ...
```

`--freq` is present in `1437ed5cc`, the commit that introduced the workflow. It
was never running on nextpnr's default, so no build in this benchmark was
measured against 12 MHz. Whatever that figure described, it was not these runs.

## 2. The harness emits no timing verdict at all

The measurement record is built by hand and contains exactly this:

```json
{"design":…, "run":…, "synth_ms":…, "pnr_ms":…, "bit_ms":…, "total_ms":…, "cores":…}
```

Six wall-clock fields and a core count. **There is no pass/fail field**, and the
invocation carries `--timing-allow-fail`, so nextpnr does not fail the build on
a timing violation in the first place.

So this repository's half of the benchmark never produced a timing column. If
one appeared in a comparison table, it came from somewhere else, and that
somewhere else is what needs auditing — not this harness.

---

## 3. What *is* wrong, and is worth stating

The frequency targets and the constraint files disagree.

| design | `--freq` passed | XDC used | what the XDC constrains |
|---|---|---|---|
| blinky | **100.0** | `specs/fpga/constraints/ax7203.xdc` | `create_clock -period 5.000` = **200 MHz** |
| gf12_mul | **5.0** | `fpga/openxc7-synth/ax7203_corona.xdc` | **no `create_clock` at all** |
| gf128_mul | **5.0** | `fpga/openxc7-synth/ax7203_corona.xdc` | **no `create_clock` at all** |

Two things follow.

**The GF designs have no clock constraint in their XDC.** Their only target is
the 5 MHz on the command line. A build that "meets timing" there has met 5 MHz,
which for a combinational GF multiplier on an Artix-7 is close to unconstrained.
Any statement about those designs closing timing should say 5 MHz out loud, or
say nothing.

**For blinky the two sources differ by 2×** — the file asks for 200 MHz, the flag
for 100 MHz. Which one nextpnr honours is answerable but not currently answered
anywhere, and the benchmark has never recorded it.

---

## 4. Consequence for the wall-clock numbers

None. The seconds are the seconds: the harness times three subprocesses, and
nothing above touches that. `-abc9`, the placer, the seed and the frequency are
all pinned and stated.

What changes is what may be said *around* them. "openXC7 builds this design in
N seconds" stands. "…and meets timing" does not, unless the target is named —
and for two of the three designs the target lives only in a command-line flag
set to 5 MHz.

---

## 5. Why I got it wrong

I carried the claim forward from an earlier conversation without opening the
file. It sounded specific — a named default, a named unit — and specificity is
not evidence. The check that settled it took two greps.

The general form, for the journal: **a correction is a claim too, and inherits
no credibility from being self-critical.** Being the one who says "I was wrong
about X" does not establish that X was wrong.
