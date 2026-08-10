---
name: fpga-synth
description: "AX7203 openXC7 synthesis and flashing. Board truth, the synth recipe, and the failure modes that cost whole sessions. Use for any bitstream, flash, or UART conformance work on the AX7203."
allowed-tools: Bash(docker *), Bash(ls *), Read, Grep, Glob, Write, Edit
---

# FPGA Pipeline — AX7203 XC7A200T

## 🔥 3-BOARD FLEET — all independently flashable + a working inference cluster (2026-08-08)

**Fleet = 3× AX7203 (XC7A200T), each with its OWN onboard FT232H JTAG *and* CP2102N UART.**
This corrects an earlier belief that there is one AL321 JTAG cable that flashes one board at a
time. There isn't — **each board has its own JTAG interface, so all three flash from software
with NO cable-moving.**

- **All three JTAG interfaces share the hardcoded serial `210512180081`** → you MUST address
  by **BUS:DEV, not serial**. `openFPGALoader --scan-usb` lists them; each `--busdev-num`
  detects a valid `xc7a200` independently. As enumerated 2026-08-08 (after a power-cycle):
  **`000:004`, `002:002`, `002:003`** — all three `openFPGALoader -c digilent_hs2
  --busdev-num <BD> --detect` → `idcode 0x3636093, model xc7a200`.
- **UART ports @115200** (CP2102N, serials end `…153e`): `/dev/cu.usbserial-130` (`04f8…`),
  `-2110` (`f29b…`), `-2120` (`6afc…`). **Port names shift across power-cycles/replugs**
  (`1130`→`130` seen) — always re-probe, don't hardcode.
- **USB topology:** 2 boards on one USB2.0 hub (their JTAG at `002:002`/`002:003`), 1 board on
  a USB2.1 hub (JTAG `000:004`). `busdev ↔ UART-port` pairing is NOT stable across replugs —
  for data-parallel it doesn't matter (flash every busdev; the orchestrator finds every UART).
- The `xc7z020` Zynq (if present, on a different FTDI serial) is NOT in this scan — all three
  detected here are Artix-7. Safe to flash Artix bitstreams to all three busdevs.

