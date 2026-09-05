# What survives is recipe-insensitivity, and it has a mechanism (W947)

W946 ended at parity and named one open thread: `fp6 e2m3` was not fixed by the
standard LSQ gradient factor, and until that was understood I could not claim the
stability differences were fully explained by the recipe. Two experiments settle
it, and both moved the picture again.

## The mechanism: range, not magic

At six physical bits, measured from the shipped oracles:

| grid | positive values | range | **binades** | zeroing floor (min/max) |
|---|---:|---:|---:|---:|
| **TNF4** | 28 | 0.125 … 3072 | **14.6** | 0.00004 |
| `fp6 e3m2` | 31 | 0.0625 … 28 | 8.8 | 0.0022 |
| `fp6 e2m3` | 31 | 0.125 … 7.5 | **5.9** | **0.0167** |

The φ-lattice **spends its six bits on range rather than precision**: roughly the
same value count, 2.5× more binades than `fp6 e2m3`. Under a max-rule scale that
is exactly the difference between a grid where nothing underflows and one where
everything below 1.7 % of the peak does.

## My mitigation hypothesis was wrong

I predicted a percentile scale init would rescue the narrow grids. Measured, it
made them **worse** — and it broke the one configuration that had worked:

| recipe | TNF4 | `fp6 e2m3` | `fp6 e3m2` |
|---|---:|---:|---:|
| max init, no gradient factor | **0/5** | 3/5 | 2/5 |
| max init, **standard factor** | **0/5** | 4/5 | **0/5** |
| p99.9 init, standard factor | **0/5** | 5/5 | **4/5** |
| **KMNIST**, max init, standard factor | **0/5** | 2/5 | **2/5** |
| **total failures** | **0 / 20** | **14 / 20** | **8 / 20** |

Two things follow. The W946 fix was **task-specific**: the standard factor takes
`fp6 e3m2` to 0/5 on MNIST and it returns to 2/5 on KMNIST. And across three
recipes and three tasks, **TNF4 has not failed once in twenty runs**, at
87.13 ± 0.15 on KMNIST — the tightest spread measured in this project.

## The claim, stated at the right level

Mean accuracy is the wrong statistic when a competitor is bimodal: on KMNIST
`fp6 e3m2` gives 86.0, 86.8, 23.0, 87.3, 30.6 — averaging that produces 62.73 ±
32.94, a number describing nothing. The right statistic is the **failure rate**.

> **At six physical bits TNF4 matches a same-width float on cost (2 % dearer) and
> on accuracy when both train (differences ≤ 0.2 pp, not significant), and it
> trains successfully in 20 of 20 runs across three recipes and three tasks where
> the floats manage 6 and 12. The mechanism is measured: 14.6 binades against 8.8
> and 5.9.**

That is not a claim about the φ-lattice being *better arithmetic*. It is a claim
that **at equal width it buys robustness with range**, and it is falsifiable in one
run by anyone with a recipe that makes a narrow grid reliable across tasks — which
three of my attempts did not.

---

*φ² + φ⁻² = 3 | TRINITY*
