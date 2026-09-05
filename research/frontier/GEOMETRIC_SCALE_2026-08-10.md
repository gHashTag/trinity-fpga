# A geometric scale grid beats a float one at every width, and the margin is 1/ln 2

Yesterday's frontier concluded that a scale carrying a mantissa beats any
geometric grid. The comparison behind that sentence gave E4M3 eight bits and the
phi grid four. That is not a comparison, and the conclusion drawn from it does
not stand. What replaces it is stronger, and it is an inequality rather than a
measurement.

## The inequality

A float scale `2^e (1 + m/2^k)` places `2^k` points in each binade, at
`1, 1+2^-k, ..., 2-2^-k`. The ratio between adjacent points is largest at the
bottom of the binade, where it is `1 + 2^-k`.

A geometric grid with the same `2^k` points per binade places them at
`2^(j/2^k)`, and every adjacent ratio is `2^(2^-k)`.

For `x > 0`, `2^x = e^(x ln 2) < 1 + x`, because `ln 2 < 1`. Hence

    2^(2^-k)  <  1 + 2^-k

for every mantissa width `k`: **the geometric grid's worst-case step is strictly
smaller than the float grid's at the same point count.**

| mantissa k | points/binade | float `1+2^-k` | geometric `2^(2^-k)` | advantage |
|---|---|---|---|---|
| 1 | 2 | 1.500000 | 1.414214 | 1.2071x |
| 2 | 4 | 1.250000 | 1.189207 | 1.3213x |
| 3 | 8 | 1.125000 | 1.090508 | 1.3811x |
| 4 | 16 | 1.062500 | 1.044274 | 1.4117x |
| 8 | 256 | 1.003906 | 1.002711 | 1.4407x |

The advantage rises monotonically to `1/ln 2 = 1.442695`.

**T37 (the geometric scale grid).** For scales read as multipliers -- where the
error that matters is relative -- a geometric grid strictly dominates a float
grid of the same width, in worst-case step at every mantissa width and in
root-mean-square relative error at every width measured. The float grid's defect
is structural: it is uniform in value within a binade and therefore non-uniform
in log, spending resolution where the relative step is already small.

RMS relative error over a binade, rounding up, 400,000 log-uniform samples:

| mantissa | float | geometric |
|---|---|---|
| 2 | 0.113782 | 0.106773 |
| 3 | 0.054960 | 0.051621 |
| 4 | 0.027020 | 0.025406 |

## What it predicts, and what was measured

Prediction: at equal bits a geometric scale beats E4M3. Measured on
SmolLM2-135M, K=32, E2M1 elements, 40 windows:

| scale | bits | b/w | ppl |
|---|---|---|---|
| `phi^k` | 4 | 4.1250 | 21.3545 |
| geometric | 6 | 4.1875 | 20.0199 |
| **geometric** | **7** | **4.2188** | **18.8024** |
| E4M3 | 7 | 4.2188 | 19.8628 |
| **geometric** | **8** | **4.2500** | **18.1238** |
| E4M3 | 8 | 4.2500 | 19.8628 |
| NVFP4-like E4M3 8b/16 | 8 | 4.5000 | 18.5445 |

Geometric beats E4M3 by 5.3% at seven bits and 8.8% at eight, as the inequality
requires. And a geometric grid at eight bits per block of 32 -- 4.25 bits per
weight -- beats the NVFP4-like configuration at 4.5 bits per weight, at lower
cost.

## The tension this exposes, stated plainly

The optimal grid is geometric with ratio `R^(1/N)` for the occupied range `R`
and point count `N`, and that ratio is an arbitrary real. It is not
multiply-free: applying it needs a multiplier.

`phi^k` is geometric *and* multiply-free, but its ratio is fixed at 1.618, which
is optimal only where the range and the point count happen to want it -- at four
bits, which is where we measured it winning.

So the honest placement is a pair of statements. Among all scale grids,
geometric beats float, and the best geometric grid needs a multiplier. Among
multiply-free grids, `phi^k` is the finest available at four bits. The first is
a contribution to the field; the second is what our datapath gets for nothing.

## Replicated

Qwen2.5-0.5B, same protocol:

| at equal bits | SmolLM2 | Qwen |
|---|---|---|
| 7 bits: geometric / E4M3 | 18.8024 / 19.8628 | 13.6401 / 13.7636 |
| 8 bits: geometric / E4M3 | 18.1238 / 19.8628 | 13.6910 / 13.7636 |

The inequality's prediction holds on both models. The margin does not transfer:
5.3--8.8% on the smaller model against 0.5--0.9% on the larger. Sign replicates,
size does not, which is the pattern every result tonight has followed.

One further claim is model-dependent and is not made. On SmolLM2 a geometric
grid at 4.25 bits per weight (18.1238) beats the NVFP4-like configuration at
4.50 (18.5445) -- cheaper and better. On Qwen it does not: 13.6910 against
13.5340, cheaper and worse. So *geometric beats float at equal bits* replicates;
*geometric at lower cost dominates NVFP4's configuration* does not.
