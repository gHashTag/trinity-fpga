# The AX7203's Ethernet port as a job link: what it would take (2026-09-27)

The owner connected the board's RJ45 port to the router this Mac uses and asked
how that channel can be used. Short answer: **today it cannot carry jobs.**
The node bitstream on the board has no Ethernet MAC. Using the port needs new
RTL and a reflash. The reflash waits for the owner's yes.

Tags: **checked** = run on this Mac today. **recorded** = from repo history,
an upstream tracker, or the operator's notes; not re-run. **derived** =
arithmetic from the numbers cited. **unchecked** = none of these.

## What was checked, 04:04 UTC (checked)

- The Mac is 192.168.1.101 on **Wi-Fi** (`en0`). The router is 192.168.1.1.
- The ARP table resolves the router, this Mac and one other host (.103). So
  the probe can see hosts on this LAN.
- Nothing answers at 192.168.1.222 or 02:00:5E:F9:00:01. The earlier
  Ethernet builds used that address; they are not on the board now. Two
  pings: 0 replies.
- As expected: the node has no MAC. An absent ARP entry says nothing about the
  copper link. The PHY can link without the FPGA only if the FPGA releases
  `phy_rst_n` (D16, active low), and no current RTL drives that pin. The
  router's port LED is the only link check that needs no reflash. Reading it
  is for the operator: logging into the router is not done here.

## What the port could carry (derived)

Keep the TRI-NET frames unchanged, 24-byte request and 19-byte response,
signed the same way. Carry K of them in one UDP datagram with a 4-byte
sequence number. The harness's receipt checks then stay as they are. Only the
transport changes.

Frame cost on the wire: 8 preamble, 14 Ethernet, 20 IP, 8 UDP, 4 FCS and a
12-byte gap, with a 64-byte minimum. Requests are the tighter direction.

| link | jobs per datagram | jobs/s ceiling | vs UART |
|---|---|---|---|
| UART, CP2102N at 1,142,857 baud | 1 | 4,762 | 1x |
| 100BASE-TX | 1 | 132,979 | 28x |
| 100BASE-TX | 60 | 496,689 | 104x |
| 1000BASE-T | 60 | 4,966,887 | 1,043x |

The node's tag core states "12 clocks plus setup" per tag
(`trinet_siphash24.v`). At 65.6 MHz, even 64 clocks per job would be
1.0 M jobs/s, so up to 100BASE-TX the link, not the core, stays the bound
(derived; the dot-product clocks are unchecked). This Mac reaches the router
over Wi-Fi, whose throughput here is unchecked. For a clean number the Mac
should be wired to the router: it has USB Ethernet adapters `en4` to `en6`
with no address now.

## What is already known about Ethernet on this board with the open flow (recorded)

- **Pins.** `~/trinity/fpga/openxc7-synth/ax7203_rgmii.xdc` gives 15 pins for
  port 0 (KSZ9031RNX PHY). They match LiteX's `alinx_ax7203` platform
  (litex-hub/litex-boards) on all 15 pins (checked). LiteX sets `LVCMOS33` on
  them; our file leaves IOSTANDARD unset, and that has to be fixed before a
  build.
- **The RGMII receive clock** is on SRCC pin B17. It routes only with
  openXC7/nextpnr-xilinx #110, which the local `nextpnr-xilinx` includes
  (`a17f9415`, checked).
