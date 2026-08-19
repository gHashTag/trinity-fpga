# openXC7 vs Vivado — same-machine benchmark, bit0 (2026-08-15/16)

Raw artefacts of the same-machine half of the openXC7-vs-Vivado benchmark
(method and freeze as agreed in the thread with @gHashTag; the CI half lives
in `gHashTag/trinity-fpga`). Every number quoted in the write-up for the
bit0 rows is derivable from these files.

Machine: bit0 — Intel i5-13500 (20 threads), 125 GB RAM, bare metal, Ubuntu,
egress-filtered network (see the Flexera note below). Per-run machine
snapshots (`*-machine.txt`) accompany every CSV.

## Layout

| path | what |
|---|---|
| `openxc7/bench-openxc7-20260816-000221.csv` | **The clean openXC7 campaign** (N=5 per design; medians in the write-up). Columns: per-stage seconds (json = yosys, fasm = nextpnr, bit = fasm2frames+xc7frames2bit), total, and the toolchain revisions **stamped from the built tree at run time** (nextpnr `05aaa06b`, prjxray-db `d17fea2`, yosys `0.62-7326bb7d6`). |
| `openxc7/REVISIONS.txt` | Provisioning record of the frozen environment (regymm/openxc7 image by digest, in-image rebuild of nextpnr at the frozen revision). Informational — the harness re-reads revisions from the tree and does not trust this file. |
| `openxc7/timing-context/max-frequency-lines.txt` | Every `Max frequency` and `Annotating ports…` line from every openXC7 stage log, with the log line number. **Read the LAST block per log**: since nextpnr-xilinx #139 (inside the freeze) each log carries the placer's pre-route ESTIMATE mid-flow and the routed analysis at the end. Minimum-over-all-lines mixes the two. |
| `vivado/bench-20260815-162240.csv`, `vivado/bench-20260815-162613.csv` | **The clean Vivado 2026.1 campaign (v2)**, run hermetically (see `harness/vivado-nonet.sh`). Per-stage seconds (synth/place/route/bitgen), total, wns/tns/timing_met from `report_timing_summary`. Two files = the campaign was run in two consecutive batches; both are v2. |
| `vivado/contaminated-v1/` | The first Vivado campaign, ARCHIVED AS EVIDENCE, never as rows: write_bitstream stalled 4–7 nondeterministic minutes on Flexera RUI telemetry making raw `connect()` calls that ignore the proxy env (`NOTE.md` has the diagnosis). |
| `harness/` | The two harness scripts (`bench-openxc7.sh`, `bench.sh` + `run-design.tcl` + `designs.tsv`) and `vivado-nonet.sh` (rootless `unshare -r -n` wrapper with a dummy interface carrying the licensed MAC — the fix for the telemetry stall). **Archived evidence, not tooling** — see `harness/NOTE.md` before touching or copying anything in there. |

## Known caveats (already stated in the thread)

- litex-ddr-arty-s7 (main) fails DRC BIVRU-1 under Vivado 2026.1 as frozen
  (INTERNAL_VREF for the SSTL135 clock input); rows read "openXC7 builds it,
  Vivado refuses it". Inputs were kept frozen per the method.
- picosoc's `create_clock` is commented out in its XDC (the live clock is in a
  `.sdc` the flow does not read); its timing cells are `na` on both sides.
- Every openXC7 timing "PASS" is against nextpnr's 12 MHz default target: the
  designs' own `create_clock` on the pad net does not propagate through
  IBUF/BUFG nor to PLL outputs in nextpnr-xilinx, so no domain carries the
  intended target. Filed as
  [openXC7/nextpnr-xilinx#155](https://github.com/openXC7/nextpnr-xilinx/issues/155).
- **Ten of the twenty openXC7 rows timed a bitstream that does not run.** Both
  `litex-ddr-arty-s7` designs are VexRiscv SoCs, five runs each, and the frozen
  toolchain (`05aaa06bc`) predates `f1c771349` — the fix in
  [openXC7/nextpnr-xilinx#150](https://github.com/openXC7/nextpnr-xilinx/pull/150),
  where the console is dead at 16 MHz on silicon. The seconds are unaffected;
  the harness times three subprocesses and none of this touches that. What is
  affected is any sentence placed next to them: "openXC7 built this in N
  seconds" stands, "and it met timing" does not, and for these two designs "and
  it ran" does not either.

## Would a re-run on a post-#150 toolchain change these numbers?

**No — and the diff says so without needing a campaign.** `f1c771349` touches
exactly one file, `xilinx/fasm.cc`, `+49/-1`, entirely inside
`write_bram_width`. That function runs in the FASM backend, downstream of
everything the harness times:

| stage the harness times | what #150 touches | effect |
|---|---|---|
| `synth_ms` (yosys) | nothing | none |
| `pnr_ms` (nextpnr place + route + FASM write) | two integer comparisons per BRAM width parameter, during FASM write | unmeasurable |
| `bit_ms` (`fasm2frames` + `xc7frames2bit`) | sets additional bits in frames that were already emitted; frame count is fixed by the part | none |

So the wall-clock rows stand as measured, and the headline ratio stands with
them. The fix changes *what the bitstream contains*, not *how long it took to
produce* — it emits `READ_WIDTH_B_18` / `WRITE_WIDTH_A_18` for SDP ports whose
opposite side yosys leaves at 0, which is why the VexRiscv ROM returned garbage
in the upper half of every read while the timing was fine.

**What a re-run would legitimately establish is functional, not temporal:** that
the design now boots. That is a silicon test on an Arty-S7, not a timing
campaign — and it belongs with whoever holds that board.

Two things make a timing re-run on other hardware worthless regardless: the
campaign is *same-machine* by construction, and Vivado does not run on Apple
Silicon at all, so the comparison half cannot be reproduced off bit0.

## Reading the frequency figures

Take them from `openxc7/timing-context/max-frequency-lines.txt`, and cite the
log line. The routed values for the two SoC designs are:

| design | line | clock | routed |
|---|---|---|---|
| `litex-ddr-arty-s7` | 1515 | `main_crg_clkout_buf0` | **68.73 MHz** |
| `litex-ddr-arty-s7-deephier` | 1512 | `sys_clk` | **69.72 MHz** |

Identical across all five runs of each — the seed is pinned, so there is no
run-to-run spread to report.

The placement estimates at lines 373 and 381 are 65.52 and 74.21. Note the
direction: routing came out **above** the estimate on one design and **below**
it on the other, so a figure that mixes the two is wrong in an unpredictable
direction rather than merely imprecise. A published "65.5–69.7 MHz" range did
exactly that — floor from an estimate, ceiling from a routed value — and is
corrected on #150.
