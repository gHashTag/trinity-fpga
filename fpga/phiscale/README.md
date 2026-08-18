# The layer scale, with and without a multiplier

BitNet-style ternary networks store weights in `{-1,0,+1}` plus a real per-layer
scale `α = mean|W|`. The ternary weights remove the multiplier from the inner
product; applying `α` puts one back at the layer boundary, once per output
element. The golden alphabet removes it there too: with the value carried as an
integer pair `(a,b) ≡ a + bφ`, the scale `φ^k` is `k` applications of

```
(a, b) -> (b, a + b)        one integer addition, no shift, no multiplier
```

## Measured (yosys 0.65, `synth_xilinx`, XC7A200T primitives)

| arm | DSP allowed | LUT | DSP48 | FF | CARRY4 |
|---|---|---:|---:|---:|---:|
| `scale_mul` — real α, Q1.15 × 32-bit acc | yes | 0 | **2** | 3 | 0 |
| `scale_mul` | no | **1215** | 0 | 33 | 12 |
| **`scale_phi`** — φ^k, Fibonacci step | yes | **171** | **0** | 135 | 10 |
| **`scale_phi`** | no | 171 | 0 | 135 | 10 |

**Read the table's own first row before the 7.1×.** Given its DSPs — the normal
case on an XC7A200T, which has 740 — the multiplier arm is **0 LUT and 2 DSP48**.
That is **171 LUT smaller than the φ arm**, not 7.1× larger. The 7.1× compares us
against the `no` row, a multiplier denied the resource its design assumes, and
that comparison measures the denial (T52).

What stands, on this table, is narrower and still true: **the φ arm is
DSP-invariant** — identical with and without, because there is no multiply to
map — and it is **7.1× smaller than a multiplier built from logic**. On a part
with no DSP blocks, or one where they are spent, that is the whole product. On a
part with DSPs to spare it is not a saving at all.

Sized since: the φ arm trades 436–492 LUT per DSP freed, on parts carrying
182–264 LUT per DSP, and the multiplier arm is LUT-bound on every Artix and
Kintex part measured — so it fits *more* layers, not fewer. See
`ON_A_PART_WITH_DSP.md` and `conformance/device_fit.py`.

## What it costs us, stated

- **45× the registers**, not 4×. The 4× compared 135 FF against the 33 of the
  DSP-denied row, which is the baseline that flatters us. Against the multiplier
  as it would actually be built — the `yes` row — it is **135 against 3**. The
  pair representation carries two components where the multiplier carries one,
  and the iteration state carries the rest. This is real and unavoidable, and it
  was understated here by an order of magnitude until the claims in this
  directory were re-audited against T52.
- **`k` cycles instead of 1.** With `α = mean|W| ≈ 0.02`, `k = round(log_φ α)`
  is about 8. The "~1.6% of the layer's work" this line used to claim was 8/512
  — the scale's share of ADDITIONS — while the sentence reads as a share of
  time, and against a one-cycle multiplier it is not. Measured since: at |k| = 8
  the multiplier arm is 2.15× faster per output element despite half the clock
  (`FMAX.md`). The unrolled variant IS built now and takes the cycles back —
  660 LC at 204.08 MHz, one element per cycle (`PIPELINED.md`).
- **No Fmax.** `nextpnr-xilinx` is not installed on this machine, so this is
  area only. Saying "faster" here would be unsupported.
- **The built direction is not the one deployed.** Real layer scales are below
  one — `α = mean|W| ≈ 0.02` gives `k = round(log_φ α) ≈ −8` — so a deployed
  layer needs the *inverse* step `(a,b) → (b−a, a)`, from `φ⁻¹ = φ − 1`. That
  is one subtraction where the built circuit does one addition, so the area
  transfers directly and the count above stands. It is nevertheless the forward
  direction that was synthesised and simulated here, and the inverse variant is
  not yet built. Stated because a reader would otherwise assume the measured
  circuit is the deployable one.

## Correctness before area

A small circuit that computes the wrong thing is smaller still, so the area
number is only meaningful after the function is checked. `scale_phi_tb.v` runs
200 randomised cases against a golden model computed independently in the
testbench: **200 checks, 0 errors**. The bench also asserts a deliberately wrong
expectation and confirms it would be caught, so the pass is not vacuous.

```
iverilog -g2012 -o /tmp/phitb scale_phi_tb.v scale_phi.v && vvp /tmp/phitb
```

## Why this matters beyond the ratio

The accompanying measurement (`research/block/PHI_GRID_2026-08-10.md`) shows
snapping the scale to `φ^k` costs **2.44%** excess reconstruction error against
the unreachable exact `α`, where snapping to `2^k` costs **4.86%** — a ratio of
0.501 against a predicted 0.500. So the φ grid buys back half the accuracy that
removing the multiplier costs, and this file shows what removing it is worth:
two DSP blocks per layer boundary, or 7.1× the LUTs.
