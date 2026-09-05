# The range is bought for free, and longer training widens the gap (W948)

W947 named the mechanism — the φ-lattice spends its six bits on range (14.6
binades) where the floats spend theirs on precision (8.8 and 5.9). The obvious
price is a coarser step, and the obvious place to find it is at convergence. So:
ten epochs instead of three, same seeds, same recipe, weights **and** activations
quantised.

## The coarser step costs nothing at convergence

| task | format | accuracy of the runs that trained |
|---|---|---:|
| MNIST | **TNF4** | **97.68** (n = 5) |
| MNIST | `fp6 e2m3` | 97.54 (n = 1) |
| Fashion | **TNF4** | **87.38** (n = 5) |
| Fashion | `fp6 e2m3` | 87.10 (n = 3) |
| Fashion | `fp6 e3m2` | **88.12** (n = 1) |

Where a narrow grid trains at all, it lands within **0.7 pp** of TNF4 and on one
task **above** it. Ten epochs do not expose a precision penalty: **the range is
bought for free on these tasks.**

## But the failures get worse with training, not better

| configuration | TNF4 | `fp6 e2m3` | `fp6 e3m2` |
|---|---:|---:|---:|
| MNIST 3 ep, max, no factor | 0/5 | 3/5 | 2/5 |
| MNIST 3 ep, max, standard factor | 0/5 | 4/5 | **0/5** |
| MNIST 3 ep, p99.9, standard | 0/5 | 5/5 | 4/5 |
| KMNIST 3 ep, max, standard | 0/5 | 2/5 | 2/5 |
| **MNIST 10 ep**, max, standard | 0/5 | 4/5 | **5/5** |
| **Fashion 10 ep**, max, standard | 0/5 | 2/5 | 4/5 |
| **total** | **0 / 30** | **20 / 30** | **17 / 30** |

`fp6 e3m2` goes from **0/5 at three epochs to 5/5 at ten** on MNIST — the same
task, the same recipe, only more steps. That is exactly what a runaway predicts:
each step is another chance for the activation scale to fall, and once it is near
zero the gradient that would raise it is gone. **More training makes a
collapse-prone grid more likely to collapse, not less.**

TNF4 is now **0 failures in 30 runs** across four recipes, three tasks and two
training lengths.

## What this settles and what it does not

**Settles:** the range is not paid for in accuracy at these depths — the two are
equal when both train — and the failure mode is a training-dynamics property that
worsens with steps.

**Does not settle:** whether a recipe exists that stabilises a narrow grid across
tasks. Four of mine did not, and that is the whole warrant for the claim.
`FALSIFY-ME.md` states the protocol that would refute it in one run.

**Also unsettled:** everything at wider formats and larger models. Six bits on
MLPs is where this holds; nothing here speaks to 8-bit deployments, where every
format was already indistinguishable, or to models where the activation
distribution is not what a small MLP produces.

---

*φ² + φ⁻² = 3 | TRINITY*
