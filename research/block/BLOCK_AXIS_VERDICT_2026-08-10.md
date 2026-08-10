# The block axis is decided, and it is decided against us

Measured on SmolLM2-135M, wikitext-2, 40 windows of 2048 tokens, block of 32
along the contraction axis, E8M0 shared scale (the MX spec's own), baseline
perplexity 14.4874 verified in band before any comparison.

| candidate | magnitudes | ppl | vs fp32 |
|---|---:|---:|---:|
| **MXFP4** E2M1 + E8M0 | 8 / 8 | **21.9397** | 1.514x |
| int4 uniform + E8M0 | 8 / 8 | 30.8859 | 2.132x |
| TNF4 E_t=1 packed | **7 / 8** | 36.7214 | 2.535x |
| **MXFP6** E2M3 + E8M0 | 32 / 32 | **14.7269** | 1.017x |
| TNF6 E_t=1 packed | 25 / 32 | 20.4270 | 1.410x |
| TNF6 E_t=2 packed | 19 / 32 | 18.0275 | 1.244x |

**MXFP4 wins at 4 bits and MXFP6 wins at 6 bits. TNF loses on this axis.**

## Why, structurally

`3^E_t` never divides `2^k`. A ternary exponent packed into a binary word
therefore always wastes codes, and the waste is unaffordable where the alphabet
is small:

- 4 bits: TNF uses **7 of 8** magnitudes. One code lost is 12.5% of everything.
- 6 bits: TNF uses **25 of 32** (E_t=1) or **19 of 32** (E_t=2) — up to 41% lost.

At the same time E2M1 spends all 8 codes and covers 4 binades against TNF4's 3.
TNF4 is strictly worse on both counts at once: fewer levels *and* less range.
There is no trade here to argue about.

This is the no-free-range theorem (T6) carried to its conclusion. On the number
axis a trit is a position and spans `log2(3)` binades, so ternary wins. On a
packed binary word the codes must be counted, not the positions, and ternary
pays. The block axis is the regime where the word is so short that the packing
remainder dominates everything else.

## What survives, and it is not nothing

**The KKT law picked the winner correctly, and the winner was not ours.** Given
the measured within-block span (1.89 binades median, 3.04 at the 99th
percentile), the multiplier argument returns `E* = ceil(log2 3.04) = 2`, hence
E2M1 — a *binary* exponent. The law recommended the industry standard over our
own family. A rule that only ever recommends its author is not a rule; this one
does not.

**The range constraint is visibly active.** TNF6 E_t=2 (19 magnitudes) beats
TNF6 E_t=1 (25 magnitudes) — 18.03 against 20.43 — so fewer levels with more
range wins. That is complementary slackness showing up in perplexity.

## Consequence for the claim

The reference-format claim is now bounded explicitly and correctly:

> For a **ternary datapath** — weights are codes, no multiplier, the accumulator
> is the only object carrying range — the pair {GFTernary, TNF} is a reference
> format. For a **block-scaled binary datapath with multipliers**, MX holds the
> ground, our ladder loses, and we say so.

The stop rule on publication stands: the block axis was the named condition, it
has now been measured, and the measurement went against us.
