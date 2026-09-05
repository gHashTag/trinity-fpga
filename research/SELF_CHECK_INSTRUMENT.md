# Sixteen ways a measurement can be right and its comparison wrong

A self-check instrument, derived over thirty-three iterations of one hardware
measurement campaign. It is offered as what the evidence supports: a procedure
for catching your own errors, not an audit tool for other people's.

## The evidence for that framing

| applied to | withdrawals produced |
|---|---:|
| our own claims | **16** |
| external papers, read in full | **0** |
| our own applications *of the checklist to others* | **2** |

Sixteen of our own claims were withdrawn, two of them later withdrawn in turn.
Two external papers were read in full and neither had a confirmed defect; both
times the checklist instead caught our reading of them. That is the honest
character of the thing.

---

## The sixteen

### On what is being compared

**T1 -- the terms of a comparison are part of its result.** A ratio is meaningful
only if both sides were built as their own advocate would build them. Seven times
here a ratio changed sign or magnitude when the other side was rebuilt.

**T7 -- incommensurability.** Systems whose range scales differently with width,
one exact and one approximate, have no storage-matched ratio. A quantity
depending on an unstated choice has no limit and cannot converge.

**T8 -- report a crossover, not a verdict.** If one system's figure of merit is
constant in a parameter and another's varies in it, no single-number comparison
is well-posed.

**T9 -- a crossover is a statement about the workload.** "Fixed beats tapered" is
an assertion about the workload's span, not about the formats.

**T10 -- a selection needs both axes and their exchange rate.** Accuracy and cost
can point opposite ways; absent knowledge of what is scarce, the honest output is
the pair, not a winner.

**T12 -- the exchange rate moves.** Every project with its own rate has its own
break-even width. The absence of a single answer is a property of the question.

### On the instrument

**T3 -- area is deterministic, timing is not.** Placement-seed variation leaves
LUT count invariant and moves frequency by 11.4%. Any metric combining them
inherits the timing variance in full.

**T2 -- a ranking needs a resolution.** A ranking on a metric with spread `s`
orders only rows separated by more than `s`. Printing more digits hides the
absence of resolution.

**T4 -- a ratio over correlated factors restates the dominant one.** If `F(A)`
decreases in `A`, ranking on `F/A` approximates ranking on `1/A`.

**T5 -- a monotone response to instrument improvement is a warning.** If
successive corrections all move a result one way, the remaining confounds
probably do too.

**T6 -- a claim's sign can converge while its magnitude does not.** An ordering
across several instruments is stronger evidence than a magnitude from the best
one alone.

**T13 -- fit only inside the model's domain.** Saturating points are excluded
before fitting, not explained afterwards.

**T14 -- a constraint met is not a maximum measured.** Designs with 1% and 80%
slack file identical reports.

### On the harness

**H1 -- a shared component is a confound, not a constant.** It leaves area
differences intact and delay differences not, because it may hold the critical
path. Removing one changed an area-frequency correlation from −0.90 to −0.62 and
reversed a conclusion.

**H2 -- partial observation is an unequal pruner.** Synthesis removes logic not
reaching an output, so a harness observing a fixed number of bits cuts each
design in proportion to *its own* output width. Observing four bits of a 32-bit
datapath left 27 LUT of 179.

**H3 -- harness subtraction requires harness invariance.** A design consuming
fewer harness sources prunes the rest, so the subtrahend varies with the design.

### On sources

**T15 -- a defect found in an abstract is a hypothesis.** Abstracts compress and
compression is indistinguishable from omission.

**T16 -- a search summary is not a source.** Aggregated output may combine claims
from several papers into wording present in none, and drop the qualifications
each original carried.

---

## Three gates that mechanise part of this

- **`check_artefact_agreement.py`** -- compares declared parameters *across*
  artefacts. Every other check verifies an artefact against itself, and all of
  them passed while an oracle and an RTL implemented different formats under one
  name.
- **`check_script_rot.py`** -- every module a build script instantiates must
  exist in the files it reads. *A reproduction path that is never run is a claim,
  not a capability.*
- **`check_harness.py`** -- every output of the design under test must reach the
  observed port. It caught its author's own correction one hour after that
  correction was written.

All three run as ratchets: known entries baselined, failure only on new ones and
on baseline entries that stop reproducing.

---

## How to use it

Before reporting a comparison, in this order:

1. **What is held equal?** If a different choice changes the answer, the single
   number is not a result (T7).
2. **Would the competitor build it this way?** If not, rebuild it (T1).
3. **Is the difference above the instrument's noise?** Measure the floor first
   (T2, T3).
4. **Does the harness observe everything, and is it the same in every build?**
   (H1, H2, H3).
5. **Is one side's figure constant and the other's varying?** Report a crossover
   (T8, T9).
6. **Has correcting the instrument moved the number the same way twice?** Expect
   it to move again (T5).
7. **Is the source a paper, or a summary of papers?** (T15, T16).

## What it does not do

It does not find defects in other people's work -- that was tested and it found
none. It does not replace domain knowledge; every theorem here was learned by
having a specific number turn out wrong. And it is derived from one campaign in
one field, so its generality is a conjecture with a sample of one.

What it did do, sixteen times, is stop a wrong claim from being published under
our own name.
