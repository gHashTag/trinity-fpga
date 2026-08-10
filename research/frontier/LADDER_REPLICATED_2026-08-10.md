# The ladder law replicates on a second model

One model makes an observation. The crossover was measured on SmolLM2-135M; this
repeats it on Qwen2.5-0.5B -- a different architecture, four times the
parameters, a different tokenizer and different training data -- with the
protocol unchanged: per-output-channel scale, codebook of exactly `2^bits`
entries including zero and sign, wikitext-2, 12 windows of 2048 tokens.

| bits | SmolLM2-135M (fp32 14.36) | Qwen2.5-0.5B (fp32 12.27) |
|---|---|---|
| 3 | **shift 2309.86**, phi 41836, sg 1.37e6, pl 6.72e6 | **shift 2384.96**, phi 1.23e5, sg 2.14e6, pl 1.08e7 |
| 4 | shift 76.81, **phi 24.43**, sg 25.10, pl 55.72 | shift 20.94, **phi 16.24**, sg 17.98, pl 47.41 |
| 5 | shift 77.52, phi 22.73, sg 18.93, **pl 16.45** | shift 20.87, phi 15.33, sg 14.09, **pl 13.17** |

**Same winner at every budget, and the same complete ordering at every budget.**
Shift at three bits, `phi` at four, the plastic number at five, with supergolden
second at five and third at four in both models.

The crossover is therefore not a property of one weight distribution. It follows
from the span identity -- a ladder of ratio `r` with `n` magnitudes covers
`r^(n-1)`, so finer steps are bought with range -- which holds for any
distribution of finite dynamic range. What a particular model sets is the
*location*, and the two models put it in the same place.

## The four-bit case reads better on the larger model

On SmolLM2 `phi` beat supergolden by 2.7%, which twelve windows cannot resolve,
so the honest statement there was a tie. On Qwen the margin is 10.7% -- 16.24
against 17.98 -- which is outside anything the window count explains. Taken
together: at four bits `phi` is at worst tied and on the larger model clearly
ahead, while supergolden costs an extra register either way.

That is the operating point this work is about, and it is the one place in the
sweep where the cheapest adequate rung is also the best one.

## Where our alphabet loses, stated plainly

Five bits, both models: the plastic number wins, by 28% on SmolLM2 and 14% on
Qwen. `phi` is third of four there. We are not going to pretend otherwise, and
the reason it does not overturn the design is separate and measured: by five
bits the optimum has moved past the plastic number too, and the next rung down
costs 2.1x the area (degree 4, three add/subtracts against one). The regime
where a multiply-free datapath pays for itself is three to five bits, and inside
it degrees 2 and 3 are the only affordable rungs.
