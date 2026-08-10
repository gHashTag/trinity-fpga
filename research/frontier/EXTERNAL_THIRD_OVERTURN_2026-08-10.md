# Withdrawal 18: the prescription claim was too strong, and this is the third time

## What was claimed

"Every comparison of number formats we have read reports a verdict or a ratio.
For two of the four staircase forms that shape is wrong."

## What the source says

Hunhold's takum paper (arXiv:2404.18603), read in full -- 145,000 characters
extracted -- reports **by regime, with thresholds**:

> "Although the posit encoding scheme offers superior coding efficiency at values
> close to unity, its efficiency markedly diminishes **with deviation from
> unity**."

> "their relative accuracy exceeds that of posits **near unity**, nearly aligning
> with it **for slightly larger exponents**."

> "In the realm of small values (0 -- 15), posits maintain an overall superiority."

> "Takum encoding remains at 8 bits **until number 30** (where posits already
> require 11 bits)."

That is regime-aware reporting with numeric thresholds. The paper also states its
own format's logarithmic nature explicitly -- "the intrinsic logarithmic
characteristics of takum arithmetic" -- which is precisely the property our T19
says forces the closed form.

**The claim is withdrawn.** This literature is not doing what we said it does.

## What survives, narrowed

Not found in the paper: the closed form `2^(p-m)` for a geometric taper against a
constant-form competitor, and no treatment of the wobble case at all. So the
narrower statement stands:

> The staircase form determines the shape of a well-posed comparison. That
> mapping -- difference, linear crossover, `2^(p-m)`, duty cycle -- is stated
> here; the takum literature reports by regime without deriving the closed form,
> and we have found no treatment of the wobble case.

That is a contribution about **method**, not a criticism of anyone's work.

## The pattern, which is the real finding

| external check | our flag | outcome |
|---|---|---|
| posit64 "four orders of magnitude" | best case as general result | **withdrawn** -- qualifications present, and misattributed |
| "10.8% area, no frequency impact" | unresolvable below noise | **reclassified** -- a constraint met, measurement sound |
| "literature reports verdicts" | wrong answer shape | **withdrawn** -- takum reports by regime with thresholds |

**Three external checks, three times our flag was too strong.** None of the three
found a defect that survived reading the source.

**T21 (a checklist tuned on one's own errors over-flags others').** A procedure
derived from a specific set of mistakes acquires that set's priors. Applied
outward it fires on the shapes it was trained on, and those shapes are how *we*
went wrong, not how anyone else did. Its false-positive rate on external work is
therefore high and its true-positive rate is unmeasured -- three attempts, zero
confirmed.

**Corollary.** The instrument's demonstrated value is entirely inward. That is
not a small thing: sixteen of our own claims were withdrawn by it. But it should
be described as a self-check and never as an audit tool, and any flag it raises
on someone else's work is a question to ask them, not a finding to report.
