---
name: trinet
description: TRI-NET ternary internet — node cell, receipts, mesh, TRI settlement, IGLA CODER agent. Board truth, the honest status of every claim, and the next wave. Use when working on ternary compute nodes, compute receipts, the TRI credit ledger, or growing the network.
---

# TRI-NET

A network whose unit of work is a 32-wide ternary dot product, executed on FPGA
nodes, returned with a verifiable receipt, and settled as work credit.

Read `docs/TRI_NET_ARCHITECTURE.md` before changing anything. The two `.t27`
records are the source of truth for what is actually established:
`specs/trinet/ternary_hw_verification.t27` and `specs/trinet/settlement_law.t27`.

## Status — do not restate these upward without re-reading the specs

| Claim | Tier |
|---|---|
| trinet_mac32 dot product **and** receipt tag bit-exact on AX7203, 512/512 | `[measured on FPGA]` |
| the board answers a second independent host (Zig CLI, 64/64) | `[measured on FPGA]` |
| trinet_mac32 routed, 429 LC, 0 DSP48 | `[synthesised and routed]` |
| gfternary MUL bit-exact, 16/16 exhaustive | `[measured on FPGA]` — **but the datapath is FP32, not ternary** |
| mesh, ledger, adversary rejection | `VERIFIED_SW` (42 Zig tests) |
| three *physical* nodes exchanging work | not done — one board exists |
| a trained IGLA CODER model | does not exist on this workstation |
| a spec-first GF-T on-chip **trainer** (forward+backprop+update) | **exists + CI-proven bit-exact** in t27 (`emit-bitexact-gate`, Verilog=C=Rust=model, fuzz-hardened) — but simulated/synth only; not yet flashed (JTAG down). The *learning* complement to IGLA RACE's *inference* |
| a receipt proves work ran on an FPGA | **false**, and must not be claimed |

**Do not cite gfternary as a ternary-compute hardware result.** That cell
expands each 2-bit code into an FP32 constant, runs `gf_mul_param(8,23)`, and
re-quantises. It verifies the format's decode/compute/quantise law only.
`trinet_mac32` is the cell whose datapath is actually ternary.

**Three incompatible trit encodings live in this tree** — gfternary and
trinet_mac32 agree (`00`=0, `01`=+1, `10`=−1), TF3 swaps the signs
(`01`=−1, `10`=+1), and `ternary_mac_16` shifts them (`00`=−1, `01`=0, `10`=+1).
Wiring any two together without a converter produces sign errors that
arithmetic self-tests cannot catch, because each is internally consistent.

Keep **RTL written ≠ routed ≠ measured on the board** apart. A bitstream that
builds is not a measurement.

## Two results that bound what can be claimed

**Device DNA is a dead end on this toolchain.** `DNA_PORT` places, routes, and
answers over UART — 8/8 reads, correct framing, 57 bits reported — and `DOUT` is
**zero for all 57 bits** on an AX7203 through openXC7 (2026-08-01). All bits
zero points at the primitive not being configured by the bitstream rather than
at a wrong shift sequence; a vendor-toolchain build on the same board would
settle it and has not been run. **Do not re-run this probe expecting a different
answer** — and never let a zero DNA become a node id, or every board on this
flow claims `0x00000000`.

**Throughput: 6842.9 jobs/s batched, after 36x of work.** The ladder, each step
of which moved the bottleneck somewhere new:

| mode | jobs/s | share of ceiling |
|---|---|---|
| BAUD_DIV=434, one job per round trip | 191.1 | 28% |
| BAUD_DIV=30, one job per round trip | 843.9 | 8.5% |
| BAUD_DIV=30, **batched x32** | **6842.9** | 69.2% |

**Raising the line rate alone is not enough** — at BAUD_DIV=30 the share of the
ceiling *fell* and p50 latency sat at 1.17 ms, a USB frame interval. One job per
USB transaction caps a serial node near 850 jobs/s however fast the wire is. Use
`Node.executeBatch`; a model layer is already a run of jobs.

**The ceiling is full duplex.** Request goes out on TX while the response comes
back on RX, so it is `baud / 10 / max(req, resp)`, not their sum. Summing them
produced a batched figure of 125% of the ceiling — a measurement above a ceiling
means the ceiling is wrong, not the measurement.

compute/transport is now 240x, down from 6221x. **No power figure exists** —
nothing here has been on a bench supply, so any TOPS/W comparison would be
fabricated.

