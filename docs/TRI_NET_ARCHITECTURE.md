# TRI-NET — a ternary internet

TRI-NET is a network whose unit of work is a ternary dot product, executed on
FPGA nodes, returned with a verifiable receipt, and settled as work credit to
the developer who attached the board. An agent runs on top of it: its model's
arithmetic is performed by the network rather than by the machine hosting it.

This document states what is measured, what is built but unmeasured, and what
is neither. Those three categories are kept apart deliberately, because the
distance between them is the entire risk in a project like this.

---

## 1. Status

| Claim | Status | Evidence |
|---|---|---|
| The TRI-NET node — ternary dot product **and** its receipt tag — is bit-exact on an XC7A200T | **measured on hardware** | 512/512 receipts verified, `trinet_mac32`, flashed 2026-08-01 |
| The same board answers a second, independent host | **measured on hardware** | Zig CLI `probe` 64/64, separate serial implementation |
| The node cell synthesises with zero DSP48 | **measured** | 429 LCs, CI run `30702638896` |
| An agent's inference ran partly on that board | **measured** | `demo`: 288 jobs, 96 dispatched to serial-attached nodes (the earlier label "96 on silicon" was a transport-type label, not a measurement of hardware origin — `docs/TRI_NET_REPORT_2026-08-02.md`, W03), mesh result equals local recomputation |
| `gfternary MUL` bit-exact on hardware | **measured, but see below** | 16/16 exhaustive, CI run `30702513394` |
| Mesh, settlement, adversary rejection | **verified in software** | 42 Zig tests |
| GF8 ADD re-verified after the frame fix | **measured on hardware** | 4096/4096 bit-exact, CI run `30704172264` |
| Three *physical* nodes exchanging work | **not done** | one board is attached; see §7 |
| A trained ternary code model | **does not exist here** | see §6 |
| A receipt can only be produced by a key holder | **measured on hardware** | `trinet_node_v2` 256/256 with the key, every job rejected without it |
| A receipt proves work ran on specific silicon | **false, and not claimed** | see §5 |

Before this session the ternary column of the format matrix had no compute
entry backed by hardware (the Artix-7 board). There is now one.

**The gfternary result needs a caveat, and it matters.** That cell is not a
ternary datapath: it expands each 2-bit code into a full FP32 constant, runs a
generic `gf_mul_param(8,23)` FP32 multiplier, and re-quantises to two bits. Its
16/16 establishes the format's decode/compute/quantise *law* — it says nothing
about the cost or structure of ternary arithmetic. `trinet_mac32` is the cell
that carries that claim, because its datapath is popcount and subtraction with
no floating-point core anywhere in it.

---

## 2. The work unit

```
y = sum_{i=0..31} w[i] * x[i],    w[i], x[i] in {-1, 0, +1}
```

Thirty-two trits per operand, packed two bits each into eight bytes. The result
fits in a signed byte, range −32 to +32.

The unit was chosen so that a ternary-weight model's forward pass decomposes
into it exactly: one job per output neuron, one layer per batch of jobs. Nothing
about the network is a simulation of compute — the numbers a layer produces are
the numbers the nodes returned.

The hardware computes it as `popcount(agreements) − popcount(disagreements)`, so
the datapath is AND/OR/XOR and an adder tree. No multiplier, no DSP48. This is
not an aesthetic preference: DSP inference is what made every previous multiply
cell in this repository unroutable under openXC7, and a ternary product needs no
multiplier in the first place.

### Trit encoding

| Code | Value |
|---|---|
| `0b00` | 0 |
| `0b01` | +1 |
| `0b10` | −1 |
| `0b11` | 0 (reserved, canonicalised) |

The reserved code decodes to zero in the FPGA cell, in Zig and in Python, so a
malformed operand degrades to a well-defined answer rather than an
implementation-specific one.

---

## 3. The wire

```
request  (24 B)  AA 55 OP NONCE[4] W[8] X[8] TRIG
response (15 B)  A5 Y STATUS NONCE[4] NODE_ID[4] CRC[4]
```

`CRC` is CRC-32 (IEEE 802.3, reflected, polynomial `0xEDB88320`) over the
26-byte preimage

```
OP | NONCE[4] | W[8] | X[8] | Y | NODE_ID[4]
```

