# tern_tc on the node cell: what is verified, and by what

2026-09-26. Companion to `tern_tc_layer_ax7203.py` and `formal/tern_tc_layer_rtl_tb.v`.

## Correction to commit 1f131fd

The first `tern_tc_layer_ax7203.py` printed `receipts authenticated : 284160/284160
under node0's key`. It never compared a tag. `pyflakes` on that file:

    'trinet_mac32_conformance_ax7203.siphash24' imported but unused
    local variable 'pre' is assigned to but never used
    undefined name 'c_dummy'

It counted `status == 0x01` as authentication, ignored the nonce echo, and
compared only per-row sums. Negative control: fed a software cell that signs with
a key the host does not hold, it printed `receipts authenticated 160/160` and
PASS.

| claim from the 2026-09-27 board run | status |
|---|---|
| 28,416 / 28,416 row dots bit-exact (wq/wo/gate/up, 6 layers) | **stands**: the y values were compared per row against the oracle |
| 320 / 320 rows, 3,200 receipts, random 320x320 (`trinet_matvec_demo.py`) | **stands**: that harness does compare tags and nonces |
| 284,160 / 284,160 receipts authenticated under node0's key | **withdrawn** until the board reruns the fixed harness |

## What the fixed harness checks

Per response: status 0x01, nonce issued by this run and answered once, node id
equal to the first answer's, SipHash-2-4 tag recomputed under the key, y equal to
that chunk's dot product. Per row: every chunk accepted, and the chunk sum equal
to the row dot computed from the model's int8 weights directly (not from the
packed wire bytes). `--self-test` shows each check failing on a cell built to
break it: wrong key, a validly signed wrong answer, a flipped tag bit, an
unissued nonce, another node id, a dropped response, an unkeyed node.

## Booked as new hardware, needs none

- **w_down** (864-wide input): 864 = 27 x 32, so 27 jobs per row on the same cell.
- **wk, wv** (320-wide input): were skipped, not blocked.
- **int8 activations** (Stage B.3): q = sum 3^k d_k with d_k in {-1,0,+1} over six
  digits covers [-364, 364], so w.q = sum 3^k (w.d_k): six ternary jobs per
  chunk, recombined on the host. `--act int8`.

All 42 ternary matrices (6,451,200 weights) therefore run on the existing
bitstream: 403,200 jobs for two ternary x-vectors, about 90 s at the 4,560 jobs/s
measured on 2026-09-27 (derived).

## RTL co-simulation (no board)

`fpga/portable/trinet_node_core.v` and `fpga/openxc7-synth/trinet_siphash24.v`,
unchanged, under Icarus Verilog 12.0, UART at bit level (BAUD_DIV=8), node
unkeyed at reset and keyed over the wire by op 0x02, exactly as on the board.
Weights: random ternary in tern_tc's exact shapes (`--synthetic`, seed 0x7C02,
59.7% nonzero), because the trained `model.bin` was not in this environment.

| run | jobs | rows bit-exact | receipts verified |
|---|---|---|---|
| layer 0, all 7 matrices (`--all --layers 0`) | 67,200 | 5,632 / 5,632 | 67,200 / 67,200 |
| layer 5 w_down, int8 activations (`--mats down --layers 5 --act int8 --n_x 1`) | 51,840 | 320 / 320 | 51,840 / 51,840 |
| layer 0 wk, no setkey frame (control) | 640 | 0 / 64 | 0 / 640, all status 0x04 |
| layer 0 wk, verified under a different key (control) | 1,280 | 0 / 128 | 0 / 1,280 |

Stream hashes (sha256): layer 0 requests `2379d8f2...5619f`, responses
`f4ca4909...5890e`; w_down int8 requests `bcf0b51f...74b95`, responses
`e6443bf1...99add`.

Reproduce:

    python3 conformance/tern_tc_layer_ax7203.py --synthetic --all --layers 0 \
        --setkey --keys test --emit-requests req.hex
    iverilog -g2012 -o tb formal/tern_tc_layer_rtl_tb.v \
        fpga/portable/trinet_node_core.v fpga/openxc7-synth/trinet_siphash24.v
    vvp -n tb +req=req.hex +resp=resp.hex          # ~20 min for 67,200 jobs
    python3 conformance/tern_tc_layer_ax7203.py --synthetic --all --layers 0 \
        --setkey --keys test --responses resp.hex

## Board rerun (the owner's machine)

    cd ~/trinity-fpga/conformance
    python3 tern_tc_layer_ax7203.py --self-test
    python3 tern_tc_layer_ax7203.py --all --setkey --port /dev/cu.usbserial-130 \
        --baud 1144744 --keys ../trinet-keys.txt --model ~/igla-coder-gpu/c_infer/model.bin

`--setkey` installs node0's key and checks the ack tag. After a power cycle it
is required; if the board already holds a key the ack is 0x03, and the receipts
then show whether it is the right one. Needs `pyserial`.

## Not claimed