**PROVEN 3-board inference cluster (data-parallel):**
```
# flash the SAME classifier to all 3 boards (SRAM, ~sec each, reversible by power-cycle):
for BD in 000:004 002:002 002:003; do
  openFPGALoader -c digilent_hs2 --busdev-num $BD board/ax7203_gft_classify3.bit
done
python3 board/cluster_infer.py /dev/cu.usbserial-130 /dev/cu.usbserial-2110 /dev/cu.usbserial-2120
```
Result 2026-08-08: **all 3 boards LIVE 3-class classifiers, 16/16 held-out bit-exact
(round-robin), throughput 253 → 816 inf/s = 3.22× vs single board.** `cluster_infer.py`
(scratchpad/board/) auto-discovers live boards, load-balances over per-board worker threads,
verifies correctness + benchmarks scaling. `classify3` protocol: 8 bytes `(x0,x1)` BE GF-T →
1 byte class {0,1,2}. This is "3 boards = one inference network" (Tier-1 cluster). Tier-2
(peer-to-peer layer pipeline over the boards' GbE / tri-net mesh) is the next step.

## ⚡ FLASH IN 15 SECONDS, NOT 13 MINUTES (2026-08-08 — read this first)

**`openFPGALoader` flashes an XC7A200T bitstream in ~15 s. `openocd` over the AL321 at 100 kHz
takes 778 s — 52× slower.** A whole session was spent at 13 min/iteration before re-reading this
skill. Always reach for openFPGALoader first; keep openocd only for `virtex2 read_stat`.

```
openFPGALoader --scan-usb                                  # find busdevs
openFPGALoader -c digilent_hs2 --busdev-num 002:002 --detect   # -> idcode 0x3636093
openFPGALoader -c digilent_hs2 --busdev-num 002:002 design.bit # ~15 s, prints "done 1"
```
Busdev numbers **shift across power-cycles** (seen: `000:004`/`002:002`/`002:003`, later only
`002:002`/`002:003`). Re-scan; never hardcode. `001:003` (idcode `0x4ba00477`) is an ARM
CoreSight device, **not** an Artix — do not flash it.

### 🧱 The whole openXC7 flow runs NATIVELY on this Mac — no Docker (recipe, 2026-08-09)

Docker is not needed: `yosys` and `iverilog` come from Homebrew, `nextpnr-xilinx` is built in-tree
in the scratchpad fork, and prjxray's tools are built under `prjxray/build/`. Four steps per build:

```
yosys -p "read_verilog design.v gft_mul.v; chparam -set MY_ID 1 top; synth_xilinx -flatten -abc9 -nocarry -nodsp -family xc7 -top top -json d.json"
nextpnr-xilinx/nextpnr-xilinx --chipdb xc7a200t.bin --xdc d.xdc --json d.json --fasm d.fasm --timing-allow-fail --seed 7
PYTHONPATH=prjxray python3 prjxray/utils/fasm2frames.py --db-root <DB> --part xc7a200tfbg484-2 d.fasm d.frames
prjxray/build/tools/xc7frames2bit --part_file <DB>/xc7a200tfbg484-2/part.yaml --part_name xc7a200tfbg484-2 --frm_file d.frames --output_file d.bit
```

**Three traps that each cost a failed run:**
1. `synth_xilinx` takes **`-family xc7`**, not `-arch xc7`.
2. prjxray is **not pip-installed** — `python3 -m prjxray.fasm2frames` fails with
   *No module named prjxray*. Run `utils/fasm2frames.py` in-tree with `PYTHONPATH=<prjxray root>`.
3. `<DB>` is **`nextpnr-xilinx/xilinx/external/prjxray-db/artix7`**, NOT `prjxray/database/artix7`
   — the standalone checkout's `database/` submodule is empty (one `settings.sh`), and the error
   you get is the misleading *"Mapping file .../mapping/devices.yaml does not exist"*.
   As always `--db-root` is the FAMILY dir, never the part dir.

A whole 3-node build takes ~3 minutes end to end, seed 7 routed first try for all three.

### 🧪 Editing FASM directly is the cheapest one-variable experiment

To test whether a single config bit matters, do **not** rebuild nextpnr — `grep -v` the bit out of
the `.fasm`, re-run `fasm2frames` + `xc7frames2bit`, and flash. Everything else in the bitstream is
bit-identical, so the comparison isolates exactly one variable and costs ~40 s instead of ~8 min.
This is how `IFF.ZINV_OCLK` was ruled out for issue #114 (below).

### ❌ Issue #114 (IDDR inert): `IFF.ZINV_OCLK` RULED OUT on silicon (2026-08-09)

Comparing the prjxray DB against `fasm.cc` shows the `ILOGICE3_IFF` (IDDR) branch omits two bits
that the `ISERDESE2_ISERDESE2` branch writes: **`IFF.ZINV_OCLK`** and **`IFFDELMUXE3`**. The OCLK
bit looked like the answer — the IFF's second flop is OCLK-clocked, which would explain why
`DDR_CLK_EDGE` made no difference. **It is not the cause.** Adding it produced captures
bit-identical to the control: `seen_q1=0x0`, `seen_q2=0xF`, bytes `A/B/C=0xF0, D=0x0F` in both,
with live traffic on the wire (dv_edges climbing in both runs).

**Reproduced signature to work from next: Q1 stuck at 0, Q2 stuck at 1** — constant across two
different sample positions inside a frame. That reads as the IFF's Q1/Q2 site outputs never being
connected to the fabric, rather than a mis-set mode bit. **Next lead:** the `pp_config`
pseudo-pip table in `fasm.cc` covers `IOI_ILOGIC*_O` (the combinational output) — check whether an
equivalent entry exists for the IFF's Q1/Q2 outputs. `IFFDELMUXE3` is still untested.

### 📏 Size the counter to the cap, or the counter lies

A telemetry pass counter of 2 bits with an 8-attempt cap always ends at **0** (8 mod 4 = 0), so
`passes = 0` cannot be distinguished from "never retried". Three cold-start rounds were run and the
one question they were meant to answer — did the retry fire? — was unanswerable from the data.
**Whenever a counter is reported modulo N, make the cap N-1 or narrower**, and prefer reporting the
raw attempt count over a wrapped one. This is the same broken-ruler failure as the sticky-OR
liveness detector earlier in this project: an instrument whose range hides the state you care about.

### 🔌 Reconfiguration is not a reset — so PULSE THE PHY RESET PIN FROM THE DESIGN

"Re-flash the node and it comes back" held for most of a long session, then stopped working: about
six re-flashes (lone, staggered, and simultaneous, across two different designs) failed to restore
the network. I concluded a physical power cycle was required. **That conclusion was wrong.**

Reconfiguration really isn't a reset — a state latched inside the KSZ9031 survives it. But on the
AX7203 the PHY's reset is **driven by the FPGA** (pin D16), so the design can issue a real hardware
reset:

```verilog
assign e_reset = phy_rst_n & ~pulsing;   // pulsing is held ~10 ms by the retry FSM
```

Pulsing it for ~10 ms before each reprogramming attempt brought both stuck nodes straight back
(4.0 M and 4.5 M operations, zero errors) from the exact state nothing else had cleared.

**The general lesson: "X is not a reset" does not imply "only a human can reset it." Enumerate which
reset lines the FPGA actually drives before declaring anything physically blocked.**

### 🛑 Bring-up is ~48% and NOT an RTL problem — stop iterating on the design

**Established over 48 bring-ups across four designs**, each node scored on a composite criterion
(`link_up OR ops > 0 OR peers != 0`):

| design | linked |
|---|---|
| zero PHY resets | 5/12 |
| eight PHY resets | 6/12 |
| PHY held in reset ~2 s through configuration | 5/12 |
| final build, composite scoring | 7/12 |
| **pooled** | **23/48 = 48%** (95% interval ≈ 34–62%) |

The arms are indistinguishable within that interval. Quote it as **"roughly half of power-ups,
measured over 48 bring-ups across four designs"** — not as a precise number.

A note on the composite criterion: it was introduced because the PHY status bit had once reported
DOWN on a node that was passing traffic. Scoring both ways in the same run showed **7/12 either way,
with no disagreement in 12 reads** — so that observation was a transient, and the link bit is fine.
Running the check was still correct; the cost was one measurement round.

Indistinguishable. Hypotheses killed with hardware evidence along the way: lost MDIO write (the
register reads back correct on a dead node), retry count, retry interval, simultaneous vs staggered
flashing, 4-minute vs 11-minute settling, and holding the PHY in reset across configuration. Also
retracted: bad cable, dead UART bridge, faulty board — all three boards link at gigabit and run
millions of verified operations.

**Remaining suspects are all outside the FPGA**: switch behaviour when a port re-negotiates
repeatedly, PHY strap resistors sampled at reset, cabling. **The cheapest untried test needs no code
— put one board on the switch alone, or wire two boards back-to-back with no switch**, and measure.
The switch is the leading suspect and is the one thing never varied.

Practical rule meanwhile: flash, read back each node's link bit, re-flash any node reporting DOWN.
One working link is enough to run real workloads.

### ⛔ A properly powered A/B showed the reset knob does nothing

The curve below is **noise**. Re-run with a sound criterion (each node's own BMSR link bit, all three
nodes polled) and 12 bring-ups per arm: **zero resets 5/12, eight resets 6/12.** One in twelve is not
a difference. Four hardware designs and two parameter sweeps went into tuning something that does not
move the outcome, and the apparent 0/4 → 4/6 "trend" came from 4–6 samples per point using a
criterion that conflated a node's health with its peers'.

**Rule: before optimising a parameter, spend the samples to show the parameter matters at all.**
One well-powered A/B first would have replaced the entire sequence below.

Established on 24 measured bring-ups: a node links at 1000M **roughly 45% of the time per power-up**,
independent of reset policy and of which board. All three boards work. Recovery is a lone re-flash.
Since the rate is board-independent, look at what is *common* — switch negotiation when three ports
come up at once, or PHY strap/reset timing at configuration — not at more retry logic.

### 📊 Superseded: "FEWER recovery attempts beat more" (small-sample artefact — see above)

Four designs differing only in how many times the PHY-reset-plus-reprogram attempt may fire, 12 s
apart, each run through three independent reflash-and-settle rounds:

| attempts allowed | nodes converged |
|---|---|
| 1 | 2/6 |
| **3** | **4/6** — op counts jumped to 17–20 M vs 3–7 M |
| 8 | 3/6 |
| uncapped (≥15) | 0/4 — link never came up at all (`rx_all` stuck at 0–3) |

**The curve has an interior optimum**, and I guessed the shape wrong twice on the way there. First:
seeing every node pinned at the cap of 8, I concluded the cap was the constraint and removed it —
strictly worse. Then, reading that failure, I concluded "less intervention always wins" and tried
cap 1 — also worse. The real shape: too few attempts and a PHY that lost the first write is never
rescued; too many and each reset restarts negotiation before it can finish.

**Only measure your way to this.** Both intuitions were plausible and both were wrong; the four-point
sweep took about an hour and settled it.

The **interval** was then swept too, with the cap fixed at 3: **6 s → 0/6; 12 s → 4/6; 30 s → 2/6**.
Both dimensions have an interior optimum and the current setting already sits on it.

Best configuration, now final for this mechanism: **12 s interval, ~10 ms PHY reset pulse, cap 3**
(measured 4/6). Too short or too many, and each reset restarts auto-negotiation before it finishes —
6 s was the worst result measured anywhere, 0/6. Too long or too few, and a PHY that lost the first
write is never rescued.

**Getting past 4/6 needs a different mechanism, not better tuning.** The retry currently triggers on
a proxy ("no peer heard yet"). The honest version is to read MMD 2.8 back over MDIO and retry only
on a verified-bad read — an independent instrument instead of an inference.

### 🔁 A retry loop can be self-defeating — and a distributed search can fail to converge

Two design mistakes made on 2026-08-09, both worth not repeating:

1. **Retrying too fast defeats the thing you are retrying.** Re-writing the PHY's MMD skew register
   once a second to survive a lost first write plausibly restarts link auto-negotiation before it
   can ever complete. The retry visibly ran (`mdio_passes` cycling) and the link never came up.
   **Set the retry interval from the settling time of what you are configuring**, not from
   "as often as possible", and cap the attempts.
2. **Never make a search's stop condition depend on a peer that is also searching.** Auto-calibrating
   the RGMII skew by stepping 21..31 until a peer is heard cannot converge when every node sweeps
   independently — each one's success test needs some *other* node to be simultaneously correct.
   Either calibrate against a fixed reference (a node with a known-good pinned value), or stagger the
   search so only one node moves at a time.

Until this is properly fixed the working procedure is: flash, **read back**, and re-flash any node
reporting `rx_all = 0`. A lone re-flash usually cures it. The known-good build is the one-shot write
with skew pinned at 31.

### ⛔ THE ONE-SHOT-MDIO-WRITE THEORY IS DEAD — read the register back before believing any of it

Everything in the two sections below was built on the theory that a PHY which is not ready loses its
first MMD skew write. **An MDIO read-back disproved it.** A node that was completely down — hearing
nothing, `rx_all = 0`, not even its own broadcasts looping back through the switch — reported the
skew register reading back **exactly the value written**, with the retry counter at zero because no
retry was ever needed.

So the register takes the value fine and the link still does not come up. The retry designs, the PHY
reset pulse, and both parameter sweeps were tuning the wrong knob. Their 4/6-vs-0/6 spread is real
but is not explained by lost writes.

Read them below for the *methods* (they are sound) but not for the diagnosis.

**Do this instead — and it worked:** poll the PHY's own link-status registers over MDIO — clause-22
**BMSR (register 1)**, bit 2 link up and bit 5 auto-negotiation complete, plus KSZ9031 register 0x1F
for speed — and put them in telemetry. Working implementation: `probe/trinet_link.v` (magic 0x8E),
with `trinet_link2.v` (0x8F) retrying on `(!skew_ok || !bmsr[2])`, i.e. resetting the PHY while there
is genuinely no link.

**It immediately split one "mystery" into two ordinary faults:** one node reported
`LINK=1, AUTONEG=1, 1000M` and was entirely healthy (15.4 M verified operations, zero errors) — it
merely had no working peer; the other reported `LINK=0, AUTONEG=0` **after eight hardware PHY
resets**, which is not an RTL problem at all and points at cable, connector or switch port.

**Two rules out of this:**

1. **Put LINK and AUTONEG in telemetry from the first bring-up design onward.** A whole session of
   "lottery", "livelock" and "we need a power cycle" theorising would have been unnecessary with this
   one register visible.
2. **A node that hears no peers is not evidence that *it* is broken.** Any convergence metric built
   on "did I hear someone" silently conflates a node's own health with its peers'. Re-scoring the
   same fleet on each node's own BMSR link bit moved the measured reliability from 4/6 to **5/6**,
   and showed the failure moving between boards — killing a "that board's cable is bad" conclusion
   that was about to be handed over as a physical action.
3. **BMSR bit 2 is LATCH-LOW — read it twice.** A single read returns the latched value after any
   transient, so it reports DOWN while the link is actually UP. Symptom that this is biting: the
   retry counter pinned at its cap on nodes that are demonstrably healthy and passing millions of
   verified transactions. `LINK=UP` readings are trustworthy (latch-low only under-reports);
   `LINK=DOWN` readings and anything derived from them are not.

**The general lesson, which cost several cycles:** a plausible mechanism supported only by indirect
signals will survive any amount of tuning, because tuning changes outcomes without testing the
mechanism. Read the thing itself.

### 〰️ Historical: cause believed to be a ONE-SHOT MDIO write (superseded — see above)

The RGMII skew was programmed over MDIO **exactly once**, ~0.26 s after PHY reset release, after
which the sequencer parked forever. If the PHY was not ready for that MMD write, it was lost and
the board kept the default skew for good — sticky, per-board, never self-healing, cured only
sometimes by a re-flash (each configuration re-rolls the timing).

**Fix: keep re-programming until the node has heard a peer, then stop.**

```verilog
3'd4: begin   // re-program about once a second until a peer is heard
          if (dwell != 28'd65_000_000) dwell <= dwell + 1'b1;
          else begin
              dwell <= 0;
              if (!peer_seen) begin st <= 3'd1; step <= 0; wr_cnt <= wr_cnt + 1'b1; end
          end
      end
```

Gating on `peer_seen` matters: unconditional re-writes would re-touch the skew of a *healthy* link
once a second. Expose the pass counter in telemetry — `wr_cnt` reaching **3** is direct proof that
one write was never enough.

⚠️ **This helped once and then failed to reproduce.** A node that had been dead through two
re-flashes came up and ran 23 M operations with zero errors — but on the next trial both nodes
retried indefinitely without ever converging. The one-second interval is the prime suspect (see the
section above). **Treat the one-shot write as a confirmed defect and this retry as an unproven
remedy** until it survives several cold starts in a row.

**Any one-shot configuration handshake against an external device deserves this treatment**: retry
until an independent signal confirms it took, and report the attempt count so the retry is visible
rather than assumed.

### 🧷 Vary ONE parameter, and build the control with the others held identical

Bisecting frame length against bring-up nearly produced an uninterpretable result: the test builds
differed from the known-good one in **four** parameters at once (frame length, sweep mode, skew,
request interval). A failure could not have been attributed to any of them. Building the control —
same everything, frame length back at its original value — is what made the measurement mean
something, and it exonerated two of the four parameters for free.

Measured (node link-ups, all other parameters identical): 74 bytes on the wire ~48%, 314 bytes 3/8,
714 bytes 4/8, **1514 bytes 0/20**. A sharp threshold, ordinary lottery rate either side of it.
Mechanism still open: 1024 sits in the gap, but the RX and TX indices are both 11-bit, so no
10-bit bound exists in the datapath.

**Watch parameter widths:** `parameter [13:0] IVL0` silently truncated 25 000 to 8 616, so an
interval quoted as 200 µs was really 69 µs.

### 📏 Check frame duty cycle before choosing a request interval

A 1514-byte frame occupies **12.1 µs** at 1 Gbit/s. A design whose request interval sweeps down to
10 µs and 6 µs runs at **121% and 202% duty** at full MTU — saturated, no inter-frame gap, on every
node at once. The same table is fine at 64 bytes (~5%). Compute
`frame_time = (FLEN + 14) * 8 / 1e9` against the interval before believing a load figure: a
throughput number from a saturated transmitter measures the transmitter, not the link.

### 🔁 Audit MDIO designs for HOW OFTEN they write, not just what they write

"Rewriting the PHY configuration restarts auto-negotiation" invalidated **three separate designs**
here: an uncapped 1 s retry (0 links in 4), a 6 s runtime skew sweep built to measure the timing
window, and a *supposedly fixed-skew* build that gated the skew **stepping** but not the
**reprogramming** — its state machine still re-entered the MDIO write sequence every 6 s.

The third is the instructive one: the parameter was named `SWEEP`, the intent was "do not disturb
the PHY", and it disturbed it every six seconds. **Grep every path that can re-enter the programming
state, not just the one that changes the value.** A measurement procedure that perturbs what it
measures yields no data, and looks exactly like broken hardware.

### 🧪 Assume the instrument is wrong until a second signal agrees

Three separate instrument defects surfaced in one investigation on this project:

1. a sticky-OR liveness detector that could not tell "toggling" from "stuck high";
2. a mismatch counter latched into a register and transmitted nowhere;
3. a PHY status bit reading `LINK=DOWN` on a node that was simultaneously passing verified traffic
   and hearing a peer — and it still did so after the documented latch-low double-read fix.

Each one produced a confident, wrong conclusion before it was caught. **Score a condition on a
composite of independent signals, not on one register.** For link state here that means
`link_up OR ops > 0 OR peers != 0` — traffic is proof of a working link whatever the status register
says. Any reliability figure scored on a single bit inherits that bit's defects: the bring-up rates
measured this way may undercount working nodes, so "~45%" is not established.

**Two smaller traps from the same change, both cheap to avoid:**
- A `//` comment inserted **mid-line** into a long single-line block comments out the rest of the
  line, including its `end`. The error surfaced two lines later as "unexpected TOK_ALWAYS".
- A new lint result means nothing until you run the **same lint on the known-good design**. Five
  scary binding errors turned out to be identical in the reference.

### 🔴 When you repurpose a telemetry field, the old field silently becomes a lie

Byte 5 was reused for `{skew_ok, skew_read_back}` and byte 6 for link status. The GF-T mismatch
counter was left latched into `hbad` and assigned to **no output byte at all** — captured internally,
dropped on the floor. Every "zero errors" reading for the next five designs was reading nothing, and
a stale parser expression then decoded the link byte as an error count and produced `errors=200`
(which is `0xC8` = autoneg + link-up + 1000M).

Two rules:

1. **Edit the RTL and its parser in the same change**, and re-derive what every byte means afterwards.
   A decoder pointed at the wrong byte is indistinguishable from a measurement.
2. **A counter that is latched but never transmitted is worse than no counter**, because the
   telemetry still has a field where it used to be and everything downstream keeps reporting it.

What survived here: the success counter increments only on a verified match, so "N verified matching
operations" stayed true. What did not: "…and zero divergences" — divergences had become invisible.

### 🔭 Sweep every serial port for the magic byte — never trust a remembered port name

A board was written off for several cycles as "UART bridge dropped off USB, cannot be diagnosed".
It was answering perfectly the whole time on a port I wasn't reading. Port names have shifted
repeatedly in this project after replugs and power cycles. Probe **all** of `/dev/cu.usbserial*`
and identify boards by their telemetry magic byte, which is what the magic byte is for.

⚠️ zsh trap while doing it: `ls /dev/cu.usbserial* /dev/cu.SLAB*` aborts the **entire** command when
any one glob fails to match (nomatch), so the `ls` never runs and you get a misleading empty result.
Glob one pattern per command.

### 🎲 Bring-up is a LOTTERY: a board can come up with a dead PHY path and never recover

Reproduced repeatedly on 2026-08-09. After a reconfiguration a board may sit with
**`RX_CRC_good = 0` and `peer_mask = 0` while its RXC is demonstrably clocking** (the free-running
sweep-phase counter advances normally). It is dead in both directions — its peers do not hear it
either — and it **does not self-heal**: still zero after 4+ minutes of waiting. Re-flashing that
one board *sometimes* fixes it (node 1 recovered instantly and hit 5.6 M ops; node 2 stayed dead
through two re-flashes).

Consequences for every measurement:
- **Never trust a fleet number without first checking `peer_mask` / RX-good on each node.** A node
  reporting 0 ops may simply have lost its bring-up lottery, and that looks identical to a
  protocol or timing bug. This has now produced two wrong conclusions in this project.
- Re-flash boards **one at a time** and read each one back before flashing the next; a simultaneous
  three-board flash raises the odds of at least one bad node.
- Attribute nothing to an RTL change until a control build has been re-verified **in the same
  session** — see the retraction below for why.

### ⚠️ `done 1` proves configuration happened, NOT that the bitstream is correct

A `fasm2frames` run that dies with `FasmInconsistentBits` still leaves a partial `.frames`, and
`xc7frames2bit` will happily turn it into a normal-looking **9.7 MB** `.bit` that flashes with
`done 1` — and the board is completely silent. **Check `fasm2frames`' exit status**, don't infer
success from file size or from the flasher's output.

Corollary from the same day: `ISERDES.NETWORKING.DDR.W4` and `IFF.DDR_CLK_EDGE.SAME_EDGE` are the
**same physical bit with opposite polarity** — the assembler says so outright. Reading that error
message is a free way to learn which config options are mutually exclusive in the silicon.

### ⚠️ A flash is proven by `done 1`, never by the exit code

`openFPGALoader` **exits 0 even when handed a garbage `--busdev-num` and a nonexistent file.**
Combined with the zsh no-word-split trap (`set -- $pair` inside a `for` leaves `$1` = the whole
packed string, `$2` empty), a three-board flash loop printed `ok` three times and flashed nothing.
The boards kept running the *previous* bitstream, its stale telemetry parsed cleanly, and the
zeros in it read exactly like dead hardware — a full broken-ruler detour.

Write the three flashes as three literal command lines and check the tool's own words:

```
openFPGALoader -c digilent_hs2 --busdev-num 002:002 t3c1.bit 2>&1 | tail -2   # -> "... done 1"
openFPGALoader -c digilent_hs2 --busdev-num 002:003 t3c2.bit 2>&1 | tail -2
openFPGALoader -c digilent_hs2 --busdev-num 000:004 t3c3.bit 2>&1 | tail -2
```
If the design carries UART telemetry, give every build a **distinct magic byte** — the magic is
what tells you which bitstream is actually running, and it is how this mistake was caught
(boards answered `0x81` long after they had supposedly been reflashed to the `0x80` design).

## 🔌 openocd on the AL321: 100 kHz or garbage (2026-08-08, re-learned the hard way)

`scan_chain` at default speed returned **bogus IDCODEs** (`0xebfae8fa`, `0xf5fd747d`, "IR capture
error saw 0x3f not 0x01") — which reads exactly like a dead board. At `adapter speed 100` the
IDCODE is correct and repeatable: **`0x13636093`**. The cfg file itself documents this; I
rediscovered it by panic. **Strange IDCODE → lower JTAG speed FIRST, suspect hardware LAST.**

## ✅ How to actually prove a bitstream configured (not just "loaded")

`openocd`'s "loaded file ... in 778s" only means bits were shifted — it is a signal *inside* the
failure domain. Verify independently:

```
sudo -n openocd -f fpga/openxc7-synth/ax7203_al321.cfg -c init -c "virtex2 read_stat 0" -c shutdown
# 0x401079fc = DONE=1, EOS=1, GWE=1, GHIGH_B=1, MMCM_LOCK=1, DCI_MATCH=1, CRC/ID/DEC_ERR=0
# (reference decode: fpga/bitstream/MANIFEST.md)
```
⚠️ **Broken-ruler trap:** that value looks identical for *any* previously-loaded bitstream. To
prove it was YOURS, do the differential: `xc7_program xc7.tap` (JSHUTDOWN+JPROGRAM) → STAT becomes
**`0x5000190c`** (unconfigured) → reflash → back to `0x401079fc`. Only the erase/reflash cycle
proves it. `openFPGALoader` shortcuts all of this: it prints `done 1` itself.

## 🔬 ALWAYS give a bring-up design a UART telemetry channel

The vendor Ethernet design has **no UART and no LED**, so a dead link was indistinguishable from a
held-in-reset PHY, a wrong pin, or an unplugged cable — hours of blind guessing. The fix that
actually moved things: build a **probe** that reports over UART.

**Reusable skeleton: `trinity-fpga/build/gft_mul/gft_mul_ax7203.v`** (silicon-proven). Key trick —
it clocks off **`STARTUPE2` CFGMCLK, so it needs NO external clock pin**:
- `STARTUPE2 → CFGMCLK` ≈ 65–70 MHz (uncalibrated ring oscillator; **varies per board by ±5%**,
  so use it for ratios, not absolute frequency)
- `BAUD_DIV = 434` → **baud 160000**; pins `uart_tx=N15`, `uart_rx=P20`, `rst_n=T6`,
  `led=B13/C13/D14/D15`
- Working example: `scratchpad/probe/phy_probe_ax7203.v` + `read_probe.py` — counts `rgmii_rxc`
  edges over a CFGMCLK window and streams `[0x5A][cnt31:0 BE][status][0x00]`.

**Measured 2026-08-08 on all three boards:** RXC ≈ 118 / 120 / 115 MHz (one 125 MHz clock; the
spread is each board's own CFGMCLK), `phy_reset_released=1`, `rxctl_seen=1`. That is *functional*
proof on silicon — far stronger than DONE=1 — and it exercised the SRCC clock path end to end.

⚠️ **RXC ≠ link — this nearly produced a false positive.** A KSZ9031 in RGMII drives RXC
continuously regardless of link state, so "RXC ≈ 125 MHz" on all three boards read like three
gigabit links. It wasn't. **Always decode RGMII in-band status** — sample `RXD[3:0]` while
`RX_CTL` is **LOW** (inter-frame gap): `RXD[0]=link up`, `RXD[2:1]=speed (00/01/10 = 10/100/1000)`,
`RXD[3]=full duplex`. ~10 lines of RTL, and it is the only honest link answer short of MDIO.

**🏆 Result with in-band decoding (2026-08-08), reproduced 4×:**
```
usbserial-2120: RXD=0xD -> LINK UP, 1000M, FULL DUPLEX     <- real gigabit link
usbserial-130 : RXC 118 MHz but RXD=0x0 -> link DOWN
usbserial-2110: RXC  24 MHz (100M mode) , RXD=0x0 -> link DOWN
```
A bitstream built entirely on the open flow reads a live gigabit link off the PHY. Note the two
"link down" boards still clock RXC at full rate — exactly the trap above.

**🎉 Packets, not just link (probe v4 — `scratchpad/probe/phy_probe_v4.v`):** count `RX_CTL`
rising edges (= frame starts) and capture the first 8 rising-edge nibbles of a frame.
```
frames_rx 36 -> 52 -> 61 -> 79   (~1/s: background broadcast/multicast)
frame head nibbles = 5555555F    seven 0x5 = ETHERNET PREAMBLE, then F = FF:FF:FF broadcast (ARP)
                     55555551    ... 01:xx IPv4-multicast / STP
                     55555553    ... 33:xx IPv6-multicast
```
That is real traffic received and decoded by open-flow logic — the full chain
`yosys → nextpnr(5 fixes) → prjxray → silicon → gigabit link → packets`, no vendor licence.
⚠️ Scope: RGMII-level capture (preamble + first MAC nibbles). **No CRC check, no MAC layer.**
⚠️ **A frame counter alone LIES:** the link-*down* board reported `frames_rx=23040` (RX_CTL noise).
Always gate the frame count on in-band link status.

**Tip:** only posedge-`rxc` nibbles are visible if you clock on one edge — that is still enough,
because the preamble byte `0x55` gives nibble `0x5` on both edges.

## 🔴 IDDR IS HALF-DEAD ON THE OPEN FLOW — Q1 never fires (openXC7 issue #114)

**Do not build an RGMII receive path on `IDDR` with this toolchain yet.** Measured on silicon,
controlled A-B-A-B on ONE board (same cable, same PHY, only the bitstream changed):

| bitstream reads pins via | in-band status | frames |
|---|---|---|
| raw pins, `posedge rxc` only | `RXD=0xD` → **link up, 1000M, full duplex** | counter climbs |
| `IDDR` (Q1 rising / Q2 falling) | `0x0` → link down | 0 |

Sticky-OR on the raw IDDR outputs: `seen_q1 = 0x0` (never a single bit, all 4 lanes),
`seen_q2 = 0xF`, `seen_dv = 0`, `seen_ctl2 = 1`. P&R passes, timing passes, FASM emits both
`ZINIT_Q1/ZSRVAL_Q1` and `..._Q2` — the config is there, the Q1 **output** is not.

Consequence: every DDR input path silently loses half of every byte, and RGMII in-band link status
(which lives on the rising nibble) reads "link down" forever. Filed as
[openXC7#114](https://github.com/openXC7/nextpnr-xilinx/issues/114).

**Corrected finding (an earlier version of this section was wrong — see the trap below).**
Measured with a *toggle* detector (sticky-one AND sticky-zero), frames confirmed via the raw
`RX_CTL` pin:

| emitted `IFF.DDR_CLK_EDGE` | Q1 | Q2 |
|---|---|---|
| `SAME_EDGE` | stuck **LOW** | stuck **HIGH** |
| neither bit emitted | stuck HIGH | stuck HIGH |
| `OPPOSITE_EDGE` | never high | never high |

**The IDDR captures nothing in any mode** — both outputs sit at constant levels while the pin
carries gigabit traffic. Byte assembly reads `F0`/`FF` where Ethernet preamble `0x55` must be.

**Ruled out:** CKB routing (`CK`-only packing → no change), incomplete routing (both CLK/CLKB and
both Q1/Q2 pips present), missing Q-side config (`ZINIT_Q1/Q2`, `ZSRVAL_Q1/Q2` emitted).
**Diagnosis is open.** Needs a Vivado reference FASM for the three IDDR modes to compare against.

**✅ WORKAROUND THAT FULLY WORKS: fabric DDR capture.** Skip ILOGIC entirely — a normal FF on
`posedge rxc`, a second on `negedge rxc` (yosys infers `FDRE_1`), resync into the rising domain:

```verilog
reg [3:0] rise_r, rise_d, fall_r, fall_sync;
always @(posedge rgmii_rxc) begin rise_r <= rgmii_rxd; rise_d <= rise_r; fall_sync <= fall_r; end
always @(negedge rgmii_rxc)       fall_r <= rgmii_rxd;
wire [7:0] rx_byte = {fall_sync, rise_d};    // NOTE the extra delay on the rising path
```

⚠️ **The alignment costs two iterations if you guess.** In RGMII the rising edge carries the LOW
nibble and the falling edge the HIGH nibble **of the same byte**, but the falling sample only
reaches the fabric on the *next* posedge — so the rising path needs **one extra register**.
Without it the SFD `0xD5` is still found (nibble order is right) and every CRC fails.
**Finding the SFD does not prove alignment. Only the FCS does.**

Measured result (`scratchpad/probe/phy_probe_v14.v`, reproduced over minutes):
```
link=UP 1000M | CRC_GOOD 6 -> 8 -> 17 -> 30 -> 58 -> 62 | CRC_BAD = 0
last CRC register = 0xDEBB20E3     <- exact Ethernet FCS residue
```
Closes timing easily (286 MHz for the capture domain at a 125 MHz requirement) and costs a few FFs
per lane. This also **isolates issue #114**: same pins, same clock, same PHY — fabric works
perfectly, so the fault is strictly inside the `ILOGICE3_IFF` configuration.

**⚖️ ODDR (output side) is FINE — only the input DDR is broken.** Self-loopback with no PHY in the
loop (`scratchpad/probe/oddr_test2.v`): an `ODDR` (`D1=1,D2=0`) drives a pad through `IOBUF(T=0)`,
the same pad is read back by fabric capture, everything clocked from CFGMCLK.
Result `rise ever-1=1 ever-0=1 | fall ever-1=1 ever-0=1` → the pad genuinely toggles.

| primitive | path | works? |
|---|---|---|
| `ODDR` | OLOGIC output | ✅ |
| `IDDR` | ILOGIC input FF | ❌ inert |

**📬 MAC-level reception works** (`scratchpad/probe/phy_probe_v15.v`): capture the first 14 bytes
(dst/src/ethertype) and **commit them only when the FCS checks out**, so a reported header is
always from a valid frame. Live result on the bench:
```
dst=ff:ff:ff:ff:ff:ff (BROADCAST)  src=ee:b8:36:be:2b:6f  type=0x0800 (IPv4)
CRC_GOOD 43 -> 93 -> 101 -> 106,  CRC_BAD = 0
```
**📤 TX WORKS — but only with the PHY's internal TX delay, and here is the measured window.**
`scratchpad/probe/eth_tx_fixed.v` transmits a gratuitous ARP over `ODDR` (4 data + TX_CTL + TX_C).
The frame is constant, so its **FCS is precomputed on the host with `zlib` and baked into a ROM** —
no hardware CRC generator needed.

**Do not try to centre the RGMII TX clock on the FPGA side.** An `ODDR` fed from the data clock can
only make 0° or 180°, and neither lands mid-eye — both fail. The fix is the **PHY's own GTX_CLK
skew over MDIO** (KSZ9031: MMD 2, register 8, bits [9:5]; 0.06 ns per step).

Measured by sweeping skew 0..31 (~4 s per value) while a **second board on the same switch acted as
an independent witness** running the MAC-header receiver:

```
skew 0..20  -> our frame never seen
skew 21..31 -> our frame received, 27 consecutive hits
threshold ~= 21 x 0.06 ns = 1.26 ns   (matches the RGMII-ID requirement)
fixed at skew = 26 (middle of the window) -> witness sees our frame 8/8, rock solid
```

**🌐 The board answers ARP — a standard OS now sees and addresses it**
(`scratchpad/probe/eth_arp_resp.v`). It parses an incoming ARP request (ethertype `0x0806`,
oper `0x0001`, target IP == ours), captures the sender's MAC/IP, builds a reply and **generates the
FCS in hardware** (the frame varies, so a precomputed checksum is no longer an option).

```
ping 192.168.1.222  ->  arp -a:  ? (192.168.1.222) at 2:0:5e:f9:0:1 on en0
board telemetry:  ARP_REQ_MATCHED = 1  ->  ARP_REPLIES_SENT = 1
```
(the ping itself times out — only ARP is implemented, no ICMP.)

**macOS accepting the reply is the proof that the hardware-generated FCS is correct** — a bad
checksum would be dropped silently. TX CRC recipe, verified against `zlib` in iverilog before
touching hardware: init `0xFFFFFFFF`, poly `0xEDB88320`, **final inversion**, sent **LSB-first**
(`ad5f5564` goes on the wire as `64 55 5f ad`).

**🏓 The board answers ping — reliability still ~25%** (`scratchpad/probe/eth_ping4..6.v`):
frame buffer + IPv4/ICMP parse + echo reply.
```
64 bytes from 192.168.1.222: icmp_seq=0 ttl=64 time=7.885 ms
```
macOS accepting the reply proves the IP checksum, the ICMP checksum and the FCS are all correct.

**Two shortcuts worth knowing** (both verified in Python before writing RTL):
- For an echo reply the **IPv4 header checksum is unchanged** — swapping src/dst doesn't change the sum.
- The **ICMP checksum only needs `new = old + 0x0800`** with one's-complement wrap (type 8 → 0);
  no need to re-sum the payload.

**Why it is only ~25% reliable, both diagnosed:**
1. *Marginal timing* — "buffer read + 8 CRC stages in one cycle" lands at 119–132 MHz depending on
   seed against a 125 MHz requirement. **Pipeline it; do not seed-shop.**
2. *Single-buffer race* — RX keeps writing `fbuf` while the reply is being replayed, so background
   LAN traffic clobbers the stored ping. Freezing writes during TX took it 2/10 → 3/10; the real
   fix is double buffering.

⚠️ **The bug that cost three builds: a field register reused across two protocols.** `ipdst` held
IPv4 bytes 30–33, but the ARP target IP lives at bytes 38–41 — so the ARP match silently broke, the
host's ARP entry aged out, `No route to host` appeared, and ICMP never even arrived. The telemetry
then read `ICMP_MATCHED=0`, pointing away from the real cause. **Never share a field register
between protocols with different offset layouts.**

⚠️ **Registered memory reads need the address one cycle ahead** (`fbuf[tidx-7]`, not `tidx-8`).
And when two fixes are in flight, change one at a time — I bundled `ram_style` with the off-by-one
and had to unpick them.

## 🔬 Simulate byte-ordering questions — hardware iteration will not find them

Three consecutive hardware builds failed to locate an indexing bug; an iverilog testbench found
four in minutes (`scratchpad/probe/ping_tb13.v` + `sim_cells.v` with behavioural
STARTUPE2/ODDR/IOBUF models: drive a real ping frame in as RGMII nibbles, capture the transmission,
compare byte-for-byte against a Python-generated reference).

**Bugs it caught that silicon only expressed as "no reply":**
1. **`tx_byte_r` used before it was declared** — yosys accepted it (implicit wire); iverilog refused.
2. **A signal that no longer existed** (`inband`), still referenced by telemetry — again an implicit wire.
3. **⭐ ODDR nibble pairing.** `tx_byte_r` updates on the rising edge, so ODDR samples `D1` with the
   OLD byte and `D2` (half a cycle later) with the NEW one — the two nibbles of one "byte" come from
   *different* bytes. Fix: hold the high nibble one slot back.
   ```verilog
   always @(posedge clk) begin tx_byte_r <= tx_byte; tx_hi_r <= tx_byte_r[7:4]; end
   ODDR u(.D1(tx_byte_r[i]), .D2(tx_hi_r[i]), ...);
   ```
4. **CRC missed the last body byte** when the first FCS byte was computed (non-blocking update lands
   at end of cycle). Fix by forwarding:
   `tcrc_fwd = crc_en ? crc32_byte(tcrc, tx_byte_r) : tcrc;`

Result: the ICMP reply path verifies **byte-for-byte including the FCS**.

**Testbench traps worth knowing (each cost an iteration):**
- FPGA flip-flops power up to 0; in simulation they are X and poison every comparison —
  initialise them hierarchically from the TB.
- A power-on delay counter (`phy_rst_n` waits 0.23 s) never expires in a microsecond simulation,
  and the design's own reset clears whatever you force at t=0 — force it **after** `EOS` releases.
- **Sample ODDR output mid-phase, not on the edge.** On the edge you read the previous half-phase,
  which makes every non-symmetric byte look nibble-swapped and sends you chasing a phantom.

**⏳ A zero counter right after reconfiguration is "not ready yet", not a diagnosis.**
I read `RX_CRC = 0` on a board and concluded its Ethernet cable was unplugged. It wasn't — the PHY
had simply not finished negotiating after the reflash. Even 70 seconds of waiting was not enough
that time. **Before declaring a physical fault, give link-layer state tens of seconds and re-read.**

**🔦 Identify a specific physical board by flashing a blinker to its busdev**
(`scratchpad/probe/ident.v`: all four LEDs at ~4 Hz off CFGMCLK, no UART, no pins beyond the LEDs).
It is visible across the desk, and it **cross-checks itself**: the board's UART goes silent while
the blinker runs and revives when the real design returns — which is how the
`busdev ↔ /dev/cu.* ↔ node-id` mapping was finally pinned down.

**Fleet map (verified this way):** `002:002 ↔ usbserial-2120 ↔ id1`,
`002:003 ↔ usbserial-2110 ↔ id2`, `000:004 ↔ id3` — the last one's **CP2102N bridge dropped off USB**
(its port stays silent through reflashes) while its Ethernet keeps working, proven by id1 hearing it.

**🕸️ Three-node network confirmed:** id1 reports hearing **both** peers `['2','3']`; ~8.7 million
verified GF-T operations across the fleet, **zero mismatches**, ~14k ops/s per node.

**🔧 Verify every batch RTL edit with assertions — three misses this session.**
A search-and-replace keyed on `ti` silently did nothing because the identifier was `tx_i`: the
telemetry array stayed `b[0:7]`, writes to `b[8..11]` went out of bounds, the frame stayed 8 bytes,
and the parser read the *next* frame's magic as data (`RX_CRC = 32768 = 0x8000`). Earlier the same
failure mode hit `reg [7:0] flen;` (one space vs two). The fix is mechanical:
```python
before = s; s = s.replace(old, new); assert s != before, "edit did NOT apply"
# then re-check every intended fragment is present before building
```
**Also: lock a telemetry parser onto a magic that repeats exactly one frame later**
(`buf[i]==MAGIC and buf[i+LEN]==MAGIC`), or it will latch onto a false alignment and hand you
plausible nonsense.

**🔍 Put RX counters in telemetry from the start.** A node reporting "0 transactions" was
indistinguishable from a protocol bug until `RX_CRC_GOOD` was added — it read **0**, meaning the
board was not receiving *background LAN traffic* either. That is a physical link, not a protocol:
its Ethernet cable simply was not connected. One field turned an open mystery into a one-line answer.

⚠️ **After a USB replug, the busdev ↔ UART pairing shifts.** The board that worked as "B" before
the replug is not the board called "B" after it. Re-derive the mapping from what each board *says*
(its own id in the telemetry), never from the port name.

**📊 Load-tested: >1.1 million verified GF-T operations per board, zero errors**
(`scratchpad/probe/trinet3.v`). Dropping the request interval from 250 ms to 100 µs turns the demo
into a measurement:
```
board 1: 1 144 213 ops total   17 393 ops/s   0 errors
board 3: 1 206 168 ops total   17 493 ops/s   0 errors
```
Each "op" is a full round trip: operands out, peer computes on its own silicon, result back,
compared against a local reference. That is a real reliability figure, not a demo.

⚠️ **The bug that made the first load build report zero: a timer that only ran when idle.**
The request interval counter lived inside the "not sending" branch, so with a peer asking at the
*same* rate it could never accumulate a full interval — each incoming request consumed the cycles
it needed. Symptom: everything looks alive (frames flowing, telemetry streaming) but the
transaction count sits at 0. **Free-running timers belong in their own always block**, with a
pending flag the consumer clears:
```verilog
always @(posedge clk) begin
    if (gap == INTERVAL) begin gap <= 0; want_req <= 1'b1; end
    else gap <= gap + 1'b1;
    if (!busy && want_req) want_req <= 1'b0;
end
```
⚠️ And when you move a counter out of a block, **grep for leftovers** — an old
`else gap <= gap + 1'b1;` stayed behind in the FSM, recreating the multiple-driver bug in the same
edit that was meant to fix it.

⚠️ **UART port names shift after any replug** (`/dev/cu.usbserial-3`, `-7` appeared). Re-probe by
reading each port and matching the telemetry magic byte; never hardcode the mapping.

**🧮 Distributed GF-T arithmetic between boards — bit-exact, zero mismatches**
(`scratchpad/probe/trinet_gft.v`). The private `0x88B5` frame carries
`[msg][id][seq][a][b][y]`: one board sends a GF-T16 operand pair, the peer computes the product
**on its own silicon** and returns it, the sender compares against a locally computed reference.
```
board A: matched 63 -> 110 -> 157   mismatches 0   RTT 4.72 µs
board B: matched 66 -> 113 -> 160   mismatches 0   RTT 4.74 µs
```
The core (`trinity-fpga/build/gft_mul/gft_mul.v`, BIAS 40 / OFFSET_MAX 80 / MANT_ONE 512) is
**combinational** — `gft_mul_seq` only registers it — so it drops in with no latency handling.
Two instances (local reference + remote answer) avoids arbitration entirely; on a 200T that is free.

⚠️ **Latch the operands and their reference from the same source.** First version computed the
reference from `op_a`/`op_b` while assigning those in the same cycle, so the reference belonged to
the *previous* pair. Feed the multiplier from the `next_a`/`next_b` wires and latch operands and
reference together.

**⏱️ Board-to-board transaction with a hardware-timestamped round trip: 4.71 / 4.74 µs**
(`scratchpad/probe/trinet_rtt2.v`). Frame `[msg][id][seq]` over EtherType `0x88B5`; msg 1 = request,
msg 2 = response. A board asks 4×/s, answers any incoming request immediately (answering preempts
asking), and when a response carrying its own `seq` returns it latches
`rtt = counter - t_send` — the counter ticks once per receive clock, so 8 ns resolution.
```
board A: 589 ticks = 4.71 µs      board B: 592 ticks = 4.74 µs
```
Symmetric to within 24 ns and stable across readings. The magnitude checks out: a 64-byte frame is
0.5 µs each way at gigabit, plus switch store-and-forward and response turnaround.

⚠️ **Multiple drivers again — second time in two iterations.** `resp_pending` was set in the RX
block and cleared in the TX block. Symptom: peer frames counted fine but RTT stayed 0, because
responses were never built. Fix: the flag belongs to ONE block; the other signals consumption
through a wire (`resp_take = !sending && resp_pending`, same clock domain).
**Standing rule now: after every RTL edit, grep `<=` per register and confirm every assignment
lives in a single always block.** Synthesis will not tell you.

⚠️ **Identify a probe with the right cable type before believing its IDCODE.** The third USB device
reads `0x4ba00477` (ARM CoreSight — meaningless here) with `-c digilent_hs2`, but `0x3727093`
(**Zynq-7020**) with `-c digilent` or `-c ft2232`. It is an FTDI2232 (`0x0403:6010`), not an
FT232H (`0x6014`).

**✅ Replugging the third board's USB restored it** — all three now enumerate
(`000:004`, `002:002`, `002:003`), and all three flash and run. The note below explains why it was
missing and why a power cycle would not have been the fix.

⚠️ **Three boards powered, two flashable — and the reason is not what it looks like.**
All three CP2102N UARTs are alive (serials `04f881b7…`, `f29b9f74…`, `6afc9f45…`, all ending
`153e`), yet `openFPGALoader --scan-usb` finds only two FT232H. **The tell:
`/dev/cu.usbserial-210512180081` opens as an ordinary serial port** — macOS's `AppleUSBFTDI`
claimed one of the three JTAG interfaces and turned it into a COM port, and a device held by the
kernel driver is **invisible to libusb**. Probing busdev numbers outside the scan finds nothing,
confirming it. Root cause: all three FT232H carry the **same hardcoded serial** `210512180081`, so
macOS creates one node for that name and which chip gets claimed is an enumeration race.

**A power cycle does not fix this — it just re-runs the same lottery.** Fixes, in increasing effort:
1. Replug **only** the third board's USB — libusb may win the race this time.
2. Unplug the two working boards, flash the third while it is alone, plug them back. Deterministic.
3. **Write unique serials into each FT232H EEPROM** (`ftdi_eeprom` / FT_PROG). Permanent: after
   that all three always appear and can be addressed by serial instead of a shifting busdev.

**🕸️ Board-to-board over a private protocol, no OS in the path** (`scratchpad/probe/trinet_link2f.v`,
built twice with different `MY_ID`). EtherType **`0x88B5`** (local-experimental), broadcast heartbeat
4×/s carrying `[id][seq]`, MAC `02:00:5E:F9:00:ID`. Each board counts frames from the *other* id
only — your own broadcast comes back through the switch and must be filtered out.
```
board A: TX 208 -> 265 -> 321   frames-from-peer 144 -> 201 -> 257
board B: TX 160 -> 216 -> 273   frames-from-peer 151 -> 208 -> 264
```
Symmetric and sustained. The heartbeat frame was verified byte-for-byte (FCS included) on the
calibrated bench before it ever reached silicon.

⚠️ **The bug that cost the first attempt: `tcrc` was assigned from TWO always blocks** — initialised
in the TX FSM, updated in a separate block. Yosys built it without complaint, the transmit counter
incremented happily, and **nothing appeared on the wire at all** (proven by putting the MAC-header
analyser on the second board: it saw everyone else's traffic, never ours). Fold both assignments
into one block. **Multiple drivers on a register are silent in synthesis and total on silicon.**

⚠️ Use-before-declaration bit again here (`crc_en`) — the fourth time this session. Yosys accepts
it; iverilog refuses. Elaborating the design in a simulator is the cheapest lint you have.

**📏 Full MTU works — and TX skew has to be calibrated on the LONGEST frame you will send.**
```
payload   56 B  ->  25/25, 0.0% loss, RTT 1.6-2.3 ms
payload  200/500/1000/1400 B  ->  6/6
payload 1472 B (1514-byte frame, full Ethernet MTU)  ->  5/6
```
Widening the frame buffer to 2048 bytes needed `bidx`/`flen`/`tidx`/`tlen` at 11 bits — while
leaving byte comparisons (`ipproto == 8'd1`) at 8. Even then large pings failed on hardware at
skew 30 while telemetry showed `ICMP_MATCHED +6 / TX_SENT +6` for both sizes: received and sent
fine, lost on the wire. **Skew 30 → 31 opened the whole range.**

**The pattern has now held three times: longer frame ⇒ more TX skew needed.** Calibrate at the
maximum frame length, not at the middle of the window and not on short frames.

⚠️ **A width bug that only simulation catches cheaply:** a search-and-replace missed
`reg [7:0] flen;` (one space vs two), so `flen = 1046 & 0xFF = 22` and replies were truncated to
18 bytes. On hardware this looks like "big pings don't work" with no further hint; the testbench
printed `flen=22` next to `bidx=1046` immediately.

(Fabric timing again reports FAIL — 115.65 MHz — on the build that works perfectly. Same lesson.)

**🏓 Ping works 100% — and the fix was PHY skew, not fabric timing.**
```
ping 192.168.1.222  ->  30 packets transmitted, 30 received, 0.0% loss, RTT 1.7-2.3 ms
```
Diagnosis came free from existing telemetry: over 10 pings the board reported
`ICMP_MATCHED +10`, `TX_SENT +11`, yet only 2 replies arrived — so nothing was wrong with matching
or with deciding to send; **the transmitted frames themselves were being lost.** ARP replies
(60 bytes) were accepted reliably while ICMP replies (98 bytes) were not — longer frame, more
accumulated skew. Changing `GTX_CLK` skew from 26 to **30** took it from 20% to 100%.

⚠️ **The fabric Fmax report was a red herring here** — the 100%-reliable build actually *fails*
timing (107.56 MHz against a 125 MHz constraint), while a build that passed at 128.95 MHz was
only 20% reliable. **For a source-synchronous interface, check PHY-side skew/alignment first;
fabric Fmax and I/O skew cause different failures.** Two cycles were lost chasing pipelining and
frequency margin.

⚠️ **Calibrate skew on the frame length you will actually send.** 26 was the middle of the window
measured with short ARP frames and turned out to be worse than 30 for 98-byte ICMP frames.

*Known limit, not a bug:* the frame buffer is 256 bytes, so `ping -s 1000` (a 1042-byte frame)
gets no reply. Working build: `eth_ping16b.v`, skew 30, seed 7.

**✅ Calibrate the testbench against a design you KNOW works on silicon, before trusting it.**
Running the proven-on-hardware ARP responder through the harness confirmed a byte-exact reply —
only then were the harness's verdicts on new designs worth acting on. It also surfaced that the
*working* design contained an undeclared signal (`inband`) that yosys had silently turned into an
implicit wire; harmless there because it only fed telemetry, but the same pattern elsewhere is fatal.

**A useful structural fingerprint:** the SFD index in the captured stream. The known-good design
emits it at index 7; any pipeline stage you add shifts it to 8. Matching that index is a quick
check that a new design has the same emission alignment as the one that works.

**Prefer a minimal delta from working silicon over a rewrite.** Three pipeline changes at once
cost a full cycle to untangle. `eth_arp_resp` + frame buffer + ICMP parse (no pipeline, no double
buffer) reached a working ping immediately.

⚠️ **Your primitive models are instruments too — verify them against the datasheet first.**
I modelled `ODDR` as `posedge → Q<=D1; negedge → Q<=D2`. That is **OPPOSITE_EDGE** behaviour. Real
`SAME_EDGE` latches **both** inputs on the **rising** edge and presents D1 during the high phase,
D2 during the low phase:
```verilog
reg q1, q2;
always @(posedge C) if (CE) begin q1 <= D1; q2 <= D2; end
assign Q = C ? q1 : q2;
```
The wrong model reported a "nibble pairing bug" that did not exist; I then "fixed" it and broke
code that had been correct. A model is as capable of being the broken ruler as any detector.

⚠️ **Check the stimulus, not just the design.** My IPv4 test header was built as
`[0x45,0,0] + length(2)` — five bytes where the first four fields take four — so every offset after
it was shifted and the simulation validated the wrong frame. Assert the offsets explicitly
(`byte23 == protocol`, `byte34 == ICMP type`) and use the real frame size (macOS ping = 98 bytes).

⚠️ **Never share a field register between protocols — I made this mistake twice in one session.**
`req_ip` captured bytes 26–29, correct for the IPv4 source address, but an ARP sender IP lives at
bytes **28–31**. The symptom was a reply that looked shifted by two bytes; the cause was the
register holding `0xeeffc0a8` (two bytes of the MAC plus two of the IP). Give each protocol its own
capture register. The earlier instance of the same mistake (`ipdst` reused for the ARP target)
silently broke ARP and produced `No route to host`, which points nowhere near the real cause.

**Trace, don't dump.** With no waveform viewer available, printing one line per cycle
(`tidx / selector / mux output / registered byte`) from the testbench located this in a single run.
Also worth scripting: check the `case` labels for duplicates before suspecting the case statement —
here 42 labels were all unique, which is what redirected suspicion to the data.

⚠️ **Verify TX with a second board, not with `arp -a`.** macOS silently ignores an unsolicited
gratuitous ARP, so an empty ARP table proves nothing. The witness board — capturing everyone
else's traffic happily — is an honest instrument. The sweep-plus-witness method generalises to any
source-synchronous interface whose timing window you need to characterise.

**Topology tip that closed a long-running mystery:** cross-check a captured source MAC against
`arp -a` on the host. Here `ee:b8:36:be:2b:6f` resolved to `192.168.1.100 on en0` — the boards are
cabled into the **real LAN switch**, not into the Mac's USB-Ethernet adapters (which is why
`en4/en5/en6` always read `inactive` while the boards saw a healthy gigabit link).

⚠️ **The first version of that test said "ODDR inert" — and was invalid.** It clocked from
`rgmii_rxc` but the design didn't drive `e_reset`, so the PHY stayed in reset, that clock never
toggled, and the whole measurement domain was frozen. **The tell: all four sticky flags read 0,
which is impossible for any real signal** (a constant-0 pad still sets "ever-zero").
**If your instrument reports an impossible combination, fix the instrument — don't publish the
conclusion.** Also: any bring-up design that uses the RGMII clock MUST drive the PHY reset, or it
has no clock at all.

⚠️ **A sticky OR is a broken ruler for liveness.** `seen |= q` cannot distinguish *toggling* from
*stuck at 1*; both read `0xF`. It made "stuck high" look like a working output and produced a
confident, wrong conclusion that had to be publicly retracted. Always pair it with `zero |= ~q`
and require **both** before calling a signal alive.

**Related trap:** using one pin BOTH as an `IDDR` input AND as a direct fabric input makes the flow
emit two conflicting ILOGIC configs for that site (`IFF.SRTYPE.SYNC` from the IFF plus `.ASYNC`
from the pass-through) → `FasmInconsistentBits`. Take everything from the IDDR outputs instead.

**FCS check (ready, blocked on the above):** reflected CRC-32, poly `0xEDB88320`,
init `0xFFFFFFFF`, run from the byte after the SFD (`0xD5`) through the FCS — the raw register then
equals **`0xDEBB20E3`**. Verified against `zlib` in iverilog before touching hardware, and it closes
timing at 125 MHz (200.9 MHz achieved). Code: `scratchpad/probe/phy_probe_v5.v`.

## ⚠️ Two broken-ruler traps caught in one session — read before diagnosing

1. **Don't read the suspect through the suspect.** I judged "is IDDR Q1 broken?" from in-band status
   that is itself carried on Q1 — circular. The loop only broke by reflashing the *raw-pin*
   bitstream to the *same* board and seeing the link come back.
2. **Put a version/magic byte in every telemetry frame.** A board still running the previous probe
   was parsed by the new reader, and its preamble bytes (`0x55`) decoded as plausible-looking
   liveness flags (`seen_q1=0x5`) — a convincing false positive. Same-length frames from different
   designs will silently cross-parse.

## 🌐 RGMII / Ethernet on AX7203 — verified pinout and traps

**Gigabit Ethernet 0 (KSZ9031RNX), confirmed against `video-ax7203/tx_board/tx_ov5640_eth.xdc`
— AX7203 and AX7103 share this pinout:**
`txc=E18 · txd=C20/D20/A19/A18 · txctl=F18 · rxc=B17 (SRCC!) · rxd=A16/B18/C18/C19 ·
rxctl=A15 · mdc=B16 · mdio=B15 · phy_rst_n=D16 (ACTIVE LOW)`

- Add `set_property SLEW FAST` to every TX pin (the verified reference does; it is easy to miss).
- ⚠️ **nextpnr's XDC parser matches ports by EXACT name and does not expand `[*]`** — a
  `[get_ports {bus[*]}]` line silently does nothing. Write SLEW/IOSTANDARD lines **per pin**.
- ⚠️ **Vendor `reset.v` trap:** its counter (which releases `rst_n`, and hence the PHY reset) is
  **held at zero while `key1 == 0`**. A floating/pressed button keeps the PHY in reset forever.
  In a probe, release the PHY reset unconditionally on a power-on delay instead.

## 🛠️ Open-flow gaps found in nextpnr-xilinx — 5 upstream PRs (2026-08-08)

Taking a full RGMII design to a flashable bitstream hit five distinct tool bugs. All are fixed in
branches off `stable-backports`; each builds standalone. **Status: submitted, NOT merged.**

| PR | Symptom you would see | Fix |
|----|----------------------|-----|
| [#110](https://github.com/openXC7/nextpnr-xilinx/pull/110) | SRCC clock pin (e.g. B17) → `Unable to find legal placement` for the BUFG | preplace BFS cap 50k → 1M (the path is 75 492 wires; MRCC is only 6 069) |
| [#111](https://github.com/openXC7/nextpnr-xilinx/pull/111) | FF-generated (fabric) clock → same placement abort | fall back to `preplace_unique` when `try_preplace` finds no dedicated route |
| [#113](https://github.com/openXC7/nextpnr-xilinx/pull/113) | `STARTUPE2`/`ICAPE2`/`DNA_PORT` → `Unable to find legal placement for cell 'u_startup'` | `preplace_unique` the single-site cfg primitives in `pack_cfg()` |
| [#112](https://github.com/openXC7/nextpnr-xilinx/pull/112) | inferred SDP block RAM → `FasmInconsistentBits` in fasm2frames | don't emit the width-1 bit for the unused port of an SDP direction |
| [#109](https://github.com/openXC7/nextpnr-xilinx/pull/109) | `set_multicycle_path` silently ignored | parse it + apply the multiplier in the timing engine |

**Design-side gap (not a tool bug):** `IDDR` in `SAME_EDGE_PIPELINED` cannot be expressed by the
FASM backend (prjxray encodes only SAME/OPPOSITE). **Never silently substitute `SAME_EDGE`** — it
pairs Q1/Q2 from different clock periods and would corrupt every received byte. Use `SAME_EDGE`
plus a **one-cycle delay on the Q1 group** (rising nibbles + rx_dv); proven bit-identical in
simulation (`scratchpad/ethkit/iddr_same_edge_realign_proof_tb.v`, 1991 checks, 0 mismatches).

## 📦 Bitstream packing traps

- **`fasm2frames --db-root` takes the FAMILY directory** (`prjxray-db/artix7`), *not* the part
  directory — `devices.yaml` lives in `artix7/mapping/` while `<part>/mapping/` is empty.
  Wrong root → `AssertionError: Mapping file .../devices.yaml does not exist` and a 0-line frames
  file, yet `xc7frames2bit` still writes a plausible-looking 9.7 MB `.bit`. **Always check the
  frames line count (expect ~20230), not just that a .bit appeared.**
- `synth_xilinx` **needs `-nocarry`** for these designs: with CARRY4 inferred, placement fails
  deterministically at every seed (`Unable to find legal placement ... carry4`) — this is NOT the
  seed lottery.
- A valid `.bit` is 9 730 7xx bytes with sync `0xAA995566` near offset 157 and the IDCODE write
  `0x30018001` → `0x03636093` right after.
- The `ImportError: antlr_to_tuple ... circular import` from fasm2frames is a **harmless** fallback
  to the slow parser, not a failure.

## Read this before trusting any count below

**`fpga/CATALOG_MATRIX_83.md` is the matrix of record, not this file.** The
counts in the table below drifted from it once already. Check the catalog.

## Environment truth, verified 2026-08-01

- **No local place-and-route.** No `nextpnr-xilinx` binary, and the Docker
  daemon is usually down. Synthesis goes through CI; a plan step that assumes a
  local P&R run will fail. `yosys` and `iverilog` *are* installed, so RTL
  elaboration and simulation work locally.
- **`tri` is not installed and `zig-out/` does not exist.** Any skill step
  invoking `zig-out/bin/tri` or `zig-out/bin/vibee` is dead. `tools/bin/vibee_gen`
  does exist; `tools/bin/vibee_arm64` is a 0-byte file.
- **CI workflows only register from `main`.** Pushing a new workflow to a
  feature branch triggers nothing. Cherry-pick onto a branch based on
  `origin/main` and push there.
- **A flash takes 778 s**, not the ~78 s some notes claim — 9.7 MB at the
  AL321's stable 100 kHz. Run it in the background and pipeline other work.
  openocd's stdout is block-buffered when redirected, so a 0-byte log during a
  flash is not a hang.
- Verify passwordless flash with `sudo -n openocd --version` (NOT `sudo -n true` —
  that fails; the `/etc/sudoers.d/openocd` rule is scoped to openocd). Confirmed
  working 2026-08-05.

## Reproduced end-to-end on silicon + paper data point — 2026-08-05 (updates the above)

The "no local place-and-route / Docker usually down" note above was **not true on
2026-08-05**: `docker` was up, image `regymm/openxc7:latest` present (11.3 GB), and
the **full local openXC7 P&R ran** (it ships nextpnr-xilinx inside the image).

- **Local GF16 bitstream, start to finish:** `yosys synth_xilinx -flatten -abc9
  -nocarry -nodsp -arch xc7 -top gf16_mul_ax7203` → bbaexport/bbasm chipdb
  (`xc7a200tfbg484-2`, slow under QEMU) → `nextpnr-xilinx --placer sa --router
  router1 --timing-allow-fail` → `fasm2frames`+`xc7frames2bit` → real `.bit`.
  Recipe lives in `.github/workflows/ax7203-gf16-*.yml`.
- **nextpnr seed flake (openXC7):** some seeds die with `ERROR: post-placement
  validity check failed for Bel 'SLICE_X…/A5FF' (no cell). Placing design failed.`
  — a placer bug, not your RTL. **Always seed-sweep** (`for s in 1..8; … --seed $s
  --timing-allow-fail; break when the .fasm appears`) and skip a failed seed. Seen
  2026-08-05: gf16_clean seed 1 failed this way, **seed 2 routed** and produced the
  bitstream. Reuse a cached `chipdb/xc7a200tfbg484-2.bin` across builds (same part)
  to skip the slow QEMU `bbaexport`. Do NOT double-background the flow with `( … ) &`
  inside an already-backgrounded call — it orphans the job and you get no completion
  signal.
- **Numbers (reproduced, honest):** yosys est **541 LCs**; nextpnr **27.55 MHz**
  for clock `mclk` (FAIL vs 50 MHz target) on the wrapped `gf16_mul_ax7203` top.
  It still computes correctly on silicon because the datapath is **UART-paced
  (160 kbaud)** — static timing does not gate the slow conformance workload.
- **On-silicon conformance vs golden:** flashed to SRAM, read on `/dev/cu.usbserial-1130`
  @160000. **GF16 mul 5/5** (gf16_mul(1.5,2.0)=0x4100=3.0, …), **GF8 add 5/5**,
  NaN/inf confirmed (exp==0x3F). Bit-exact vs `conformance/gf_ref.py`.
60. **Spec-first GF-T on-chip TRAINER exists and is CI-proven (2026-08-07, t27 gate CI-02 `emit-bitexact-gate`).** A microsequencer (one shared `GftSmul`+`GftSadd`, microcode over a register file, `tools/gft_backprop_microcode.py`) runs a full forward+backprop+weight-update loop in GF-T16, generated to Verilog *and* C *and* Rust from one description. Proven **bit-exact across {Verilog, C, Rust, Python model}** — primitives (`verify_multitarget.py`) AND the whole training loop (`verify_trainer_c.py`), hardened by a differential fuzzer over 250 random topologies (`fuzz_trainer.py`, 4000 edge-injected step-comparisons, 0 divergence); also `yosys synth_xilinx`-checked with a one-shared-multiplier datapath invariant. Any topology/depth (2–4 layers), trainable biases, learns real nonlinear tasks (2-layer ~97% / 3-layer 98% held-out). **This is exactly the automated correctness oracle IGLA RACE's `specs/igla/race/ternary_mac|gemm` lack** (those are sealed/simulated, not multi-target-verified) and the verified GF-T mul/add substrate IGLA CODER's P7 `IGLALowBitTernary` (#1040, still an open conjecture) needs. On-chip *training* is the complement to IGLA RACE's *inference* silicon (train→save→deploy). Blocked only on a physical JTAG re-connect (AX7203 `210512180081`).

### PLAN — feeding this into the papers (arXiv:2606.05017 / 2606.09686)

The synthesis loop exists to **update the publications**. Status:
- **Board §1.2 is OPEN:** three parts are cited for "the" GF16 result — abstract
  **XC7A35T**, `trinity-gf16.tex` body **XC7A100T (QMTECH FGG676)**, this work
  **XC7A200T (ALINX AX7203, FBG484)**. Paper should name one part + package.
- **Fmax is an unstated distinction:** paper's **323 MHz** is the bare-core
  *combinational* max-freq (probe clock `chain[19]`), NOT a routed clocked design.
  A routed wrapper on 200T is ~27.55 MHz static. Report both, labelled.
- **Prepared correction material** (not a submission — needs author arXiv creds):
  `trinity-fpga/research/XC7A200T_GF16_DATAPOINT_2026-08-05.md` (this row + the
  board table + on-silicon conformance vectors).
- **Other pending corrections** are in `trinity-fpga/research/ARXIV_V2_CORRECTION_PACKAGE.md`:
  remove "fabricated TTSKY26b dies" from Paper A abstract; Paper B **84→83** formats
  (`ERRATUM_arXiv_2606.09686_catalog_count.md`); citation fixes. Science holds
  (φ-rule 17/17, Lucas 256/256, ml_dtypes 66,224/0, 83 SHA-256).
- **Blockers:** t27c codegen bug — array-literal `[N]T{...}` not lowered → gf16
  gen-rust AND gen-verilog don't compile (R7; branches `fix/gen-verilog-array-lowering`,
  `fix/r7-rust-wrapping-ops`). ALWAYS compile t27c output, not just `parse=0`.

### Repo map + landing order (for the paper update)

Paper sources (verified 2026-08-05): **Paper A** (2606.05017) EN =
`goldenfloat-preprint/gf_preprint_v19.tex`, RU = `trinity-papers-ru/paper1-goldenfloat/main_ru.tex`
(already has a `sec:hw-ax7203` XC7A200T section noting a routing failure),
derived = `t27/docs/arxiv-submission/trinity-gf16.tex`. **Paper B** (2606.09686) =
`paper3-methodology/main.tex` (still titled "84-Format"). `t27/neurips/gf_paper.tex`
is theory-only (no FPGA). `arxiv_v2_table.tex` holds the bare per-op XC7A200T LUTs.

Nothing is merged yet — land in this order so repo ⇄ preprint agree before any
arXiv replacement (which only the author can submit):
1. **`trinity-papers-ru` PR #17 = commit `925bdf6d`** (remove "fabricated dies",
   standardise on ALINX AX7203 / XC7A200T) — NOT an ancestor of `main`.
2. **t27 codegen branches → master:** `fix/gen-verilog-array-lowering` (`701d79b3`),
   `fix/r7-rust-wrapping-ops` (`377d9a27`), `fix/gen-verilog-typealias`,
   `fix/gf16-conformance-vectors` (5 corrected GF16 vectors), `fix/gf-fpga-audit`
   (GF16 rounding). Then the cited SSOT matches the paper.
3. Apply `ERRATUM_arXiv_2606.09686_catalog_count.md` (84→83) to `paper3-methodology/main.tex`.
4. Apply `ARXIV_ABSTRACTS_READY_TO_PASTE.md` + `ARXIV_BODY_FIXES_READY_TO_PASTE.md`
   (abstract wording, 20 citation defects, `-nodsp` soft-logic subsection).
5. Reconcile board §1.2 using `research/XC7A200T_GF16_DATAPOINT_2026-08-05.md`:
   bare-core combinational 323 MHz vs routed-wrapper ~27.55 MHz; part = XC7A200T-FBG484.

## The failure this pipeline keeps producing: the frame path, not the arithmetic

On 2026-08-01 a first-ever hardware run of `gfternary` scored 7/16 — and the
seven passes were exactly the seven input pairs whose answer is zero anyway.
Root cause was commit `6f3001b17`, titled *"frame format bug fix"*, which
inserted a `0x00` between the `AA 55` magic and the payload across the corpus.
The `fpga/vivado/gf*` wrappers have no `fmt` field, so **32 hosts had been
computing `gf_add(0, 0)` for every input for two weeks.**

Every golden self-test passed the whole time. None of them exercises the wire
encoding.

- **A conformance host is not verified by its self-test.** The encode path needs
  a witness that did not come from the same source file — the RTL in simulation,
  or the board.
- `conformance/frame_alignment_check.py` now compares each host's request length
  against its wrapper's frame FSM, gated in CI. **Run it before any flash
  session**; it costs a second and it is the cheapest possible check.
- When an RTL/host mismatch is suspected, settle it by driving the RTL with both
  byte sequences rather than by reading the Python — see
  `formal/gf8_frame_regression_tb.v`.

## Counts as of 2026-07-14, Wave 13 — verify against the catalog before citing

| Axis | Count | Detail |
|------|-------|--------|
| SW-bitexact | ~62-69/83 | (CATALOG_MATRIX: strict 62, self-consistent 69) |
| decode-HW Tier-E | 41 formats | 41 unique formats with bit-exact decode cells |
| compute-HW Tier-E | 10 GF formats × {ADD,MUL} | GF4-GF32 (10 formats), 0 failures on silicon (vectors vary by run) |
| GF64 ADD | 70.1% (359/512) | timing closure failure; clamp reverted (regressed to 48.9%) |
| DIV/SQRT | binary32 proxy | NOT native GF, stale output bug, no conformance |
| QUIRE | untested | no conformance vectors |

**Honest catalog**: 10 formats bit-exact (add/mul) + 2 proxy (div/sqrt) + 1 untested (quire)
**Paper**: ~41/83 formats (NOT 71 — that was cell count, not format count)

## Synthesis Flags (MEASURED, not assumed)

| Design type | Flags | Notes |
|-------------|-------|-------|
| ADD/SUB | `-flatten -abc9 -nocarry -arch xc7` | -abc9 REQUIRED (removal = 70%→19%) |
| MUL | `-flatten -abc9 -nocarry -nodsp -arch xc7` | -nodsp for MUL only |
| GF16 MUL | uses 1 DSP48E1 | explicitly instantiated, not inferred |

LUT measurements (yosys 0.63, -abc9 -nocarry):
- GF16 parametric adder: 486 LUT
- GF16 old adder: 176 LUT (BENCH-005 "118" was stale)
- tekum16 stub: 573 LUT
- takum16: N/A (RTL doesn't exist)

## Build Recipe

```
docker run --rm regymm ... bash -c '
  yosys -p "read_verilog gf_adder_param.v ${DESIGN}.v; synth_xilinx -flatten -abc9 -nocarry -arch xc7; write_json ${DESIGN}.json"
  nextpnr-xilinx --chipdb /chipdb-xc7a200tfbg484-2.bin ...
  fasm2frames ... && xc7frames2bit ...
'
```

## GF64 Root Cause (Waves 3-8)

**NOT a logic bug** — iverilog 6/6 + Python 1544/1544 ALL_PASS.
**IS a timing closure failure** — 43-bit barrel shifter + 64-bit priority encoder too deep for CFGMCLK.

Timeline:
- Wave 3: root cause found (timing, not logic)
- Wave 4: clamp attempted → -0+0 fixed but overall regressed 70→49%
- Wave 8: clamp REVERTED → HEAD reproduces 70.1%
- Future: 2-stage pipeline is definitive fix

## LESSONS (Waves 1-8, auditor-verified)

1. HAS_INF per-format (only GF16)
2. cur_byte must be reg
3. iverilog is fast gate
4. Provenance before every flash
5. Trinity moat = catalog × open-source-silicon proof
6. Tekum = nearest competitor (GF16 0.85x LUT, not 4-11x)
7. DePIN + openXC7 = strongest niche
8. TX NBA race: use buffer+mux
9. -abc9 REQUIRED (removal = catastrophic regression)
10. GF64 timing: barrel shifter + priority encoder, pipeline needed
11. ELiTeFormer + MxGLUT validate zero-DSP thesis
12. **"4-11x lower LUT" is FALSE** — measured 0.85x
13. BENCH-005 "118 LUT" is stale — same module gives 176
14. takum16 adder RTL does NOT EXIST
15. **div/sqrt = binary32 proxy** — NOT native, hardcoded, stale output
16. **gf_mul_param same timing risk** as adder for GF64+
17. **"71/83 formats" was wrong** — double-counted cells as formats (real: ~41)
18. **"-nodsp mandatory" was wrong** — only MUL uses -nodsp, ADD doesn't
19. **Clamp regressed** — reverted to make HEAD reproducible at 70.1%
20. **build-matrix.yml was dead code** — both if/else branches identical, now fixed
21. **"11392/11392" was FABRICATED** — table sums to 11976, GF16 log shows 512 not 128, no artifact contains it. Replaced with honest per-cell summary.
22. **LUT wrapper committed** — gf16_param_top.v in repo, reproducible from clean clone (491 LUT with -flatten)
23. **LaTeX skeleton created** — paper.tex exists but full conversion still needed for arXiv
24. **27-agent system is vapor** — only self.json exists, verdict.zig missing, tri CLI not built
25. **72 formats have oracle** — 10 new oracle files (posit, bf16, fp8, mxfp, takum, decimal, ieee, legacy, lns, int)
26. **1496 TX race wrappers fixed** — auto-script converted all to buffer+mux
27. **2-stage pipeline implemented but REGRESSED** — iverilog 9/9 but silicon 50.6% (worse than 70.1%). Reverted.
28. **GF64 ceiling = 70.1%** on AX7203/CFGMCLK — no RTL modification improves on original. External clock = only untested approach.
29. **Full LaTeX paper** — 648 lines, 3888 words, research/arxiv_submission/paper.tex
30. **Paper PDF compiled** — 314KB via CI (build-paper.yml), arXiv-submittable
31. **All 12 oracles have self-tests** — gf_ref.py was the last (added Wave 13)
32. **Paper structural count reconciled** — ~10 structural + 2 routing-pending + 3 single-witness = 15
33. **takum64 routing claim was FALSE** — CI failed all 8 seeds, paper fixed to ✗
34. **`make oracle/repro/bench/lut`** — reproducibility from clean clone, no hardware needed
35. **#199 body updated** — honest ~49-55/83 (was stale 71/83 double-count)
36. **Paper is fully honest** — zero known falsehoods remaining
37. **72/72 formats have conformance vectors** — 791,115 vectors via `make vectors`
38. **`make vectors`** — generates JSON vectors for all 72 oracle formats from clean clone
39. **MUL vectors generated** — 72 ADD + 72 MUL = 144 files, 1,559,190 total vectors
40. **Honest catalog coverage = 72/83 THEORETICAL MAX** — 15 oracle modules, 84 format names. Remaining 11 are structural (no decode law). Zero concrete gaps.
41. **SUB vectors generated** — 287 total JSON files (ADD+MUL+SUB), 2,426,879 vectors
42. **61 CI workflows** (was 3388 → 102 → 61). 41 orphan May-era workflows deleted.
43. **arXiv submission checklist** — ALL items checked except "Upload" (user action)
44. **Paper 1 (2606.05017) needs v4**: add GF64 ceiling, takum comparison, FL-002 update
45. **Paper 2 (2606.09686) needs v3**: add 72-oracle suite, reproducibility, replace φ-anchor
46. **Zero citations on both papers** — 3-6 weeks old, no community uptake
47. **Biggest competitor**: Hunhold takum (2404.18603 + FPGA codec 2408.10594)
48. **EXISTENTIAL risk**: OCP-MX (9 citations, silicon shipping) + IEEE P3109 (standards-track)
49. **GF16 = minimum 4/4 ROBUST** — matmul + gradient + dynamic range + attention all pass
50. **FP16 fails dynamic range** (5/11 values lost), **BF16 fails matmul** (10× worse)
51. **φ-rule finds the balance point** where neither E nor M is the bottleneck
52. **LUT ≈ 2.3 × W² — ONLY under a pinned protocol** `[method-dependent]`. Measured 2026-07-30: GF16 MUL is **587 / 692 / 1953 LUT** depending on core identity and synthesis flags — a ~3× spread. Two distinct laws, not one: **dedicated** cores ≈ 0.93·W² (ADD), **parametric** cores ≈ 3.56·W² (ADD) / 5.79·W² (MUL), ratio ~3.1–3.5×. Never quote a LUT figure without stating top module, explicit params (`gf_mul_param` default = GF16, `gf_adder_param` default = GF14 — set them), FORMAL-tap vs registered output, and `-flatten`.
53. **"505" is the dedicated-core figure**, not a universal constant — closest measurement is `gf16_multiplier` = **483**. The GF16≡takum16 equivalence holds *within one protocol*; it is not established across protocols.
54. **Three tiers** (same protocol only): ternary 52 LUT → GF16 → takum16. All figures are **yosys pre-P&R** `[simulated]`; post-route P&R numbers on AX7203 are **not yet measured** — that gap is what `research/ARXIV_V2_CORRECTION_PACKAGE.md` tracks.
55. **IGLA RACE**: GF16 used in trios-trainer-igla, champion BPB=2.5329, target <1.50
56. **BF16 loses 92.7% gradient updates** (7-bit mantissa → step 0.0039 at w=0.5)
57. **GF16 preserves 63.9% updates** (9-bit mantissa → step 0.00098) — 8.7× more than BF16
58. **Training ranking**: posit16 (90.8%) > takum16 (89.6%) > FP16 (80.5%) > GF16 (63.9%) >> BF16 (7.3%) >> GF8 (0%)
59. **Paper has §4.4 Training Stability** — noise floor table + gradient accumulation + IGLA connection
49. **GF16 = minimum 16-bit format with 4/4 robustness** (matmul+grad+range+attn) — the φ-sweet spot
50. **FP16 fails dynamic range** (loses 5/11 values to zero), **BF16 fails matmul** (10× worse max error), **GF16 passes all** → minimum robust IEEE-style format
51. **φ-rule finds the E/M balance point** where neither exponent nor mantissa is the bottleneck (E/M → 1/φ ≈ 0.618: GF16 = 6/9 = 0.667)