Three independent implementations produce it — a Verilog LFSR, Python's
`zlib.crc32`, and Zig's `std.hash.Crc32` — and they agree. CI fails if they
diverge.

Including the *inputs* in the tag is what makes it a receipt rather than a
checksum on the answer. It caught a real bug: the testbench was reversing the
byte order of every multi-byte field, which the dot product could not detect
(reversing both operands applies the same permutation to each and leaves the sum
unchanged) but the CRC failed immediately.

---

## 4. Layers

```
fpga         trinet_mac32_ax7203.v         ternary MAC + CRC receipt engine
protocol     src/trinet/protocol.zig       framing, verification
transport    serial.zig / net.zig          UART to a board, TCP to a peer
node         node.zig                      fpga | remote | emulated backends
mesh         mesh.zig                      dispatch, judge, settle
settlement   ledger.zig                    credit, stake, slashing
model        model.zig                     ternary forward pass over the mesh
agent        agent.zig                     IGLA CODER
```

Dispatch, judgement and settlement are three separate steps and stay that way.
Collapsing them is the specific mistake that lets a compute network pay for work
that never happened: `node.execute` produces an *untrusted claim*,
`protocol.verify` judges it against an independent recomputation, and only
`ledger.settle` moves credit.

---

## 5. What a receipt does not prove

**A receipt does not prove the work ran on an FPGA.** CRC-32 is a checksum any
party can compute, and the node identity is a synthesis-time constant. A GPU, or
a laptop, can produce a receipt indistinguishable from a board's.

This is the central unsolved problem, and it is stated here rather than buried,
because a network that pays for "hardware compute" while unable to detect
emulation is paying for nothing in particular.

What *is* solved:

| Attack | Caught by | Demonstrated |
|---|---|---|
| Returning a plausible wrong answer without doing the work | independent recomputation | `node.zig` test: >450 of 500 caught; the residue is lucky guesses in a 65-wide answer space, which is why nodes are scored over many jobs |
| Replaying an old receipt | nonce binding | `node.zig` test |
| Claiming another node's identity | ledger refuses to credit a receipt whose id differs from the dispatch target | `ledger.zig` test |
| Billing the same receipt twice | spent-nonce set | `ledger.zig` test |
| Corrupting a model's output | coordinator recomputes rejected rows | `model.zig` test: layer output correct while a node lies |

What is not:

- **Emulation.** Requires a hardware root of trust, and the cheapest candidate
  has now been tested and did not work. `DNA_PORT` places, routes and answers
  over UART under openXC7 — 8/8 reads, correct framing, 57 significant bits
  reported — and returns **zero for all 57 bits** on an AX7203. All bits reading
  zero points at the primitive not being configured by the bitstream rather than
  at a wrong shift sequence; a vendor-toolchain build on the same board would
  settle it and has not been run. So device-bound identity is not currently
  reachable on the open flow, and node identity remains **asserted, not proven**.
- **Unforgeability by the operator.** Partly addressed. `trinet_node_v2` replaces
  CRC-32 with SipHash-2-4 under a key that exists only inside the bitstream, so
  a tag can only be produced by a key holder. That stops third parties forging on
  an operator's behalf, and with per-node keys it stops one operator forging for
  another — it does not stop an operator forging their own, because they hold the
  bitstream and therefore the key. Closing the rest needs eFUSE or BBRAM with an
  encrypted bitstream, or an external secure element.
- **Sybil identities.** Node ids are chosen at synthesis. Stake is the only
  current cost of a new identity.

Until the first of these is solved, the honest description of a TRI-NET receipt
is: *proof that a specific answer was given for a specific job by a party
claiming a specific identity* — not proof of where it was computed.

---

## 6. The agent, and the name

"IGLA CODER" in this repository's issue tracker (t27 #1037–#1041) names a
training programme whose deliverable is a ternary code model. No trained weight
file for it exists on this machine.

What is built here is the *execution* half: the substrate such a model would run
on. The agent encodes a task into a ternary hypervector (a real vector-symbolic
encoder — token vectors bundled by majority, position bound in by rotation),
runs it through a ternary-weight model whose every dot product is a mesh job,
and reads an action out of the result by similarity against action prototypes.

When no trained weights are supplied, `Model.synthetic` generates deterministic
ones and every report the agent produces carries the string
`synthetic (untrained — the arithmetic is real, the weights are not)`. The
inference path is genuine; the action choices are not meaningful until real
weights are loaded. Loading them is a file path, not a rewrite.

