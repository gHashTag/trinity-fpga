# The cost–quality frontier, and what it says about the rung names (W940)

W939 measured a 93× alphabet effect from three points at three different widths —
a width effect quoted as a format effect. This sweeps **fourteen decoders** in the
tree, auto-discovering each one's input port and width, and prices each twice:
alone, and behind an identical 12×8 multiply whose RTL never changes. Record
[`alphabet_w940.json`](alphabet_w940.json), rig
[`alphabet_sweep.py`](alphabet_sweep.py).

## The curve

The multiplier is the same Verilog in every row. What changes is how much of it
survives constant-propagation from the format's alphabet:

| alphabet bits | the multiply's own cost | rows | spread |
|---:|---:|---:|---|
| 2 | **3.43** | 1 | — |
| 8 | 128.31 | 5 | 126.57–133.43 |
| 10 | 212.57 | 2 | exact |
| 14 | 341.29 | 1 | — |
| 16 | 385.29 | 6 | 384.57–386.00 |
| 17 | 402.86 | 2 | exact |
| 32 | 426.57 | 1 | — |

Monotone, and it spans **112×** from two bits to sixteen. This is the effect that
dominates a datapath, and the decoder — the quantity three waves were spent
measuring — is 2 % of it.

**And it saturates.** Two to sixteen bits costs 112×; sixteen to thirty-two adds
only **11 %** (385.29 → 426.57). The consumer here slices twelve bits out of the
decoded word, so once the alphabet's image exceeds the consumer's own precision
there is nothing left to constant-propagate away. The alphabet effect is therefore
a property of the *pair* (format, consumer), not of the format alone — and it is
largest exactly where compact formats live, below the consumer's width.

## The frontier, joined with accuracy (784-256-256-10, five seeds)

| format | physical bits | consumer cells | MNIST drop | Fashion drop |
|---|---:|---:|---:|---:|
| **fp8 e4m3** | 8 | **138.57** | +0.00 | −0.01 |
| fp8 e5m2 | 8 | 138.57 | −0.02 | −0.04 |
| **TNF8** (`tnf8s`) | **10** | **230.57** | −0.00 | −0.02 |
| `binary16` | 16 | 438.57 | ≈0 (small net) | — |
| **TNF16** (`tnf17`) | **17** | **424.86** | ≈0 (small net) | — |
| `posit16` | 16 | 511.00 | ≈0 (small net) | — |
| `takum16` | 16 | 546.00 | ≈0 (small net) | — |

**Correction to this document's first version, applied the same day.** The TNF16
row originally used `tnf16_decode` at 16 bits (386.57 cells). TNF16's physical
width is **17** — the manuscript says so itself — so the width-honest row is
`tnf17_decode` at **424.86**. Quoting the 16-bit module was exactly the naming
error this report was written to expose, committed by the report. **At its true
width TNF16 still beats binary16 (424.86 against 438.57), posit16 (511.00) and
takum16 (546.00)** — a fair win, one bit wider and 3 % cheaper than binary16.

**At zero accuracy loss, fp8 is the cheapest format measured, and TNF8 costs
1.66× more.** Not because its decoder is expensive — the decoder is 18 cells
against fp8's 12 — but because **TNF8 physically stores ten bits, not eight**, and
the consumer is priced by physical width.

The manuscript already concedes the premise: its own caption states the TNF rungs
store more bits than their names (TNF8 → 10, TNF16 → 17). What this measurement
adds is the consequence: **a name-matched comparison flatters TNF, and a
width-matched one is the frontier the field will hold it to.**

## Where TNF wins, and it is not on cost

At four bits the comparison stops being cost-versus-cost. TNF4 holds within
0.33 pp of fp32 while fp4 e2m1 and GF4 lose **38 to 65 points** across two tasks
and two network sizes, 5/5 seeds, t up to 24.7 (W940 scaling). At that width fp4
is not a cheaper option, it is a non-option — and *that* is the defensible claim.

So the honest two-sentence result is: **above four bits, choose on cost, and fp8
wins because it is genuinely eight bits wide. At four bits, choose on whether the
network survives, and TNF4 is the format that does.**

## Caveats

- Synthesis cells, not post-route; `-nodsp`; one synthesiser.
- The consumer is one 12×8 multiply, the smallest honest one. A wider accumulator
  or a systolic tile would change the constant, not the ordering by width.
- The 2-bit row is `gfternary`, one decoder — the curve's cheapest point rests on a
  single measurement.
- Accuracy is weights-only PTQ on MLPs; the joined rows are the three formats
  measured on both sides of the join.

---

*φ² + φ⁻² = 3 | TRINITY*
