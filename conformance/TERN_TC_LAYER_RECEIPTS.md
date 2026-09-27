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
unissued nonce, another node id, a dropped response, an unkeyed node, and 16
bytes lost from the middle of the answer stream (the 2026-09-27 board failure,
below).

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
    python3 tern_tc_layer_ax7203.py --all --setkey --port /dev/cu.usbserial-1130 \
        --baud 1144744 --keys ../trinet-keys.txt --model ~/igla-coder-gpu/c_infer/model.bin

The port name depends on the Mac and the hub: `usbserial-130` on the Air,
`usbserial-1130` on the M1 Pro on 2026-09-27. `trinet_discover.py` finds it.
`--setkey` installs node0's key and checks the ack tag. After a power cycle it
is required; if the board already holds a key the ack is 0x03, and the receipts
then show whether it is the right one. Needs `pyserial`.

## Not claimed

A forward pass (embeddings, norms, attention, softmax and head do not run on the
board); any token rate or power figure; public verifiability (SipHash is a
shared-key MAC: it authenticates the node to the key holder and does not stop an
operator forging their own receipts).

## Board run, 2026-09-27 UTC

**Result: FAIL for the full run.** The main run lost UART framing after 19,049
jobs. Steps 4 and 5 were held back at first (a failed step is recorded and the run
stops there), then run once each at the owner's request: step 4 passed, step 5
lost framing the same way after 9,951 jobs. Step 5 rerun with `--window 8`
passed: 51,840/51,840 receipts, 320/320 rows. The full run has not been repeated
at that window, and the 284,160-receipt figure stays withdrawn.

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

**4. `trinet_matvec_demo.py`.** Not run with steps 1 to 3. Run once at the
owner's request, 02:22:04Z to 02:22:05Z. There was no power cycle after step 3,
so the node still held the key that step 3 installed.

    python3 trinet_matvec_demo.py --port /dev/cu.usbserial-1130 --baud 1144744 --keys ../trinet-keys.txt

Expected 320/320. Got:

    jobs (32-wide dots)   : 3200
    receipts authenticated: 3200/3200 under node0's key
    rows bit-exact        : 320/320
    elapsed               : 0.79 s (4032 jobs/s)
    RESULT: the datapath a model layer needs is verified on silicon.

PASS. This harness checks status, nonce, y and the tag of every job.

**5. `--act int8`, layer 5 w_down.** Not run with steps 1 to 3. Run once at the
owner's request, 02:22:27Z to 02:22:29Z.

    python3 tern_tc_layer_ax7203.py --mats down --layers 5 --act int8 --n_x 1 --setkey \
        --port /dev/cu.usbserial-1130 --baud 1144744 --keys ../trinet-keys.txt \
        --model ~/igla-coder-gpu/c_infer/model.bin

Expected 51,840 jobs, `receipts verified (tag) : 51840/51840`, `rows bit-exact :
320/320`, PASS. Got:

    model.bin: 1 matrices, 320 rows, 276480 ternary weights (61.8% nonzero)
    jobs: 51840 (32-trit chunks x 1 x-vectors x 6 digit planes)
    setkey: node 0x5452494e already holds a key (0x03); receipts below will show whether it is ours
      [FAIL] L5/down       61/320    rows bit-exact
    jobs sent               : 51840
    receipts verified (tag) : 9886/51840 under node 0x5452494e
    rejected                : {'fabricated': 1, 'short': 1, 'missing': 41954}
    rows bit-exact          : 61/320  (activations: int8)
    elapsed                 : 2.08 s (24872 jobs/s)
      ! nonce 0x5401269e was never issued
      ! after 9951 sent: short or unframed read (19 bytes)
    RESULT: FAIL - do not cite these matrices as verified.

- Job 9,886 (nonce `0x0001269e`, bytes `9e 26 01 00`) was answered with nonce
  bytes `9e 26 01 54`. The next 19-byte read did not start with 0xA5, and the
  harness stopped. This matches step 3: one frame with a wrong byte, then no
  frame.
- The 9,886 jobs answered before that each had a matching tag and the right y,
  so node0 still signs with the key that step 3 installed. 61 rows are complete;
  each row is 162 jobs (27 chunks x 6 digit planes).
- `jobs sent` and `jobs/s` count planned jobs again. Derived: 9,887 answers in
  2.08 s, about 4,750 jobs/s.
- No retry: the failure came after the first job.

**5a. Step 5 with `--window 8`.** Run once at the owner's request, 02:29:44Z to
02:29:56Z, to probe the window candidate below. Same port, same hub, same baud,
no power cycle. The only change is 8 jobs in flight instead of 64. The harness
was still `2b9830c5` from this checkout. `b1e95f6f`, which sets the default
window to 24 and adds the failed-read diagnostics described below, reached the
branch at 02:28:34Z, a minute before this run, and was not used. This is not the
rerun planned under "Rerun that tells the causes apart".

    python3 tern_tc_layer_ax7203.py --mats down --layers 5 --act int8 --n_x 1 --setkey --window 8 \
        --port /dev/cu.usbserial-1130 --baud 1144744 --keys ../trinet-keys.txt \
        --model ~/igla-coder-gpu/c_infer/model.bin

