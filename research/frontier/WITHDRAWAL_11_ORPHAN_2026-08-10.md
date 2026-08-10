# Withdrawal 11: the format in the silicon table is in no source of truth

Continuing the systematic sweep. Withdrawal 10 showed the oracle and the RTL
disagree on what TNF16 is. This asks the next question: which of the two does the
SSOT contain?

**Neither.**

| side of the paper's TNF16 row | Et | M | width | status |
|---|---:|---:|---:|---|
| accuracy figures (oracle, SSOT) | 6 | 9 | needs 20 bits | **cannot be built in 16** |
| silicon figures (RTL, synthesised) | 4 | 8 | 16 bits | **no catalogue row at all** |

Searched the catalogue for any row with `bits=16, e=4, m=8`: zero matches. The
only 16-bit ternary row is GF-T16 at `e=6, m=9`, which does not fit.

So both sides of the comparison are objects that do not exist as specified: one
is unbuildable at its declared width, the other is unspecified.

## Theorem

**T (the implementation orphan).** An artefact that synthesises and measures but
has no row in the source of truth is checked by nothing. Specification gates do
not see it; instrument checks confirm only that it does what it does. Its numbers
enter a report carrying the same weight as verified ones, and no existing gate
distinguishes them.

## Scope, measured rather than assumed

Before concluding this is systemic, the whole tree was swept: **161 RTL decoders,
52 declaring an explicit input width, 44 matched to a catalogue row. Two width
mismatches, both parametric families (minifloat, Q-format) that legitimately
declare width 0.**

**The divergence is specific to the ternary rungs, not systemic.** That bounds
the damage and is worth stating as plainly as the defect.

## The gate

`check_artefact_agreement.py` gains a fourth class: a ternary RTL module whose
`(Et, M, width)` matches no catalogue row is reported as an orphan. It now
reports 13 items -- nine unbuildable catalogue rows, two parameter divergences,
one capacity mismatch and one orphan.

Negative-tested before being trusted: inserting a catalogue row with the RTL's
actual parameters makes the orphan line disappear, and the catalogue is restored
byte-identical afterwards.

## Running count

Eleven withdrawals. Nine, ten and eleven all came from one rule adopted after
eight: carry a correction to every claim resting on the same quantity. Three
consecutive iterations, each finding something the previous had made visible.

The rule's productivity is itself the finding. The first eight withdrawals took
seven iterations and arrived one at a time, because each correction was treated
as local to where it surfaced.