**CFGMCLK is ~71.18 MHz, not the 69-70 MHz recorded elsewhere.** Measured
2026-08-02 with `conformance/trinet_baud_sweep.py`, which sweeps the HOST rate
against a fixed-divisor bitstream and brackets where the link holds — no
re-synthesis needed. Window 156800..171200 baud at BAUD_DIV=434, centre 164000.
**So the canonical 160000 baud sits ~2.4% below the board's real rate** and
works on margin, not by being correct. Tolerance is ±4.4%, wider than the
textbook ±2-3%, because the receiver re-syncs on every start bit. That is what
makes small divisors reachable: quantisation is 1/BAUD_DIV, so 120 → 593 kbaud
is comfortable, 60 → 1186 kbaud is in budget, 30 → 2372 kbaud is at the edge.

## Running a fleet — what three boards teach that one cannot

- **CFGMCLK differs per chip.** It is an internal RC oscillator. Measured across
  this fleet on 2026-08-03: 70.46, 67.13 and 68.69 MHz (±0.18), a 4.97% spread.
  Each board tolerates about ±4.5%, so the windows still overlap — **one rate
  serves the fleet: 1144744 baud, 6400/6400 on each of the three.** Do not
  assume that survives a re-flash or a new board; measure it.
- **Measure the window, never take the first rate that answers.** A board a few
  percent off its rate still replies — it just loses a few percent of jobs, and
  that reads as a bad board, a bad cable or a bad hub. node2 was written up as
  the marginal board of the fleet at 97.6%; it delivers 6400/6400 once the rate
  is measured, on the same cable and the same hub port. The old check asked six
  probes per candidate and took the first that passed all six. A rate losing
  2.4% of jobs passes six probes 86% of the time.
  ```bash
  python3 conformance/trinet_baud_sweep.py --port <p> --centre <b> --span 0.08
  ```
  It prints a clean window, the rate to use, and — separately — the degraded
  shoulder either side. Operate at the centre. Never inside a shoulder.
- **A fleet runs at the rate every member sustains**, not the fastest any member
  reaches. At BAUD_DIV=30 one board was clean at 600/600 while another returned
  18% of its responses damaged — same design, same host, different cable. Re-read
  that last clause with the above in mind: "different cable" was the conclusion
  reached without a sweep, and it is exactly the conclusion the sweep overturned
  for node2.
- **Every AL321 in this set reports the same USB serial.** openocd cannot tell
  them apart and silently picks the first, so use
  `ax7203_al321_multi.cfg` and pass `adapter usb location`. Sweep to find the
  live ones; the locations move when hubs change.
- **Parallel flashing works.** Three boards on three programmers flash
  simultaneously in the same 778 s a single one takes.
- **A freshly plugged board can read 0xffff... for a few seconds** before
  settling. One bad IDCODE is not evidence a programmer is dead — all three read
  as unconnected on the first sweep and valid on the second, untouched.
- **`virtex2 read_stat 0` answers whether a board is configured.** `0x401079fc`
  is DONE=1. A board that reads that and still says nothing on UART has a wiring
  problem, not a bitstream problem — that distinction saves a 13-minute reflash.

## A ledger must tell damage from dishonesty

Running two real boards surfaced what no emulated adversary could: one returned
a few percent of responses damaged, and the ledger slashed it as a cheat.

**The keyed tag separates them.** A node that skips the work still holds the key
and signs its guess — wrong answer, tag *valid for that answer*. Corruption
cannot make that pair, because the tag then fits neither the correct answer nor
the returned one. So:

| observation | verdict |
|---|---|
| wrong answer, tag fits it | **lie** — slash |
| wrong answer, tag fits nothing | damage — no credit, no charge |
| right answer, tag does not fit | damage |
| nonce mismatch, tag reconstructs with our operands | damaged request |
| nonce mismatch, nonce previously issued | lost-response desync |
| nonce never issued | **fabrication** — slash |

Two mitigations were tried and **removed after measurement**: draining the
receive buffer before each request measured worse on every count, and the drain
itself stalled two seconds per call because a read on an empty buffer waits out
VTIME. Flushing a serial port is an ioctl, not a read loop.

## The receipt, and exactly how far it reaches

| tag | resists | does not resist |
|---|---|---|
| CRC-32 (`trinet_mac32`) | corruption, wrong job, replay, stale nonce | anyone at all — the function is keyless |
| SipHash-2-4 (`trinet_node_v2`) | third parties forging on an operator's behalf; with per-node keys, one operator forging for another | the operator forging their own — they hold the bitstream, so they hold the key |

Closing the remaining gap needs a key that never leaves the device: eFUSE or
BBRAM with an encrypted bitstream, or an external secure element. Until then
node identity is **asserted, not proven**, and must be described that way
wherever it is published.

### The key is loaded over the wire, not baked in (changed 2026-08-03)

