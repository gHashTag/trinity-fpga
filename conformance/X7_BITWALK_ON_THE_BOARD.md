# A bitstream written by the t27 bitwalk, run on the AX7203

2026-10-02 19:50–19:56 UTC (2026-10-03 local). One attempt per run, no retries.

## What was built

`tri fpga-build --out /tmp/x7board/node0`: trinet node 0 (`trinet_node_v2_ax7203`,
`USE_DNA=0`, `FALLBACK_NODE_ID=32'h5452494E`, `BAUD_DIV_P=60`), yosys 0.67 →
nextpnr-xilinx 0.9.2-107-g7037c948 (heap placer, seed 1, mclk Fmax 25.16 MHz) →
prjxray `fasm2frames.py` → `xc7frames2bit`, db `prjxray-db-ab1fc60/artix7`,
part `xc7a200tfbg484-2`. The FASM has 121,587 lines; the frames file 20,230
frames.

## The back half, ours against openXC7's, on that FASM

`bitwalk` is the Rust driver generated from the gHashTag/t27 `specs/xilinx7`
specs (`packets.t27`, `frames.t27`, `far.t27`; worktree commit `1fc957483`). Its
FASM input is a digest of the same db rendered by prjxray's own `Database`
(`x7.py fasm_digest`).

| Step | openXC7 | bitwalk | Output |
|---|---|---|---|
| FASM → frames | `fasm2frames.py` 71.45 s in the build, 68.38 s re-timed (41.2 s user) | 0.95 / 0.81 / 0.79 s (0.5 s user) | byte-identical, 20,230 frames, 371,806 bits |
| frames → .bit | `xc7frames2bit` 0.36 s in the build, 0.41 s re-timed | 0.47 / 0.52 / 0.47 s | byte-identical, 9,730,774 bytes |

sha256 of both .bit files: `68249475b57e623f05564e3d839cfb0c7e7b3e21fe89a014953f12fdd53f95b3`.
The .bit header strings (source, date, time) were passed to `bitwalk --write`
from openXC7's file; everything after the header is bitwalk's own.

The host was loaded the whole time (1-minute load 40–80 on 8 cpus), and every
timing above shares that load. FASM → frames is about 85× faster wall-clock on
this design and about 80× in user time. frames → .bit is a tie.

## On the board

| Run | Log | Result |
|---|---|---|
| SRAM load of bitwalk's .bit, `openFPGALoader -c digilent_hs2 --write-sram` (no flash) | `board_runs/x7-bitwalk-node0-sram-load.log` | `done 1`, 16.73 s |
| UART discover | — | `/dev/cu.usbserial-110 @ 1144744`, status 0x04 (no key), CP2102N direct |
| All 42 ternary matrices, `--all --setkey` | `board_runs/x7-bitwalk-node0-tern-all.log` | `receipts verified (tag) : 403200/403200 under node 0x5452494e`, rows bit-exact 33792/33792, 87.30 s, 4618 answers/s |
| Layer 5 w_down, int8 activations | `board_runs/x7-bitwalk-node0-down5-int8.log` | `receipts verified (tag) : 51840/51840 under node 0x5452494e`, rows bit-exact 320/320, 11.06 s |

`tri fpga-keycheck`: 3 files, 0 key hits, none of 1 MB or more.

## What this does and does not show

- It shows that a .bit whose frames and packets came from the t27 specs
  configures an XC7A200T and runs a real design bit-exact. Because the file is
  byte-identical to openXC7's, it shows nothing the openXC7 file would not; the
  claim is equivalence on this design, not a better bitstream.
- The front half (yosys, nextpnr-xilinx) is openXC7's, unchanged.
- One design, one part, one board, one load.
