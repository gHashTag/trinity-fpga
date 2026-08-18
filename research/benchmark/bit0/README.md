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
| `harness/` | The two harness scripts (`bench-openxc7.sh`, `bench.sh` + `run-design.tcl` + `designs.tsv`) and `vivado-nonet.sh` (rootless `unshare -r -n` wrapper with a dummy interface carrying the licensed MAC — the fix for the telemetry stall). |

## Known caveats (already stated in the thread)

- litex-ddr-arty-s7 (main) fails DRC BIVRU-1 under Vivado 2026.1 as frozen
  (INTERNAL_VREF for the SSTL135 clock input); rows read "openXC7 builds it,
  Vivado refuses it". Inputs were kept frozen per the method.
- picosoc's `create_clock` is commented out in its XDC (the live clock is in a
  `.sdc` the flow does not read); its timing cells are `na` on both sides.
- Every openXC7 timing "PASS" is against nextpnr's 12 MHz default target: the
  designs' own `create_clock` on the pad net does not propagate through
  IBUF/BUFG nor to PLL outputs in nextpnr-xilinx, so no domain carries the
  intended target (issue to be filed).
