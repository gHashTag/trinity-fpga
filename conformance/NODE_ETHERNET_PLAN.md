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
| E3 | ARP + ICMP responder at 192.168.1.222 | Icarus testbench on frames generated in Python; build | ping from the Mac |
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
