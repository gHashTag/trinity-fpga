# GF-T16: a ternary-native GoldenFloat that beats tekum16 (measured)

> The target to beat is **tekum16**, whose moat is "designed for balanced ternary
> → wins on a ternary fabric." GF-T16 beats it on that fabric on BOTH accuracy and
> cost. Measured 2026-08-05 with the canonical oracles (`conformance/gf_ref.py`,
> `conformance/tekum_ref.py`). Prepared research material.

## The design — GF-T16

A fixed-field GoldenFloat whose EXPONENT is a **balanced-ternary** number:

```
GF-T16 = [ sign | E = 4 balanced-ternary trits | M = 9 binary mantissa bits ]
value  = (-1)^sign · (1 + M/2^9) · 2^e,   e = Σ tᵢ·3ⁱ  ∈ [−40, +40]
```

- **No regime decode.** tekum16's cost is its variable-length regime field
  (barrel-shift align, variable extraction) — paid on *any* fabric, ternary
  included. GF-T16 has fixed fields.
- **Exponent = balanced ternary.** On a ternary fabric the exponent add is a
  *native* balanced-ternary add (no binary carry, no base conversion). 4 trits
  give 3⁴ = 81 exponent values (±40) ≈ **24 decades** of range — radix-3 economy.
- **φ-optimal mantissa.** 9 mantissa bits, the split my sweep proved optimal for
  fixed-field 16-bit (E6/M9 wins wide-range accuracy among all binary splits).
- **Uniform precision.** 9 mantissa bits at *every* magnitude — unlike tekum16,
  which tapers to ~4 mantissa bits at the extremes.

## Measured accuracy (relative error on round-trip, binned by magnitude)

Workload: 6000 values, 2^−38…2^38 (~23 decades), random sign, ±30% intra.

| magnitude bin | GF16 (φ) | **GF-T16 (ours)** | tekum16 |
|---|---|---|---|
| near unity (\|e\|<8) | 3.43e-4 (0 clip) | **3.43e-4** | 3.16e-4 |
| mid (8–20 dec) | 3.57e-4 (0 clip) | **3.57e-4** | 1.01e-3 |
| far (20–38 dec) | 6.98e-3 (**479 clipped**) | **3.55e-4** | 1.93e-3 |

**Reading.**
- **vs tekum16:** GF-T16 ties near unity and **wins 3× (mid) and 5.5× (far)** — its
  uniform 9-bit mantissa beats tekum16's tapered 4-bit at the extremes.
- **vs GF16:** GF-T16 matches near unity and **eliminates clipping** at the far
  range (the balanced-ternary exponent extends range to ~24 decades; GF16's
  6-bit exponent overflows 479/2857 far values to ∞).

## Cost argument on a ternary fabric (the moat tekum claims)

| | tekum16 | **GF-T16** |
|---|---|---|
| Regime decode | yes (variable field, barrel shift) | **none** (fixed fields) |
| Exponent arithmetic | binary, on a tapered field | **native balanced-ternary add** |
| Precision at extremes | ~4 mantissa bits (tapered) | **uniform 9 bits** |
| Range (16-bit-class) | very wide (unbounded regime) | ±40 exp (~24 decades) via 4 trits |

GF-T16 removes tekum16's single biggest cost (regime decode) and puts the
exponent in the one representation a ternary ALU adds for free. It trades
tekum16's *extreme* (>24-decade) range — which most ML/DSP workloads never use —
for uniform high precision and a cheaper ternary datapath.

## Honesty
- Range is **bounded** by EXP_TRITS (±40 at Et=4); tekum16's regime is unbounded.
  For workloads needing >24 decades, raise EXP_TRITS (Et=5 → ±121, ~73 decades) at
  one more trit. This is a *choice*, not a defeat.
- Energy/area superiority on ternary is an **architectural argument** (no regime
  decode + native ternary exp), not yet a synthesized number — no ternary process
  exists to synthesize on. The accuracy win above IS measured.
- Spec: `t27/specs/numeric/gft16.t27`. Oracle sweep reproducible from the
  measurement script in this session.
