# I derived as new what the paper already contained

Iteration 88 presented a "Theorem (no exact tiling)" and, from it, the discovery
that $E_t=5$ is the good rung at 16 bits and that the ladder had skipped it.

**The paper already contained both.**

## What was already there

`Theorem (the radix argument holds on positions, not on bits)` states:
*"since $3^{E_t}$ never divides a power of two the remainder is lost."* That is
the tiling theorem, stated more sharply, and it is followed by
`Table (Codes lost to packing)` whose rows are:

| width | best packed member | codes used | lost |
|---|---|---|---|
| 4 bits | $E_t{=}1$, $M{=}1$ | 6 / 8 | 25.0% |
| 6 bits | $E_t{=}3$, $M{=}0$ | 27 / 32 | 15.6% |
| 8 bits | $E_t{=}3$, $M{=}2$ | 108 / 128 | 15.6% |
| **16 bits** | **$E_t{=}5$, $M{=}7$** | **31,104 / 32,768** | **5.1%** |

The last row is exactly the rung iteration 88 announced as skipped. The paper had
identified it, named its parameters, and computed its loss. It also carries the
citation — *"Parhami's analysis of binary-encoded balanced ternary treats exactly
this encoding penalty"* — so the mechanism has prior art the paper already
acknowledges.

The paper is also blunter than my summaries have been about what ternary buys:

> We add no support to "ternary beats binary" as a general statement. We
> measured it three times and it went against us each time.

and `Corollary (the slack is a position artefact)`: *"A ternary exponent encoding
provides no budget slack at equal storage."*

## What is actually new from iterations 88 and 89

1. **The closed form** $w(k) = 1 - 2^{-(1-\{k\log_2 3\})}$ and its values for
   every $k \le 15$. The paper's table gives four widths; the unevenness across
   $k$ — 5.1% at $k{=}5$ against 46.6% at $k{=}7$ — is not stated there, and it
   is what makes the rule actionable.
2. **Silicon for that table row.** The paper identified $E_t{=}5,M{=}7$ on paper;
   iteration 88 built it, checked it exhaustively (62,208/62,208 in-spec exact),
   and placed and routed it. A table entry is not a measurement.
3. **The reservation cost** — that the out-of-specification offsets must be
   guarded, what the guard costs, and that the guard is what the same-width win
   over `binary16` had been resting on.
4. **The noise floor** — that two of four comparisons this session are inside the
   seed spread, and that `full_table.json` never stored per-seed data, so no
   ranking in the paper had ever been tested for significance.

## The shape of the mistake

I theorised before reading. The record already held the result, and the twenty
minutes it would have cost to search the paper for "packing" would have saved
an iteration and produced a better question.

**This is the same error class as computing a caveat instead of measuring it:
asserting from my own reasoning what the record already contained.** The
project's own doctrine states it — *RTFM before reverse-engineering; check what
documentation already exists on disk before experimenting* — and I did not follow
it.

**Standing rule from here: before stating any structural result about the
format, grep the paper for it first.**
