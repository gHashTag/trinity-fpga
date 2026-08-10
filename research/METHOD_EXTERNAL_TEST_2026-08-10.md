# The method's first external test

Thirteen theorems were derived from our own defects and validated on our own
data. That is weak evidence: a checklist built from a set of mistakes will
naturally catch that set. This applies them to published claims from other
groups, chosen for having concrete numbers rather than for being wrong.

## Claim A -- "posit64 obtains up to four orders of magnitude lower MSE than
doubles"

Checked with **our** measured slope for posit64 (peak 58.19 bits at `|e|=1`,
slope 0.115 bits/binade) against binary64's measured constant 52.27.

Crossover by T9: `|e| = 52 binades`. binary64 spans 2046.

| region | width | winner |
|---|---:|---|
| `\|e\| < 52` | **5.1%** of binary64's range | posit64 |
| `\|e\| > 52` | **94.9%** | binary64 |

"Up to four orders of magnitude" is the best corner of a comparison that
**reverses over 95% of the range**. This is exactly the T8 defect: a verdict
where a threshold is required.

**Well-posed replacement:** posit64 is more accurate than binary64 within 52
binades of unity and less accurate beyond; on any workload spanning more than
about 105 binades the advantage is gone.

## Claim B -- "10.8% area increase without impacting operating frequency"

T3: area is deterministic under placement-seed variation and frequency is not.
Our measured noise floor is **11.4%** across five seeds on one netlist.

A claim of "no impact" from a single run cannot resolve an effect smaller than
that floor. The statement is not wrong; it is **unresolvable as reported**, and
needs a median over at least five seeds with the spread stated.

## Claim C -- "posit multiplier reduced LUT utilisation by 46.8%"

**Passes T2**: 46.8% is far above an 11.4% floor, so the difference is
resolvable.

**Open under T1**: whether the baseline design was built as its own advocate
would build it does not follow from the abstract. Our own record is that a ratio
changed sign or magnitude **seven times** when the competitor's side was rebuilt
properly, so this is the question to ask, not an accusation.

## Claim D -- "posit operators consume more LUTs than IEEE for adders, and more
DSP blocks for multipliers"

**Agrees with T11** (`N^1.16` for a scan against `N^0.17` for field reading), and
it is a counter-finding inside the authors' own work -- the marker of a
comparison posed honestly rather than to a conclusion.

## Result

Four claims examined. **Two defects found, one claim passed with an open
question, one independently confirmed one of our theorems.**

The two defects are of classes we had already paid for: a verdict where a
crossover belongs, and a timing claim below the seed-noise floor. Finding them in
work we did not produce is the first evidence that the thirteen theorems describe
**measurement**, not merely our own history with it.

## What this does not establish

Four claims from abstracts is a small sample and abstracts compress. A real test
would read the papers in full and check whether the qualifications we ask for
appear in their bodies. This is a first pass, and it is reported as one.

The honest summary: **the checklist transfers**, on the evidence of four cases,
and the two failures it found are the two most common shapes -- a best-case
corner presented as a general result, and a difference smaller than the noise of
the tool that produced it.
