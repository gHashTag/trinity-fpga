# What an arbitrary codebook actually costs, and the ruler that nearly hid it

`BLOCK_AXIS_CLOSED_2026-08-10.md` dismisses the squared-error optimum as "not
implementable" and never measures it. That dismissal is now the only thing
standing between the KL-optimised codebook — 20.2586 perplexity against MXFP4's
21.9397 on SmolLM2-135M, an advantage that grew to −8.66 % on held-out windows
with t(39) = −12.51 — and a claim that the block axis is not closed.

> **The motivating claim was withdrawn the same day** — see
> `KL_CODEBOOK_WITHDRAWN_2026-08-11.md`. The codebook was fitted to SmolLM2 and
> **loses to MXFP4 on both models it had not seen** (+1.98 % Qwen2.5-0.5B,
> +8.63 % Pythia-160M). Held-out windows were not a held-out model. **The silicon
> measurements below are unaffected** — they price a decoder, not a winner — and
> the question "what does an arbitrary codebook cost" is worth answering either
> way, since it is the question `BLOCK_AXIS_CLOSED` dismisses without measuring.

So it was measured. yosys 0.65 + nextpnr-xilinx, xc7a200t, `-nodsp` where stated,
harness subtracted, and every load-bearing number re-run independently by a
second agent before anything below was written.

## The width is not free, and it was measured rather than chosen

An arbitrary table needs its levels in fixed point. Too few bits and the codebook
stops being the codebook that won.

| fractional bits | table (× 2^B) | perplexity | win over MXFP4 |
|---:|---|---:|---:|
| exact | — | 20.2586 | +7.66 % |
| 4 | 0,1,3,5,7,10,13,16 | 22.0395 | **−0.45 %, loses outright** |
| 5 | 0,2,6,10,15,20,25,32 | 21.2020 | +3.36 %, under half the win |
| **6** | **0,5,12,20,30,39,51,64** | **20.2552** | **+7.68 %, the full win** |
| 8 | 0,20,48,80,119,156,202,256 | 20.3644 | +7.18 % |
| 10 | 0,79,193,321,477,626,810,1024 | 20.2335 | +7.77 % |

**Six fractional bits, so a 7-bit magnitude.** E2M1 needs no such choice: in units
of 0.5 its magnitudes are the integers 0,1,2,3,4,6,8,12 — four bits, exactly.

## The first answer was wrong, and the ruler is why

The measurement reported the two decoders as costing the same — 16 LUT each, "the
table is exactly as cheap as E2M1's shifter". The adversarial check refuted it:

> `nextpnr-xilinx`'s `SLICE_LUTX` is **LUT-BEL occupancy, not logic**.

A LUT1 buffer and a fully used LUT6 both occupy one SLICE_LUTX. Subtracting a
differently-packed wire baseline from a differently-packed design therefore
compares packing, not arithmetic. Counted as logic instead:

| decoder | reported (BEL occupancy) | **corrected (logic)** |
|---|---:|---|
| E2M1 | 16 LUT | **9 LUT + 2 CARRY4** |
| codebook, B=6 | 16 LUT | **15 LUT + 2 CARRY4** |
| codebook, B=10 | 25 LUT | **22 LUT + 3 CARRY4** |

**The ratio is 1.67×, not 1.00×.** The headline "costs nothing" is withdrawn. It
was confirmed three ways by the checker — standalone yosys stat, harness-top minus
wire-top at the yosys level, and a re-synthesis — so this is the number.

Both arms carry **zero flip-flops**: the decode adds no state either way.

## What it costs where it would actually run

Fifteen LUT against nine is a ratio; it is also six LUT. The number that decides
deployment is what happens to a whole multiply-accumulate lane.

| lane | LUT | FF | DSP |
|---|---:|---:|---:|
| E2M1 decode + multiply, DSP48 allowed | 102 | 64 | 1 |
| codebook B=6, DSP48 allowed | 105 | 64 | 1 |
| E2M1 decode + multiply, LUT-only fabric | 228 net | 96 | 0 |
| codebook B=6, LUT-only fabric | 295 net | 96 | 0 |

**With a hard multiplier the lane grows by 3 LUT and no extra DSP.** On a
LUT-only fabric it grows 1.29×, and the reason is not the table: E2M1's eight
magnitudes have two distinct odd parts (1 and 3) so one adder serves them all,
while the codebook's have six (1, 3, 5, 15, 39, 51) and need five.

Frequency separates them nowhere a multiplier is present — every lane and block
comparison has a gap smaller than the placement-seed spread, which under this
project's own rule (`MEDIAN_SWEEP_2026-08-10.md`) asserts no ordering.

## The table does not amortise across a block

It was worth checking whether 32 lanes could share one decoder. Measured, they do
not: thirty-two E2M1 decoders cost 1832 LUT inside a 32-wide block, where sharing
would have cost one. A combinational table is replicated per parallel lane. Only
the E8M0 alignment amortises — at most 8 LUT per weight, identical for both
formats, so it cancels out of the comparison entirely.

## So is it implementable?

Yes, and the dismissal in `BLOCK_AXIS_CLOSED` is not supported by measurement —
but the honest statement is narrower than the first draft of this document
claimed:

- the decoder is **1.67× the logic** of E2M1's, not equal to it
- in absolute terms that is **six LUT**, and no flip-flops
- on a DSP-based accelerator — what a real deployment is — the lane costs
  **+3 LUT (+2.9 %) and zero extra DSP**
- on a LUT-only fabric it costs **1.29× the lane**, driven by the multiplier's
  odd-part count rather than by the lookup

Whether +2.9 % of a lane buys 7.66 % of perplexity is an engineering judgement,
not a fact this document can settle. What it can settle is that "not
implementable" was never measured and is wrong as stated.

---

*Scope: xc7a200t through the open flow, one fabric family. Fmax figures are
unconstrained post-route critical-path estimates — `bench.xdc`'s `create_clock` is
not consumed by nextpnr, confirmed again here. The perplexity figures reproduce
the published rulers exactly (14.4874 / 21.9397) before any new number was
quoted. The first version of the LUT comparison in this line was wrong and is
corrected above rather than removed; the artefacts are in `fpga/codebook/`.*
