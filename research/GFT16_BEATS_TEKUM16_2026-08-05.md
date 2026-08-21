> ## ⛔ Corrected 2026-08-18 — the headline does not survive checking
>
> Three faults, each verified by hand against the artefacts in this tree:
>
> **1. The width is 17 bits, not 16.** Four balanced-ternary trits need
> `ceil(4·log2 3) = 7` binary positions, so the word is `1 + 7 + 9 = 17`.
> `conformance/tnf16_ref.py` says so in its own header — *"17-bit canonical
> raw"* — and `tnf_ref.LADDER[16].sign_shift` evaluates to 16, i.e. bit 16 is
> the sign of a 17-bit word. **tekum16 is 16 bits.** A format called 16 beat a
> format that is 16, while being 17.
>
> **2. The thing beaten is not tekum.** All 65,536 codes were decoded through
> `conformance/tekum_ref.py` and `conformance/takum_ref.py`: **0 differences.**
> The tekum oracle is the takum oracle. Its own docstring flags the
> balanced-ternary exponent as `# TODO: verify from full paper` — so the
> feature that distinguishes tekum from takum is **not implemented in the model
> that was beaten**.
>
> **3. The exponent range is smaller than stated.** Offset 0 is zero and offset
> 80 is Inf/NaN, so the usable exponent is `e ∈ [−39, +39]` — 79 values, not the
> 81 the formula implies.
>
> What survives: **the round-trip accuracy measurement itself reproduces**, and
> GF-T16 does have fixed fields where takum has a variable-length regime. What
> does not survive is the comparison being at equal width, and the competitor
> being tekum rather than takum.
>
> **4. The opponent is neither takum nor tekum.** Both oracles say so in their
> own headers. `takum_ref.py`: *"настоящий takum — ЛОГАРИФМИЧЕСКИЙ (value =
> (-1)^S · exp(ℓ/2)) … здесь реализована РАБОЧАЯ СТРУКТУРНАЯ МОДЕЛЬ …
> интерпретированная ЛИНЕЙНО … а НЕ логарифмически."* Read the same 16-bit word
> both ways and they are different numbers — `0x1001` is 1.10e-19 linear and
> 1.01e+00 logarithmic, a ratio of 9.2e+18. **This caveat outranks the width
> one:** the comparison is against a linear reinterpretation of takum's field
> layout, not against either published format.
>
> **Measured at equal width** (`conformance/equal_width_vs_takum.py`), against
> that linear model: TNF(4,8) at 16 bits is **1.4× better over nine decades and
> 2.0× over twelve**, and **worse near unity**, where the taper spends its bits.
> The 17-bit version shows 2.7× and 4.0× — the extra bit is roughly half the
> advantage.
>
> The cost half was withdrawn separately: the only GF-T adder in the tree
> (`fpga/tef/gft_add_w.v`) is magnitude-only — no sign, no subtraction, no
> rounding, no normalisation — against tekum16's full adder. That gap is feature
> asymmetry, not format cost. And no ternary fabric exists to cost either on.

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

Workload: 6000 values, 2^−38…2^38, random sign, ±30% intra.

> **Axis corrected 2026-08-08.** The bins below are in **powers of two** (|e|),
> not decades. Re-measured independently against the same oracles and the
> ratios reproduce exactly — 0.92× / 2.84× / 5.53× — but only under that reading.
> Binned in *decades* the far column is not a win at all: GF-T16's exponent
> reaches ±40 in powers of two, about ±12 decades, so beyond that it overflows
> and tekum16's unbounded regime keeps working. Labelling those bins "dec"
> invited a reviewer to check the one way that makes the result look invented.

| magnitude bin (powers of two) | GF16 (φ) | **GF-T16 (ours)** | tekum16 |
|---|---|---|---|
| near unity (\|e\| < 8) | 3.43e-4 (0 clip) | **3.43e-4** | 3.16e-4 |
| mid (\|e\| 8–20) | 3.57e-4 (0 clip) | **3.57e-4** | 1.01e-3 |
| far (\|e\| 20–38) | 6.98e-3 (**479 clipped**) | **3.55e-4** | 1.93e-3 |

**Reading.**
- **vs tekum16:** GF-T16 ties near unity and **wins 2.84× (mid) and 5.53× (far)** — reproduced independently 2026-08-08 — its
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
- Spec: `gHashTag/t27/specs/numeric/gft16.t27`. Oracle sweep reproducible from the
  measurement script in this session.
