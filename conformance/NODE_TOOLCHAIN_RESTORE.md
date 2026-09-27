# Rebuilding the TRI-NET node for the AX7203 on this Mac (2026-09-27)

What it takes to rebuild the node bitstream that runs on the board, what was
broken, and what a reflash would need. **Nothing here touched the board.** No
bitstream was loaded, openocd was not started, and no JTAG device was opened.

Tags: **built** = run on this Mac on 2026-09-27. **recorded** = taken from repo
history or CI, not re-checked. **unchecked** = neither.

## Recipe

The recipe is the CI workflow `.github/workflows/ax7203-trinet-fleet.yml`:
yosys `synth_xilinx`, then nextpnr-xilinx, fasm2frames and xc7frames2bit. It is
not restated here. `fpga/openxc7-synth/build_trinet_node.py` runs the same
steps on the local openXC7 tools. The script:

- snapshots the sources, or takes them from `--rev`;
- deletes each step's outputs before running the step;
- times each step;
- writes `manifest.json` with commands, versions and hashes;
- prints the flash command as text and never runs a programmer.

    python3 fpga/openxc7-synth/build_trinet_node.py --out /tmp/trinet-node-build/node0

Keep `--out` outside the repository.

## What was broken

The prjxray-db checkout that nextpnr-xilinx carries on this Mac is f4pga
upstream `0a0adde`. nextpnr-xilinx pins the openXC7 fork at `ab1fc60`. The
upstream tree lacks the `ppips_cfg_center_*` files. On the upstream tree,
fasm2frames stops with `FasmLookupError` on 11 STARTUPE2 (`CFG_CENTER_MID`)
pips and leaves a 0-byte `.frames`. The build fails only if you notice: the
`.bit` from the last good run stays in place.

The fix leaves the repository untouched. The script exports the pinned tree
once with `git archive ab1fc60 artix7` into `~/.cache/openxc7/`, 187 MB, in
about 8 s. The chipdb is unaffected: in artix7 the two revisions differ only in
ppips and segbits.

## Build result (built)

node0, sources at HEAD. The node's three sources are unchanged since
`1bb1d97e`, the commit CI built the on-board bitstream from.

| step | wall | max RSS |
|---|---|---|
| yosys | 11.3 s | 217 MB |
| nextpnr-xilinx (heap, seed 1) | 38.9 s | 548 MB |
| fasm2frames (pinned db) | 37.3 s | 410 MB |
| xc7frames2bit | 0.4 s | 45 MB |

Resources and timing:

- 1,995 LUTs, 1,046 FFs, 0 DSP48, 1 STARTUPE2, no unrouted nets.
- Post-route Fmax of `mclk`: 56.6 MHz against the 50 MHz target.

The payload hash was identical in four builds (three by the restore agent,
one with the committed script):

    99d90a6a775b969bfefc7d03da0f66b580aa6661d41a6c69661808305b01eef5

It covers the `.bit` from the sync word `AA995566` to the end. The whole-file
sha256 differs on every run, because the header embeds the `.frames` path and
a timestamp, so do not compare whole files. A round trip through `bit2fasm`
and fasm2frames reproduced `node.frames` byte for byte. node1 builds to a
different payload, as the fleet gate needs.

## What this does not show

- **Not the bitstream on the board.** The board runs CI run 30762491794
  (recorded). Its sha256 is recorded only as the prefix `0fafd225e2`, and CI
  used an unpinned `regymm/openxc7:latest` image with yosys 0.62. Here it was
  yosys 0.67. The two netlists already differ in LC count (1,476 here, 1,455 in
  CI), so the local build is a new netlist that has never run on silicon.
- **Timing is not closed at the real clock.** The node clock is CFGMCLK:
  65.6–68.7 MHz on this board (`TERN_TC_WEAK_POINTS.md`, point 6; the older
  per-chip figures near 1.1 Mbaud are adapter artefacts, same place). The
  local Fmax is 56.6 MHz. The CI netlist
  passed on silicon anyway, but a new netlist has to be proven on the board,
  with discover plus a 640-job check, before any result is quoted from it.
- The CI artifact `trinet-fleet-node0-UNKEYED` still exists: 73,169 B, expires
  2026-10-31. Fetching it (`gh run download 30762491794 -n
  trinet-fleet-node0-UNKEYED`) would pin weak point 5, but it is a download and
  waits for the owner's OK.

## Reflash: needs the owner's explicit yes, and a sudo password

From `~/trinity-fpga`:

    sudo /opt/homebrew/bin/openocd -f fpga/openxc7-synth/ax7203_al321.cfg \
        -c "init" -c "pld load 0 <file.bit>" -c "runtest 2000" -c "shutdown"

Before running it:

- The JTAG adapter is the Digilent FT232H (0403:6014, one interface), set to
  100 kHz. The load takes about 778 s and goes to SRAM only. A power cycle
  brings back the SPI-flash default, which is not the node.
- The node key lives in SRAM: a reload wipes it, and `--setkey` has to follow.
- This Mac has no NOPASSWD rule for openocd, so `sudo -n` fails. The operator
  types the password.
- Run one openocd at a time. A leaked root openocd holds the adapter. `sudo cmd
  & kill $!` kills only the wrapper; check `ps`.
- Identify the board by the node id it reports, not by the serial port name.

The flash history of this board is in `fpga/openxc7-synth/FLASH_HISTORY.md`.

## Reload after MXDOT4, 2026-09-27 (written before the control run)

The owner said yes to returning the node («да, вариант 1, верни узел TRI-NET»)
and picked the CI artifact over the local build.

- **Bitstream.** `trinet-fleet-node0-UNKEYED` from CI run 30762491794
  (2026-08-02, success, head 1bb1d97e). It was fetched with the owner's OK,
  stored gitignored as `artifacts/bitstreams/trinet_node0_ci30762491794.bit`.
  Its sha256 is `0fafd225e2d18f73f6b605a85d0fb592f5a684dd17a7313aad76249ac89eddb4`.
  That matches the recorded prefix `0fafd225e2`, which pins weak point 5
  above. The load is logged in `board_runs/node0_ci_flash.log`.
- **Control, from `conformance/`.** This is the window-24 command from
  `TERN_TC_LAYER_RECEIPTS.md`, which is the one that passed:
  `tri fpga-run tern_tc_all_w24_reload --limit 1800 -- python3
  tern_tc_layer_ax7203.py --all --setkey --port /dev/cu.usbserial-1130 --baud
  1144744 --keys ../trinet-keys.txt --model
  /Users/playra/igla-coder-gpu/c_infer/model.bin --window 24`.
- **Harness.** The code is unchanged since b1e95f6f, the version that passed.
  The later commits changed only help text and comments.
- **PASS** means the log shows all three of these:
  - `receipts verified (tag) : 403200/403200`;
  - `rows bit-exact : 33792/33792`;
  - exit 0.
- **Anything else is a FAIL** and is recorded as it stands.
- **One attempt.** A second run is allowed only if the first fails before its
  first job (port busy, the node does not answer). Both logs are then kept.
