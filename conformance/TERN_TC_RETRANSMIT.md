# 8-token generation with retransmit, AX7203 node: record

Pre-registered in `specs/trinet/tern_tc_retransmit_ax7203.t27` (sha256
`4dbdee34…`) before any board run of it, committed with this document. The
runner is `conformance/tern_tc_generate_rt_ax7203.py`, and its parameters are
generated from the spec by `conformance/tern_tc_retransmit_from_spec.mjs`
(`tri fpga-specs` checks them for drift). The protocol is
`conformance/tern_tc_retransmit.py`.

This is a new claim with its own record. It is not a second attempt at the
generation run in `TERN_TC_GENERATE.md`: that run stays **FAIL**, and no token
from it is cited.

## What the run is

The same 8-token igla-coder generation as `TERN_TC_GENERATE.md`, with the same
jobs, activations, model, harness, node RTL and bitstream. All of them are
pinned by sha256 in the spec and checked before the first byte. The only change
is the transport.

- **What is retried.** An answer that does not arrive, or arrives without a tag
  that verifies, is asked for again under a fresh nonce. Retry nonces count up
  from `0x20000000`.
- **What is never retried; the run stops.** A tag that verifies over a `y`
  other than the host's own dot product (a lie). A verified answer from another
  node id. A status other than OK. A second answer to one nonce. A job past 3
  nonces. More than 256 retransmits or 32 resyncs in the run. A run longer than
  3600 s.
- **Why the node needs no change.** `trinet_node_core.v` keeps no nonce state,
  so a re-sent job is simply a new request to it. Its parser hunts for `AA 55`,
  then takes 22 body bytes with no timeout. After a lost request byte, 24 zero
  bytes complete any partial frame and cannot start a new one.

## Checks without the board

All of these ran on 2026-09-27. None of them used the board or the key file;
they use the harness's test key.

| check | command | result |
|---|---|---|
| protocol | `python3 tern_tc_retransmit.py --self-test` | PASS: 13 loss shapes recovered, 8 stop cases stop, 40 random hole patterns against a lying cell |
| runner | `python3 tern_tc_generate_rt_ax7203.py --self-test` | PASS: BoardDots clean and lossy, sums equal the CPU's; lie, impersonate, wrong_key behind a hole stop |
| RTL | `python3 tern_tc_retransmit_rtl_cosim.py` | PASS: 400/400 credited, 6 retransmits, 1 resync; 7695 answer bytes, model and `trinet_node_core.v` identical; the negative control (`h.RefCell`) differs |
| spec | `tri fpga-specs` | the spec compiles, its 7 test blocks pass, and the params have not drifted |
| all at once | `tri fpga-selftest` | every Python file a spec names, 7/7 PASS |

The co-sim is the check that matters most for the claim that "the node needs no
change". It replays the exact request stream the protocol wrote into the real
RTL under iverilog: re-sent jobs, one frame missing a `w` byte, one missing its
last byte, and the flush zeros. The RTL's answers equal the Python model's byte
for byte.

## Rehearsal: the whole run through the reference cell

The rehearsal command is `python3 -u tern_tc_generate_rt_ax7203.py --refcell`.
It runs all 7,682,304 jobs through the harness's reference cell, placed behind
the RTL's frame parser. Five losses are scheduled in the spec:

- three in the answer stream, among them the 56-byte hole at the place where the
  generation run lost it;
- two in the request stream.

| | rehearsal 1 | rehearsal 2 |
|---|---|---|
| log | `rehearsal_runs/gen_tokens_8_rt_refcell_1.log` | `rehearsal_runs/gen_tokens_8_rt_refcell_2.log` |
| spec | `9901f145…` (the log has no spec line; see below) | `4dbdee34…` (first line of the log) |
| ended (UTC) | 14:55:53 | 15:08:24 (started 14:59:20) |
| token ids | 1 3 204 276 405 659 85 1516 | same |
| receipts | 7682304/7682304 | same |
| rows bit-exact | 135168/135168 | same |
| retransmits / resyncs | 9 / 2 | same |
| lost / unverified / foreign / late | 9 / 2 / 1 / 0 | same |
| elapsed in `run()` | 408.3 s | 542.8 s (self-tests ran alongside) |
| result | REHEARSAL OK | REHEARSAL OK |

The two rehearsals logged the same events, word for word. Only the times differ.

**Why there are two.** The spec's comment on the rehearsal schedule claimed each
loss hits the job its offset is computed from. That is true only for the first
loss. The offsets count bytes in the stream as it flows. Retransmitted answers,
re-sent requests and flush zeros all add whole frames, so each loss keeps its
shape but lands a few jobs earlier than the index in its formula. The losses
actually hit jobs 1000, 2999998, 4999996, 5999995 and 7235182 (global job index
= nonce − `0x10000`).

The fix was to the comment only. The constants did not change. The params were
regenerated, since the spec's sha changed, and the rehearsal was run again on
the new sha. The runner did not yet print the spec's sha when rehearsal 1 ran.
The value `9901f145…` for rehearsal 1 is what the generator printed when it
wrote the params that rehearsal read. The runner refuses to start when the
spec's sha differs from the one in its params, so that is the spec it ran on,
but its log does not show it. The runner now prints the spec, protocol, harness and RTL
hashes as its first line.

## The board run: not run yet

It needs the owner's «да». There is one attempt. A second is allowed only if the
first fails before its first job (port busy, the node not answering setkey), and
then both logs are kept.

```
tri fpga-usb
tri fpga-ioclients
tri fpga-run gen_tokens_8_rt --limit 3900 -- python3 -u tern_tc_generate_rt_ax7203.py --setkey --port /dev/cu.usbserial-110 --keys ../trinet-keys.txt
```

- **Port.** The port is the one `tri fpga-usb` names at the time; 110 is today's.
  The run is allowed behind the hub. It exists precisely so that a rare loss no
  longer ends the run.
- **`--setkey` on a node that already holds a key** returns status `0x03`. The
  harness accepts that, and the receipts then show whether the key is ours.
- **The outer `--limit`** is 300 s above the spec's `LIMIT_S`, so the runner's
  own time check reports first. The limit guards the run; it is not a claim.
- **Expected duration.** About 27 minutes. At the generation run's 4712
  answers/s, 7.68 million answers take 1630 s. The CPU forward pass comes on top.
- **Claim.** The runner prints `receipts verified (tag) : A/J` on every board
  run, a failed one included. The record calls the run verified only if
  A = J = 7,682,304 and the last line is `RESULT: PASS`. That line also needs
  three more things: the ids equal to `CPU_INT_IDS`, every row exact, and the
  ceilings and the time limit held. The retransmit and resync counts are
  printed next to it, whatever they are.

## What it does not say

- It does not say the UART is lossless; it says losses no longer end the run.
  It does not find the cause of the 56-byte hole. For that, see
  `UART_LOSS_HUBFREE.md`.
- **A lie can be retried if the lying answer itself goes missing.** The node
  signs whatever it answers, so a lost answer shows nothing. In the protocol
  self-test, 40 random hole patterns were run against a cell that lies once:
  - 39 stopped on the lie;
  - in 1, the lie fell into a hole, and the re-asked job was answered honestly.

  Every credited answer is still verified and exact. What the run cannot tell is
  whether a lost answer was honest.
- It is not speed, and it is not text: the tokenizer is not on this Mac.

## Results

None yet.
