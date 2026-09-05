# T39 — the geometric scale grid is optimal, and the float penalty is 1/(2 ln²2)

T37 (`GEOMETRIC_SCALE_2026-08-10.md`) **measured** that a geometric scale grid
beats a float one at every width. T38 (`SCALE_PHASE_THEOREM_2026-08-11.md`)
**proved** that an E8M0 scale wastes `1 − frac(log₂a − log₂T)` bits of headroom
per block, half a bit in expectation.

T39 derives the first from the second, and turns "geometric wins" from a
measurement into a uniqueness result with a closed-form penalty.

## Setup

A scale grid with `2^m` points per octave partitions each octave of
log-magnitude into gaps `g₁ … g_{2^m}` with `Σgᵢ = 1` bit. A block whose maximum
falls inside gap `i` is rounded up to that gap's top, so its headroom waste is
uniform on `[0, gᵢ]`.

## Proposition (expected waste)

*Over log-uniform block maxima,*

    E[waste] = (1/2) · Σᵢ gᵢ²   bits.

**Proof.** A log-uniform maximum lands in gap `i` with probability `gᵢ / Σgⱼ = gᵢ`,
and conditional on landing there its waste is uniform on `[0, gᵢ]` with mean
`gᵢ/2`. Summing, `E[waste] = Σᵢ gᵢ · gᵢ/2`. ∎

## Theorem T39 (optimality of the geometric grid)

*Among all scale grids with `2^m` points per octave, expected headroom waste is
minimised **uniquely** by equal log-spacing — a geometric grid — attaining*

    E[waste] = 2^−(m+1)  bits,

*and any other grid is strictly worse by `(1/2)(Σgᵢ² − 2^−m) > 0`.*

**Proof.** Minimise `Σgᵢ²` subject to `Σgᵢ = 1`. By Cauchy–Schwarz,
`(Σgᵢ)² ≤ 2^m · Σgᵢ²`, so `Σgᵢ² ≥ 2^−m` with equality **iff** all `gᵢ` are equal.
Equal gaps in log-magnitude is precisely a geometric grid, and substituting gives
`E[waste] = 2^−m/2 = 2^−(m+1)`. ∎

**Corollary (T38 is the m = 0 case).** One point per octave leaves a single gap
of one bit, which cannot be unequal, so every grid coincides and
`E[waste] = 1/2` — exactly T38's Proposition 3, and exactly what E8M0 is.

## Corollary (the float penalty, in closed form)

*A float scale grid `2^e(1 + j/2^m)` — equally spaced in the **mantissa**, which
is what E4M3 and NVFP4 use — has*

    E[waste]_float / E[waste]_geometric  →  1/(2 ln²2) = 1.040684491…

*as `m → ∞`, and exceeds 1 for every `m ≥ 1`.*

**Proof.** For large `m` the gap at mantissa position `u = j/2^m ∈ [0,1)` is
`g(u) = log₂(1 + 2^−m/(1+u)) ≈ 1/(ln2 · 2^m (1+u))`. Then

    Σ gᵢ² ≈ 2^m ∫₀¹ g(u)² du = (1/(ln²2 · 2^m)) ∫₀¹ du/(1+u)² = 1/(2 ln²2 · 2^m),

against the geometric grid's `2^−m`. The ratio is `1/(2 ln²2)`. ∎

Measured against the exact sums:

| m | float / geometric | |ratio − 1/(2ln²2)| |
|---:|---:|---:|
| 6 | 1.040672141 | 1.23e-05 |
| 10 | 1.040684442 | 4.82e-08 |
| 14 | 1.040684490 | 1.89e-10 |
| 18 | 1.040684491 | 6.84e-13 |

## This is a different constant from T37's, and the difference matters

T37 reports the geometric advantage rising to **1/ln2 = 1.4427**. T39 reports a
float penalty of **1/(2 ln²2) = 1.0407**. They are not in conflict and they are
not the same quantity:

