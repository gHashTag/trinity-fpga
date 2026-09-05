# TRI-NET — handoff

Written 2026-08-03 so the next person can continue without the conversation
that produced this. It is meant to be read top to bottom once, then used as a
reference. Where it states a number, that number was measured; where it states
a limit, the limit was hit.

Branch `trinet-fleet-truth`, PR
[#355](https://github.com/gHashTag/trinity-fpga/pull/355). Merged up to `main`
on 2026-08-03, so the PR is mergeable rather than conflicting.

---

## 1. What the fleet is, right now

Three ALINX AX7203 boards (Artix-7 `xc7a200tfbg484-2`), all running the same
cell from CI artifacts, all keyed with per-node secrets that have never been
published.

| node | id | clean window (baud) | rate to use | CFGMCLK | health |
|---|---|---|---|---|---|
| node0 | `0x5452494E` | 1 121 020 – 1 227 778 | 1 174 399 | 70.46 ± 0.18 MHz | 6400/6400 |
| node1 | `0x5452494F` | 1 068 248 – 1 169 444 | 1 118 846 | 67.13 ± 0.18 MHz | 6400/6400 |
| node2 | `0x54524950` | 1 121 020 – 1 168 468 | 1 144 744 | 68.69 ± 0.18 MHz | 6400/6400 |

**Every column except `id` is unstable.** Port names move when hubs change —
`-1110` was node0 one hour and node1 the next. JTAG locations move with them,
and the bus number changes too: what this document once recorded as `1-1.2` is
`2-1.2` today. Line rates differ per board because CFGMCLK is an untrimmed RC
oscillator; the spread is **4.97%**, and each board tolerates about **±4.5%**.

Because the windows overlap, **1 144 744 baud reaches all three** — 6400/6400
on each. That does not carry to a re-flashed or a fourth board; measure it:

```bash
python3 conformance/trinet_baud_sweep.py --port <p> --centre 1144744 --span 0.08
```

*(An earlier version of this table listed 71.18 / 70.46 / 67.47 MHz and per-die
rates of 1 186 267 / 1 124 474, and said no single rate could serve the fleet.
Those figures came from a sweep that asked six jobs per rate. Six cannot tell a
clean rate from one losing 2.4%.)*

Never identify a board by its device name or by argument order. Ask it:

```bash
python3 conformance/trinet_discover.py
```

### Keys

`trinet-keys.txt` in the repo root, mode 600, gitignored — **verify that before
every commit**. It maps node name → 16-byte key. It is not in git and there is
no other copy: lose it and the boards must be re-flashed and re-keyed (which
now costs minutes, see §3).

> **It was lost, on 2026-08-03.** A search of the whole home directory found no
> `trinet-keys.txt` and no `trinet-fleet-node*` build directory; the working
> copy that held them is gone and the current checkout's reflog has one entry, a
> clone. All three boards still answer `status 0x01`, so each holds a key nobody
> has. Every receipt they produce is unverifiable — and settlement handles that
> correctly, refusing to credit without slashing, because the boards are honest
> and it is the verifier that cannot check.
>
> The lesson is not "back up the key file". It is that **a fleet whose
> configuration is volatile and whose re-flash path needs a password is a
> perishable measurement**: take the hardware readings before anything else,
> because you may not get the chance twice.

---

## 2. The measurement of record

100 independent runs × 64 jobs per board, port reopened every run — that
matters, because the FPGA's frame parser holds state across host processes.

| | dot products | receipts authenticated | perfect runs |
|---|---|---|---|
| node0 | 6400/6400 | **6400/6400** | 100/100 |
| node1 | 6400/6400 | **6400/6400** | 100/100 |
| node2 | 6245/6400 (97.6%) | 6235/6400 | 25/100, min 59 |

**node2's row measures the host's choice of line rate, not the board.** It was
taken at 1 186 267 baud, 3.6% above the top of that board's window. Re-measured
at 1 144 744 on the same cable and the same hub port: **6400/6400, 100/100
perfect runs**, and again at 1 147 713 to make it a reproduction rather than an
anecdote. The node0 and node1 rows stand — both rates are inside their windows.

Agent forward pass across all three: **96 of 96 accepted, 0 rejected, 0
slashed, 96 mTRI credited, all three nodes active.**

Reproduce:

```bash
python3 conformance/trinet_discover.py   # ports move; ask, never assume
for p in <the ports it reports>; do trinet census $p 0 100 64; done  # 0 = negotiate
```

**Report the minimum, not the mean.** A fleet is used at its worst run.

This section used to end: *"Its losses are the link, not the key or the clock:
swept to its own centre rate it scored slightly worse (98.08% vs 98.56%), which
cleanly falsifies the baud hypothesis."* It falsified nothing. That "own centre
rate" was 1 174 399, from the `BAUD_DIV=60` candidate table — **also outside
node2's window**, by 0.5%. Two numbers half a percent apart, on a sample too
small to separate them, were read as a refutation of the one hypothesis that was
right. Every rate anyone tried came from a list the wrong assumption had
generated, so no test drawn from that list could have escaped it.

*When a hypothesis is refuted by two nearby numbers, suspect the sample, not the
hypothesis.*

### Numbers that are withdrawn, not restated

**Every jobs/s figure this project ever published is void.** They divided by
jobs *attempted*, not verified, so a board answering nothing read as the fastest
run ever recorded — 5409 jobs/s against a transport ceiling of 4942, with 0/64
verified. The bench now counts verified work only and prints `IMPOSSIBLE` above
the ceiling.

**Restated 2026-08-03**, 2000 jobs per board at each board's negotiated rate:

| node | rate | one at a time | batched ×32 | of ceiling |
|---|---|---|---|---|
| node0 | 1 174 399 | 495.7 jobs/s | **3843.6 jobs/s** | 78.5% |
| node1 | 1 144 744 | 483.7 jobs/s | **3680.1 jobs/s** | 77.2% |
| node2 | 1 144 744 | 475.6 jobs/s | **3678.6 jobs/s** | 77.1% |

2000/2000 whole on each. **Not authenticated** — no receipt was checked, because
the keys these boards hold are not on this machine (§3). Cite it as a
measurement of the transport, not as verified compute.

Batching is worth 7.6–7.8× because the round trip is USB latency, 2.05 ms p50
against ~0.4 ms of wire time.

The ceiling is arithmetic: at 1 144 744 baud and 24 bytes on the busier
direction, **no node on this transport can exceed ~4770 jobs/s**, against a
derived compute ceiling 480× higher. The cell is idle for all but ~30 of the
~200 clocks per job. Any throughput claim about this node is a claim about a
UART.

`trinet bench` had four defects of its own and none were visible in the code —
it never loaded the key file, so `verified` was structurally zero and the
throughput line read 0.0 jobs/s on any machine; it took the node's identity from
argument order; it derived the compute ceiling from a CFGMCLK constant belonging
to no board here; and it printed the requested baud beside a ceiling computed
from the negotiated one.

**Still no power figure of any kind.** Nothing has been on a bench supply. This
is the single most valuable missing measurement and it blocks the paper.

---

## 3. How the key works now (changed 2026-08-03)

`RECEIPT_KEY` used to be a synthesis parameter. It was committed to a public
repository, the fix was applied to the source, and **the fix never reached the
boards** — the fleet ran for a day signing with keys any reader of the git log
could compute, while every test stayed green, because a compromised key and a
good key are indistinguishable to anything that only asks "does the tag match".

The reason it never reached the boards is the part to keep: rotating a baked-in
key needs a place-and-route run **this workstation cannot do** (see §5), plus 13
minutes of flashing, per board. *A key that costs an hour to rotate is a key
nobody rotates.*

So the node takes its key over the wire:

- `op 0x02`, 16 key bytes in the W and X operand fields. The request stays 24
  bytes, so the frame parser and `conformance/frame_alignment_check.py` are
  untouched.
- **Write-once per configuration.** A second `setkey` returns `0x03 KEY_LOCKED`
  and changes nothing. Proven on the Artix-7 boards (AX7203) against an attacker's
  key, not only in simulation.
- The acknowledgement is **signed with the key just installed**, so acceptance
  is distinguishable from an echo. `Node.setKey` checks the tag, not the status.
- An unkeyed board answers `0x04 NO_KEY` with a **real** dot product. Anything
  measuring arithmetic must call `protocol.statusMeansComputed()`.
- A non-null `RECEIPT_KEY` still bakes a key in and locks it at reset, for
  anyone with a build machine who prefers the key never touch a wire. CI must
  never pass one.

Cost: 1292 → 1484 LC (+15%), still 0 DSP48.

**The trade, stated plainly:** whoever reaches this UART in the window after
configuration can claim the node. They can also just re-flash it, so this
concedes little that physical access did not already concede, and it buys a
rotation cheap enough to actually happen.

---

## 4. Bringing a board up, in order

```bash
# 1. Who is on the bus, and at what rate
python3 conformance/trinet_discover.py

# 2. Find the JTAG locations — from ioreg, never guessed
ioreg -p IOUSB -w0 | grep -E "Hub|Digilent|CP2102N"
#   Digilent USB Device@01120000  ->  openocd location 1-1.2
#   (first byte = bus, each remaining non-zero nibble = a port down the chain)
#   A CP2102N and a Digilent under the SAME hub are the same board.

# 3. Flash — 778 s per board, and they run in PARALLEL on separate programmers
sudo -n /opt/homebrew/bin/openocd \
  -f fpga/openxc7-synth/ax7203_al321_multi.cfg \
  -c "adapter usb location 1-1.2" -c "init" \
  -c "pld load 0 build/fleet/trinet-fleet-node1/trinet_node1.bit" \
  -c "runtest 2000" -c "shutdown"
# NOTE: the copies currently on disk are in ...-node1-UNKEYED/ — they predate
# the artifact rename. That suffix was dropped because these bitstreams are
# complete and deployable now; a build after 06e781644 has no suffix.

# 4. Confirm the NEW bitstream is running: it must answer status 0x04 NO_KEY
# 5. Key it
trinet keygen > trinet-keys.txt      # only when starting fresh; mode 600
trinet setkey <port0> <port1> <port2>

# 6. Now it can settle
trinet fleet <port0> <port1> <port2>
```

Bitstreams come from CI:

```bash
gh workflow run ax7203-trinet-fleet.yml --ref <branch>
gh run download <run-id> --dir build/fleet
```

**Verify the artifacts before flashing:** the three `.bit` files must have
*different* sha256s. Identical ones mean the `node_id` chparam did not take, and
all three boards would claim the same identity — discoverable only after three
13-minute flashes.

---

## 5. Environment limits, measured not assumed

- **No local place-and-route.** 8 GB host RAM. Docker's default 4 GB OOM-kills
  `bbaexport` for `xc7a200tfbg484-2`; raising it to 6 GB stops the Docker VM
  starting at all. Any plan step assuming a local bitstream build is dead on
  arrival. Use CI.
- **`sudo` is narrow.** `/etc/sudoers.d/openocd` grants NOPASSWD for
  `/opt/homebrew/bin/openocd` **and nothing else**. `sudo -n pkill` therefore
  fails with "a password is required", and with `-n` it fails *silently*. It
  does not survive a reboot — check `sudo -n /opt/homebrew/bin/openocd --version`
  at the start of every flash session. **It was gone on 2026-08-03**, the
  directory empty, which blocked the whole re-flash path; the one-line fix is in
  §8 and it needs a password, so no agent can apply it.
- **openocd needs root** on macOS: `AppleUSBFTDI` claims the FT2232H, so a
  non-root openocd reports "no device found".
- **All AL321 cables share USB serial `210512180081`**, so `adapter usb
  location` is mandatory with more than one attached.
- A flash takes **778 s**, not the ~78 s some old notes claim. openocd's stdout
  is block-buffered when redirected, so an empty log during a flash is not a
  hang.

---

## 6. Traps that cost real time here

**Bound a privileged probe correctly.** Backgrounding `sudo`, capturing `$!` and
`kill -9`-ing it does **not** work: `$!` is the sudo wrapper, openocd runs as
root beneath it, and a user kill cannot touch a root child. The wrapper dies,
the timeout looks like it worked, and the adapter stays held. Two leaked
processes wedged two cables for nearly three hours. Put the timeout inside:

```bash
sudo -n timeout -s KILL 25 /opt/homebrew/bin/openocd -f <cfg> -c "init" -c "shutdown"
```

**`mpsse_flush()` stall ≠ dead cable.** Order of suspicion: leaked openocd
first (`ps -eo pid,stat,etime,comm | grep openocd`), then replug the cable, then
board power. A bus-position theory was recorded here confidently and was wrong —
three consistent observations of a correlation are not a cause.

**A board that does not answer has not been tested until it has been swept.**
node1 was written off as a wiring fault for a day. It was answering the whole
time at 1 124 474 baud, 5.2% off the hardcoded rate.

**Verify the artifact, not the source.** Three separate defects this session
came from a fix that changed source and never reached the thing that runs.

---

## 7. The recurring defect, named

Six defects this session, and **not one was visible from reading the code**.
Each was found by disbelieving a number: a throughput above a physical ceiling;
a testbench that passed no key; a board written off without a sweep; a slash
against a board with nothing wrong with it.

Three of them had the *same shape*: **a rule written in one place, enforced by
enumerating cases somewhere else.**

- `Verdict.unverifiable` was added so a keyless verifier could not accuse.
  `ledger.settle()` never asked — it named `.corrupt` as the one verdict that
  costs nothing and slashed everything else. Two honest boards lost 600 mTRI
  each for keys *we* could not check.
- The mesh's outcome accounting had a catch-all that printed "39 rejected as
  dishonest" beside "slashed: 0 mTRI". A summary that accuses and then charges
  nothing is either a lie or a bug and a reader cannot tell which. It was two.
- `setkey` counted a board as keyed only if 32/32 later jobs came back clean, so
  a successfully keyed board was reported as not keyed, hidden behind its own
  lossy cable.

The structural fix, applied: **ask, don't enumerate.** `settle()` now calls
`verdict.indictsTheNode()`, and the mesh's switch is exhaustive with no `else`,
so adding an outcome is a compile error until someone decides what it means.

Apply the same test to new code: *if someone adds a case tomorrow, does this
default to safe, or does it default to accusing an honest operator?*

---

## 8. What is still open

### Structural, unfixed, and stated in the report rather than buried

- **W02 — a symmetric MAC verified by the key holder is not a receipt.** The
  coordinator holds every key, is the verifier, and is the ledger. No third
  party can check anything. This is the deepest issue in the design; fixing it
  needs asymmetric signatures the FPGA cannot currently produce.
- **W07 — the coordinator recomputes every job, so nothing is offloaded.** At a
  100% audit rate the host does all the work the network does. The demonstration
  is of *verification*, not of *offload*.
- **W06 — stake is conjured, not deposited**, and TRI has no external value, so
  the `p·s > r` soundness check is circular.
- **W04 — fleet identification is a trust step.** The coordinator asks a board
  its id and uses the answer to choose which key verifies it.
- **W08 — no power figure.** Blocked on a bench supply.

### Next actions, in the order they unblock most

1. **Option B — the TernaryCore issue.** Draft written and *held* at
   `docs/outreach/ternarycore-issue-draft.md`. It was held because its strongest
   line ("per-job verifiable receipts, demonstrated on silicon") was false. **It
   is now true** of the Artix-7 boards; there is no Trinity ASIC, so the draft
   should say "on FPGA", not "on silicon". Needs the operator's go-ahead — it is outward-facing to a third
   party. Falsifier: no substantive reply in 30 days.
2. **Re-key the fleet — blocked on an operator, not on work.** The keys
   installed on these boards exist nowhere: `trinet-keys.txt` is not on this
   machine and the checkout that made it is gone. Nothing from this fleet can be
   authenticated until it is re-keyed, and re-keying needs a re-flash (that
   clears the configuration, which clears the write-once key latch — no power
   cycle required). Re-flashing needs openocd as root and
   `/etc/sudoers.d/openocd` is absent; the directory is empty. One line fixes it,
   and it needs a password, so an agent cannot:

   ```bash
   printf 'ssdm4 ALL=(root) NOPASSWD: /opt/homebrew/bin/openocd\n' | sudo tee /etc/sudoers.d/openocd >/dev/null && sudo chmod 440 /etc/sudoers.d/openocd && sudo visudo -c
   ```

   The bitstreams are already on disk under `build/fleet/` (CI run 30762491794,
   built from `1bb1d97e`; no RTL changed after it), three distinct sha256s.
3. **A power measurement.** Everything about efficiency is unclaimable without
   it, and referees will lead with it.
4. **Re-run throughput authenticated.** The transport numbers exist now (§2);
   what they lack is a checked receipt, which is item 2.
5. **Option A — the paper.** The statistical base and the portability result now
   exist; power does not.

**Done since this document was written:** node2's link (it was the line rate,
not the board — §2), and throughput restated at the measured rates (§2, as a
transport measurement).

