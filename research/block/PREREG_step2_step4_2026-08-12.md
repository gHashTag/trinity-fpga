# Pre-registration: the two gaps in the scale-ladder curve

Written **before** the measurement, committed **before** the measurement, so
that the record shows what was predicted rather than what was rationalised.

## Why these two points

The paper's own closing sentence for the block section reads: *"a referee would
need one afternoon and $2^{k/2}$ to say so first."* That is a standing invitation
to refute the section's ordering, and it is cheaper to accept it than to wait for
someone else to. The curve is measured at $N \in \{1, 1.4404, 3, 8, 16\}$ points
per binade. $N=2$ and $N=4$ are the gaps, and $N=2$ is the one the paper names.

## The prediction and where it comes from

Bennett's law for a companding quantiser says distortion falls with the square of
the step, so total squared error should read
$\mathrm{MSE}(N) = a + b/N^{2}$, with $a$ the element-grid floor that no scale
ladder can remove and $b/N^{2}$ the scale-misfit term.

Fitted on $N=3$ and $N=8$ (smollm2), the law gives:

| N | predicted gain | measured |
|---|---|---|
| 16 | $+23.04\%$ | $+23.74\%$ — **control, under-predicts by 0.70 points** |
| **2** | $\mathbf{+10.01\%}$ | *to be measured* |
| **4** | $\mathbf{+19.75\%}$ | *to be measured* |

The control fails on the conservative side by 0.70 points, so the honest band is
**$N=2$: 10.0–11.5%** and **$N=4$: 19.7–20.7%** on smollm2.

## What would falsify what

1. **Ordinal (the claim that matters).** The paper asserts error is monotone in
   points per binade *and in nothing else*. That requires
   $\varphi^{k}\,(8.51\%) < 2^{k/2} < 2^{k/3}\,(17.11\%) < 2^{k/8}$.
   **If $2^{k/2}$ beats $2^{k/3}$, the section's central ordering is false** and
   the referee's afternoon has been spent here instead.
2. **Cardinal.** If the measured value lands outside the band above, Bennett's
   law is not the right model for this quantiser at coarse $N$, which is itself
   worth saying — the section currently cites the law as explanation.
3. **A specific trap.** $N=2$ is $\sqrt{2}$, and $\sqrt{\varphi}$ at $N=2.8808$
   already sits beside $2^{k/3}$ at $N=3$. If $N=2$ instead sits beside
   $\varphi^{k}$ at $N=1.4404$ — a 39% gap in $N$ — the axis is not $N$.

## The instrument

`research/block/verify_block_rmse.py`, the same independently-written script that
reproduced the MXFP4 baseline to ten significant figures and the $2^{k/3}$ and
$2^{k/8}$ arms exactly. Its bracket spans equal octaves for every ladder — the
bug that this file's predecessor caught and that would otherwise have handed
$N=2$ an unfairly wide search relative to $N=16$.

## Prior on my own predictions

The last pre-registered prediction in this campaign — the ordering of the three
horn treatments — **failed on both axes**, both in the ranking and in which axis
decided it. That is the reason this file exists.
