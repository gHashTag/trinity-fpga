# Mutation-testing the gates: two holes, one misclassification, one false suite count

## Why

Iteration 113 found the self-consistency gate counting retraction marks in the
**passive voice only**, so three retractions written "we withdraw it" were
invisible and the paper's self-reported count drifted below the truth **while the
gate stayed green**. That is not an adversary routing around a check. It is an
author writing English.

One gate with that hole implies a habit, and the same author wrote all 24.

## Method: inject the defect, twice

A gate that passes its own regression is only known to catch the one phrasing its
author happened to write. So each defect is injected **twice**: once in the
phrasing the gate was written against (a **control** — it must FAIL, or the
harness is broken) and once in an equally ordinary alternative (the **test** — if
it PASSES, the hole is real). `tools/mutate_gates.py`, restoring the paper from a
byte-verified backup after every mutation.

**The first version of the harness reported four holes. All four were the
harness.** Two controls passed, which is what controls are for: `check_paper_numbers`
and `check_scoped_superlatives` end in unconditional `sys.exit(0)` and cannot
fail, and the `check_withdrawn_live` mutation put the withdrawal and the live
assertion in the **same paragraph**, which the gate correctly ignores.

## Finding 1 — two of my nine "gates" are reports

`check_paper_numbers` and `check_scoped_superlatives` end in
`sys.exit(0)` unconditionally. **I have reported "all 9 gates green" every
iteration for thirteen iterations.** Two of the nine could not have been
anything else.

Worse, `check_paper_numbers` was **not** silent: it was listing **65** literals in
the paper with no source in any data file, including every number added in
iterations 111–112. The suite line said green; the tool said 65.

> **A tool that cannot fail is a report. Counting it among gates is a false
> statement about your own verification, and it is one you make to yourself.**
> The suite is **8 gates and 2 reports**, and the reports' contents must be read
> aloud each run, not summarised as "green".

## Finding 2 — the provenance rule, broken by me, three iterations running

Of those 65, the block-shape table (2.404, 2.431, 2.454, 2.465), the
lattice-exponent sweep and the sensitivity columns were all mine, from scripts
whose stdout went to `/tmp`. The paper's own rule is that *a number whose only
witness is a log has no instrument behind it*.

`model_sensitivity.json` and `lattice_exponent.json` now carry them. **65 → 51.**

## Finding 3 — the same voice hole in a second gate, confirmed by behaviour

`check_withdrawn_live` guards the most dangerous failure there is here: a number
the paper withdraws still asserted as live somewhere else. Its zone-opening
pattern was **passive only**. Mutation-confirmed: "We withdraw the 77.77% figure"
opened no zone, so the gate never went on to look for 77.77 elsewhere.

Fixing it exposed two further defects, both worth more than the original:

**3a. Extending the pattern created false positives.** The paragraph where
`cor:designrule`'s strong form is withdrawn *mentions* the ratios 1.02 and 1.31,
which are current measured values. The gate cannot tell "number withdrawn" from
"number cited while explaining a withdrawal". The fix is not ad-hoc exclusions
but **scoping by voice**: the active voice names its object in the same sentence;
the passive voice heads a paragraph of elaboration. Sentence zone for one,
paragraph zone for the other.

**3b. A decimal point is not a full stop.** With a sentence zone, `[^.]*`
truncated `We withdraw the $77.77\%$ figure.` **at the decimal**, so the only kind
of number this gate exists to track fell outside its own zone. The passive branch
had survived solely because its zone is the whole paragraph.

> **The gate that guards numbers could not parse a sentence containing a number.**
> Found by mutation, invisible to reading — I had read that regex twice that hour.

## Status

All four mutations now caught; controls all fail as they must; the real paper
passes all 8 gates.

| gate | mutation | verdict |
|---|---|---|
| check_withdrawn_live | passive withdrawal + live number | ✓ control fails |
| check_withdrawn_live | **active** withdrawal + live number | ✓ now caught |
| check_latex_hygiene | duplicate `\label` | ✓ control fails |
| check_latex_hygiene | `\ref` with no `\label` | ✓ control fails |

## The transferable lesson

> **Regression-passing tells you a checker catches the case you wrote. Mutation
> testing tells you what it catches.** And the mutations must come with controls,
> because a harness that finds holes everywhere has usually found itself.