- T37 measures **accuracy** — the precision a scale delivers to the elements
  under it, where a geometric grid's constant relative spacing is the whole point.
- T39 measures **headroom** — the fraction of an octave thrown away by rounding
  the scale *up*, which is a packing question and answers to `Σgᵢ²`.

A format pays both. Quoting either as "the" advantage of a geometric scale would
be wrong, and a document that quotes both must say which is which.

## Measured 2026-08-12: the log-uniformity assumption is false, and a ruler broke

The assumption was stated and not tested. It has now been tested over **19,808,256
blocks** across four models, and it fails in every one.

| model | KS D against U[0,1) | measured E[waste] | vs predicted ½ |
|---|---:|---:|---:|
| Pythia-160M | 0.00855 | 0.465832 | −6.8 % |
| Qwen2.5-0.5B | 0.03513 | 0.490310 | −1.9 % |
| OPT-125M | 0.04834 | 0.497039 | −0.6 % |
| SmolLM2-135M | 0.05903 | 0.529067 | +6.0 % |

All `p < 1e-168`, and **not a large-N artefact**: 5,000-block subsamples reject at
α = 0.05 in 200 of 200 draws for three of the four. The phase density departs from
flat by up to ±29 %. A layer-level bootstrap — the honest unit — excludes ½ for
three models; Pythia ties it.

Pooled across all four, `E[waste] = 0.498558`. **The per-model errors cancel, so
"log-uniform" is right on average over models and wrong for every individual
one** — which is exactly the shape of assumption that survives casual checking.

### The broken ruler, and it inverts a corollary

Block maxima are not continuous. `frac(log₂ a_max)` takes **exactly 128 distinct
values on bf16 checkpoints and 1024 on fp16** — the storage mantissa lattice.

A *float* scale grid's tops are a **subset of that lattice**, so it collects exact
zero-waste hits that a geometric grid cannot: `P(waste = 0)` at m = 6 is **37.9 %
for float against 0.90 % for geometric** on SmolLM2.

On raw released checkpoints this makes the float grid **beat** the geometric one —
float/geo = 0.978 at m = 4, 0.866 at m = 5, **0.762 at m = 6** — which flatly
contradicts the corollary above.

**Both readings are true and must both be recorded.** Dithering each phase
uniformly inside its own rounding cell removes the effect entirely and restores
float/geo > 1 everywhere, so the contradiction is an artefact of the *file
format*, not of the weights. But if you quantise a released bf16 checkpoint — 
which is what everyone does — the free hits are real and the corollary does not
apply to you.

### And the honest verdict on the whole theorem

Re-deriving T39 under the measured density buys nothing, because **expected
headroom waste turns out to be nearly orthogonal to accuracy**. The theorem is
correct mathematics about a quantity that does not decide the outcome — which is
the same lesson `METRIC_DISAGREEMENT_2026-08-11.md` recorded about squared error,
arrived at from the opposite direction.

## What it does and does not license

**Does.** It explains why `SCALE_FRONTIER`'s φᵏ grid wins on the cost frontier
without appealing to φ at all: any equal-log-spaced grid attains the bound, and φ
powers are one such grid. The result is about *spacing*, not about the golden
ratio — a claim that φ specifically is optimal here would be unearned by this
theorem.

**Does not.** It says nothing about which grid is best for *accuracy*, nothing
about non-uniform block-maximum distributions (the log-uniform assumption is
stated, not proved, and real weight tensors are only approximately log-uniform
across blocks), and nothing about a scale that is allowed to round *down* with
saturation — the OCP MX rule, which is a different problem because it trades
headroom for clipping.

---

*Proofs are elementary and complete above. `verify_grid_optimality.py` checks all
six claims: the expected-waste formula against a direct simulation of the
rounding, the `2^−(m+1)` attainment, strict float inferiority at every `m ≥ 1`,
the `m = 0` reduction to T38, that none of 20,000 random grids per width beats
the geometric one, and the closed-form limit to 6.84e-13.*