- **The hardware IDDR does not capture** through the open flow:
  openXC7/nextpnr issue 22 (moved from nextpnr-xilinx #114), still open,
  last updated 2026-09-22 (checked). The earlier gigabit work captured RGMII
  in fabric logic instead. At 1000 Mb/s the skew margin was used up at
  full-size frames: step 31 of 31 at 1,514 bytes, against step 26 for ARP.
  That is from the operator's notes of 2026-08-09, not re-run.
- **The gigabit link came up on 23 of 48 power-ups.** The cause is open, and
  the switch was never checked (operator's notes).
- **RXC runs whether or not there is a link.** The honest link indicator is
  RGMII in-band status: RXD while RX_CTL is low gives link, speed and duplex
  (operator's notes).
- **The 200 MHz oscillator path** (R4/T4, `DIFF_SSTL15`) is "still pending"
  proof on silicon, per `fpga/HARDWARE_REFERENCE.md`. The node runs on
  CFGMCLK, which is only bounded to 65.6 to 68.7 MHz (`TERN_TC_WEAK_POINTS.md`,
  point 6). An Ethernet TX clock has to be within about 100 ppm, so CFGMCLK
  cannot drive one.

## Plan

**Run at 100BASE-TX first.** Its RGMII clock is 25 MHz: a 40 ns period
against 8 ns at gigabit, so fabric capture has five times the period to work
with. That is about 100x the UART rate, and it avoids the two open gigabit
problems (margin at full frames, and 48 % link-up).

Each step has a build or simulation gate. Nothing is flashed without the
owner's yes.

| step | what | gate | board? |
|---|---|---|---|
| E0 | LAN check above | done | no |
| E1 | 200 MHz heartbeat on UART, built with `tri fpga-build`, using the existing `specs/fpga/constraints/dual_clk_heartbeat_ax7203.xdc` | builds; then one flash proves the 200 MHz path | yes, 1 flash |
| E2 | PHY bring-up: release `phy_rst_n`, advertise 100M only over MDIO, report in-band status on UART | Icarus testbench on a KSZ9031 status model; build | yes, 1 flash |
| E3 | ARP + ICMP responder at 192.168.1.222 | Icarus testbench on frames generated in Python; build; board step pre-registered in `specs/trinet/eth_arp_icmp_e3_ax7203.t27` | ping from the Mac, judged by `eth_arp_icmp_ax7203.py --judge` |
| E4 | UDP bridge: K TRI-NET frames per datagram into the unchanged node core. **OP_SETKEY is refused on UDP**; the key is set over UART only. | co-sim with `formal/tern_tc_layer_rtl_tb.v`-style streams; build | pre-registered 640-job check, then `--all` |
| E5 | Harness transport `--udp HOST:PORT` in `tern_tc_layer_ax7203.py`, with no change to the checks | self-test with a software cell over loopback UDP | with E4 |

### E1 build, 04:09 UTC (checked; not flashed)

The command was `tri fpga-build --top dual_clk_heartbeat_ax7203 --src
fpga/vivado/dual_clk_heartbeat_ax7203.v --xdc
specs/fpga/constraints/dual_clk_heartbeat_ax7203.xdc --no-node-params`.

- All four steps returned rc=0, in 33 s total.
- `IBUFDS` on R4/T4 fed `BUFGCTRL_X0Y0` through dedicated routing.
- Post-route Fmax was 336.7 MHz on the 200 MHz domain and 308.6 MHz on
  CFGMCLK. The XDC's 5 ns constraint did not reach the net: nextpnr checked
  against its default 50 MHz, so the margin was read off Fmax, not off a
  constraint.
- Payload sha256 `4e1c0111f1e2be28fd48735ce5b366d2bf35bcbcefc60db7486db956e24ebb6a`.

So the open flow builds the 200 MHz input. Whether the oscillator runs is
still unproven: that needs the flash in E1, and so the owner's yes.

### E2 build and simulation (checked; not flashed)

Files: `fpga/vivado/eth_phy_status_ax7203.v` (what it does is in its header),
`specs/fpga/constraints/eth_phy_status_ax7203.xdc`, the testbench
`formal/eth_phy_status_tb.v` with a KSZ9031 MDIO and RGMII model
`formal/ksz9031_status_model.v`, and the checker
`conformance/eth_phy_status_ax7203.py`. With no arguments the checker runs all
three gates below and prints `RESULT PASS` or `RESULT FAIL`. `--port` reads a
real board's lines; it has not been run, because nothing is flashed.

**Build.** `tri fpga-build --top eth_phy_status_ax7203` with `--nosrl`, all
four steps rc=0.

- 848 LUT, 939 FF, and no CARRY4, DSP or BRAM.
- Post-route Fmax was 133.26 MHz on mclk, against the 68.7 MHz worst case,
  and 174.61 MHz on RXC, against 125 MHz. After placement the figures were
  126.37 and 201.01 MHz. As with E1, nextpnr checked against its default
  50 MHz, so the margin comes from Fmax, not from a constraint.
- Payload sha256
  `0b6d7820fbf96b2e7d4113b63e1eff638e5cbcd55769fd6f3ab6c787c5ceeac1`.

**Static timing of the full parameters,** at both ends of the measured
CFGMCLK range:

| | 65.6 MHz | 68.7 MHz | datasheet |
|---|---:|---:|---|
| PHY reset pulse | 15.98 ms | 15.26 ms | >= 10 ms |
| wait before MDIO | 31.97 ms | 30.53 ms | >= 100 us |
| MDC | 2.050 MHz | 2.147 MHz | <= 2.5 MHz |
| poll period | 512 ms | 488 ms | |
| reset after no link | 15.3 s | 14.7 s | |

The 24-bit RXC counter holds 125 MHz over the window at both clocks.

**Simulation.** Icarus, scaled timers (reset 2^6, wait 2^7, poll 2^17, window
2^12, no-link reset after 4 polls). The same judge runs on every scenario. It
checks the TB counters (model errors, X on MDIO, bus contention, a non-zero
TX pin, UART framing), the line sequence, the PHY answer map and PHYID, both
read-backs (g9 0300>0000, a4 01E1>0181), and the retry count. It also checks
the RXC count, within +-2 of the model's clock.

| scenario | RTL | gate level |
|---|---|---|
| link: model links at 100 FD after auto-negotiation | PASS, 66 MDIO frames, last line `100FD`, in-band `B`, 468 frames, RXC 24.99 MHz | PASS, byte-identical to RTL |
| no link: model never links | PASS, 108 MDIO frames, `rt` 0 then 1 from line 5, RXC 125.00 MHz, 0 frames | PASS, byte-identical to RTL |

Both gate runs print the same UART lines as RTL, byte for byte (`cmp`), and
`RESULT PASS` (10:55Z; 626 s and 908 s of simulation). Bus contention is
counted in the RTL runs only: the netlist has no `mdio_oe` net to probe.

The gate-level netlist is `synth_xilinx -flatten -abc9 -nocarry -nodsp -nosrl`,
the flags the build uses, simulated against Yosys's `cells_sim.v`. It is
synthesised with the **scaled** parameters, so it checks the synthesis of this
logic, not the exact bitstream above. That bitstream differs only in counter
widths.

**What the simulation cannot show.** The PHY model and the RTL come from one
reading of the KSZ9031 register map (9, 4, 0, 1, 0x1F). A misreading shared by
both would pass. That in-band status appears on RXD at all rests on the
operator's notes of 2026-08-09, quoted above; the model assumes it. Pin
timing, the real reset behaviour of the PHY, and the cable are not modelled.
The board read (`--port`) is the first test of any of these.

**Before any flash.** The XDC header says to open VCCO_16 first. The Ethernet
pins and, in `ax7203.xdc`, the user LEDs share bank 16 with different
IOSTANDARDs, so one of the two files is wrong. The flash command is printed by
`tri fpga-build`, not run. It needs the owner's yes.

### E2 on the board, 2026-09-27 12:14Z to 12:42Z (measured)

The owner said yes to both flashes ("все три", variant 1 of the loop report)
and typed the sudo password for each. One attempt, no reruns.

| step | log | result |
|---|---|---|
| flash E2, payload `0b6d7820…c5ceeac1` | `board_runs/e2_flash.log` | loaded, 12:14:19Z to 12:27:37Z |
| read 6 report lines at 1144744 baud | `board_runs/e2_phy_status.log` | 6 of 6 lines read, 12:27:37Z to 12:27:40Z |
| flash the node back, CI payload `ee75d97b…3f39f03` | `board_runs/node0_restore_after_e2.log` | loaded, 12:27:40Z to 12:40:39Z |
| `--setkey`, then `--all --window 24` | `board_runs/tern_tc_all_w24_after_e2.log` | `receipts verified (tag) : 403200/403200 under node 0x5452494e`, rows 33792/33792, 85.81 s, exit 0 |

All four logs have 0 hits for the key and are under 4 KB.

**What the six lines say,** field by field:

| field | n=2 to n=6 | n=7 | reading |
|---|---|---|---|
| `pm`, `id` | `00000000`, `FFFFFFFF` | same | **no address of 32 answered MDIO**: no PHY pulled TA low, every read is all ones |
| `ib` high nibble | `1` | `1` | bit 1 clear: no MDIO answer; bit 0 set: in-band status was seen on RXD |
| `ib` low nibble | `0` | `C` | the link bit is clear on every line. `C` has the 1000 and full-duplex bits set with link down |
| `rc` (RXC) | 24.91 to 24.92 MHz | 124.52 MHz | the PHY clocks RXC, so it is out of reset and powered |
| `fr` | 0 | 0 | no frames |

**A display artefact, corrected in the reader after this run.** Each decoded
line printed `speed=1000 fd=True`. Those two fields come from the MDIO PHY
control register `pc`, which read `FFFF` because nobody answered, so they said
nothing. The reader now prints them as `-` when no PHY answered. In `--port`
mode it also prints a `board:` line with the counts of MDIO answers, in-band
status and in-band link, and says that its `RESULT` counts lines read, not a PHY
verdict. The log above is the unchanged original; `--parse` on it now prints
`speed=- fd=-`.

**What it shows.**

1. **MDIO is silent at every address.** This is a real failure and is not
   explained yet. The PHY is alive (RXC runs and changes rate), so a held reset
   is unlikely. Candidates are listed below.
2. **Link did not come up within the read, which is inconclusive.** The six
   lines are one poll each, about 0.5 s apart, so the read covered about 3 s
   right after the PHY reset. The RXC rate and the in-band nibble changed on the
   last line (25 to 125 MHz, `0` to `C`), which fits a PHY still negotiating
   1000 full duplex when the read stopped. Gigabit auto-negotiation commonly
   takes about 3 s. `--lines 6` was carried over from the simulation, whose
   timers are scaled. On the board it is too short.
3. **The node came back.** It is the same CI bitstream as at 08:51Z, and the W24
   control passed again with every receipt verified.

**For the next E2 read (needs a flash, so the owner's yes).** Read at least 40
lines, about 20 s, which is more than one no-link reset period (14.7 to
15.3 s). Note in the log what the cable's other end is.

**Hypotheses for the silent MDIO** (first written before the FASM check below;
none tested on the board):

- MDC or MDIO lands on the wrong package pin, or the two are swapped. The
  constraint file follows LiteX's `alinx_ax7203` (B16 MDC, B15 MDIO); the
  routed FASM has not been checked against it.
- The MDIO output enable does not reach the IOB, so the FPGA never drives the
  line. The testbench counted contention only at RTL level, and the gate netlist
  has no `mdio_oe` net to probe.
- The PHY needs an MDIO pull-up that the board does not fit, and the FPGA does
  not enable one.
- The PHY is not the one the model assumes. That alone would not explain
  silence at all 32 addresses, because registers 2 and 3 are standard.

**FASM check, 2026-09-27 after the run (read-only; checked, not tested on the
board).** In `/tmp/trinet-node-build/e2/node.fasm`, the build that was flashed:

- B15 (MDIO) is `LIOB33_X0Y235.IOB_Y0` with an input buffer, LVCMOS33, 12 mA,
  slow slew, no pull. Its OLOGIC tile has the output path (`OQUSED`, `OMUX.D1`)
  and the tristate route (`LIOI_T0.LIOI_OLOGIC0_TQ`,
  `IOI_OLOGIC0_T1.IOI_IMUX15_1`).
- `LIOI3_X0Y235.OLOGIC_Y0.ZINV_T1` is absent: `grep -c ZINV_T1 node.fasm`
  prints 0. In prjxray this bit is `1 ^ IS_T1_INVERTED`, so an absent bit is not
  "unset"; it means the T input is inverted.
- In `node_routed.json` the IOBUF became an OBUFT plus an input buffer. T is
  driven by a LUT1 NOT of `mdio_oe` and routed by router1 through OLOGIC
  site-internal pips. nextpnr-xilinx `fasm.cc` writes no FASM for
  site-internal pips, so the bit is never emitted. nextpnr.log has no warning.
- The fix exists upstream and is reverted in the tree used here:
  `6bc9a7ef fix missing ZINV_T1 bits when routing tristate IOs with router1`,
  then `d1524b4c Revert ...`. Both are ancestors of `7037c948`, the build's
  HEAD. Why it was reverted is not established.

**Ranked, after the check:**

1. **Tristate polarity inverted (missing ZINV_T1).** The pad drives while the
   FSM means to listen and floats while it means to talk. The PHY never sees a
   preamble or a start pattern, so it never answers, and in every listen phase
   the FPGA reads back its own idle 1s. That gives `FFFF` at all 32 addresses
   with `pm=0`, which is every line of the log. It also means the RXC change
   from 25 to 125 MHz is the PHY's own doing, not an E2 write.
2. Wrong or swapped pins. Three sources agree on B15/B16 and bank-16 RX pins
   next to them work, so this is now less likely.
3. Pull-up, drive or IOSTANDARD. None of these produces `FFFF` everywhere on
   its own.

**Cheapest test that separates 1 from 2 (needs a flash, so the owner's yes).**
Add the single line `LIOI3_X0Y235.OLOGIC_Y0.ZINV_T1` to the FASM and re-run
`fasm2frames` and `frames2bit` without re-running P&R. Off the board, confirm the
frames differ from the flashed ones by exactly that one bit. Then flash it:
hypothesis 1 predicts `pm` with a PHY bit set and `id=00221622` (KSZ9031, the
ID an earlier bring-up read, `formal/ksz9031_status_model.v:12`), and hypothesis
2 predicts `FFFF` again. The lasting fix is to re-apply `6bc9a7ef` or route
with router2, and to gate CI on `ZINV_T1` being present for every IOBUF pin.
Note that the node build uses `--nosrl` because SRL hangs router1, so moving
off router1 is not free.

### The one-bit fix, checked off the board (not flashed)

Two builds carry the fix. Neither has been on the board.

- **Hand-edited (`e2z`).** It is the flashed E2 FASM plus the single line
  `LIOI3_X0Y235.OLOGIC_Y0.ZINV_T1`, then `fasm2frames` and `frames2bit`, with no
  new P&R.
- **Patched engine (`e2p`).** P&R was re-run with nextpnr-xilinx and the
  ZINV_T1 fix backported. The work is in a local branch,
  `fix/zinv-t1-pad-pip` at `f3a8c73c`, not pushed. Its FASM has the ZINV_T1
  line in place of the pad pip line `LIOI_T0.LIOI_OLOGIC0_TQ`. That line sets no
  bits, and the frames are equal without it.

| check | result |
|---|---|
| frames, flashed E2 against `e2z` | one bit differs: frame `0x0002001E`, word 73, bit 3 |
| frames, `e2z` against `e2p` | identical, byte for byte |
| payload from the sync word, flashed E2 against `e2z` | 6 bits in 3 bytes: that bit, and 5 bits of word 50 of the same frame, which is the frame's ECC that `frames2bit` recomputes |
| `tri fpga-tristate` on the three FASMs | flags the flashed E2; passes `e2z` and `e2p` |

**What changed in `tri fpga-tristate`.** At first the check looked only for the
pad pip line. On `e2p`, which has no such line, it therefore saw no tristate at
all, and it would have passed that build even with ZINV_T1 missing. It now also
keys on the routed T1 input, `LIOI3_X0Y235.IOI_OLOGIC0_T1.IOI_IMUX15_1`. That is
a real pip with bits, present whichever writer ran. A copy of `e2p`'s FASM with
the ZINV_T1 line removed is now flagged.

**The bitstream** is `artifacts/bitstreams/e2_eth_phy_status_zinv_t1.bit`. The
file is gitignored; its hashes are in the tracked `.sha256` next to it. Its
payload is `be28e221…0161e637`.

**Prediction, written before the flash.**

- **Hypothesis 1 (inverted output enable).** The `board:` line counts MDIO
  answers above 0, `id` reads `00221622`, and `pm` has a PHY bit set.
- **Hypothesis 2 (pins).** `id` reads `FFFFFFFF` at every address again.

The link bits are not part of either prediction. The cable's far end is the
router. `fpga-run` has no field for that, so the record states it.

**Board steps.** Each flash needs the owner's «да», and the owner types the
sudo password. There is one attempt per step name. The port is whatever
`tri fpga-usb` names at the time.

```
tri fpga-usb
tri fpga-ioclients
tri fpga-flash e2z_flash artifacts/bitstreams/e2_eth_phy_status_zinv_t1.bit --owner-yes "QUOTE" --expect be28e221
tri fpga-run e2z_phy_status -- python3 -u eth_phy_status_ax7203.py --port /dev/cu.usbserial-110 --lines 40
tri fpga-flash node0_restore_after_e2z artifacts/bitstreams/trinet_node0_ci30762491794.bit --owner-yes "QUOTE" --expect ee75d97b
tri fpga-run tern_tc_all_w24_after_e2z -- python3 -u tern_tc_layer_ax7203.py --all --setkey --port /dev/cu.usbserial-110 --baud 1144744 --keys ../trinet-keys.txt --model /Users/playra/igla-coder-gpu/c_infer/model.bin --window 24
tri fpga-keycheck
```

- **`--lines 40`** covers about 20 s, more than one no-link reset period.
- **The last two runs** return the board to the node and repeat the W24
  control, as after the first E2.

### E2 with the one-bit fix on the board, 2026-09-27 16:03Z to 16:16Z (measured)

The owner said «все три» to variant 3 of the 15:34Z loop report and typed the
sudo password for each flash. One attempt per step, no reruns. The cable's far
end is the router.

| step | log | result |
|---|---|---|
| flash `e2z`, payload `be28e221…0161e637` | `board_runs/e2z_flash.log` | loaded in 778 s, 16:03:00Z to 16:16:07Z, exit 0 |
| read 40 report lines at 1144744 baud | `board_runs/e2z_phy_status.log` | 40 of 40 lines, 16:16:07Z to 16:16:27Z, exit 0 |
| flash the node back, CI payload `ee75d97b…3f39f03` | `board_runs/node0_restore_after_e2z.log` | loaded in 778 s, 16:16:27Z to 16:29:26Z, exit 0 |
| `--setkey`, then `--all --window 24` | `board_runs/tern_tc_all_w24_after_e2z.log` | `receipts verified (tag) : 403200/403200 under node 0x5452494e`, rows 33792/33792, 85.20 s, exit 0 |

All four logs have 0 hits for the key and are under 10 KB. The node is back and
passed the same control as after the first E2.

The reader's own summary line:

```
board: 40/40 lines read; PHY answered MDIO on 40, in-band status seen on 40, in-band link up on 36.
```

**Against the prediction.**

- **Hypothesis 1 (inverted output enable): confirmed.** Every line has
  `pm=00000002` (one PHY, at address 1) and `id=00221622`, the KSZ9031 ID the
  prediction named. `rt` is `00` on every line.
- **Hypothesis 2 (pins): refuted.** No line reads `FFFFFFFF`.

So the one missing config bit, `LIOI3_X0Y235.OLOGIC_Y0.ZINV_T1`, was the whole
of the silent-MDIO failure. The routing, the pins and the RTL were unchanged.
The frames of the patched-engine build `e2p` are byte-identical to `e2z`, so
this result also covers them.

**Outside the prediction.** The link bits were not part of either hypothesis.

| field | n=2 to n=5 | n=6 to n=41 | reading |
|---|---|---|---|
| `g9`, `a4` | `0300>0000`, `01E1>0181` | same | both advertisement writes landed. These are the read-backs the simulation expects: 100M only, as E2 is designed |
| `sr` (BMSR) | `7949` | `796D` | link and auto-negotiation-complete bits set from n=6 |
| `ib` | `30` | `3B` | MDIO answer and in-band status; low nibble `B` is link up, 100, full duplex, as in the simulation's link scenario |
| `rc` (RXC) | 24.92 to 24.94 MHz | 24.91 to 24.93 MHz | 25 MHz, the 100M rate |
| `fr` | 0 | 0 at n=6 and 7, then rising to 27 (`001B`) at n=41 | the RX side counts frames from the LAN |

The link came up about 2 s into the read (lines are about 0.49 s apart). The
first E2 read saw RXC jump to 125 MHz, and the ranked reading above said that was
the PHY acting on its own because no write landed. With the writes landing, RXC
stays at 25 MHz, which fits that reading.

**What this does not show.** It shows MDIO, the PHY's link at 100 full duplex
and a frame counter going up. It says nothing about frame contents, the TX path
(E2 drives no TX data), or the node over Ethernet. Those are E3 and later.

**The lasting fix** is still in the engine, not the FASM: the local branch
`fix/zinv-t1-pad-pip` (`f3a8c73c`, not pushed), or router2. Until then,
`tri fpga-tristate` runs on every FASM before a flash.

### E3 build and simulation, 2026-09-27 17:55Z to 19:19Z (checked; not flashed)

**What it is.** An ARP and ping responder at 192.168.1.222, MAC
02:00:5E:F9:00:01 (both are RTL parameters), on top of E2's PHY bring-up and
report. It answers ARP who-has for its IP and ICMP echo requests to its MAC and
IP, and ignores everything else. What it does, nibble by nibble, is in the
header of the RTL; this section does not repeat it.

Files, all new:

| file | what |
|---|---|
| `fpga/vivado/eth_arp_icmp_ax7203.v` | the design; E2's MDIO and report logic, unchanged except for the new report fields |
| `specs/fpga/constraints/eth_arp_icmp_ax7203.xdc` | E2's pins and IOSTANDARDs, SLEW FAST on the six TX pins |
| `formal/ksz9031_frame_model.v` | E2's KSZ9031 model with frames both ways: plays a stimulus file on RXD, decodes TXD, checks TX timing |
| `formal/eth_arp_icmp_tb.v` | the bench |
| `conformance/eth_arp_icmp_ax7203.py` | the checker. With no arguments it runs `--self-test`, `--static`, `--sim` and `--gate` and prints `RESULT PASS` or `RESULT FAIL`. `--port` reads the board; not run |
| `fpga/openxc7-synth/RAMB36E1_mock.v` | a behavioural RAMB36E1 for the gate run (see "Found on the way") |
| `artifacts/bitstreams/e3_eth_arp_icmp_zinv_t1.bit` + `.sha256` | the bitstream to flash, from the patched engine. The `.bit` is gitignored; the `.sha256` is tracked |
| `specs/trinet/eth_arp_icmp_e3_ax7203.t27` | the board step's prediction and judge, fixed before any flash (see "E3 on the board" below) |
| `conformance/eth_arp_icmp_e3_from_spec.mjs`, `conformance/eth_arp_icmp_e3_params.py` | the spec's generator and its output, the numbers `--judge` reads |

**Design choices, and why.**

| choice | why |
|---|---|
| 100BASE-TX only: E2's MDIO writes advertise 100M and nothing else | 40 ns nibbles; fabric capture has room. The board showed `ib=3B` (link, 100, full duplex) with these writes |
| RXD sampled on the **falling** edge of RXC | the KSZ9031 sends edge-aligned data and adds about 1.2 ns of RX clock delay (the Linux micrel driver's figure, not the datasheet's). Mid-nibble sampling leaves about +-20 ns whatever that delay really is. A second, rising-edge sample is compared inside every frame and the mismatches are counted in `ed`, so the board says whether the choice mattered |
| TXC = RXC inverted: two flip-flops XNORed in one kept LUT2, **no ODDR, no clock net as data** | at 100M the link partner's recovered 25 MHz is within 100 ppm and the PHY re-times TX through a FIFO. CFGMCLK (65.6 to 68.7 MHz) is not a 25 MHz multiple; the 200 MHz oscillator is unproven (E1 not flashed). An ODDR has no model in `cells_sim.v` and has never run in this flow; at 100M both TXC edges carry the same nibble, so flip-flops do |
| TXD and TX_CTL leave flip-flops at the TXC falling edge, through `TX_DLY` = 10 kept LUT1 stages each | the PHY samples TX_EN on the rising edge (mid-nibble) and TX_EN xor TX_ER on the falling edge. Without a delay the data would change on that falling edge (the negative scenario below shows the model flagging it). The chain moves the change some ns later; the bench stands in 3 ns for it |
| SLEW FAST on the TX pins | at the default slow slew, 12 mA LVCMOS33 edges take several ns out of the 20 ns half period |
| transmit only while in-band status reads 0xB (link, 100, full) four nibbles in a row | without a link RXC runs at 125 MHz and TXC with it; TX_CTL stays low then. Frame logic needs 25 MHz and at 125 MHz sees only idle |
| a 2-slot buffer of 2 KiB per slot, one RAMB36 | ping payloads from 0 to 1472 bytes (1500-byte datagram, 1514-byte frame). **BRAM cost:** 4 KiB of one RAMB36, 1 of 365 on the xc7a200t. The required minimum, 56 bytes (98-byte frame), would fit 2 x 128 bytes (2 Kib), an eighth of a RAMB18 or some LUT RAM; the step from there to 1472 bytes costs one block |
| the reply is a template plus bytes read back from the stored request; the IP header checksum and the ICMP checksum of the reply are summed as the request goes by, the FCS as the reply goes out | the frame is received once, checked (FCS, IPv4 header checksum, ICMP checksum), then answered; nothing is sent from a frame that failed a check |
| counters `rx fe ce aq ar eq er ed lk` added to E2's report line | 189 bytes per line; E2's fields keep their order and meaning |

**Known limit: the 2-slot buffer drops in one pattern.** A request is stored if
a slot is free at its SFD, and a slot stays busy until its reply has been
sent. At line rate that never drops unless a request is shorter than the reply
sent before it, such as ARP, ping, ARP, ping at the 12-byte minimum gap. The
dropped request is counted in `aq`/`eq` and not in `ar`/`er`. The scenario
`min_ifg_drop` checks exactly that case, worked out by hand in the checker. A
ping once a second never meets it.

**Static check of the full parameters** (`--static`, RESULT PASS): E2's timers
unchanged at both CFGMCLK ends; the largest ping fits a slot (1514 <= 2048
bytes); IFG 24 nibbles (96 bit times). Counters are 16-bit: a flood of
minimum-size frames wraps `rx` in 0.44 s, a little less than the 0.49 to
0.51 s between report lines. A ping cannot.

**Simulation.** Icarus, E2's scaled timers, frame logic at the real 25 MHz.
Every request is built in the checker with `struct` and `zlib.crc32`. Every
reply is computed there from the protocols, not from the RTL, and compared
byte for byte from preamble to FCS. The judge also checks the preamble (15 x 5
then D), padding to 60 bytes, the idle nibbles between replies (at least 24,
and exactly 24 where the timing forces it), every counter on the last report
line, E2's fields, and zero model errors (TXD/TX_CTL setup and hold of 1 ns at
each TXC edge, TX_ER, TXC period while sending, MDIO). The self-test runs the
judge on made-up output that is wrong in one detail at a time, and it must fail
each.

| scenario | RTL | gate level |
|---|---|---|
| `arp_us`: who-has .222, broadcast and unicast | PASS, 2 exact replies, 200 idle nibbles apart | PASS, same as RTL |
| `arp_other`: who-has .1; a request for us to another MAC | PASS, no TX | PASS, same as RTL |
| `icmp_56`: ping, 56-byte payload | PASS, exact reply 5 nibbles (200 ns) after the request's last nibble | PASS, same as RTL |
| `bad_fcs`: bad FCS, a flipped data bit, a 58-byte runt with a good CRC, a trailing dribble nibble | PASS, no TX, `fe=4` | PASS, same as RTL |
| `not_for_us`: ICMP to .223, to another MAC, to broadcast; UDP; echo reply; fragment; IP options; IPv6 | PASS, no TX, all 8 counted in `rx` only | PASS, same as RTL |
| `back_to_back`: ARP then ping at the minimum 12-byte gap | PASS, both, in order | PASS, same as RTL |
| `icmp_large`: `-s 1000` and `-s 1472` | PASS, both exact | PASS, same as RTL |
| `icmp_small`: `-s 0` with junk padding, `-s 17` (odd length), `-s 18`, a shortened preamble | PASS, 4 exact replies, zero padding | PASS, same as RTL |
| `min_ifg`: 4 ARP then 4 pings, all at the minimum gap | PASS, 8 replies, exactly 24 idle nibbles apart within each run | PASS, same as RTL |
| `min_ifg_drop`: ARP, ping, ARP, ping, ARP, ping at the minimum gap | PASS, 5 replies; the 4th request dropped and counted (`eq=3 er=2`) as worked out by hand | PASS, same as RTL |
| `bad_csum`: bad IPv4 header checksum; bad ICMP checksum | PASS, no TX, `ce=2` | PASS, same as RTL |
| `overflow`: `-s 1000` then two `-s 56` at the minimum gap | PASS, third request finds both slots busy (`eq=3 er=2`); second reply after exactly 24 idle nibbles | PASS, same as RTL |
| `rxd_late_8ns`: RXD 8 ns after RXC | PASS, exact replies; `ed=241` (a rising-edge sample would have failed) | PASS, same as RTL |
| `rxc_late_15ns`: RXC 15 ns after RXD | PASS, exact replies, `ed=0` | PASS, same as RTL |
| `nolink`: the PHY never links (RXC 125 MHz) | PASS, requests counted, nothing sent, `lk=0` | PASS, same as RTL |
| `tx_skew_zero` (negative): no TX delay, data changes on the TXC falling edge | PASS: the model reports 361 errors, as it must | PASS, the same 361 errors |

Final run with no arguments, 18:40Z to 19:19Z under `nice -n 19`, `--jobs 4`: self-test 25 of 25, static PASS, RTL 16 of 16, gate 16 of 16, **`RESULT PASS`**. Log `/tmp/e3sim/run_all.log` (not kept in the repo). RTL runs took 11 to 25 s, gate runs 428 to 770 s. In every scenario the gate run prints the same `TXF` lines, timestamps included, the same report lines and the same `TB` summary as the RTL run (compared line by line).

The checker gained `--judge` (below) after that run. Rerun with
`--self-test --static --sim`, ending 19:37:22Z: self-test 46 of 46 (the 25 above and 21 judge
cases), static PASS, RTL 16 of 16 with the same counters as before,
**`RESULT PASS`**. The gate runs were not repeated: the gate code and the RTL
are unchanged, and the spec pins both.

The gate-level netlist is `synth_xilinx -flatten -abc9 -nocarry -nodsp -nosrl`,
the build's flags, with E2's scaled parameters set by `chparam`. As in E2, it
checks the synthesis of this logic, not the exact bitstream. Cells in the
netlist: 1864 FDRE, 129 FDSE, 6 FDRE_1 (falling edge), 50 LUT1 (the TX
delay chains), 807 LUT2, 327 LUT3, 273 LUT4, 299 LUT5, 527 LUT6, 1 RAMB36E1,
1 IOBUF, 2 BUFG.

**Build.** `tri fpga-build --top eth_arp_icmp_ax7203 --nosrl`, all four steps
rc=0. Resources are the same in every build below: **2316 LUT, 2015 FF, 1
RAMB36**, no CARRY4, no DSP.

| build | engine | post-route Fmax, mclk / rxc | payload sha256 | `tri fpga-tristate` |
|---|---|---|---|---|
| `e3` | archived nextpnr-xilinx (the default), router1 | 80.64 / 86.00 MHz, checked at 50 | `df43fa66a968678a924be69b98b2796ab5c9179e3fcdda5fcbcf90220457ccec` | **flagged**: `LIOI3_X0Y235.OLOGIC_Y0` (MDIO) without ZINV_T1, as with E2 |
| `e3z` | nextpnr-xilinx `fix/zinv-t1-pad-pip` `f3a8c73c`, router1 | 80.64 / 86.00 MHz, checked at 50 | `4fd7923d0d65b06cfffd877c7a73411e73f7d1e2e535b2acff18b49cb6b684c9` | pass, 1 ZINV_T1 |
| `e3h1` | `nextpnr-himbaechel` (nextpnr-live), router1 | 92.11 / 111.54 MHz; rxc FAIL at 125 | `fa48b770ddf8c7364b6225f7b8f5059f1780a5f1d48196b943804fe254bb43b6` | pass, 1 ZINV_T1 |
| `e3h2` | `nextpnr-himbaechel` (nextpnr-live), router2 | 91.75 / 106.53 MHz; rxc FAIL at 125 | `2c1eb0c44bfe71e3abd4340f13a63a30a1b9326c520e7a651c818f9612b3ef36` | pass, 1 ZINV_T1 |

- **`e3z` is the one to flash**: `artifacts/bitstreams/e3_eth_arp_icmp_zinv_t1.bit`,
  payload `4fd7923d…1b6684c9`. It is the same engine and fix as `e2p`, whose
  frames were identical to the `e2z` that ran on the board.
- **What the Fmax numbers mean.** nextpnr-xilinx ignores `create_clock` and
  checks every clock at 50 MHz. With a link, RXC is 25 MHz (40 ns) and every
  rxc path has 86 MHz (11.6 ns) or better. himbaechel reads the XDC, so it
  checks rxc at the 125 MHz of the no-link case and fails it, at 106 to 112 MHz.
  At 125 MHz the frame logic only sees idle and TX_CTL is held low, so that
  fail matters for nothing that is sent. The longest rxc path is the reply byte
  multiplexer (`tbyte`) into the transmit register in `e3z` and `e3h1`, and
  the end-of-frame decision (`v_ping` into the slot bookkeeping) in `e3h2`.
- **Checked in the routed netlists** of `e3z` and `e3h1`: the 50 LUT1 of the
  TX delay chains (5 pins x 10) and the TXC LUT2 survive place and route. The
  six falling-edge flip-flops (RXD, RX_CTL, the TXC half) sit in slices with
  `CLKINV` set in the FASM and no rising-edge flip-flop beside them. nextpnr
  reports no falling-edge path, so their hops (one net each into the
  rising-edge logic, 20 ns at 25 MHz) are not timed by it.
- The build writes Fmax for mclk only into `manifest.json`: see "Found on the
  way".
- himbaechel used `/Users/playra/openxc7-src/nextpnr-live/build/nextpnr-himbaechel`
  as it is, unchanged (binary sha256 `402471c6…9f26bfbd`; its `fasm.cc` carries
  the other agent's uncommitted changes), with its own chipdb, then the same
  `fasm2frames` and `xc7frames2bit`. It warns "ignoring unsupported XDC option
  '-name'" on the `create_clock` line and applies the period anyway.

**Found on the way.**

1. **himbaechel's router2 routes through unused BRAM tiles' cascade wires.** In
   `e3h2`, 24 address nets of the one RAMB36 (at `BRAM_L_X6Y225`) enter
   through the neighbouring, unused BRAM tiles `X6Y220` and `X6Y230`: their
   `IMUX` into `BRAM_CASCOUT_ADDR*`, then `BRAM_CASCINBOT_ADDR*` into the used
   tile, feeding both halves (48 pin connections). The FASM sets
   `CASCOUT_ARD_ACTIVE` and `CASCOUT_BWR_ACTIVE` in those neighbours. prjxray
   knows the bits, but nothing on this board has used them. router1 (`e3h1`,
   `e3z`) enters every pin through the tile's own IMUX. Do not flash `e3h2`
   first.
2. **`tri fpga-build` records no Fmax for `rxc`.** nextpnr pads short clock
   names: `Max frequency for clock  'rxc'` has two spaces, and the regex in
   `fpga/openxc7-synth/build_trinet_node.py` line 252 expects one. So
   `manifest.json` has only `mclk`. The figures above are read from
   `nextpnr.log`. **Fixed 19:25Z** (file time): the regex now takes `\s+`. Run on the
   four E3 `nextpnr.log` files it finds `mclk` and `rxc` in each (80.64/86.00,
   80.64/86.00, 92.11/111.54, 91.75/106.53), where the old one found `mclk`
   only. No build was rerun for it.
3. **`cells_sim.v`'s RAMB36E1 has no behaviour.** Yosys's
   `/opt/homebrew/share/yosys/xilinx/cells_sim.v` declares the ports and a
   `specify` block and nothing else, so every output floats. The first gate
   run failed `arp_us` with X on TXD in the bytes read back from the buffer
   and in the FCS. The gate run now compiles a copy of `cells_sim.v` without
   that module plus `fpga/openxc7-synth/RAMB36E1_mock.v`. The mock covers the
   subset this design uses (true dual port, no output register, no cascade or
   ECC, zero INIT, widths 1 to 36) and stops the simulation on anything else.
   The checker refuses to run if `cells_sim.v` ever gains behaviour for it. The
   mock is written from one reading of UG473, the same reading as the RTL, so
   it checks yosys's mapping (width 9, READ_FIRST, address bits) and not the
   silicon.
   It prints same-address read-during-write collisions. The receiver only
   writes the free slot and the transmitter only reads the busy one, so a
   collision can only happen while the transmitter is idle and its read data is
   unused; every one printed is of that kind (37 in the 16 gate runs, each checked against the `TXF` times: none
   during a frame or the 200 ns before one). Both ports are
   READ_FIRST on one clock, so the read would return the old byte anyway.

**What the simulation cannot show.**

- **The KSZ9031's timing is from memory.** The 1.2 ns RX clock delay and 0 ns
  TX delay are the Linux micrel driver's defaults; the model's 1 ns TX setup and
  hold are the RGMII receiver figures as I recall them. None was checked
  against the datasheet. `rxd_late_8ns` and `rxc_late_15ns` show the receive
  side has about 20 ns either way; the transmit side has no such sweep.

  **Followed up at 19:49Z, against sources rather than memory, but still not
  against the datasheet.**

  - **The driver.** Linux `drivers/net/phy/micrel.c`, last changed in
    `95c4d54ed022` on 2026-09-19, read through `gh api`. Its comment says the
    KSZ9031 has an internal RX delay of 1.2 ns and a TX delay of 0 ns. Both
    match what the model assumed.
  - **The RGMII v2.0 table.** Receiver setup and hold (TsetupR, TholdR) are
    1.0 ns minimum, as found by web search in TI SNLA243 and the HP document.
    That matches the model's 1 ns.
  - **So nothing in the PHY adds TX hold time.** With a 0 ns TX delay, the hold
    after the TXC falling edge is only what the LUT chain gives, as designed.
  - **A fallback if H2 appears, derived from the driver's constants.** The
    driver's pad-skew registers step in 60 ps (MMD 2 registers 4, 6 and 8), and
    their neutral values are 0x7 for data and 0xF for clocks. Writing
    GTX_CLK = 0x00 moves the PHY's sample point 0.90 ns earlier. Writing
    TXD0-3 and TX_CTL = 0xF delays the data by 0.48 ns. Together that is about
    1.4 ns more hold, from MDIO writes alone: no new TX logic. It is not built
    and not simulated. It would be a new pre-registered step, not a change to
    E3.
- **The TX edge timing on the board.** The bench puts TXD 3 ns after the TXC
  falling edge. The real figure is the routed LUT chain minus the routed TXC
  path, and no tool in this flow reports it. If it is under the PHY's hold time,
  the last FCS nibble goes out as an error and the Mac drops every reply; the
  RX counters would still rise.
- **BRAM on this board.** No bitstream from this flow has used a block RAM
  here. `e3z` writes it as two RAMB18 halves at width 4 plus the RAMB36 bit for
  width 9, READ_FIRST, as nextpnr-xilinx's `fasm.cc` does. The mock checks the
  netlist against UG473, not those bits against the silicon.
- **Pin-level effects**: SLEW FAST edges, reflections, the PHY's reset
  behaviour, the cable. VCCO_16 is still not read off the schematic, as in E2.
- **The pre-link 125 MHz case is untimed** (nextpnr-xilinx) or failing
  (himbaechel). Nothing is sent then; the counters and the in-band parser are
  what run at that rate.
- **The host's side**: whether macOS answers its own ARP cache from a reply
  over Wi-Fi through the router, and whether 192.168.1.222 is in the router's
  DHCP pool. E0 saw nothing at .222 at 04:04Z.

### E3 on the board: pre-registered 19:36Z, not run

**The prediction and its judge were fixed before any flash.**
`specs/trinet/eth_arp_icmp_e3_ax7203.t27` holds every number the board step is
judged by:

- the address, MAC and PHY id;
- in-band status 0x3B;
- the `rc` bounds;
- the ping counts;
- the six log names.

It also pins these files by sha256:

- the RTL, the XDC, the model and the bench;
- both mocks;
- the bitstream record;
- the E2z log;
- the checker itself.

`node conformance/eth_arp_icmp_e3_from_spec.mjs` does four things:

1. compiles the spec;
2. runs its test blocks;
3. reads the pinned values back out of the RTL, the checker and the logs;
4. writes `conformance/eth_arp_icmp_e3_params.py`.

With `--check` it fails on drift instead of writing. Because the checker's own
sha is pinned, its judging rules cannot change after logs exist unless the spec
changes too, in the open. `tri fpga-specs` runs the check with every other
generator's.

**Two constants in my notes were wrong. Both were caught before anything
ran.**

- **The address as a 32-bit number was off by 32.** The spec's test block and
  its read-back from the RTL both refused it.
- **The upper `rc` bound was 399648.** Writing the generator's exact
  recomputation showed the ceiling is 399650. The generator now recomputes both
  bounds itself. As a mutation test, a spec with the bound one below 399651 was
  refused by its test block and by the generator.

**The `rc` bounds.** They take 25 MHz ± 100 ppm, counted over 2^20 CFGMCLK
cycles, at the 68.7 and 65.6 MHz ends:

- low bound: floor(24997500 × 2^20 / 68.7e6) − 1 = 381538;
- high bound: ceil(25002500 × 2^20 / 65.6e6) + 1 = 399651.

The E2z log's 36 in-band lines read 388996 to 389366, inside both bounds. A
test block checks that.

**The judge.** `python3 conformance/eth_arp_icmp_ax7203.py --judge` reads the six
logs from `conformance/board_runs/` and prints one verdict. A counter change is
the last `e3_uart_after` line minus the last `e3_uart_before` line, mod 2^16.
The verdicts are tried in this order:

| verdict | when |
|---|---|
| CONFLICT | the `ping -c 2` before the flash got a reply: another host holds .222. Stop |
| **H1** (works), all of | 20 sent and at least 18 received; `arp -an` has .222 at `2:0:5e:f9:0:1`; `eq` rose by at least the replies received, and `er` by as much as `eq`; `aq` rose by 1 or more, and `ar` by as much as `aq`; `lk=1`, `ib=3B` and `id=00221622` on every line; `rc` inside 381538..399651 on every line |
| H4 (no link) | a line has `lk=0` or `ib` other than 3B: E2's link not reproduced |
| H3 (RX broken) | neither `aq` nor `eq` moved |
| H2 (TX or BRAM broken) | `ar` or `er` rose, but the Mac got no reply |
| OTHER | anything else; the judge lists the H1 conditions that failed |

`ed`, `fe` and `ce` are printed as information only.

H2 cannot tell a TX timing fault from a BRAM fault, because the reply's
destination MAC is read out of the BRAM. The next step would be a build that
sends a fixed frame without the BRAM.

**When the judge refuses.** It exits 2 with "not judged" if any of these hold:

- a log is missing or unfinished;
- a command differs from the one listed below;
- the logs' `# start` stamps are out of order;
- the flash log names another payload, or the load did not finish.

`--self-test` runs 21 made-up cases for the judge, covering every verdict and
the refusals. They include counters that wrap between the two reads, and `rc`
on each bound and one past it. On the empty `board_runs/`, the judge refuses
all six logs and exits 2.

**Steps.**

- Each flash needs the owner's «да», and the owner types the sudo password.
- One attempt per log name.
- The port is whatever `tri fpga-usb` names at the time. The
  `/dev/cu.usbserial-110` below is the 09:32Z one.
- `tri fpga-run` runs in `conformance/`.
- `tri fpga-steps E3` reads this block and `board_runs/` and prints which
  steps have logs and what comes next. It prints "none" once any step has
  failed. It runs nothing and judges nothing. Added 20:41:21Z (`date -u`),
  before any E3 log.

```
tri fpga-run e3_preping -- ping -c 2 192.168.1.222
tri fpga-run e3_hostnet -- tri fpga-hostnet 192.168.1.222
tri fpga-usb
tri fpga-ioclients
tri fpga-flash e3_flash artifacts/bitstreams/e3_eth_arp_icmp_zinv_t1.bit --owner-yes "QUOTE" --expect 4fd7923d
tri fpga-run e3_uart_before -- python3 -u eth_arp_icmp_ax7203.py --port /dev/cu.usbserial-110 --lines 10
tri fpga-run e3_ping -- ping -c 20 192.168.1.222
tri fpga-run e3_arp -- arp -an
tri fpga-run e3_uart_after -- python3 -u eth_arp_icmp_ax7203.py --port /dev/cu.usbserial-110 --lines 10
python3 conformance/eth_arp_icmp_ax7203.py --judge
tri fpga-flash node0_restore_after_e3 artifacts/bitstreams/trinet_node0_ci30762491794.bit --owner-yes "QUOTE" --expect ee75d97b
tri fpga-run tern_tc_all_w24_after_e3 -- python3 -u tern_tc_layer_ax7203.py --all --setkey --port /dev/cu.usbserial-110 --baud 1144744 --keys ../trinet-keys.txt --model /Users/playra/igla-coder-gpu/c_infer/model.bin --window 24
tri fpga-keycheck
```

- **`e3_preping` must show 0 received.** If anything answers at .222, stop
  before the flash. The judge would say CONFLICT.
- **`e3_hostnet` must end with `ok` (exit 0).** Otherwise stop before the flash.
  Added 2026-09-27 after the pre-registration, before any E3 log existed; the
  judge does not read this log, and its bytes did not change. The reason: H3
  means "the link is up and the board recognised none of the host's requests".
  The same counters appear when the Mac's packets for .222 never reach the LAN.
  That happens if they go out through a gateway or a VPN tunnel. At 20:14:11Z
  (`date -u`) this Mac had a default route through `utun8` next to the Wi-Fi
  one. `tri fpga-hostnet` reads the kernel's route, the interface's subnet and
  the ARP table, and sends nothing.
- **The two steps together were rehearsed off the board**, at 21:57:48Z to
  21:58:01Z (`date -u`, two runs at once). `ping -c 2` to .222 got 0 of 2
  replies and left `(incomplete)` in this Mac's ARP table. `hostnet` read that as
  "no answer" and said ok. So `hostnet` does not stop on the entry that
  `e3_preping` itself leaves. Nothing answered at .222 at that time. Logs:
  `rehearsal_runs/e3_preping_hostnet_{1,2}.log`.
- **The two UART reads.** Each takes about 5 s. The counters count from
  configuration and never reset, so the ping's effect is the difference between
  the reads.
- **The last two runs** put the node back on the board and repeat the W24
  control, as after E2 and `e2z`.
- **The flash command is written here, not run.** Its raw form is
  `sudo /opt/homebrew/bin/openocd -f fpga/openxc7-synth/ax7203_al321.cfg -c
  "init" -c "pld load 0 artifacts/bitstreams/e3_eth_arp_icmp_zinv_t1.bit" -c
  "runtest 2000" -c "shutdown"`. `tri fpga-flash` adds the payload check, the
  UART lock and the log.

**Prior art (searched 2026-09-27, three web searches plus gh).** No public
report was found of an Artix-7 RGMII design built with the open flow that
answers ARP or ping on a board. The nearest are:

- openXC7/nextpnr#35 (jrrk2): a VC707 SoC whose netlist includes a boot
  loader doing DHCP, ARP and TFTP. It is Virtex-7 over SGMII on a GTX, not
  RGMII. The PR is open and unmerged, and it does not claim a board run.
- openXC7/nextpnr#22: IDDR does not capture on this board. It is open, with 25
  comments, last updated 2026-09-22. E3 works around it with fabric capture.
- enjoy-digital/liteeth#232 (opened 2026-09-26, no replies when read): several
  LiteEth RGMII receivers, the 7-series one included, ignore the falling-edge
  RX_CTL sample, so RX_ER never reaches the MAC. E3 samples RX_CTL only on the
  falling edge, where it carries RX_DV xor RX_ER (RTL line 166). An RX_ER inside
  a frame therefore ends the frame early, and the FCS check drops it into `fe`.
  This was read from the RTL. The RX_ER bench below checks it in simulation.
- The common advice for 10/100 RGMII is to sample on the rising edge. E3
  samples on the falling one. Its reason is that the KSZ9031 changes the
  nibble near the rising edge (RTL lines 11-21). The `ed` counter compares the
  two samples on the board, so the board decides which reason held.

So an H1 would be worth a comment on openXC7/nextpnr#22 with the logs: fabric
capture at 100M answered a ping. Two things limit the wording:

- **Not "first".** A search that finds nothing does not show that nothing
  exists.
- **Nothing is claimed before the verdict.**

**RX_ER bench (simulation; expectations written 21:29:27Z `date -u`, before
the first run).** The pinned bench has no RX_ER, because the KSZ9031 frame
model drives none. `conformance/eth_rxer_bench.py` compiles the pinned TB,
model, RTL and mock unchanged. It adds `formal/eth_rxer_inject.v` as a second
top module, which forces RX_CTL around one falling RXC edge. Each forced edge
prints the RTL's own falling-edge sample, so a case in which the RTL never saw
the error cannot pass. The five cases and what the RTL reading predicts:

- `control`: a ping, then an ARP request, with nothing injected. Both are
  answered, and the counters are rx 2, fe 0.
- `er_in_ip_header`: RX_ER on the ping's data nibble 60. The frame ends there
  at 30 bytes, which counts in `fe`. The tail starts with nibble C and is
  skipped. Only the ARP request is answered, and the counters are rx 2, fe 1.
- `er_in_preamble`: RX_ER on preamble nibble 5. R_PRE clears its "seen a 5"
  flag, the next 5s set it again, and the SFD starts the frame. Both requests
  are answered as if nothing happened. IEEE 802.3 clause 22.2.2.5 marks such a
  frame as errored, so a MAC would drop it.
- `er_then_false_sfd`: RX_ER on nibble 67 of a frame whose payload has `55 D5`
  just after it. The frame ends at 34 bytes, counted in `fe`. The tail then
  reads 5 5 5 D, which is an SFD, so it starts a second frame of 84 bytes that
  also fails its FCS. One errored frame counts rx 2 and fe 2. The ARP request
  after it is answered.
- `false_carrier`: four nibbles of false carrier (RX_DV 0, RX_ER 1, RXD E)
  between the frames. R_PRE sees E and skips until the falling sample drops.
  No counter moves, and both requests are answered.

Result, RTL only (checked), finished 21:34Z. **5 of 5 cases came out as
written.** Every case had model_errors 0 and replies byte-equal to the runner's
reference. Every forced edge was sampled by the RTL as forced (`INJ ...
rtl_falling_sample`), and the edge times differ by the nibble offsets times
40 ns. Counters on the last UART line:

| case | TX | rx | fe | eq | er |
|---|---|---|---|---|---|
| control | 2 | 2 | 0 | 1 | 1 |
| er_in_ip_header | 1 | 2 | 1 | 0 | 0 |
| er_in_preamble | 2 | 2 | 0 | 1 | 1 |
| er_then_false_sfd | 1 | 3 | 2 | 0 | 0 |
| false_carrier | 2 | 2 | 0 | 1 | 1 |

The first invocation did not compile, and no case ran: iverilog refuses a
`force` from an automatic task. The fix was in the injector only, and the
expectations above were left unchanged. The logs are in `/tmp/e3rxer/`, not
kept in the repo, as with `/tmp/e3sim`. Three limits apply:

- The gate netlist was not run here.
- The model's own RX timing is unchanged, so this says nothing about the board's
  edges.
- On the board, `fe` counts errored frames and false SFDs together. One RX_ER
  can add 2 to `rx` and `fe`, so `fe` is an upper bound on the errored frames,
  not a count of them.

The judge does not use `fe` for any verdict (`judge_board`; "`ed`, `fe` and
`ce` are printed as information only" above), so this finding changes no
verdict. It changes only how an `fe` difference in the report is read.

**Where the files point.** This section and the one before it were drafted as
`conformance/E3_DRAFT_SECTION.md` and merged here. The comment in
`specs/fpga/constraints/eth_arp_icmp_ax7203.xdc` still names the draft. That
file stays as built, because the spec pins it.

## Security notes for E4

- Anyone on the LAN can send requests. They can use up capacity, but without
  the key they cannot forge a tag.
- `OP_SETKEY` on an unkeyed node would let the first sender on the LAN choose
  the key. So the UDP path has to refuse it, and a testbench has to show the
  refusal.
- The IP address is static. Whether 192.168.1.222 sits inside the router's
  DHCP pool is unchecked: reserve it in the router, or pick an address outside
  the pool.

## Prior art, for choosing what to build on

- **LiteEth / LiteX.** It has a UDP/IP stack and Etherbone, and a board file
  for this exact board, but its default toolchain there is Vivado. Its RGMII
  PHY uses IDDR (checked: `liteeth/phy/s7rgmii.py`), so under the open flow
  it hits the open IDDR issue above unless the capture is replaced.
- **alexforencich/verilog-ethernet.** MIT license, not archived, last pushed
  2025-02-27 (checked). It has an ARP/IP/UDP stack and a 7-series RGMII PHY,
  also IDDR-based (checked: `rtl/iddr.v`).

Either stack's UDP layer can sit on a fabric-capture RGMII receiver. Writing
a minimal ARP/UDP responder is also small, since there are only two frame
types. Which way to go is the owner's choice. Downloading either stack waits
for the owner's OK.
