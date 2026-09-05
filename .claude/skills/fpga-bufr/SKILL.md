---
name: fpga-bufr
description: Regional clock buffers (BUFR/BUFIO) on openXC7 — how to make one actually clock fabric, the two placer fixes it needs, and how to prove a candidate segbits row on silicon with a one-bit A/B. Use for BUFR/BUFIO work, prjxray segbits verification, or any "is this bit real?" question on an AX7203.
---

# BUFR / BUFIO on openXC7

Written 2026-09-01 after confirming `HCLK_L.ENABLE_BUFFER.HCLK_CK_BUFRCLK2 =
00_31` on an AX7203. Everything here was measured; where it was not, it says so.

## The one-bit A/B — the method that settles "is this bit real?"

This is the transferable part. It works for any candidate segbits row.

1. Build a design that **asserts the feature**. Check the FASM, not your hopes.
2. Produce the control by deleting **that one FASM line** — not by editing the
   database, not by changing the design:
   `grep -v 'ENABLE_BUFFER.HCLK_CK_BUFRCLK' ax.fasm > ax_ctrl.fasm`
3. Assemble both against the **same** database. Everything else is then
   identical by construction.
4. **Diff the frames before flashing.** If they are byte-identical, the row sets
   no bits and flashing proves nothing — that is the `I2IOCLK` outcome, where a
   predicted bit turned out to be the all-zero default. Confirm exactly which
   bit differs:
   `frame 0x00401C00, word 50, bit 31` ← this is what `00_31` means in practice.
5. Flash both. **Read the LED only after the log shows `exit=`.** A device held
   in configuration is dark — identical to the failure you are testing for. This
   cost two false readings in one evening; see `observe-only-a-ready-apparatus`.
6. Interpret: differs → the bit is load-bearing. Same → default-on, row unproven.

Cost: ~13 min per flash on an xc7a200t (778 s for 9.73 MB), so ~30 min per bit.

## Making a BUFR actually clock something

**Sink the clock into CLB fabric, not into the IOI column.** Every probe in
nextpnr-xilinx#149 before this ended in an ISERDESE2/ODDR, which keeps the
regional clock inside the IOI column, so nothing in `HCLK_L` is ever asserted. A
plain counter forces the clock out to the leaves:

```verilog
IBUFDS ... (.O(clk_ibuf));
BUFR #(.BUFR_DIVIDE("BYPASS"), .SIM_DEVICE("7SERIES"))
     bufr_i (.I(clk_ibuf), .CE(1'b1), .CLR(1'b0), .O(clk_bufr));
reg [27:0] cnt = 0;
always @(posedge clk_bufr) cnt <= cnt + 1;   // fabric: this is the point
assign led = cnt[27];
```

Probes live in `/Users/playom/t27/build/fpga/openxc7/probe/`.

## Two placer fixes, both required

Sent as openXC7/nextpnr-xilinx#170 and #171; 6/6 CI green. They **conflict
textually** in `pack_clocking_xc7.cc` — adjacent hunks — so the second to merge
needs a rebase.

1. **#170** — `constrain_bufios()` tested `id_BUFIO_BUFIO` only. A pad-fed BUFR
   has the same dedicated-site constraint. Symptom without it:
   `Failed to route arc 0 of net 'clk_ibuf'`. Invisible on xc7a35t (few sites,
   the placer guesses right), fatal on xc7a200t.
2. **#171** — nothing kept the clocked flops inside the buffer's clock region;
   the placer does not cost global nets, so they follow their data pin. Symptom:
   `Failed to route arc 0 of net 'clk_bufr'`. Fix: BFS from the buffer's `O`
   wire, bound-box what it reaches, `createRectangularRegion` +
   `constrainCellToRegion` on each sink's cluster root.
   **Collect only bel pins named `CLK`.** Counting every pin the walk touches
   returns the whole die (`x8..264 y26..234`) — a constraint that constrains
   nothing. With the filter: `x141..263 y103..157`.

