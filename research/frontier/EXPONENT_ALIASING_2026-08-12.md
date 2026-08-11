# Three ladder rungs cannot distinguish exponents 256 apart

A twelve-agent review swept `tnf64b` at 210,248 codes and found the guard
perfect — 46,543 of 46,543 out-of-spec codes flagged, zero misses — and the
**decode path wrong on 80,362 of 86,675 comparable in-spec codes.**

## The mechanism

    wire [7:0] e32 = e[7:0] + 8'd127;

keeps eight bits of an exponent that spans $\pm 3279$. $(e+127) \bmod 256$ is
correct only for $e \in [-127, 128]$; outside it, `off` and `off+256` are
indistinguishable.

The same line is in `tnf32s_decode` and `tnf64s_decode`, which have been in the
throughput table since they were built. Direct test:

| module | off | exponent | output |
|---|---|---|---|
| TNF32 | 364 | 0 | `3f800000` = **1.0** |
| TNF32 | 620 | **256** | `3f800000` = **1.0** |
| TNF32 | 876 | **512** | `3f800000` = **1.0** |
| TNF64 | 3280 | 0 | `51000000` |
| TNF64 | 3792 | **512** | `51000000` |

Three distinct values, one output. The comment beside the line says *"fp32
window; wider rungs clip"* — but it does not clip, it **wraps**, and a wrapped
exponent is a wrong finite number rather than a saturated one.

## What is withdrawn

`TNF32`, `TNF64`, `TNF64b` and `TNF64b-bare` are moved to the rejected table.
`TNF32` had been rank 8 at $+15.0\%$ against `binary16` with $p_{\text{Holm}} <
10^{-4}$ — a statistically solid measurement of a decoder that does not decode.

**Twelve iterations of significance testing cannot rescue a number taken from a
wrong module.** This is the fourteenth defect of the campaign and the first found
by an independent reviewer rather than by the author.

## What survives, tested properly

On the common 128-bit harness, Welch against `binary16` with Holm correction
over 25 comparisons:

| ours | vs `binary16` | $p_{\text{Holm}}$ |
|---|---|---|
| **GFTernary** | $+52.4\%$ | $<10^{-4}$ |
| **TNF16a** | $+19.9\%$ | $<10^{-4}$ |
| **TNF17e** | $+15.7\%$ | $<10^{-4}$ |
| **GF10** | $+14.3\%$ | $<10^{-4}$ |
| **TNF16c** | $+12.5\%$ | $<10^{-4}$ |

`TNF16c` is the sixteen-bit rung at $E_t{=}5$ with every out-of-specification
offset reserved: equal storage to IEEE half, every code defined or flagged,
separated above it. Its exponent spans $\pm121$, **inside fp32's window**, so it
carries no aliasing exposure.

Not separated: `TNF17e-bare`, `minifloat`, `TNF8`, `GF14`, `TNF16`, `TNF16b`,
`BNF16`.

## Prior art the review found, and it is serious

- **TERNAC (Frieder, SUNY Buffalo, 1972/73)** — 48-trit float, **6-trit
  exponent**, emulated on binary hardware. **Refutes any claim of "first ternary
  exponent field."** Must be cited; the headline must be rewritten.
- **Compilade, "How to pack ternary numbers in 8-bit bytes" (26 June 2024)** —
  publishes the 5-trits-in-8-bits packing at **"99.06% efficient"**, which *is*
  $w(5) = 5.08\%$. The associated thread records that 17 trits in 27 bits and 111
  in 176 beat 1.6 bits/trit — i.e. **the unevenness of $w(k)$ is public.** The
  general formula and the theorem survive; the $k{=}5$ datum does not.
- **TerEffic (arXiv:2502.16473, 2025)** — the packed-$3^5$-in-8-bits decoder
  built in FPGA LUTs. A reviewer will know it.

## The instrument, quantified

Pooled CV **3.71%**. Two rows separate at $\alpha{=}.05$ only if their MHz/LUT
differ by more than **5.50%**. Detection floor for a decoder-cost difference:
**41.3 LUT — 79% of a whole decoder**; the harness inflates it **ten-fold**.
Reporting the **mean** of five seeds instead of the median is a free ~30%
variance reduction.
