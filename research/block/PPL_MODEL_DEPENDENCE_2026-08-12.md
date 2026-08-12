# The perplexity gain halves between the two models — partial record

Second witness for the perplexity half, second model. `step8` still running;
everything below is complete and reproducible from `verify_block_ppl.py`.

| arm | smollm2 (148 windows) | Qwen (146 windows) |
|---|---|---|
| fp32 (the ruler) | 15.4148 | 13.0687 |
| mxfp4_floor | 25.0798 | 16.1795 |
| mxfp4_argmin | 22.1015 | 15.8346 |
| **step3** (2^(k/3), ours) | **20.0022** | **14.6979** |
| step8 (2^(k/8), binary) | 18.9053 | 14.5698 |

| gain | smollm2 | Qwen |
|---|---|---|
| encoder alone (argmin vs floor) | **+11.88%** | **+2.13%** |
| step3 vs floor | **+20.25%** | **+9.16%** |
| step3 vs the baseline's own best encoder | **+9.50%** | **+7.18%** |
| step8 vs floor | +24.62% | +9.95% |
| step8 vs the baseline's own best encoder | +14.46% | +7.99% |

## The binary ladder's perplexity advantage is also SmolLM2-sized

On SmolLM2 the binary `2^(k/8)` ladder beats our ternary `2^(k/3)` by **4.37
points** against the floor and **4.96** best-against-best. On Qwen the same
comparison gives **0.79** and **0.81** — an advantage five to six times smaller.

The sign replicates: binary wins on both models, on both baselines, and the
paper continues to say so. But *how much* it wins by is another magnitude that
does not transfer. This is recorded because it runs mildly in our favour and is
therefore exactly the kind of number that needs stating carefully rather than
promoted.

## The finding

**The headline gain more than halves between the two models** — +20.25% against
+9.16%. And the split moves with it: on smollm2 the encoder alone is 11.88 of
the 20.25 points (59%); on Qwen it is 2.13 of 9.16 (23%).

The RMSE axis showed the same asymmetry in the same direction and with the same
sign: the encoder arm was +3.50% on smollm2 against +2.81% on Qwen.

## Why it matters for how the claim is stated

Best-against-best is the honest comparison, and there the two models are much
closer — **+9.50% and +7.18%** — because the encoder term, which is where the
models disagree most, has been removed from both sides.

> **A gain that halves between two models is partly a property of the model.**
> Quoting one model's figure as the headline is quoting the favourable one. The
> best-against-best figure is not only the fairer comparison, it is the more
> *stable* one — which is an argument for it that has nothing to do with fairness.

## Standing

Both models, both metrics, two independent instruments each. The stop-rule as
**written** remains met. As **intended** it remains unmet, and this record adds a
second reason: the size of the win depends on which model is asked.
