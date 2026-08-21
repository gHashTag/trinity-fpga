# Apparatus audit: six headline claims, one fault

2026-08-12. Six claims of the block/ladder/FPGA campaign audited for **one fault class only** —
a statistic that is arithmetically correct, passes its self-tests, and still answers a different
question than the conclusion needs, because it depends on a free choice of the experimenter rather
than on the system under study. The template was the `depth` fault confirmed the same day
(see `DEPTH_WAS_THE_GRID_2026-08-12.md`).

Each alleged fault was put through an adversarial pass whose default was *refuted*. Every
surviving finding below was then **re-verified by hand** against the files, not accepted on
report.

| claim | verdict |
|---|---|
| ladder winners change with the bit budget (shift/φ/plastic at 3/4/5 bits) | already disclosed |
| one fitted λ reproduces six measured winners | clean — the overfit is disclosed and already withdrawn |
| GF-T beats tekum16 by 2.84x mid / 5.53x far | already disclosed — window dependence is a stated theorem; quote as a range |
| per-layer weight MSE tracks perplexity damage at r = +0.13 | clean |
| per-model tie-rule floors track 2^−m in the stored mantissa width | already disclosed |
| **GF16 matmul reaches 323 MHz on Artix-7, from actual hardware runs** | **FAULT** |

**One fault in six.** Five arms are sound in the audited sense, and that is the honest yield.

---

## The fault: 323 MHz is a ring oscillator's toggle rate on a netlist with no GF16 in it

### What the number mechanically is

`Max frequency for clock 'chain[19]': 323.31 MHz` is the reciprocal of the longest
posedge-to-posedge path on `chain[19]` — the output of a 20-stage LUT1 inverter ring the test
wrapper instantiates. Verified directly in `gHashTag/t27/fpga/vivado/gf16_matmul4x4_top.v`:

```verilog
 6:  (* KEEP = "TRUE" *) wire osc;
 7:  (* KEEP = "TRUE" *) wire chain [19:0];
 8:  reg [22:0] counter = 0;
10:  assign chain[0] = ~chain[19];
14:      (* KEEP = "TRUE" *) LUT1 #(.INIT(2'b01)) inv ( .I0(chain[i-1]), .O(chain[i]) );
20:  assign osc = chain[19];
22:  always @(posedge osc) counter <= counter + 1;
```

That `always` block is the design's **only** sequential statement. The GF16 arithmetic contains no
clocked logic at all — `grep -c posedge` over `gf16_mul.v`, `gf16_add.v`, `gHashTag/t27/fpga/vivado/gf16_dot4.v`,
`gHashTag/t27/fpga/vivado/gf16_matmul4x4.v` returns **0, 0, 0, 0**.

### GF16 is not in the netlist that produced the bitstream

Census of the synthesised design module in `t27/target/gf16-build/gf16_matmul4x4_top.json`:

    gf16_matmul4x4_top: 184 entries, of which 129 are $scopeinfo metadata
      -> 55 real logic cells:  LUT1 19   FDRE 23   CARRY4 6   BUFG 1   INV 4   OBUF 2

Every one of the 55 is accounted for by the probe: 19 ring inverters, a 23-bit counter with its
6-CARRY4 increment chain, a clock buffer, and the LED drivers. **GF16 contributes zero cells.**
The wrapper feeds the DUT literal constants, so the arithmetic is constant-folded away entirely.

A caution for anyone re-running this census: the same JSON contains lines like `DSP48E1: 18 cells`.
Those are the **cell-library model** modules carrying `$specrule` / `$specify3` timing metadata,
not instances in the design. Count the design module, not the library.

### There is no 100 MHz constraint either

`t27/fpga/vivado/gf16_matmul4x4_top.xdc` in full contains two LED pin assignments, two bitstream
settings, and `CLOCK_DEDICATED_ROUTE FALSE` / `ALLOW_COMBINATORIAL_LOOPS TRUE` on `osc`.
**No `create_clock`.** So "PASS at 100.00 MHz" and "0 timing violations at 100 MHz" describe a
default target applied to an auto-inferred domain that contains only the counter.

### The free choice

Which net is declared the clock — ring length, counter width, and whether the DUT's operands are
ports or literals. Change any of them and the number moves; GF16 is untouched either way.
Sensitivity of the published number to the apparatus is 100 %, to GF16 exactly 0 %.

This also explains a tell that was visible without any of the above: three designs whose claimed
sizes differ by 62x report 330 / 322 / 323 MHz — a 2.5 % spread. **A real critical path cannot be
invariant to a 62x size change.** The same ring and counter appear character-for-character in
`gHashTag/t27/fpga/vivado/gf16_top.v` and `gHashTag/t27/fpga/vivado/gf16_matmul_top.v`.

## What this retracts, and what it does not

The **research notes already withdrew this number** — memory `gf16_323mhz_withdrawn.md` records
it, and `research/XC7A200T_GF16_DATAPOINT_2026-08-05.md` §2 and
`research/THREE_PAPER_UPDATE_2026-08-08.md` both state the ring probe, the constant-fed tops and
the ~54-cell netlist, and prescribe replacement wording.

**The correction was never applied to the paper.** `gHashTag/t27/docs/arxiv-trinity-gf16-draft.md` and
`gHashTag/t27/docs/arxiv-submission/trinity-gf16.tex` still carry it, last touched by `56e73bde9` (2026-07-04)
— which was itself an honesty pass ("FPGA-synth instead of 'verified on silicon'") that the Fmax
claim survived:

* title — "…with FPGA Implementation at 323 MHz"
* abstract — "achieves 323 MHz combinational throughput", "0 timing violations at 100 MHz"
* §4.2 table row — `GF16 matmul 4x4 | 40,350 | 64 | 323 MHz | 35/35`
* §5 — "41.2 GOPS @ 323 MHz"
* §7 — "All verified numbers (323 MHz, 40,350 LUTs, 64 DSP48E1, …) are from actual FPGA hardware
  runs (Artix-7 XC7A100T), not ASIC silicon nor simulation estimates"

The §7 sentence is the one that cannot stand under any reading: it asserts 40,350 LUTs and
64 DSP48E1 from the same "actual hardware runs" as the 323 MHz, while the netlist that produced
the bitstream has **55 cells and zero DSP48E1**. Those two numbers cannot come from one build.

**Neither file carries an arXiv identifier and neither is submitted** — checked. So this is caught
before publication and no public retraction is owed. Fixing the draft is a decision for the owner,
not something to do unasked; what is owed is that the draft not be submitted in this state.

## The lesson this adds

A withdrawal recorded in research notes **does not propagate to documents**. Three separate
places said the number was withdrawn; the paper that carries it to readers said nothing, and a
later honesty pass over the same file did not catch it because it was looking at a different
sentence. This is the debugging doctrine's *"distinguish runtime from persistent fixes — silent
reverts create Sisyphus loops"*, applied to claims instead of configuration:

> **When you withdraw a number, grep for the number.** Not for the file you remember writing it
> in — for the digits, across the whole tree, including papers, READMEs, CHANGELOGs and chip
> docs. Then record where it still lives. `323` appears in seven further files under `t27/docs`
> and `t27/chips`.
