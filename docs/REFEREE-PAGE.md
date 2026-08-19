# One page for a referee — claim, record, limitation

Every row is a claim this project currently makes, the committed record that
supports it, and the limitation that bounds it. Nothing here is a claim from the
manuscript; these are the measurements produced by the autonomous audit
(W936–W942) and landed upstream as tf#634, #636, #638, #640, #641, #642, #643.

| # | claim | record | limitation |
|---|---|---|---|
| 1 | **TNF4 costs 51.29 consumer cells against fp8 e4m3's 152.57 — 2.97× cheaper — at −0.33 pp (MNIST) and −1.05 pp (Fashion) with weights *and* activations quantised** | `oracle_rtl_2026-08-20.json`, `activations_2026-08-20.json` | truth-table decoders; synthesis cells, no P&R; MLPs; PTQ with max scaling |
| 2 | **TNF4 is the only sub-8-bit format measured that works**: fp4 e2m1 and GF4 lose 70.5 / 71.3 pp | same | GF4 and fp4 are one lattice (identical to the digit on every seed) |
| 3 | The 4-bit effect **scales on two independent axes** — ×3.3 with task difficulty, ×2.3–4.5 with network capacity; t from 3.7 to 24.7, 5/5 seeds | `accuracy_seeds_2026-08-20.json`, `accuracy_seeds_big_2026-08-20.json` | two MLP sizes, two tasks; no conv, no QAT |
| 4 | **At 8 and 16 bits no format difference reaches the task** — five 8-bit formats inside 0.06 pp with activations quantised; six 16-bit formats inside 0.02 pp | same + `accuracy_coordinate_mnist_2026-08-20.json` | binomial SE is 0.16–0.25 pp: this is "not discriminative", not "equal" |
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

## What no measurement here can settle

Power, energy, on-hardware validation, a vendor-flow calibration of the open
toolchain, and every editorial decision about what the manuscript claims.

---

*φ² + φ⁻² = 3 | TRINITY*