Expected `receipts verified (tag) : 51840/51840`, `rows bit-exact : 320/320`,
PASS. Got:

    model.bin: 1 matrices, 320 rows, 276480 ternary weights (61.8% nonzero)
    jobs: 51840 (32-trit chunks x 1 x-vectors x 6 digit planes)
    setkey: node 0x5452494e already holds a key (0x03); receipts below will show whether it is ours
      [ok ] L5/down      320/320    rows bit-exact
    jobs sent               : 51840
    receipts verified (tag) : 51840/51840 under node 0x5452494e
    rejected                : none
    rows bit-exact          : 320/320  (activations: int8)
    elapsed                 : 11.93 s (4344 jobs/s)
    RESULT: every row above computed on the AX7203 bit-exact against the
            int8-weight oracle, and every receipt verified under the key.

- PASS. This is the first board run of the trained model's w_down with int8
  activations: layer 5, 320 rows, one x-vector, all of it on the existing
  bitstream.
- No slip in 51,840 jobs, which is 5.2 times the 9,951 jobs after which the
  window-64 run of the same matrix slipped. One run: this fits the window
  candidate, but it does not prove it.
- Every job was sent in this run, so 4,344 jobs/s is a real rate. The window-64
  runs reached about 4,660 to 4,750 jobs/s before they slipped.

Open: why the framing slipped. It slipped twice at window 64, after 19,049 jobs
and after 9,951 jobs. Between those two runs, all 3,200 jobs of step 4 (also at
window 64) came back framed. At window 8, 51,840 jobs came back framed. Nothing
else has been tested, and the full `--all` run at a smaller window has not been
done. Candidates: the CP2102N's
baud divider at 1,144,744 against the node's (earlier board runs went through a
CP2102N seen as `usbserial-130` on another Mac); the USB 2.0 hub (the CP2102N
did not enumerate on the first hub port tried); 64 jobs in flight
(`--window`) against the node's receive buffer.

### What the bytes say (analysis after the run, no new board data)

The frame layout is `A5 y status nonce[4] node_id[4] tag[8]`, little-endian; the
node id goes out as `4e 49 52 54`.

- **Step 3.** Job 18,984's answer arrived as `A5 y s 28 4a 01 00 4e` and then
  `01 00 4e`. Those three bytes are the tail of the *next* answer's nonce
  (`29 4a 01 00`) and the first byte of its node id. The answer stream lost 16
  contiguous bytes: the last 11 of one answer and the first 5 of the next.
  Before it, 18,984 answers (360,696 bytes) arrived intact.
- **Step 5.** Job 9,886's answer arrived as `A5 y s 9e 26 01` and then `54`, the
  last node-id byte. The stream lost 4 contiguous bytes (`00 4e 49 52`). Before
  it, 9,886 answers (187,834 bytes) arrived intact.

Either hole may also be longer by a whole number of 19-byte answers; the logs
kept no hex to tell. Both are holes with intact bytes on both sides, at
different offsets, after about 10,000 and 19,000 clean answers. Step 4's 3,200
jobs, run between them with 64 in flight too, came back whole.

- **Not the node.** `trinet_node_core.v` has no receive buffer to overflow: it
  parses requests byte by byte, and a lost request byte would give a misparsed
  request but still a whole 19-byte answer. Its transmitter sends each answer
  from one 19-byte buffer; a new result during a send restarts at `A5`, which
  would have put `a5` straight after the cut, not `01 00 4e` or `54`. It cannot
  happen at this pacing anyway: a 24-byte request takes longer on the wire than
  a 19-byte answer.
- **Unlikely to be the baud divider.** A rate mismatch corrupts bits inside
  bytes, scattered over the run. Both runs had hundreds of thousands of clean
  bytes and then a hole with intact bytes on both sides.
- **Consistent with a receive queue overflow.** With `--window 64`, up to 64
  answers (1,216 bytes) can be in flight towards the host. If the host stops
  reading for long enough, they queue in the USB adapter and the driver, and a
  queue that fills drops bytes. Not measured: the adapter's and the driver's
  buffer sizes, and whether the host paused.
- **Not ruled out: the hub or the cable.** A lost USB transfer would also make
  a contiguous hole.

### What changed in the harness

- `--window` defaults to 24: at most 456 bytes of answers can queue.
- The summary reports `jobs sent` as the number written (steps 3 and 5 printed
  the jobs planned) and `answers/s` from answers received, and it prints the
  longest time the host spent between two reads.
- A failed read now logs its bytes in hex, how many jobs were outstanding and
  how many bytes were still waiting in the port.
- The self-test replays the step 3 failure: a reference cell whose answer
  stream loses 16 bytes at the same offset. The harness credits the 5 answers before it,
  classifies the damaged one as a node-id mismatch, stops at the unframed read
  and reports only the jobs actually written.

The stop-on-first-unframed-read rule is unchanged: every credited receipt still
passes every check, and nothing is re-sent.

### Rerun that tells the causes apart

1. `--all --setkey` with the default window (24).
2. As a control on the same setup: the same command with `--window 64`.
3. If step 1 fails: plug the CP2102N in without the hub and repeat step 1.

Step 5a above is the first point on this: the same matrix at window 8, same
hub, came back whole over 51,840 jobs, 5.2 times the length after which it
slipped at 64. It cost about 9% of throughput (4,344 against about 4,750
answers/s); 24 should cost less, which step 1 will show.

The holes came after about 10,000 and 19,000 answers, so one pass or one fail
per window is weak evidence on its own. The stronger signal is `longest host pause` next to
the hex of the failed read: a pause of milliseconds right before a hole at
window 64 points at the queue; a hole with no pause before it points at the
link.