`RECEIPT_KEY` used to be a synthesis parameter. It was committed to a public
repository, the fix was applied to the source, and **the fix never reached the
boards** — the fleet ran for a day signing with keys any reader of the git log
could compute, and every test stayed green because a compromised key and a good
key are indistinguishable to anything that only asks "does the tag match".

The reason it never reached the boards is the part worth keeping. Re-keying a
baked-in key needs a place-and-route run **this workstation cannot perform** —
an XC7A200T chipdb OOMs at Docker's 4 GB default, and raising it to 6 GB on an
8 GB host stops Docker starting at all — plus 13 minutes of flashing, per board.
A key that costs an hour to rotate is a key nobody rotates.

So the node now takes its key from `op 0x02`: 16 bytes in the W and X operand
fields, so the request stays 24 bytes and the frame parser is untouched.

- **Write-once per configuration.** A second `setkey` returns `0x03 key locked`
  and changes nothing. Without that, anyone reaching the wire could replace the
  operator's key and every later receipt would verify under theirs.
- **The ack is signed with the key just installed**, so acceptance is
  distinguishable from an echo. `Node.setKey` checks the tag, not the status.
- **An unkeyed board still computes.** It answers `0x04 no key` with a real
  dot product and a meaningless tag. Anything measuring arithmetic must use
  `protocol.statusMeansComputed()` — testing `status == status_ok` makes a
  correctly working unkeyed board look broken at every candidate baud rate.
- A non-null `RECEIPT_KEY` still bakes a key in and locks it at reset, for
  anyone with a build machine who prefers the key never touch a wire.

Cost: 1292 → 1484 LC, +15%. Still 0 DSP48.

## Files

```
fpga/vivado/trinet_mac32_ax7203.v              node cell: ternary MAC + CRC receipt
formal/trinet_mac32_tb.v                       UART-level testbench vs golden vectors
conformance/trinet_mac32_conformance_ax7203.py golden oracle + hardware host
.github/workflows/ax7203-trinet-mac32.yml      sim-gated synthesis
src/trinet/{protocol,serial,net,node,ledger,mesh,model,agent,main}.zig
specs/trinet/*.t27                             the record
```

## Commands

```bash
zig test src/trinet/agent.zig -lc                     # whole stack
zig build-exe src/trinet/main.zig -lc                 # CLI
./main selftest                                       # adversaries vs verifier
./main probe <port> <baud>                            # arithmetic AND authenticity, reported apart
./main census <port> 0 100 64                         # 100 runs; baud 0 = negotiate
./main demo                                           # mesh + agent + books

python3 conformance/trinet_discover.py                # who is on the bus, and at what rate
python3 conformance/trinet_baud_sweep.py --port <p> --divisor 60   # a board's real rate
```

**Never trust a port name across sessions.** They move when hubs change:
`-1110` was node0 one hour and node1 the next. Identity comes from the board's
id field, never from argument order or device name.

Bring a board up, in order:

```bash
sudo -n /opt/homebrew/bin/openocd -f fpga/openxc7-synth/ax7203_al321.cfg \
  -c "init" -c "pld load 0 <file.bit>" -c "runtest 2000" -c "shutdown"
./main keygen > trinet-keys.txt          # gitignored, mode 600, never commit
./main setkey <port0> <port1> <port2>     # one 24-byte frame per board
./main fleet  <port0> <port1> <port2>     # now it can settle
```

With several programmers attached, every AL321 reports the same USB serial, so
pass `-c "adapter usb location <loc>"` with `ax7203_al321_multi.cfg` and sweep
the locations fresh — they move with the hubs too.

Get the locations from `ioreg`, do not guess them:

```bash
ioreg -p IOUSB -w0 | grep -E "Hub|Digilent|CP2102N"
```

`Digilent USB Device@01120000` → openocd location `1-1.2` (first byte is the
bus, each remaining non-zero nibble is a port down the chain). A CP2102N next to
a Digilent under the **same hub** is the same board — that is how to pair a
serial port with a programmer without flashing anything to find out.

**`mpsse_flush()` stall usually means somebody else already holds the adapter —
and on 2026-08-03 that somebody was me.**

Two of three cables stalled on every attempt for an hour. The cause was not the
cable, the board, or (as first recorded here, wrongly) which USB bus they sat
on: two `openocd` processes from earlier probes were still alive as root,
holding those two FTDI devices. Check for that before theorising:

```bash
ps -eo pid,stat,etime,comm | grep openocd
```

Anything older than the probe you just ran is a leak.

**Why they leaked — do not repeat this.** The probes were bounded by
backgrounding `sudo`, capturing `$!`, and sending `kill -9` to it after a sleep.
That does not work: `$!` is the **`sudo` wrapper**, `openocd` runs as root
beneath it, and a user `kill -9` cannot touch a root child. The wrapper dies,
the timeout looks like it worked, and the adapter stays held. (Do not copy that
form from anywhere — it is written out here only to be recognised, never run.)
Put the timeout **inside** the privileged process instead:

