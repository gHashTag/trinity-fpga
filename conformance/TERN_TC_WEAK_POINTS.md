# tern_tc on the AX7203: weak points, ranked

Written 2026-09-27, after the board runs recorded in `TERN_TC_LAYER_RECEIPTS.md`
(window 24 PASS 403200/403200, window 64 FAIL 6679/403200). Each point says what
is weak, what the evidence is, and what test would settle it. "Derived" marks
arithmetic on logged numbers, not a new measurement.

## 1. It is a conformance result, not a speed result

403,200 jobs x 32 trits = 12,902,400 ternary multiply-accumulates in 85.49 s:
about 151,000 MAC/s (derived). A laptop CPU does the same layer set in
milliseconds. The run shows the node computes every chunk bit-exact and signs
it; it does not show that the FPGA is a fast way to run tern_tc. Nothing in the
record should read as a throughput or efficiency claim.

**What would change it:** weights resident on the FPGA. 6,451,200 ternary
weights are 12.9 Mbit at 2 bits per trit, or 10.3 Mbit at 5 trits per byte
(3^5 = 243 <= 256); the XC7A200T has 13.1 Mbit of block RAM (derived; the BRAM
figure is from the Xilinx 7-series overview, not measured here). Then only
activations cross the link.

## 2. The link sets the pace, and it is already full

The node clock is STARTUPE2 CFGMCLK and the UART divides it by 60
(`fpga/portable/trinet_node_core.v`). At 1,144,744 baud a 24-byte request costs
240 bit times: 4,770 jobs/s at most (derived). Window 24 reached 4,716 answers/s,
98.9 % of that. **A bigger window cannot make it faster**, and window 64 loses
bytes (point 3). More speed needs fewer bytes per job (several chunks per frame)
or a faster link (point 8).

## 3. Why window 64 loses bytes is not known

Three long runs at window 64 slipped (after 19,049, 9,951 and 6,744 jobs); window
24 (403,200 jobs) and window 8 (51,840 jobs) did not. Before the last hole the
host had not paused for more than 4.2 ms.

**The node is probably not the cause (derived).** Window 8 ran at 4,344
answers/s, below the 4,770 ceiling, so the round trip is about 8 / 4,344 = 1.8 ms.
Any window above about 9 therefore keeps the link from host to node full, and
the node sees the same back-to-back request stream at window 24 as at window 64.
What the window changes is how many answer bytes can be in flight between the
node's transmitter and the harness: at most W x 19, which is 456 B at 24 and
1,216 B at 64. The holes also start mid-answer (inside a tag), which fits
answer bytes lost on the way back rather than a request lost on the way in.

**Hypothesis, not tested:** a buffer downstream of the node overflows. The
UART has no flow control wired to the node, so any full buffer in the answer
path drops bytes instead of holding back the sender. The candidates are the
CP2102N receive FIFO, the hub, and the macOS driver and tty input queue. USB
bulk-IN cannot drop bytes by itself: if the host stops polling, data waits in
the bridge, and then the bridge FIFO is where it overflows. If that FIFO holds
F bytes, any W with W x 19 <= F can never overflow however long the USB side
stalls. The prediction is W_max = floor(F / 19). F has to come from the Silicon
Labs datasheet before the test is pre-registered.

