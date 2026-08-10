# Reading the full text partly exonerates the paper and corrects our own flag

The previous iteration ran the checklist over four abstracts and reported two
defects. Applying our own standard -- the one demanded of every number here for
thirty iterations -- means checking that against the papers themselves.

## What the abstract said, and what the paper says

**Abstract:** "a modest 10.8% area increase without impacting operating
frequency." Flagged under T3: our seed-noise floor is 11.4%, so a frequency
claim below that is unresolvable from a single run.

**Body** (arXiv:2505.19096, Vivado 2018.3 on ZCU102, and Synopsys DC on TSMC
28 nm):

- Frequency is a **constraint of 125 MHz**, not a measured `Fmax`.
- "our modifications do not affect the critical path" -- the pipeline scheme is
  unchanged.
- "our posit-enabled FPU achieves the same frequency as the baseline with a
  moderate 19.6% area overhead."
- ASIC timing is reported as post-synthesis delay in nanoseconds, not as a
  validated maximum.
- The authors do state a caveat: one configuration needed an extra pipeline
  stage.

## Our flag was too strong

They never claimed a difference in `Fmax`. They claimed both designs met one
fixed constraint. **That is a binary outcome, not a measurement**, and
placement-seed noise does not apply to it the way it applies to an achieved
maximum: 125 MHz is either met or not.

**The measurement is posed correctly. What overstates is the wording.**

## Theorem

**T14 (a constraint met is not a maximum measured).** Reporting "the same
frequency" when both designs met a fixed timing constraint asserts only that both
have non-negative slack. It does not assert that their achievable frequencies are
equal: designs with 1% and 80% slack file identical reports. The claim is true as
written and invites a stronger reading. The well-posed forms are "both met
125 MHz" or "`Fmax` was X and Y".

**T15 (a defect found in an abstract is a hypothesis, not a finding).** Abstracts
compress, and compression is indistinguishable from omission. A checklist run
over abstracts systematically **overstates** the defect count. Confirmation
requires the full text.

## Downgrading our own external test

The previous iteration's result must be restated:

| claim | status after abstract | **status after full text** |
|---|---|---|
| A -- posit64 four orders of magnitude | defect (T8) | **unverified** -- full text not read |
| B -- 10.8% area, no frequency impact | defect (T3) | **reclassified** -- measurement sound, wording overstates (T14) |
| C -- 46.8% LUT reduction | open under T1 | **unverified** |
| D -- posit adders cost more | confirms T11 | **unverified** |

**One of two claimed defects survives contact with the source, and in a smaller
form.** The other three are unchecked.

The honest summary of the method's external test is therefore: **one paper read
in full, one wording defect found, and our own abstract-level flag corrected by
the source.** That is a weaker result than the previous iteration reported, and
it is the result.

## What this says about the method

It transfers -- it found something real in work it did not produce. But its first
application was itself subject to the defect it exists to catch: **a conclusion
drawn from a compressed source, presented at full strength.** Thirty-one
iterations in, the checklist caught its own author again.
