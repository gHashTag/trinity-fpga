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