**Test that could refute it:** one `--all` run at W = floor(F / 19). Any slip
refutes the hypothesis. A pass is weak support only, because window 24 already
passed. The owner-approved run of window 64 without the hub tests the other
candidate (the hub's transaction translator adding IN-polling gaps).

**Update, 03:40Z the same day.** F = 512 bytes (CP2102N datasheet Rev. 1.5,
section 1), so W_max = 26. Two pre-registered runs followed
(`TERN_TC_LAYER_RECEIPTS.md`, rerun step 3). Window 26 (494 B) passed,
403200/403200, and window 30 (570 B) slipped after 150,017 jobs. The threshold
therefore lies between 494 and 570 bytes, and the hypothesis survived a test
that could have refuted it. The window-30 slip came about 10 times later than
the pre-registration expected, so the stall model is incomplete.

**Update, 09:35Z.** With the UART moved off the FE1.1s dongle onto a
separate single-TT hub, window 64 still slipped, but only after 189,001 jobs
(`TERN_TC_LAYER_RECEIPTS.md`, rerun step 4). The old dongle, bus or port is
not needed for the loss, but very probably made it more frequent.

## 4. A receipt proves the key, not the FPGA

The tag is SipHash-2-4 under a 16-byte key that the host also holds. A program
on the serial port that knows the key produces the same log, so the log
authenticates "someone with the key answered". It does not show that the answer
came from the FPGA. `--setkey` also sends the key over USB in the clear. The
record already says the receipts are not publicly verifiable
(`TERN_TC_LAYER_RECEIPTS.md`, "Not claimed"). The stronger point is that they
do not even bind to hardware for the key holder.

**What would help:** a key that never leaves the FPGA, generated or fused on
chip, with an asymmetric signature. Neither exists in this RTL. DNA_PORT reads
zeros under openXC7, so it cannot supply an identity either.

## 5. The bitstream on the board is not pinned

The node runs from SRAM, loaded over JTAG from a CI artifact (run 30762491794,
per `docs/TRI_NET_HANDOFF.md`). That `.bit` file is not on this Mac, and no
answer carries a bitstream hash. `node_id` is a configured constant ("TRIN").
After a power cycle the node, and its key, are gone until someone reflashes it.

**Test:** rebuild the node from source with the restored openXC7 flow and compare
its SHA-256 with the CI artifact. Loading it is the owner's call.

**Status 2026-09-27:** the CI artifact was fetched and loaded. Its sha256 is
`0fafd225e2…ddb4`, and it passed the window-24 control again. The local rebuild
has a different payload, as expected from the two yosys versions. Details are in
`NODE_TOOLCHAIN_RESTORE.md`, "Reload after MXDOT4".

## 6. The clock is not calibrated

CFGMCLK is the configuration oscillator, specified loosely and drifting with
temperature and voltage. The baud of the day is found by discovery (1,144,744
on 2026-09-27, so about 68.7 MHz; the repository's papers say "~69-70 MHz,
measured"). The UART's margin against that drift is not measured, so a run that
starts clean could in principle start slipping as the board warms up.

**Test:** `conformance/trinet_baud_sweep.py`. It is read-only: it finds the
range of host baud rates the node still answers at, and so the margin.

## 7. One run per configuration

W24 PASS and W8 PASS are one run each; W64 FAIL is three of three. A single
pass bounds the loss rate only loosely: zero slips in 403,200 jobs gives a
95 % upper bound of about 3/403,200 per job (rule of three, derived). That is
enough to use W24, but not enough to call it loss-free.

## 8. The Ethernet port is unused

The board is cabled to the router, but the node bitstream speaks UART only and
has no MAC or IP. An earlier open-flow bring-up on another machine got gigabit
link, ARP and ICMP working on this board (fabric DDR capture, because IDDR is
broken on openXC7, issue #114). Its RTL and bitstreams are not on this Mac; only
a pin XDC survives. Using the port means new RTL plus a reflash.

## 9. What the run leaves on the host

Everything except the ternary dot: the per-tensor scales g, the int8 digit
recombination, norms, attention, softmax, and the head. The activations are
synthetic: two random ternary vectors (seed 0x7213), and one random int8 vector
for layer-5 w_down. The weights are the trained model's. The next honest step
is real activations from `tc_infer` on a real prompt (cheatsheet item 9).

## 10. No power figure, one board, one node

No current measurement, no second node, and no second board. The fleet
bitstreams for node1 and node2 exist in CI but are not loaded.

## What is solid

- Every one of 33,792 rows computed on the board equals the row dot from the
  model's int8 weights, and every one of 403,200 tags verifies under the key
  (window 24).
- The harness shows each of its checks failing on a cell built to break it
  (`--self-test`), including the 16-byte slip seen on the board.
- The failure runs are recorded as failures, with their bytes.

**Update, 03:50Z the same day: the sweep ran, and its resolution is not what it
prints.** `trinet_baud_sweep.py --centre 1144744 --span 0.08` (log
`board_runs/baud_sweep_1144744.log`, run once) printed a clean window
1,070,333..1,167,624, "USE THIS RATE 1118978" and "CFGMCLK 67.14 +/- 0.17 MHz".
The prediction recorded beforehand in the loop state was: the window contains
1,144,744 (held), and its centre lies within 1 % of 1,144,744 (missed by the
tool's own number: 2.25 %).

Both numbers are about requested rates, and the adapter does not send
requested rates. CP2102N datasheet Rev. 1.5, section 4.2.1: clock divider =
48 MHz / (2 x requested), rounded to the nearest integer; actual rate =
48 MHz / (2 x divider), so 24 MHz / N on the wire (the 48 MHz oscillator is
+/-0.25 %). Mapped that way (derived), the 33 requested rates were 5 wire rates:

| N | wire baud | sweep steps | result |
|---|---|---|---|
| 23 | 1,043,478 | 3 | 0/64 each |
| 22 | 1,090,909 | 9 | 64/64 each |
| 21 | 1,142,857 | 9 | 64/64 each |
| 20 | 1,200,000 | 11 | 0/64 each |
| 19 | 1,263,158 | 1 | 0/64 |

So 1,118,978 and 1,144,744 are the same rate on the wire, 1,142,857. The
"+/- 0.17 MHz" is the sweep step, not the resolution. What the sweep does bound
(derived, assuming the node's tolerance is symmetric; its receiver samples at
1.5 x BAUD_DIV after the start edge, i.e. mid-bit): the node's rate R satisfies
R(1-t) between 1,043,478 and 1,090,909 and R(1+t) between 1,142,857 and
1,200,000, so R is between 1,093,168 and 1,145,455 and **CFGMCLK is between
65.6 and 68.7 MHz**. The earlier "about 68.7 MHz" sits at the top edge of that
range; "67.14" is its middle, not a measurement. The margin question this point
asks cannot be answered with this adapter at this speed: its neighbouring rates
are 4.5 % apart.

**Pre-registered, before it runs: the edges are the adapter's, not the node's.**
If the rounding above sets the pass/fail edges, they sit on the divider
boundaries 24 MHz / 22.5 = 1,066,667 and 24 MHz / 20.5 = 1,170,732. Two narrow
sweeps, 7 steps of about 0.05 %, 64 jobs each, run once:

    trinet_baud_sweep.py --centre 1066667 --span 0.0015 --steps 7
    trinet_baud_sweep.py --centre 1170732 --span 0.0015 --steps 7

Prediction: lower sweep, every step below 1,066,667 is 0/64 and every step
above it is 64/64; upper sweep, every step below 1,170,732 is 64/64 and every
step above it is 0/64. A step within 0.01 % of the boundary may go either way
and does not count. Any other clean/empty pattern refutes the reading, and then
the edges belong to the node. Afterwards the port gets 24 zero bytes and one
640-job `wk` layer-0 check, as after the wide sweep (that check passed at
03:46Z: `receipts verified (tag) : 640/640`, `rows bit-exact : 64/64`).

**Result, 03:49Z and 03:50Z: the prediction held at every step.** Each sweep ran
once (logs `board_runs/edge_sweep_1066667.log`, `edge_sweep_1170732.log`).

| sweep | below the boundary | at it (+/-0.01 %) | above the boundary |
|---|---|---|---|
| 1,066,667 (N 23/22) | 1,065,066 / 1,065,599 / 1,066,132: 0/64 | 1,066,665: 0/64 | 1,067,198 / 1,067,731 / 1,068,264: 64/64 |
| 1,170,732 (N 21/20) | 1,168,975 / 1,169,560 / 1,170,145: 64/64 | 1,170,730: 64/64 | 1,171,315 / 1,171,900 / 1,172,485: 0/64 |

Both boundary steps also match the rounding: 24 MHz / 1,066,665 = 22.50004
rounds to 23, and 24 MHz / 1,170,730 = 20.50004 rounds to 21. So both edges lie
within one step (0.05 %) of the adapter's divider boundaries. The node's own
tolerance does not show in this data. The tool printed "CFGMCLK 64.06" for one
sweep and "70.19" for the other, which is what its centre-times-60 rule gives
when the edges are the adapter's. Afterwards: 24 zero bytes (nothing came back)
and the 640-job check, `receipts verified (tag) : 640/640`, `rows bit-exact : 64/64`.

**What changes (derived):**

- The link runs at 1,142,857 baud on the wire, not 1,144,744. The ceiling in
  point 2 becomes 4,762 jobs/s, and window 24 reached 99.0 % of it.
- Any requested rate from 1,116,280 to 1,170,731 is the same wire rate. The only
  other working wire rate is 1,090,909 (requested 1,066,668 to 1,116,279).
  "Use 1118978" changes nothing on the wire.
- CFGMCLK: between 65.6 and 68.7 MHz, under a symmetric-tolerance assumption.
  The sweep cannot narrow this and cannot measure the drift margin. That needs
  a finer rate grid: an adapter with a different clock, or the node timing its
  own clock against a known one.
- `trinet_baud_sweep.py` assumes the host rate is continuous. Its "USE THIS
  RATE" and "implied CFGMCLK" lines are only meaningful where the adapter's rate
  grid is finer than the sweep step, which is not so for a CP2102N near 1 Mbaud.

**Update, 04:02Z: the older per-chip figures have the same defect.**
The section "Entered 2026-08-03" of `docs/TRI_NET_REPORT_2026-08-02.md`, and
the block with `node0_cfgmclk_mhz 70.46` in
`specs/trinet/ternary_hw_verification.t27`, record three boards swept in 0.5 %
host-rate steps, with CFGMCLK taken as window centre x 60 (BAUD_DIV 60).
Every one of the five recorded edges lies within one sweep step of a
24 MHz / N divider boundary (offsets +0.42, -0.24, +0.15, -0.11 and -0.19 %,
derived). The adapter on those boards is not recorded; the edges are what
identify the grid. Mapped through 24 MHz / N (derived, `tri fpga-wire`):

| node | recorded window | wire rates inside it | recorded CFGMCLK |
|---|---|---|---|
| node0 | 1,121,020 – 1,227,778 | 1,142,857 and 1,200,000 (N 21, 20) | 70.46 |
| node1 | 1,068,248 – 1,169,444 | 1,090,909 and 1,142,857 (N 22, 21) | 67.13 |
| node2 | 1,121,020 – 1,168,468 | 1,142,857 only (N 21) | 68.69 |

Each window is one or two whole divider bins, give or take the sweep step, so
each "centre x 60" is the middle of the bins that passed, not the chip's clock.
node1's centre 1,118,846 and node2's centre 1,144,744 are the same wire rate,
1,142,857.
The "4.97 % spread" between node0 and node1 is one step of the adapter's
grid (their windows are the same two-bin width, shifted by one bin). The record's one
open item, node2's soft upper edge "96-98 % clean over 1174399..1227778", is
the N = 20 bin (1,170,732 to 1,230,769 requested), so it is one wire rate,
1,200,000, at the edge of node2's tolerance, not a range. This board today
passes the same bins as node1 did then. That is consistent with any clock in
the shared band and does not identify the chip. The single-board figure
71.18 MHz (2026-08-02, BAUD_DIV 434, about 164 kbaud) is not affected in the
same way: there the grid is about 0.7 %, finer than its window. It does not
fit this board's bound, so it was either another board or another bitstream;
the record does not say which board. The record is not edited here. Superseding it in the spec is a task for a compile-checked
edit.
