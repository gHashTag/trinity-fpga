# T38 — the E8M0 headroom phase, and why two codebooks cannot be compared at different tops

A day of confusion in this repository — two documents apparently reporting
different perplexities for MXFP4, a "three conventions spanning 7.3 %" note, and
a correction to that note — reduces to one small theorem. It is stated and proved
here, and checked against the code in `verify_phase_theorem.py`.

## Setup

A block format quantises a block of values with maxima magnitude `a > 0` using a
codebook of magnitudes `0 = L₀ < L₁ < … < L_{n−1} = T` and a shared scale `s`
drawn from E8M0, i.e. `s` is a power of two. A value `v` maps to
`sign(v)·s·L_j`, where `j` is chosen by the midpoint boundaries of `|v|/s`.

Two scale rules appear in the wild, and both are defensible:

    RULE A    s_A = 2^⌈log₂(a / T)⌉        align the codebook's top to the block max
    RULE B    s_B = 2^⌈log₂ a⌉ / T          align a power of two to the block max

## Proposition 1 (renormalisation)

*Quantising with `(L, s_B)` is the same map as quantising with `(L/T, 2^⌈log₂ a⌉)`.*

**Proof.** Write `σ = 2^⌈log₂ a⌉`, so `s_B = σ/T`. Under `(L, s_B)` a value maps
to `s_B·L_j = (σ/T)·L_j = σ·(L_j/T)`, and the index `j` is selected by comparing
`|v|/s_B = T|v|/σ` against the midpoints `(L_k + L_{k+1})/2`. Dividing both sides
of every comparison by `T` gives `|v|/σ` against `(L_k/T + L_{k+1}/T)/2`, which is
exactly the selection rule for the codebook `L/T` at scale `σ`. Same index, same
reconstruction. ∎

**In floating point** the identity is exact when `T` is a dyadic rational, since
then `1/T` is representable and both paths perform the same rounding. E2M1's
`T = 6.0` is dyadic, which is why the tensor-level check on real weights returned
a difference of exactly `0.000e+00`. For a non-dyadic top — Lloyd-Max's
`0.96567` — the paths differ at the last bits: measured `1.455e-11`. Stating the
proposition as "bit-identical" without that condition would be false, and the
check is what caught it.

## Proposition 2 (the phase)

*Define the headroom waste of a rule as `w = log₂(T·s / a)`, the bits between the
block maximum and the largest representable magnitude. Then*

    w_A = 1 − frac(log₂ a − log₂ T)        (0 when the fractional part is 0)
    w_B = 1 − frac(log₂ a)                 (likewise)

*and the two rules agree on every block if and only if `log₂ T ∈ ℤ`.*

**Proof.** For rule B, `T·s_B = σ = 2^⌈log₂ a⌉`, so
`w_B = ⌈log₂ a⌉ − log₂ a = 1 − frac(log₂ a)` when `log₂ a ∉ ℤ`, and `0` otherwise.
For rule A, put `x = log₂ a − log₂ T`. Then `T·s_A = T·2^⌈x⌉` and
`w_A = log₂ T + ⌈x⌉ − log₂ a = ⌈x⌉ − x = 1 − frac(x)` under the same convention.
So `w_A` is `w_B` with its argument shifted by `log₂ T`. The two agree for all `a`
iff `frac(log₂ a − log₂ T) = frac(log₂ a)` for all `a`, i.e. iff `log₂ T` is an
integer — iff `T` is a power of two. ∎

Define the **phase** `φ = log₂ T mod 1`. Then rule A is rule B with the headroom
argument rotated by `φ`, and `φ = 0` exactly when the codebook's top is a power
of two.

| codebook | top `T` | `φ` |
|---|---:|---:|
| E2M1 | 6.0 | 0.5850 |
| Lloyd-Max as published | 0.96567 | 0.9496 |
| any codebook normalised to `T = 1` | 1.0 | **0** |

## Proposition 3 (the phase is not an average penalty)

*If `log₂ a` is uniform modulo 1 — the natural model for block maxima spread over
many binades — then `E[w_A] = E[w_B] = 1/2` bit, for every `T`.*

**Proof.** `frac(log₂ a − log₂ T)` is a rigid rotation of a uniform distribution
on the circle, hence uniform, hence `E[1 − frac(·)] = 1/2` independent of `T`. ∎

Measured over 20,000 samples per codebook: `0.4992 … 0.5019` for every top tried.

## The corollary that matters

**Corollary (comparison hygiene).** Two codebooks with different tops, compared
under rule A, are evaluated at different phases. The comparison confounds
codebook *shape* with headroom *phase*, and Proposition 3 says the confound does
not average away — it is a different per-block perturbation for each arm.
Normalising both codebooks to `T = 1` sets `φ = 0` for both and removes it.

This is the whole of the 21.9397 / 22.4998 discrepancy that consumed a day. Both
numbers are correct. They are the same format at two phases.

It also settles the hygiene question for the result that prompted the theorem:
in the KL-optimised codebook comparison, MXFP4, Lloyd-Max and the KL codebook all
carry `T = 1.000000`, `φ = 0.000000`. That comparison holds the phase constant, so
the confound does not touch it.

## What this does not say

It says nothing about which rule is *better*. Proposition 3 shows they cost the
same on average, so the choice is not an accuracy decision; it is a convention
decision, and the only thing that matters is that one convention is used for
every arm of a comparison. The OCP MX specification uses a third rule again
(`s = 2^(⌊log₂ a⌋ − e_max)`, which permits saturation and is therefore not a
special case of either) — that one *is* different in kind, and is measured
separately in `MXFP4_SCALE_CONVENTION_2026-08-11.md`.

---

*Proofs are elementary and complete above. `verify_phase_theorem.py` checks that
they describe the quantiser this project actually runs rather than an idealised
one: P1 exact for dyadic tops and to rounding otherwise, P2's formula exact and
its coincidence condition exactly "T is a power of two", P3's expectation 1/2 bit
for every top. The check found the floating-point caveat in P1 that the first
draft of this document got wrong.*
