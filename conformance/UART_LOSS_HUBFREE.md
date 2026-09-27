# UART loss at window 24 with no hub in the path, AX7203 node: record

Pre-registered in `specs/trinet/uart_loss_hubfree_ax7203.t27` (sha256
`470a1d8d…`) before any run of it, committed with this document. The runner is
`conformance/uart_loss_hubfree_ax7203.py`, and its parameters are generated from
the spec by `conformance/uart_loss_hubfree_from_spec.mjs`. The counter is the
diagnostic's, `uart_loss_diag_ax7203.run_arm` and `.summarize`. They are
imported and pinned by sha256, and not edited.

## Why

The generation run (`TERN_TC_GENERATE.md`) lost 56 answer bytes after 7,235,186
answers at window 24. At the time the CP2102N sat behind a Genesys USB2.1 hub
(`05e3:0610`). The diagnostic (`UART_LOSS_DIAG.md`) then counted 0 loss events
in 2,016,000 answers at window 24 on the same path. Together that is 1 event in
9,251,186 answers behind the hub.

This arm repeats the diagnostic's W24 arm, the same jobs and the same counter,
with the cable in a Mac port and no hub, and runs it long enough for the answer
to mean something.

## Fixed before the run (in the spec)

| | value | why |
|---|---|---|
| window | 24 (456 B in flight) | the diagnostic's second arm |
| arm | 58 passes × 403,200 = 23,385,600 answers | the fewest whole passes for which the bound below is under 1 per generation run |
| limit | 7200 s, floor 3300 answers/s | the floor is under 70 % of the W24 arm's 4716/s |
| USB | exactly one `10c4:ea60`, no device of class 9 between it and its host controller | checked before the first byte |
| prediction | 0 loss events, 0 wrong y, instrument check ok | |

**The claim, `CLAIM_BELOW_ONE_PER_GENERATION_RUN`.** It is **yes** only if the
arm ends with all of these:

- zero loss events and zero wrong y;
- all 23,385,600 answers sent;
- not aborted, and not stopped at the time limit;
- the instrument check ok.

Then the one-sided 95 % upper bound on the event rate, times one generation run
(7,682,304 answers), is 0.9841, which is below 1. At 57 passes the same number
would be 1.0014, which is why the arm is 58 passes.

With any event the claim is **no**. The runner then prints the rate, its
interval and the point estimate per generation run.

## What it does not say

- **That a generation run without retransmit will pass.** At the bound, the
  chance of zero loss in one generation run is only e^−1, about 37 %. Showing
  95 % would take about 450 million answers, about 26 hours. For a run that
  survives loss, see `TERN_TC_RETRANSMIT.md`.
- **That the hub caused the hole.**
  - At the hub path's point rate, 1 in 9,251,186, this arm would still see zero
    events with probability 0.080.
  - So zero here is weak evidence against the hub, not proof.
  - The W64 arm showed that losses come in bursts. The bound counts events, and
    a burst is at least one event.
- **Anything beyond this one setup.** One USB path, one host, one evening.
  Nothing about the harness's PASS criterion.

## Checks without the board

| check | result |
|---|---|
| `python3 uart_loss_hubfree_ax7203.py --self-test` | PASS |
| `tri fpga-specs` | the spec compiles, its 7 test blocks pass, the params have not drifted |
| `tri fpga-selftest` | part of 7/7 PASS |

The self-test covers the following:

- the pins;
- synthetic USB trees: behind the Genesys hub is refused, direct is accepted,
  two bridges or none are refused;
- the pinned counter on the reference cell: a clean arm counts 0 events, and a
  56-byte hole counts 1 event with hole `[56]`;
- every branch of the claim;
- the bound at 58 and at 57 passes;
- the prior's 0.080.

`--usb` on the setup of 2026-09-27 refuses, as it should:

```
USB refused: AppleT6000USBXHCI -> USB2.1 Hub 05e3:0610 @ 0x00100000 -> CP2102N USB to UART Bridge Controller 10c4:ea60 @ 0x00110000; 1 hub(s) in the path: USB2.1 Hub 05e3:0610 @ 0x00100000
```

`tri fpga-usb` now runs the same walk next to its own locationID rule. It
reports an anomaly (exit 3) if the two disagree.

## The board run: not run yet

1. The owner moves the CP2102N cable from the USB-C adapter to a port on the
   Mac itself.
2. `tri fpga-usb` must print `DIRECT` and `USB ok: …`. Anything else, including
   the anomaly line, means stop.
3. `tri fpga-ioclients` records who holds the bridge.
4. Only after the owner's «да», with the port that step 2 named:

```
tri fpga-run uart_loss_hubfree_w24 --limit 7500 -- python3 -u uart_loss_hubfree_ax7203.py --run --setkey --port /dev/cu.usbserial-NNN --keys ../trinet-keys.txt --json board_runs/uart_loss_hubfree_w24.json
```

- **Expected duration.** About 83 minutes: 23,385,600 answers at 4716/s is
  4959 s.
- **The outer `--limit`** is 300 s above `LIMIT_S`, so the runner's own limit
  reports first.
- **One attempt.** A second is allowed only if the first fails before its first
  job, and then both logs are kept.
- **After the run**, `tri fpga-keycheck` must pass on the log before it is
  committed.

## Results

None yet.