Neither works alone: on the #171-only branch the divide probes still failed at
`BUFR_X1Y11` because the BUFR had no site and the region code never fired.

## Emitter: `fasm.cc`

Two `boost::contains(s, "BUFHCLK")` filters (~2087, ~2120 on `a0410d5`; grep,
line numbers drift) both drop `BUFRCLK`. **Widening the `if` alone aborts
nextpnr** — `s.find("BUFHCLK")` is npos on a BUFRCLK wire and `substr(npos)`
throws `std::out_of_range` (measured: exit 134). Reuse the found offset for both
the test and the substr. Not yet submitted: the db rows must land first.

## AX7203 board facts that cost hours

- Only clock-capable pad: **`R4`/`T4`** = `IO_L13P/N_T2_MRCC_34`, 200 MHz
  DIFF_SSTL15, `IOB_X1Y124`, **right half**. `U22` (50 MHz) is
  `IO_L3P_T0_DQS_PUDC_B_14` — **not** clock-capable.
- Every observable is **left half**: LEDs `B13/C13/D14/D15` bank 16
  (`IOB_X0Y233..238`), UART `N15` bank 14. A pad-fed BUFR cannot reach them
  without #171.
- `T6` is `rst_n`, a button **input** — do not drive it.
- `fpga/constraints/uart_bridge_j2.xdc` is a **QMTech XC7A100T-1FGG676C** file
  despite CLAUDE.md calling it canonical for the AX7203. Its `T23` does not
  exist on fbg484 (the pin table stops at T21). Check the header before trusting
  any xdc in this repo.
- Identify the board by IDCODE, not by USB port name: `0x13636093` = xc7a200t.

## Toolchain traps

- `build/fpga/openxc7/nextpnr-xilinx` and `.../prjxray` have **no `.git` of
  their own** — `git log` there answers from the parent t27 repo, so a May tree
  looks like today's HEAD, and `git submodule update` walks up and touches t27.
  Ask the artifact: `nextpnr-xilinx --version`,
  `grep BUFR_BUFR pack_clocking_xc7.cc`.
- nextpnr on Apple clang: `-DUSE_OPENMP=OFF` (no `-fopenmp`).
- prjxray: `-DCMAKE_POLICY_VERSION_MINIMUM=3.5` (gflags declares too old a
  minimum for CMake 4).
- Zig 0.16 is not a rename away: `Args` arrives as a parameter of `main`
  (`pub fn main(init: std.process.Minimal) !void`) and I/O entry points take an
  `Io`. `std.fs.cwd()` -> `std.Io.Dir.cwd()` and `GeneralPurposeAllocator` ->
  `DebugAllocator` are renames, but `std.process.argsAlloc` has no drop-in, so
  the migration is an Io-threading redesign rather than a sweep.

## BUFR_DIVIDE works on silicon — and how the probe has to be built

Two points measured on an AX7203, 200 MHz pad, 28-bit fabric counter:

| BUFR_DIVIDE | expected period | observed |
|---|---|---|
| BYPASS | 1.3 s | ~1.3 s |
| 2 | 2.7 s | noticeably faster than D8, ~4x |
| 8 | 10.7 s | ~5 s lit, i.e. ~10.7 s |

The ratio follows the parameter. Two traps cost a full flash cycle each:

1. **A divided BUFR needs its CLR pulsed** after configuration; BYPASS does not.
   Tie `CLR` low and the counter never starts — indistinguishable from "the
   divide bits do nothing". Sequence CLR from a counter on a BUFG off the same
   pad, so the reset generator does not depend on the BUFR under test.
2. **Check the flashed bitstream contains the feature under test.** My first
   divide run was built on a branch without the `fasm.cc` emitter patch, so it
   carried zero `ENABLE_BUFFER.HCLK_CK_BUFRCLK` lines: the clock never reached
   fabric and the frozen LED said nothing about the divide. Grep the FASM for
   all three of enable, divide, and CLR before flashing anything.