---

## 7. Growth, and the one-board problem

The design supports N nodes. One board is currently attached.

`trinet demo` stands up a mesh with the physical node plus emulated peers, and
its report states what fraction of jobs was dispatched to serial-attached nodes (the board). With one board and two
emulated peers that fraction is about a third, and the report says so rather
than rounding it to "a three-node hardware mesh".

A developer joins by flashing the node bitstream with their own `NODE_ID`,
running `trinet serve <port> <serial>`, and registering with a coordinator. The
remote transport speaks the identical 24/15-byte framing, so a peer on another
continent is reached the same way as a local board.

NAT traversal is deliberately not solved here. A node behind a home router is
expected to sit on an overlay (headscale, Nebula, WireGuard) and present a
routable address. Re-implementing hole punching would be the wrong thing to own.

---

## 8. Why TRI is a credit and not a token

`ledger.zig` issues a **non-transferable internal work record**. Nothing mints a
chain asset. That is a deliberate design decision, and the research behind it is
uncomfortable:

- **At n=1–3, the developers hold every node, every key and every vote.** Any
  issuance in that configuration is, after the fact and on-chain,
  indistinguishable from a founder premine. Helium carried exactly that
  reputational damage — insider-linked wallets mining a large share of early
  emissions — and never shed it.
- **The regulatory exemptions that look applicable do not cover paying
  developers for code.** The SEC's airdrop position requires recipients provide
  no "money, goods, services, or other consideration"; MiCA Art 4(3)(b) exempts
  rewards for ledger maintenance and transaction validation. Neither reaches
  software contributions.
- **Emission-funded development is currently punished.** Helium's HIP-149
  proposed minting to fund operations; the token fell over half in a week.
- **A performance advantage is not a network.** DePIN economics reward verified
  served demand, not efficiency. A validated 10× efficiency win earns nothing if
  no buyer has a workload expressed in ternary.

So the credit measures contribution precisely enough that contributors can be
paid — out of revenue or a budget — without issuing a financial instrument. If a
token is ever right, this ledger is the accounting it would need anyway.

### The economic condition

With audit rate `p`, reward `r` and slash `s`, honesty requires `p·s > r`.
`Policy.isSound` checks it and `Ledger.init` **refuses to start** on parameters
that fail. Defaults: `r` = 1 mTRI, `s` = 200 mTRI, `p` = 100% — a caught cheat
costs 200 jobs of honest work.

Full audit is affordable *because the work unit is small*. When the unit grows
past the point where recomputation is cheaper than dispatch, `p` must fall, and
`s` must rise to compensate. `dispatchQuorum` exists for that regime; it is not
how correctness is established today.

---

## 9. Open problems, ranked

1. **Proof of hardware execution.** Without it, "FPGA compute network" is a
   claim about intent, not architecture. Investigate `DNA_PORT` under openXC7
   first — it is cheap to test and settles whether any device-bound identity is
   available at all.
2. **Demand.** Nothing in this repository is a customer. A ternary compute
   network with no ternary workload is a benchmark, not a market.
3. **Signatures.** The receipt needs one before any settlement crosses a trust
   boundary.
4. **Throughput.** UART at 160 kbaud gives roughly 400 jobs per second per
   board, ceiling. Real inference needs the USB-3 FIFO boundary that issue #48
   specifies and nothing has yet built.
5. **A second physical node.** Every distributed claim is currently a claim
   about one board and some software.

---

## 10. Running it

```bash
zig test src/trinet/agent.zig -lc          # 42 tests, whole stack
zig build-exe src/trinet/main.zig -lc      # build the CLI
./main selftest                            # adversaries vs the verifier
./main probe /dev/cu.usbserial-1110        # verify a flashed board
./main demo                                # mesh + agent + the books
./main join                                # what a new operator does
```

Hardware conformance for the node cell:

```bash
python3 conformance/trinet_mac32_conformance_ax7203.py --self-test
python3 conformance/trinet_mac32_conformance_ax7203.py --port /dev/cu.usbserial-1110 --n 512
```

---

Author: Dmitrii Vasilev ([@gHashTag](https://github.com/gHashTag))
Anchor: `φ² + φ⁻² = 3`