### Portability (option C), answered

The cell contains exactly two Xilinx primitives — `STARTUPE2` for the clock and
`DNA_PORT` for identity, both board concerns. With those in a wrapper, the core
in `fpga/portable/trinet_node_core.v` synthesises **with zero errors on ten FPGA
families from eight vendors**, with **1082 flip-flops on nine of them**, 1092 on
the tenth, and no inferred multiplier anywhere. See
`docs/TRI_NET_PORTABILITY.md`.

Until 2026-08-03 the CI job that guards this claim installed yosys from apt —
version 0.33, under which the check reads no stats at all. It had failed on every
run since it was added. The claim reproduces under 0.62 and 0.65; the gate that
was supposed to protect it had never gone green. CI now pins the toolchain.

This does not establish portability of *product*: synthesis is not P&R, no
non-Xilinx mapping has met timing, and only xc7 has run on hardware (the Artix-7 boards). And it does
not make anyone want the IP — C's real obstacles were never engineering. The
recommendation to defer C stands.

`DNA_PORT` is now compiled out (`USE_DNA=0`): it places, routes, and returns
zero for all 57 bits on this flow, so it was dead weight in every bitstream, and
removing it makes the node id in simulation equal the one hardware reports.

---

## 9. Where things live

```
fpga/portable/trinet_node_core.v          the node, no vendor primitives
fpga/vivado/trinet_node_v2_ax7203.v       AX7203 wrapper — instantiates the core,
                                          never a copy, or the claim rots
fpga/openxc7-synth/trinet_siphash24.v     receipt tag engine
formal/trinet_setkey_tb.v                 the key-over-the-wire law, 11/11
formal/trinet_node_v2_tb.v                keyed receipts, 6/6
tools/gen_setkey_golden.py                goldens from Python, never from RTL
conformance/trinet_discover.py            who is on the bus, at what rate
conformance/trinet_baud_sweep.py          a board's real rate
conformance/key_default_check.py          null RTL defaults, explicit test keys
conformance/portability_check.py          the ten-family invariant
src/trinet/{protocol,serial,net,node,ledger,mesh,model,agent,main}.zig
specs/trinet/ternary_hw_verification.t27  THE RECORD — claims, limits, retractions
docs/TRI_NET_REPORT_2026-08-02.md         the report, with its corrections at the top
docs/TRI_NET_PORTABILITY.md               the ten-family measurement
docs/outreach/ternarycore-issue-draft.md  option B, written and held
.claude/skills/trinet/SKILL.md            operational truth; read before touching hardware
```

**`specs/trinet/ternary_hw_verification.t27` is the source of truth for claims**,
including a `retracted` entry where this session got a cause wrong. Add to it
rather than to prose when something is measured.

Tests: `zig test src/trinet/agent.zig -lc` runs **56** tests and nests every
other module's. Do not sum the per-file suites — that was done here and reported
as 180, then 198, both wrong.

---

Author: Dmitrii Vasilev ([@gHashTag](https://github.com/gHashTag))