A forward pass (embeddings, norms, attention, softmax and head do not run on the
board); any token rate or power figure; public verifiability (SipHash is a
shared-key MAC: it authenticates the node to the key holder and does not stop an
operator forging their own receipts).

## Board run, 2026-09-27 UTC

**Result: FAIL.** The main run lost UART framing after 19,049 jobs. Steps 4 and 5
were not run: a failed step is recorded and the run stops there. The
284,160-receipt figure stays withdrawn.

- Machine: MacBook Pro, Apple M1 Pro, macOS 26.5.2 (25F84), Python 3.14.6,
  pyserial 3.5.
- Port: `/dev/cu.usbserial-1130`, the board's CP2102N (USB `10C4:EA60`) behind a
  USB 2.0 hub (`1A40:0101`), 1,144,744 baud. The Digilent FT232H (`0403:6014`,
  one interface, `usbserial-210512180081`) is the JTAG cable and does not answer
  as a UART. openocd was not run.
- Node: `0x5452494e` (node0), no key at the start (status 0x04).
- Harness: `2b9830c5837aa47ad142a90a7279c2d8a8d401fe`.
- `model.bin`: 16,953,800 bytes, sha256
  `3102abdf35057924e077a86db4fdac726e4fe1f6574df47f39a638ba99a3ce9c`.
- Logs: `board_runs/*.log`, each checked for the key's hex (0 hits).

**1. Self-test.** `python3 tern_tc_layer_ax7203.py --self-test`, 01:41:10Z.
Expected PASS on 17 checks, 7 of them negative controls. Got 17/17 `ok` and
`self-test: PASS`, 2.23 s.

**2. Discover.** `discover_port.py` (20bf4c418, branch `trinet-fleet-truth`, run
from a temporary copy): at 01:57:33Z and 01:59:38Z `miss
/dev/cu.usbserial-210512180081`, because the UART cable was not yet enumerated;
at 02:01:31Z `HIT  /dev/cu.usbserial-1130 @ 1144744: status=0x04 (no key)`.
Then `python3 trinet_discover.py --ports /dev/cu.usbserial-1130`, 02:01:50Z.
Expected node0 `0x5452494E` at 1,144,744 baud. Got:

    /dev/cu.usbserial-1130  NODE  id 0x5452494e (node0), 1144744 baud, keyed (v2), no key yet, 64/64 clean

**3. All 42 matrices, ternary activations.** 02:10:13Z to 02:10:20Z.

    python3 tern_tc_layer_ax7203.py --all --setkey --port /dev/cu.usbserial-1130 --baud 1144744 \
        --keys ../trinet-keys.txt --model ~/igla-coder-gpu/c_infer/model.bin

Expected 403,200 jobs, `receipts verified (tag) : 403200/403200`, `rows
bit-exact : 33792/33792`, PASS. Got:

    setkey: key installed on node 0x5452494e; ack tag verifies
      [ok ] L0/wq        640/640    rows bit-exact
      [ok ] L0/wk        128/128    rows bit-exact
      [ok ] L0/wv        128/128    rows bit-exact
      [ok ] L0/wo        640/640    rows bit-exact
      [FAIL] L0/gate      362/1728   rows bit-exact
      [FAIL] L0/up          0/1728   rows bit-exact
      [FAIL] L0/down        0/640    rows bit-exact
      [... 35 lines elided: L1 to L5, 0 rows in every matrix ...]
    jobs sent               : 403200
    receipts verified (tag) : 18984/403200 under node 0x5452494e
    rejected                : {'node': 1, 'short': 1, 'missing': 384215}
    rows bit-exact          : 1898/33792  (activations: ternary)
    elapsed                 : 4.07 s (99030 jobs/s)
      ! nonce 0x00014a28: node 0x4e00014e != 0x5452494e
      ! after 19049 sent: short or unframed read (19 bytes)
    RESULT: FAIL - do not cite these matrices as verified.

- The response to job 18,984 (nonce `0x00014a28`) carried node-id bytes
  `4e 01 00 4e` instead of `4e 49 52 54`, and the next 19-byte read did not start
  with 0xA5. The harness stops at the first unframed read by design, so 384,215
  jobs have no answer.
- The 18,984 jobs answered before it each had a matching tag and the right y.
  The run as a whole is FAIL and is not cited.
- The summary's `jobs sent` and `jobs/s` count the 403,200 planned jobs, not the
  19,049 written. Derived: 18,985 answers in 4.07 s, about 4,660 jobs/s, close to
  the 4,560 jobs/s of the earlier run. Reporting only; the harness was not
  changed.
- No retry: the failure came after the first job.

**4. `trinet_matvec_demo.py`.** Not run.

**5. `--act int8`, layer 5 w_down.** Not run.

Open, none of it tested: why the framing slipped. Candidates: the CP2102N's
baud divider at 1,144,744 against the node's (earlier board runs went through a
CP2102N seen as `usbserial-130` on another Mac); the USB 2.0 hub (the CP2102N
did not enumerate on the first hub port tried); 64 jobs in flight
(`--window`) against the node's receive buffer.
