# One page for a referee — claim, record, limitation

Every row is a claim this project currently makes, the committed record that
supports it, and the limitation that bounds it. Nothing here is a claim from the
manuscript; these are the measurements produced by the autonomous audit
(W936–W942) and landed upstream as tf#634, #636, #638, #640, #641, #642, #643.

| # | claim | record | limitation |
|---|---|---|---|
| 1 | **WITHDRAWN (W946). At matched width TNF4 is at PARITY with `fp6 e3m2`:** 51.29 vs **50.29** cells (2 % dearer), **+0.11 / +0.17 pp** accuracy (n.s. on one task), and **96.70 ± 0.38 vs 96.58 ± 0.56** in stability once the quantiser has its gradient-scaling factor | `oracle_rtl_width_matched_2026-08-20.json`, `stability_gradscale_2026-08-20.json` | the earlier 2.97× compared six bits against eight |
| 1a | **Parity is the result.** A novel lattice matching a mature IEEE-style encoding at equal width means the φ-structure costs nothing to adopt | same | not superiority; the paper's current hardware claim is not supported at matched width |
| 1b | **Recipe-insensitivity survives; its EXPLANATION is withdrawn (W949).** Sweep now **45 runs** over five recipe axes: successes TNF4 **45/45**, `fp6 e3m2` **16/45**, `fp6 e2m3` **12/45**. The newest axis is the **scale initialisation**, and it alone flips `fp6 e3m2` from **0/5 to 5/5** while TNF4 moves 0.10 pp | `scaleconv_w949.json`, `stability_*.json`, derived by `verify_numbers.py` (38 checks) | **the range mechanism is withdrawn**: it was computed as min/max of the grid, i.e. peak→format max, while every run mapped peak→1.0, under which TNF4 zeroes 12.5 % against e3m2's 6.25 % and keeps 7 levels against 12. TNF4 wins while handicapped, so we do **not** know why |
| 1c | **RESOLVED AGAINST US (W950). The instability was the RECIPE's, not the format's.** With the OCP-style **computed power-of-two** scale — never learned — **all 30 runs succeed**: block 32 and per-tensor, all three formats. `fp6 e2m3` goes **28/40 failures → 0/5** at unchanged granularity. Paired at per-tensor, TNF4 is **−0.376 pp** vs `fp6 e2m3` (t = −7.24, **0/5** seeds favour TNF4) and −0.250 vs `fp6 e3m2` (t = −5.15) | `blockquant_w950.json`, derived by `verify_numbers.py` (53 checks) | **at six bits, on these tasks, the φ-lattice has no measured advantage over a same-width float and a measured deficit under the standard recipe** |
| 1d | **Mechanism MEASURED, not inferred (W951).** Every run overshoots the top of the grid, so "saturation ⟹ failure" is dead (6.7 % agreement). What separates is **magnitude**: among 45 learned-scale runs the worst success overshoots **1 510×**, the best failure **84 775×** — **non-overlapping**. A computed power-of-two scale bounds the overshoot in **[1,2)** by construction; measured max over 90 runs **2.0000** | `saturation_w951.json`, `sweep_w951_*.json` | supersedes the W950 proxy, which measured a correlated quantity (90.8 %) |
| 1e | **Sweep redone under the deployed recipe (W951): 0 failures in 90 runs**, three tasks × two granularities × three formats × five seeds. Same tasks and seeds under the learned scale: 9 failures | same | TNF4 has still never failed anywhere — a true claim about tolerating a bad recipe, not about deployment |
| 1f | **The 2 %-dearer figure prices a decoder, not a datapath (W952).** Range forces width: TNF4 needs **17** bits per value, **33** per product, a **38-bit** block-32 accumulator, against `fp6 e2m3`'s **7 / 13 / 18**. A fixed-point MAC lane costs **768** cells against **159** — **4.83×**. The part no implementation escapes, the accumulator, is **48 vs 23** cells, i.e. **+0.78 cells per element** amortised over 32 (**≈ +1.5 %**) | `mac_w952.json`, `acc_w952.json`, `widths_w952.json` | **quote the bracket +1.5 % … +383 %, never one end**: the float-style lane (mantissa multiply + exponent add) is **not measured**, and it is the implementation an MX engine most likely uses |
| 2 | **TNF4 is the only sub-8-bit format measured that works under PTQ**: fp4 e2m1 and GF4 lose 70.5 / 71.3 pp | same | GF4 and fp4 are one lattice (identical to the digit on every seed) |
| 2a | **The advantage is a range, not a number.** Without retraining: **13–65 pp**. With max-scale QAT: **+0.19 / +0.89 pp**. With a **learned** scale: **+1.58 / +0.91 pp** — a better recipe *widened* it eightfold on MNIST | `qat_2026-08-20.json`, `lsq_2026-08-20.json` | epoch budgets differ (4 vs 3) across the two QAT runs; paired tests are within-run |
| 2c | **WITHDRAWN and replaced (W945).** The 4-bit comparison was not width-matched: TNF4 is physically **6 bits / 57 grid values**, fp4 e2m1 is 4 bits / 15. Against real 6-bit floats the advantage is **+0.11 (MNIST, t 2.2)** and **+0.17 (Fashion, t 1.2 — not significant)**, and with quantised activations on Fashion **fp6 e3m2 wins by 0.42** | `lsq_width_matched_2026-08-20.json` | four waves of headline numbers were measured against a competitor two bits narrower |
| 2d | **What survives is stability, not accuracy.** TNF4's σ is **0.17–0.72 pp** in every configuration; with quantised activations on MNIST `fp6 e2m3` has **σ = 46.09** and `fp6 e3m2` **σ = 32.33** | same | one architecture, two tasks, three epochs |
| 2b | On a **CNN** the collapse is smaller and unstable: fp4 −13.13 ± 13.66 (MNIST), −25.21 ± 11.31 (Fashion), TNF4 −0.15 / −0.31 | `conv_2026-08-20.json` | two epochs; per-tensor scale over small kernels spans fewer magnitudes |
| 3 | The 4-bit effect **scales on two independent axes** — ×3.3 with task difficulty, ×2.3–4.5 with network capacity; t from 3.7 to 24.7, 5/5 seeds | `accuracy_seeds_2026-08-20.json`, `accuracy_seeds_big_2026-08-20.json` | two MLP sizes, two tasks; no conv, no QAT |
| 4 | **At 8 and 16 bits no format difference reaches the task.** The null has now held across MLP **and CNN**, weights-only **and** weights+activations, two tasks, two sizes, five seeds — largest drop 0.06 pp | same + `accuracy_coordinate_mnist_2026-08-20.json`, `conv_2026-08-20.json` | binomial SE is 0.16–0.25 pp: this is "not discriminative", not "equal" |
| 5 | **The consumer is priced by alphabet width and saturates at its own precision**: 3.43 cells at 2 bits → 385 at 16 → 427 at 32 | `alphabet_width_2026-08-20.json` | one 12×8 multiply as the consumer; a wider one moves the knee |
| 6 | **The decode gap survives fusion exactly** (TNF16 vs BNF16: 8.000 cells bare and fused) **but is 2 % of the unit** | `fusion_2026-08-20.json` | 16-bit modules; see #8 |
| 7 | **Our posit baseline is sound**: `posit16_decode` costs 1.36× PACoGen's `data_extract_v1` while assembling a full fp32 it does not; at operator level TNF's adder is 1.23× cheaper than PACoGen's `posit_add` | `head_to_head_pacogen_2026-08-20.json` | different microarchitecture (handshake vs combinational); correctness not re-verified |
| 8 | **Three physical widths circulate for one rung** — TNF16 is 19 bits by the oracle, 17 by the caption, 16 by a module name | issue #644 | a specification question for the author, not a measurement |
| 9 | **The accuracy multiple is carried by the prior**: TNF16 over posit16 is 14.63× under the published uniform-77-binade draw and 1.02× under a standard normal; TNF16's own error is prior-invariant to 1.046× | `prior_sensitivity_2026-08-20.json` | round-trip error, not task accuracy; LNS16's row is not measured by that path |
| 10 | **The empirical prior of trained weights spans 8.1 binades**, against the 77 the regenerators draw from | `accuracy_coordinate_mnist_2026-08-20.json` | one architecture, two tasks |

## What this project has withdrawn about its own work

- "LNS16 does not reproduce" — **withdrawn** (tf#632). `MATRIX.md:35` lists it at
  43.11 MHz, 0.16 % from the published value; the exception came from `None` cells
  in our own reference table, and the band was applied with a denominator it was
  never defined with.
- A 70-point 4-bit gap — **withdrawn** as an unscaled artefact: fp4 and GF4 flush
  98.8 % of weights to zero without a per-tensor scale.
- A frontier row priced by module name — **withdrawn** (tf#642), the error the
  report existed to expose.
- "A frequency harvested under a slack constraint measures headroom" — **corrected**:
  true for router1, false for router2, which does not consume `--freq`.
- "TNF4 is the only format that works at four bits" — **narrowed** to post-training
  quantisation. Under QAT the gap is 0.19–0.89 pp, not 38–64.

## What no measurement here can settle

Power, energy, on-hardware validation, a vendor-flow calibration of the open
toolchain, and every editorial decision about what the manuscript claims.

---

*φ² + φ⁻² = 3 | TRINITY*