## Still open

- `BUFRCLK0` (`00_23`), `BUFRCLK1` (`01_23`), `BUFRCLK3` (`01_31`) — pattern
  only. The index follows the pad's BUFR site and this board has one oscillator.
- **MMCM-fed BUFR routes but cannot be assembled** — issue #172. Missing:
  `HCLK_CMT.HCLK_CMT_MUX_PHSR_PERFCLK0.*` and
  `CMT_TOP_R_LOWER_B.CMT_R_LOWER_B_CLK_PERF0.*`. Not a `tag_groups.txt` problem:
  `fixup_and_group.py` runs **after** `XRAY_SEGMATCH` on an input `.rdb`, so a
  missing group cannot cause a missing row. Zero rows means no specimen ever
  exercised the pip — the 047/`I2IOCLK` class, needing Vivado specimens.

Related: `fpga-synth` skill, memories `openxc7-bufr-gap`,
`observe-only-a-ready-apparatus`, `ax7203-fpga-truths`.

## House style for patches to openXC7/nextpnr-xilinx

hansfbaier asked for this directly on #171 after merging both PRs, and refactored
my code to demonstrate it (commit `bd9c74c5`). **Extract every `if` condition into
a named `const bool` phrased as a POSITIVE assertion, then branch on it.**

```cpp
// not this
if (clk == nullptr || clk->users.empty())        return;
if (bp.pin != id_CLK)                            continue;

// this
const bool clk_has_sinks = (clk != nullptr && !clk->users.empty());
if (!clk_has_sinks)                              return;

const bool pin_is_a_clock = (bp.pin == id_CLK);
if (!pin_is_a_clock)                             continue;
```

The name states what is TRUE; the branch negates it where needed. Applies to every
guard clause, including one-liners. Write new patches this way rather than waiting
for the maintainer to refactor them.

## Both PRs are MERGED

- #170 `xilinx: constrain a pad-fed BUFR to its dedicated site` — merged
  2026-09-01T21:53Z by hansfbaier, commit `d6fc91f0d`
- #171 `xilinx: keep a regional buffer's sinks inside the region` — merged
  2026-09-01T23:24Z by hansfbaier, commit `a9edfd6f6`

cavearr's 23-design A/B (37 test×part rows, 36 byte-identical FASM) is on #170 and
hansfbaier answered "Thanks!".

**Watch the right signal.** For twenty iterations I polled `gh api .../issues/149/comments`
and reported "no reply" while both PRs sat merged. A comment list on an ISSUE does
not change when a PR merges, and a maintainer's request addressed to me lived on
the PR, not the issue. Poll `gh pr view <n> --json state,comments,reviewDecision,
statusCheckRollup` for anything you have open — comments alone still misses a review
verdict or a CI status flip with no new comment attached, the same blind spot one
level down. Every sweep since 2026-09-04 checks issue comments AND `gh pr view` for
every tracked PR (#120, #171, #877) in the same pass — habit, not automation; there
is no coded poller, this is a checklist to run by hand each time.

### One caveat the rule does not state

Two of the nine extractions in `bd9c74c5` sit **inside loops** and read a variable
the loop mutates:

```cpp
for (auto &bp : ...) {
    const bool first_clock_pin = !any;   // `any` is set to true below
    if (first_clock_pin) { ... any = true; }
}
```

That is correct **because the const is declared next to its `if`**, so it is
re-evaluated every iteration. Hoisting these out of the loop — the natural thing to
do when tidying "duplicated" declarations — freezes a value that used to change,
and the loop then takes the same branch forever. The same applies to
`already_visited` in the BFS.

So: extract the condition, but keep the `const bool` adjacent to the branch it
feeds. Never lift one out of the loop it belongs to.

Verified equivalence of all nine extractions in that commit, including the
short-circuit in `clk_has_sinks` — `(clk != nullptr && !clk->users.empty())` still
stops before dereferencing a null `clk`, which the original `||` form also did.
