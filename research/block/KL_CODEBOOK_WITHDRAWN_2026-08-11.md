# Withdrawn: the KL-optimised codebook does not beat MXFP4. It was fitted to one model.

Earlier today a codebook optimised against KL divergence measured **20.2587
perplexity on SmolLM2-135M against MXFP4's 21.9397 — a 7.66 % win**. An
adversarial check on held-out *windows* made it look stronger still: the
advantage grew to **−8.66 %** on windows 40–79, with `t(39) = −12.51`, better in
**39 of 40** windows, sign-test `p = 7.5e-11`.

It is wrong. A second check ran the same three codebooks on two models the
codebook had never seen:

| model | fp32 | MXFP4 | Lloyd-Max | KL-optimised | KL vs MXFP4 |
|---|---:|---:|---:|---:|---:|
| SmolLM2-135M *(fitted on this)* | 14.4874 | 21.9397 | 22.9166 | **20.2587** | **−7.66 %** |
| Qwen2.5-0.5B | 12.6999 | 15.4374 | 16.0703 | 15.7425 | **+1.98 %** |
| Pythia-160M | 25.9561 | 47.6504 | 52.9992 | 51.7641 | **+8.63 %** |

**It loses on both models it was not fitted to**, and the per-window paired tests
rule out noise: worse on 17 of 20 Qwen windows (`t = +4.32`) and 37 of 40 Pythia
windows (`t = +8.97`).

The ranking inverts completely. KL-optimised is *first of three* on the
checkpoint it was fitted to and *second of three* on both checkpoints it was
not. That is the signature of six free parameters fitted to one model's logits,
not of a better element format.

## The methodological lesson, which is the valuable part

**Held-out windows are not a held-out model.** The first check was a good check —
disjoint windows, a paired test, a huge t-statistic, the leaked windows deleted
and the result unchanged to 0.12 pp — and it certified an overfit. It could not
have done otherwise: the codebook was fitted to *this model's* logits, and every
window of wikitext-2 run through *this model* inherits that fit.

The unit that has to be held out is the unit the parameters were fitted against.
Here that was the model, not the text. A test that varies the wrong axis measures
generalisation across an axis nobody was overfitting to, and passes.

## What survives

**One weaker claim transfers, and it is not nothing.** KL-optimised beats
Lloyd-Max on *all three* models — 20.2587 vs 22.9166, 15.7425 vs 16.0703, 51.7641
vs 52.9992. Optimising a codebook against KL rather than squared error is a real
improvement over the squared-error optimum, on every model tried.

So the argument in `BLOCK_AXIS_CLOSED_2026-08-10.md` is still wrong as an
argument: Lloyd-Max is the ceiling for squared error, not for perplexity, and
"the best possible one" was unearned. `kl_optimal_codebook.py` demonstrates that.

**But its conclusion stands, and now on stronger evidence than it had.** "No
eight-level element format will take the block axis from MXFP4" survives on both
out-of-sample models. The search that was built to break it instead confirmed it
against a checkpoint it had never seen — twice.

## And a second deflation: most of it was optimisation, not the objective

A separate attack gave **squared error** the same optimisation budget the KL
search had — same 120-evaluation coordinate descent, same step schedule, same
seeds — and it also beats MXFP4 on the fitting model:

| codebook | perplexity | vs MXFP4 |
|---|---:|---:|
| KL-optimised | 20.2586 | **−7.66 %** |
| nSSE-optimised, equal budget, seed MXFP4 | 20.7900 | **−5.24 %** |
| nSSE-optimised, run to convergence | 21.3561 | −2.66 % |
| wSSE-optimised, run to convergence | 21.6574 | −1.29 % |
| MXFP4 (E2M1) | 21.9397 | — |
| Lloyd-Max | 22.9166 | +4.45 % |

*nSSE = block-normalised squared error, the objective Lloyd-Max is defined by.
wSSE = weight-domain squared error.*

So the brief's own falsification condition fires: **if squared-error
optimisation with an equal budget also beats MXFP4, the story is "optimisation
helps", not "the objective matters".** It does, by 5.24 %. The KL objective buys
a further 2.4 pp on the fitting model, and given the transfer failure that
remainder is most likely fit as well.

Note what this also says about Lloyd-Max: it is the *converged* squared-error
optimum and it is the **worst** row in the table. A partially-converged
squared-error search beats its own converged optimum by 2.6 pp on perplexity.
That is `METRIC_DISAGREEMENT` again — running the wrong objective to convergence
is worse than running it badly.

**The open question this opens.** The nSSE codebook was fitted to SmolLM2's
*weight statistics* only, with no forward pass. Weight distributions are far more
similar across models than logits are, so it may transfer where the KL codebook
did not. That is being measured; until it returns, nothing here says whether any
codebook beats MXFP4 out of sample.

## What this costs the other documents

- `CODEBOOK_SILICON_2026-08-11.md` measured what an arbitrary codebook costs in
  silicon, motivated by this result. **The silicon measurements are unaffected**
  — they are about a decoder, not about which codebook wins — but the motivation
  is withdrawn and the document now says so.
- `PRIOR_ART_CODEBOOKS_2026-08-11.md` opens on the 7.66 % figure. Its literature
  survey is unaffected and its central point is *strengthened*: the field
  optimises squared error, and the KL objective does beat squared error — it
  simply does not beat a hand-designed format once you leave the fitting model.
- Nothing reached the site. Checked: `20.2586` and `20.2587` appear in zero built
  files.

---

*The verification that killed this was commissioned specifically to try to kill
it, with five independent attacks, and the one that worked was the one asking
whether the result transfers. The attack that said SURVIVES with `p = 7.5e-11`
was not wrong about what it measured; it was measuring the wrong thing. Both are
recorded because the pair is the lesson.*
