# MXFP4 has three perplexities in this repository, and none of them is the spec's

Two documents dated 2026-08-10 report the perplexity of MXFP4 E2M1 + E8M0 on
SmolLM2-135M, wikitext-2, 40 windows, block of 32, baseline 14.4874 — the same
measurement by every label they carry:

- `BLOCK_AXIS_VERDICT_2026-08-10.md`: **21.9397**
- `BLOCK_AXIS_CLOSED_2026-08-10.md` and `SCALE_FRONTIER_2026-08-10.md`: **22.4998**

This was found by an instrument check. `kl_optimal_codebook.py` refuses to run
unless it first reproduces the published table; it reproduced the fp32 baseline
and Lloyd-Max exactly and returned 21.9397 where 22.4998 was published, and
stopped.

## It is not a bug in either. It is an undeclared convention

Both numbers reproduce, from their own code, on the same weights. The difference
is where the block maximum is divided by the codebook's top level relative to
rounding the E8M0 scale up to a power of two — and since E2M1's top magnitude is
**6.0, which is not a power of two**, the two orders do not commute.

Measured, all three on the same run:

| scale rule | perplexity | used by |
|---|---:|---|
| `s = 2^⌈log₂(a_max / 6)⌉` | 22.4998 | `scale_frontier.py`, `block_ladder.py` |
| `s = 2^⌈log₂(a_max)⌉ / 6` | 21.9397 | `block_tnf.py`, `rotation_verdict.py` |
| `s = 2^(⌊log₂(a_max)⌋ − 2)` | **23.5380** | the OCP MX specification |

A spread of **7.3 %** between the extremes, on a comparison whose margins are
routinely under 3 %.

The third row is the specification's own rule: the shared exponent is aligned so
the element format's maximum exponent sits at the top of the block, `emax = 2`
for E2M1 since `6.0 = 1.5 × 2²`. It permits saturation — a block maximum above
`1.5 × 2^⌊log₂ a_max⌋` clamps — which the other two avoid by construction, and
that is why it is the worst of the three.

## What this does and does not damage

**Every internally consistent comparison stands.** `SCALE_FRONTIER`'s table puts
φᵏ 4b/32 at 21.3545 against MXFP4 at 22.4998 using one `quantise` for both rows,
so the comparison is like for like whatever the convention. The same is true of
`BLOCK_AXIS_VERDICT`'s element-axis table and of the rotation work built on it.

**Our comparisons have been generous to MXFP4, not to us.** The specification's
own rule is the least favourable of the three to MXFP4 — 23.5380, worse than
either number we have published. The four-bit scale domination claim
(φᵏ 4b/32 at 4.125 bits/weight beating MXFP4 at 4.250) holds under all three, by
a larger margin under the spec's than under the one we reported.

**What must stop is quoting the numbers across documents.**
`COMPETITIVE_LANDSCAPE_2026-08-11.md` cites 22.4998 in its scale table and 21.9397
in its rotation section, both labelled MXFP4, four paragraphs apart. The live
site does the same on one page. That is not two measurements of a changing thing;
it is one thing measured two ways with the convention left out, and a reader is
entitled to read it as a contradiction because it is one.

## What to do

1. **State the convention wherever an MXFP4 number appears.** Cheap, and it makes
   the three numbers legible instead of contradictory.
2. **Prefer the specification's rule for anything comparative that leaves this
   repository.** It is what a reader will reproduce from the OCP document, and it
   is the rule least flattering to our own claims — both good reasons.
3. **Do not restate the published tables.** They are correct as measured and
   internally consistent; re-deriving them under a new convention would trade a
   documented convention for an undocumented re-run.

---

*Method: `s` computed per block from `a_max`, elements E2M1 with the eight
magnitudes the OCP spec gives (no reserved Inf/NaN code), 210 linear layers,
`lm_head` excluded, 40 windows of 2048. The three rules differ only in the
expression for `s`; everything else in the path is identical.*
