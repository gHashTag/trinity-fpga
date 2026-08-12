# Result of the pre-registration — cardinal failed, ordinal held

Scored against `PREREG_step2_step4_2026-08-12.md`, which was committed before
the run.

| N | predicted | band | measured (smollm2) | verdict |
|---|---|---|---|---|
| 16 | +23.04% | control | +23.72% | reproduces |
| **2** | +10.01% | 10.0–11.5% | **+9.83%** | ❌ below band by 0.2 |
| **4** | +19.75% | 19.7–20.7% | **+18.57%** | ❌ below band by 1.2 |

**Ordinal prediction held.** φ^k (8.51) < 2^(k/2) (9.83) < 2^(k/3) (17.11) <
2^(k/4) (18.57) < 2^(k/8) (22.37) < 2^(k/16) (23.72), no inversion, and the
same ordering on qwen. The section's closing invitation — *"a referee would need
one afternoon and 2^(k/2)"* — has been accepted and the ordering survives it.

## What the failure was worth

Bennett's law says MSE(N) = a + b/N², so along a **nested** chain the ratio of
successive differences must be exactly 4. Measured:

| chain | smollm2 | qwen |
|---|---|---|
| 2→4→8 | p = **1.310** | p = **1.327** |
| 4→8→16 | p = **1.537** | p = **1.545** |

Not 2, and not constant. **The two models agree to within 0.02 on both values**
across a 3.4× difference in block count, so this is the compound quantiser, not
a corpus. The paper's text previously attributed the ordering to Bennett's law;
that attribution is now retracted in place and replaced by
`prop:notbennett`.

Consequence: at p≈1.5 a doubling of scale resolution returns 35% of the previous
doubling, not 25%. **The case for stopping at 2^(k/8) rests on the area column
alone, not on saturation.**

## A mechanism, proposed and refuted in the same hour

The E2M1 grid {0,½,1,1½,2,3,4,6} repeats in every binade and so does every
2^(k/N) ladder. Guess: they interact, a commensurate ladder wastes points, and
that costs the missing half-exponent. This would have *distinguished φ — the
worst-approximable ratio — on exactly the grounds this paper cares about*, which
is precisely why it needed killing rather than believing.

**Control: slide the ladder's phase against the element grid in eighths of a step.**

| N | phase 0 | ⅛ | ¼ | ⅜ | ½ | swing |
|---|---|---|---|---|---|---|
| 2 | 9.72 | 9.76 | 9.77 | 9.80 | 9.82 | **0.10** |
| 3 | 17.08 | 17.08 | 17.07 | 17.07 | 17.08 | **0.01** |
| 4 | 18.53 | 18.51 | 18.52 | 18.53 | 18.55 | **0.04** |
| 8 | 22.34 | 22.35 | 22.35 | 22.36 | 22.36 | **0.02** |

Against the 7.28-point gap the mechanism was invented to explain. **Phase does
not matter. Refuted.** What survives: the scale is chosen by argmin of
downstream error rather than by rounding, and the downstream error saturates on
the element grid's floor — neither is Bennett's high-resolution rounding regime.
The measurement is stated; the mechanism is declined.

## Instrument audit, since the last one lied

The bracket was tested for binding before any of this was believed: for every
ladder the argmin is strictly interior (|d|max 1, 2, 3, 7, 13 against edges
3, 4, 5, 9, 17), and widening to ±3 octaves reproduces every figure bit for bit.

One residual discrepancy, recorded rather than smoothed: 2^k, 2^(k/3) and
2^(k/8) reproduce the workflow exactly, but 2^(k/16) lands at +23.72/+23.15
against the published +23.74/+23.23. The published figures are kept and this
note flags the 0.02/0.08 gap.
