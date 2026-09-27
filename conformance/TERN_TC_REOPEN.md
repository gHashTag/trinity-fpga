# 8-token generation with retransmit and port reopen, AX7203 node: record

Pre-registered in `specs/trinet/tern_tc_reopen_ax7203.t27` before any board run
of it, committed with this document. The runner is
`conformance/tern_tc_generate_reopen_ax7203.py`. Its parameters are generated
from the spec by `conformance/tern_tc_reopen_from_spec.mjs`, and
`tri fpga-specs` checks them for drift. The link is `conformance/tern_tc_reopen.py`.

This is a new claim with its own record. It is not a second attempt at the
retransmit run in `TERN_TC_RETRANSMIT.md`. That run stays **FAIL**, and no token
from it is cited.

## Why this run

The retransmit run stopped in call 145 of 192.

- A short read collected 11 bytes with 24 answers in flight.
- The next two resyncs collected 0 bytes each.
- Job 16873 reached its ceiling of 3 attempts.

Calls 1 to 144 had no transport event. Four minutes later a freshly opened port
gave 3840/3840 with the key still held, so the FPGA had not been reconfigured.

The record there ends with a hypothesis: reopening the port inside the run would
clear such a stop. This run tests it.

## What changes, and what does not

Only the link changes. The protocol (`tern_tc_retransmit.py`), the retransmit
runner, the generation runner, the harness, the node RTL, the model and the
activations are imported unchanged. The spec pins each of them by sha256.

- **When the link reopens.** The protocol writes 24 zero bytes once per resync
  and nowhere else. Requests and the setkey frame both start with `AA 55`.
  - The link counts the answer bytes it has returned since the last flush.
  - A flush that comes after zero bytes means the line was silent through a
    whole resync.
  - Only then does the link close the port, wait, open it again with the
    harness's own `SerialLink` (which clears the input buffer), and pass the
    flush on.
  - The wait is 2 s, doubled for each earlier reopen in the run: 2, 4, 8, 16 s.
- **Why a hole never triggers it.** The answers around a hole are bytes. The
  generator reads this coupling out of the sources:
  - the protocol writes exactly one flush, inside `resync()`, and one request
    kind;
  - the harness writes only frames built by `request()`.
- **Ceilings.** At most 4 reopens in the run; the fifth raises
  `ReopenExhausted`, and the run fails. `MAX_ATTEMPTS` rises from 3 to 4. In the
  retransmit run the stalled job spent its second nonce on the dead port, so
  with the reopen before the third there would be no spare. Every other ceiling
  is the retransmit run's: 256 retransmits, 32 resyncs, 3600 s.
- **What is never retried.** Everything the retransmit record lists: a lie,
  another node id, a bad status, a second answer, and a job or ceiling that is
  spent. The link cannot credit anything. A job whose answer was lost across a
  reopen is asked again under a fresh nonce, and that counts toward its attempts.

## Prediction

**Board.**

- Token ids equal the generation spec's `CPU_INT_IDS`.
- Every one of 7,682,304 jobs is credited by exactly one answer whose tag
  verifies under the node key.
- Every row is bit-exact.
- The ceilings hold: retransmits ≤ 256, resyncs ≤ 32, reopens ≤ 4, elapsed ≤
  3600 s.

The runner prints `receipts verified (tag) : N/N` only then. It prints the
retransmit, resync and reopen counts next to it, whatever they are.

**What each outcome says.**

| outcome | what it says |
|---|---|
| PASS, 0 reopens | Generation finished. It says nothing about whether a reopen clears a stop, because no stop happened. |
| PASS, 1 or more reopens | Those reopens cleared those stops. |
| FAIL with `ReopenExhausted`, or a job past its attempts after a reopen | A reopen at these waits does not clear the stop. |
| FAIL for any other reason | Recorded as it is; it says nothing about the hypothesis. |

**Rehearsal (no board).** The whole run goes through the reference cell behind
the RTL's frame parser, with the retransmit spec's five losses plus two stalls:

- one in the answer stream, near answer 5,754,002, the retransmit run's last
  verified answer;
- one in the request stream, 5 bytes into request 2,000,000.

It must end REHEARSAL OK with the same ids and counts, at least one retransmit
per scheduled loss, and exactly 2 reopens: one per stall, none for the ordinary
losses.

**What it does not say.** It does not find which side stalls: node TX, the
CP2102N, the hub or the host driver. It does not say the UART is lossless. It is
not a speed measurement, and not text.

## Prior reports on closing a CP210x port

Closing the port is the one new act in this run, and CP210x bridges have a
history of hanging on close. Two reports were found on 2026-09-27:

- The Linux `cp210x` driver sends a PURGE from its `close()` callback, since a
  2015 patch by Konstantin Shkolnyy (LKML, 2015-10-28, "Workaround cp2108 Tx
  queue bug"). The patch says a CP2108 stopped responding until unplugged when
  it was closed with unsent transmit data.
- A Silicon Labs community thread is titled "CP2102N stops receiving anything
  if port is closed while incoming data is received". Its page did not load
  here, so only the title is cited.

How the reopen here stands against those two triggers:

- **Incoming data at the close.** Not expected. The reopen fires only when no
  answer byte has arrived since the previous flush, and `resync()` drains the
  port until it is quiet before it writes the flush.
- **Unsent transmit data at the close.** Not ruled out. If the stall is on the
  host-to-node side, the requests written before it may still sit in the bridge
  when the port closes, and that is the trigger the Linux patch describes.

If a reopen does not clear a stop, a bridge wedge of that kind is one
candidate. This run cannot test it, because only a USB power cycle clears such a
wedge.

## Checks without the board

None of these used the board or the key file; they use the harness's test key.

| check | command | result |
|---|---|---|
| link | `python3 tern_tc_reopen.py --self-test` | PASS: ordinary holes never reopen (flushes = resyncs in every case); 5 stall shapes each cleared by the expected reopens, 1332/1332; a stall no reopen clears fails; the ceiling raises; lie and impersonate after a reopen stop the run |
| real pyserial | `python3 tern_tc_reopen.py --pty-test` | PASS: over a pseudo-terminal, the node went silent after answer 40; one reopen closed the first descriptor and the run finished 120/120 on the second |
| runner | `python3 tern_tc_generate_reopen_ax7203.py --self-test` | PASS: BoardDots clean, answer stall, request stall, hole plus stall, all 23296/23296 with sums equal to the CPU's and waits `[2]`, and every event kept (events = lost + resyncs); with a cap of 4 the same stall keeps 4 of 50 events, so that check can fail; a dead stall, a lie and an impersonation stop the run |
| spec | `tri fpga-specs` | compiles; 8 test blocks, 25 asserts pass; params not drifted |

The pty test opens at 115200 baud. A pty carries no baud rate and refuses
macOS's custom-speed ioctl (errno 25). The run's 1144744 goes through that ioctl
on every open, the first one included.

## Rehearsal

Two pairs, both through `tri fpga-rehearse`, which runs the same command twice at
once and compares the event lines with times masked. Neither used the board or
the key file.

**First pair, spec `075fba377f7db8e7`.**
`rehearsal_runs/gen_tokens_8_reopen_refcell_{1,2}.log`.

- Both runs: REHEARSAL OK. Token ids `1 3 204 276 405 659 85 1516`, equal to
  `CPU_INT_IDS`. 7,682,304 jobs, 135168/135168 rows bit-exact.
- Transport: 106 retransmits (ceiling 256), 7 resyncs (ceiling 32), 2 reopens.
  - Reopen 1, request-stream stall, call 51. The resync there (flush 2)
    collected 0 bytes. The next one (flush 3) came after 0 bytes since flush 2,
    so the link reopened before passing it on. Wait 2 s.
  - Reopen 2, answer-stream stall, call 145. The resync after the short read of
    8 bytes (flush 5) was followed by a silent one (flush 6), which reopened.
    Wait 4 s.
  - Each stall cost two resyncs, and the reopen came at the second. This is the
    pattern of the retransmit run's stop: a short read, then resyncs with 0
    bytes.
  - The five ordinary losses caused resyncs or retransmits, never a reopen.
- The two runs' event lines were identical: 288 lines once times were masked.
- Elapsed 1436.5 s and 1433.2 s. The host was busy with other jobs: a load of
  158 on 8 cpus when it was measured during the pair.

This matched the prediction. It also showed a gap in the log. The protocol's
budget keeps only its first 64 events. The run had 106 losses and 7 resyncs, so
113 events, and the log printed 64 of them, including 5 of the 7 resyncs.
Nothing in the log said that events were missing.

The fix changes no pinned file. The spec now pre-registers
`KEEP_EVENTS = 512` with a test block: 512 covers every event the ceilings
allow (256 + 24 + 32 + 1 = 313). The runner passes it to the budget. It prints
`events kept : N (cap K); lost L + resyncs R = T` and warns if the cap is
reached. The runner's self-test checks events = lost + resyncs, and a negative
control shows that a cap of 4 fails that check. The spec's sha moved to
`49faa6070fbb7f41`, so the rehearsal was run again. The first pair stays in the
record as run.

**Second pair, spec `49faa6070fbb7f41`.**
`rehearsal_runs/gen_tokens_8_reopen_refcell_b_{1,2}.log`, 17:30:35Z to
17:57:25Z on 2026-09-27.

- Both runs: REHEARSAL OK, with the same ids, jobs and rows as the first pair.
- The same transport: 106 retransmits, 7 resyncs, 2 reopens at flushes 3 and 6
  with waits `[2, 4]` s.
- `events kept : 113 (cap 512); lost 106 + resyncs 7 = 113`. All 7 resyncs are
  in the log now, including the two at calls 51 and 145 that the first pair cut
  off.
- The two runs' event lines were identical: 336 lines once times were masked.
  The first pair had 288, because 49 events were missing.
- Elapsed 1608.9 s and 1606.6 s, longest host pause 249.7 ms and 318.1 ms. The
  1-minute load was between 30 and 67 on 8 cpus when checked during the pair.
- Key hits 0 in all four logs.

The rehearsal matches the prediction: exactly 2 reopens, one per stall, none
for the ordinary losses, and every loss recovered. It says the code does what
the spec says on a simulated stall. Whether a reopen clears a real stop is what
the board run tests.

## Board run

Not run. It needs no flash: the node is loaded and keyed, and the W24 control
passed at 16:31Z on 2026-09-27. The owner's yes for it: «все три и PR в
openXC7», to variant 2 of the 16:35Z loop report.

Command:

```
tri fpga-run gen_tokens_8_reopen --limit 3900 -- python3 -u tern_tc_generate_reopen_ax7203.py --setkey --port /dev/cu.usbserial-110 --keys ../trinet-keys.txt
```
