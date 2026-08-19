# arXiv submission package — Ternary Network Floats

Everything here is ready. **Nothing has been submitted.** Submission is an
irreversible public act on your account, so it is yours to make.

## Decision on record

**Publication, not patent** (owner's decision, 2026-08-09). Publishing destroys
novelty in most jurisdictions, so this closes the patent route deliberately rather
than by default. Consequence: **the arXiv timestamp is the only priority this work
will have**, which is an argument for submitting sooner rather than polishing.

There is currently no other protection: both repositories are public, the specs
are Apache-2.0, and the earliest TNF spec commit is 2026-08-09.

## What to upload

| file | role |
|---|---|
| `tnf_paper.tex` | source |
| `tnf_accuracy.pdf` `tnf_ladder.pdf` `tnf_ladder_acc.pdf` `tnf_competition.pdf` `tnf_width.pdf` `tnf_radix.pdf` | figures, all referenced, all present |

Bibliography is inline (`thebibliography`, 16 entries) — no `.bib` upload needed.
Builds with `tectonic tnf_paper.tex`; `pdflatex` is not installed on this machine.

## Suggested classification

- Primary: **cs.AR** (hardware architecture) — the results are silicon costs
- Cross-list: **cs.MS** (mathematical software), **math.NA** (numerical analysis)

## Pre-flight checks, all run

| check | result |
|---|---|
| builds clean | yes, 0 errors |
| every `\includegraphics` resolves | 6/6 present |
| forward references | 3 remaining, each signposted "below" deliberately |
| priority language (`first`/`best`/`only`/`novel`) | 7 hits, **all legitimate** — "our first pass", "the best implementable radix", "only one axis is free". No claim of primacy |
| figures agree with tables | yes — `gen_figures.py` computes them from the oracles at seed 20260809, named in the text |
| theorems | 20, with 6 formal proofs; the rest derived in prose or measured |

## What a reviewer will push on, and where the answer is

1. **"Is this optimal?"** — Corollary `cor:determined`: three inputs determine the
   format, and Theorem `thm:radixopt` fixes the fourth axis unconditionally. The
   paper does *not* claim an unconditional optimum and says so.
2. **"You don't beat takum at all."** — Correct as of the 2026-08-18
   re-measurement, and the paper must say so before a reviewer does: the takum
   oracle was wrong on every negative code until #606, TNF's named rungs store
   more bits than their names (TNF16 = 17), and at equal stored width the
   accumulation benchmark is a three-way tie — TNF(4,8) 5.32e-3 / takum16
   5.70e-3 / tekum10 8.56e-3, and 1.20/1.26/1.43e-7 at 32 bits. Theorem
   `thm:floor` still bounds any claim beyond TNF's range; the equal-width tie
   removes it inside as well. What survives is hardware: 397 vs 1,182 LUT for
   the adder (2.98×) and 1 vs 542 LUT for the decode.
3. **"Your regime codecs are models, not the real thing."** — Also stated by us;
   Section `sec:valuelaw` then synthesises the *published* decoders and finds the
   cost is somewhere else entirely.
4. **"A ternary fabric doesn't exist."** — Theorem `thm:nofree`, and the binary
   fabric numbers are given as the measured claim.
5. **"TNF128 isn't measured."** — Said in the limitations; it does not route.

## Not claimed

- No ternary radix (Theorem `thm:scaleradix`: it is 0.331 positions per number worse)
- No advantage on a binary fabric from the ternary encoding (Theorem `thm:nofree`)
- No advantage over a tapered format outside TNF's range (Theorem `thm:floor`)
- On the regime-codec axis, no area advantage against takum worth naming (0.82
  mantissa bits; decisive against posit only). On the full-adder axis there
  now is one, measured: tef_add_full @ TNF(4,8) 397 LUT / 45 CARRY4 vs 1,182
  LUT / 211 CARRY4 for the linear takum-model 16-bit adder (2.98×), and
  tekum8_decode.v (real tekum) 542 LUT vs 1 LUT for the TNF field slice —
  yosys 0.65, post-synthesis only, no P&R, no board; on a ternary fabric trit
  extraction would be wiring

## Four of our own claims that the measurements falsified

Kept in the paper where they were made:

1. *The rungs do not fit their widths* — on positions they do (one per trit); on stored bits they do not: TNF8=10, TNF16=17, TNF32=30, TNF64=65, TNF1024=1025. TRUE_LADDER (conformance/tnf_ref.py) carries the exact-width rungs — TNF(2,3)=8b, TNF(4,8)=16b, TNF(4,24)=32b — which every equal-width claim must use
2. *One trit per tripling is a new regime class* — it is takum's, off by an additive 1
3. *The gap is empty because an intermediate regime is too expensive* — it costs 18% more than posit's, which ships
4. *TNF64 will cost 4,762 LUTs* — it costs 7,479; the single power law was low by 36%
