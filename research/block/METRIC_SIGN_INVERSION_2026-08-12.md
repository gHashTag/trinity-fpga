# The proxy is constant across four models; the task metric changes sign

## The measurement

One intervention — MXFP4's reference scale rule replaced by the squared-error
argmin over the same 254 E8M0 codes — scored two ways on four models.

**Same layers, same blocking, same quantiser, same weights.** The squared-error
script *imports* the perplexity harness's quantiser rather than reimplementing
it, so only the metric differs. That mattered here: GPT-2's `Conv1D` stores its
weight transposed relative to `nn.Linear`, and a reimplementation would silently
have blocked the other axis.

| model | encoder share, squared error | encoder share, perplexity |
|---|---|---|
| SmolLM2 | 20.5% | **+58.7%** |
| Qwen | 17.1% | **+23.3%** |
| Pythia | 20.6% | **−0.6%** |
| GPT-2 | 18.6% | **−7.2%** |
| **spread** | **1.20×** | **crosses zero** |

## What it says

**Squared error answers this question the same way on every model tried
(17.1–20.6%). Perplexity does not answer it the same way twice, and on two of
the four the squared-error-optimal encoder makes perplexity worse.**

The usual framing is that a squared-error proxy is *biased*. This is worse and
more specific: the proxy is **stable**, and stably unrelated to the task-metric
answer. A design loop tuned on squared error would get a reproducible number on
every model and be wrong about the sign on half of them.

## The control that makes it trustworthy

The argmin encoder minimises squared error over the E8M0 ladder block by block,
so **its squared-error share is positive by construction**. Measuring it anyway
is the point: a negative entry in the left column would have condemned the
harness, not the theory. All four are positive, and SmolLM2's 20.5% reproduces
the published figure from code sharing only the quantiser with the run that
produced it.

> **Measure the tautology.** A quantity that *must* come out one way is the
> cheapest available check on an instrument, and it is worth a run precisely
> because it cannot be interesting.

## Transferability, updated to four models

| claim variant | SmolLM2 | Qwen | Pythia | GPT-2 | spread |
|---|---|---|---|---|---|
| perplexity, best encoder both sides | 9.50% | 7.18% | 12.38% | 7.19% | **1.72×** |
| perplexity, against Algorithm 1 | 20.25% | 9.16% | 12.31% | 6.74% | **3.00×** |

Best-against-best remains the more stable variant, but **the gap narrowed when
Pythia arrived** — 1.32 vs 3.00 at three models, 1.72 vs 3.00 at four. Recorded
as a narrowing rather than stopping at the more favourable count.

## Standing

Stop-rule unchanged. As **written**, met. As **intended**, not — and this record
adds the sharpest reason yet: on two of four models the encoder half of the
headline is negative, so the headline's size depends on which model is asked and
on which of two defensible baselines is chosen.