```bash
sudo -n timeout -s KILL 25 /opt/homebrew/bin/openocd \
  -f fpga/openxc7-synth/ax7203_al321_multi.cfg \
  -c "adapter usb location 0-1.2" -c "init" -c "shutdown"
```

**Clearing a leak needs the operator, not `sudo -n`.** The NOPASSWD rule in
`/etc/sudoers.d/openocd` covers exactly one binary — `/opt/homebrew/bin/openocd`
— so `sudo -n pkill -9 openocd` fails with "a password is required", and being
`-n` it fails *silently* instead of prompting. A leaked openocd survived three
such attempts while every one of them was reported as having cleared it. Check
with `ps` afterwards rather than trusting the exit, and when it really needs
clearing, ask the operator to run `sudo pkill -9 openocd`.

Order of suspicion for a stall: leaked openocd first, then a replug of the
cable, then the board's power. Bus position was a coincidence — after the
cables were replugged all three answered, including both that had "always"
stalled.

## Board and toolchain truths

- **Verify `sudo -n true` at the start of every flash session.** The
  `/etc/sudoers.d/openocd` rule has been lost to a reboot before.
- **A flash takes 778 s** for a 9.7 MB bitstream at the AL321's stable 100 kHz.
  Notes claiming ~78 s are wrong by an order of magnitude.
- **openocd's stdout is block-buffered** when redirected. An empty log file
  during a flash is not a hang.
- **Docker is often not running locally** — synthesis goes through CI.
- **CI workflows only register from `main`.** A push to a feature branch does
  not trigger them; cherry-pick onto a branch based on `origin/main` and push
  there.
- **The DSP guard must match the cell-count column**, `grep -E '^ *[0-9]+ +DSP48'`.
  Grepping the whole log for `DSP48` matches pass banners and fails a clean build.

## The bug class this project keeps producing

Every RTL defect found here has lived in the **frame path**, not the arithmetic.
Two more this session:

1. A conformance host emitted one byte too many, so operands shifted and the
   FPGA read `a = 0` for every job. It scored 7/16 — the exact cases whose
   answer is zero anyway. The golden oracle's self-test passed throughout,
   because it never exercised the wire encoding.
2. A testbench read hex fields with `$fscanf %h` and transmitted them low byte
   first, reversing every multi-byte field. The dot product could not see it —
   reversing both operands applies the same permutation to each.

**Therefore:** a conformance host is not verified by its self-test, and
arithmetic alone is not a sufficient witness for a wire format. Put a checksum
over the *inputs* in the response; it turns an invisible permutation into an
immediate localised failure.

## Design invariants — do not collapse these

- `node.execute` produces an **untrusted claim**; `protocol.verify` judges it
  against an independent recomputation; `ledger.settle` moves credit. Three
  steps, three functions. Merging them is how a compute network pays for work
  that never happened.
- A **tag can never adjudicate whose account a credit belongs in.** A node that
  computes honestly and signs as someone else passes the protocol verifier —
  refusing payment is the ledger's job.
- Full audit is affordable **because this work unit is small**. If the unit
  grows, lower the audit rate and raise the slash to keep `p·s > r`.
- No multipliers in the compute core. Ternary products need none, and DSP
  inference is what made every previous multiply cell unroutable under openXC7.

## The next wave

Ordered by what unblocks the most:

1. **Name a buyer.** `open_question WHO_BUYS_TERNARY_COMPUTE` in
   `settlement_law.t27`. `docs/TRI_NET_TECHNICAL_BRIEF.md` is written and ready;
   sending it is the operator's decision. Every other item is engineering; this
   one decides whether the engineering matters.
2. **Escape the UART.** Measured throughput is 0.02% of the derived compute
   ceiling. The USB-3 FIFO boundary issue #48 specifies is the unlock, and until
   it exists no performance number here means anything about the silicon.
3. **A second physical node.** Every distributed claim today is one board plus
   software. Two boards make the mesh real.
4. **Power on a bench supply.** No TOPS/W exists. Without it there is no
   defensible comparison against TernaryCore, TeLLMe or anyone else.
5. **TF3 balanced-ternary decode** (issue #234) — a different cell from any
   currently recorded, and blocked on picking one trit encoding for the tree.
6. **Device identity, if it matters enough.** A vendor-toolchain build of the
   DNA probe for comparison, or an external secure element. Do NOT simply
   re-run the openXC7 probe.

## Words that must not appear in any TRI-NET claim

"first", "best", "only", "beats". Also: never describe credited work as hardware
compute on the strength of a receipt alone.
