# The scale-format axis on perplexity: TNF-scale ties ue5m3 exactly — they are the same function on this model

The stop-rule memory closed the scale axis on NRMSE only
(`research/block/SCALE_AXIS_2026-08-09.md`): TNF-scale — 3 balanced-ternary
trits of exponent plus 3 mantissa bits — tied IBM's ue5m3 at 1.006 on synthetic
Normal weights. NRMSE and perplexity have disagreed before on this programme
(`METRIC_DISAGREEMENT_2026-08-11.md`), so the question is re-asked here on the
metric the stop-rule names. Script: `conformance/ppl_scale_axis.py`.

## Protocol

- **Pipeline**: the 2026-08-10 block-axis pipeline (`research/block/block_tnf.py`)
  — SmolLM2-135M in fp32, wikitext-2 test, **40 windows of 2048 tokens**,
  every `nn.Linear` weight except `lm_head` quantised, block **K=32 along the
  contraction axis**, embeddings/norms untouched.
  **Ruler check: the fp32 baseline reproduces the 2026-08-10 figure digit for
  digit — 14.4874.**
- **Element format, identical in every row**: FP4 E2M1, levels
  {0, .5, 1, 1.5, 2, 3, 4, 6}, all 8 codes (OCP MX elements reserve nothing).
- **Scale convention, identical in every row**: ideal scale `s = amax / 6`
  (E2M1 top = 6), quantised through the candidate codec, elements quantised
  with the quantised scale, reconstruct.
- **Scale codecs**: taken from `research/block/scale_axis_probe.py` (the
  2026-08-09 instrument), imported directly and used as the oracle for the
  vectorised ports — **exact-match gate passed on 20,058 samples per codec**
  before any model work. TNF-scale is that file's `q_scale_tef8` codec at
  ET=3, MB=3 — the SCALE_AXIS_2026-08-09 tie configuration
  (27 exponent codes, e ∈ [−13, 13]; 216 codes ≈ 7.75 bits).
- **Determinism**: no randomness anywhere in the measurement path
  (deterministic quantisation, fixed first-40 windows). Model snapshot
  `93efa2f097d58c2a74874c7e644dbc9b0cee75a2` (HuggingFaceTB/SmolLM2-135M);
  dataset `Salesforce/wikitext`, `wikitext-2-raw-v1` test parquet, snapshot
  `b08601e04326c79dfdd32d625aee71d232d685c3`; torch 2.11.0,
  transformers 5.14.1.

## Result

```
scale codec                  ppl  vs fp32  vs floor  zeroed blocks
fp32 (unquantised)       14.4874   1.000x        --             --
fp32 scale (floor)       17.6535   1.219x    1.000x        0/3317760
e8m0 (MX)                27.8029   1.919x    1.575x        0/3317760
ue4m3 (NVFP4-style)      17.8378   1.231x    1.010x        0/3317760
ue5m3 (IBM)              17.8396   1.231x    1.011x        0/3317760
TNF-scale 3t+3m          17.8396   1.231x    1.011x        0/3317760
```

Occupied ideal-scale range, measured over all 3,317,760 blocks:
log2 s ∈ [−7.68, 0.63] — **8.32 binades**, reproducing the campaign's own
figure.

## The verdict, stated plainly

**TNF-scale does not beat ue5m3. It ties it exactly — and the tie is a
functional identity, not a measurement.** Enumerated over all 3,317,760 block
scales of this model: the TNF-scale codec and the ue5m3 codec produce the
**identical quantised scale on every single block** (0 differences), because
for any s ∈ [2^−13, 2^13] the two codecs compute the same function — same
floor-log2 exponent, same 3-bit mantissa rounding — and this model's scales
occupy [2^−7.68, 2^0.63], well inside. Identical scales give bit-identical
reconstructions, hence the identical 17.8396. The NRMSE tie of 2026-08-09
transfers to perplexity because on real weights there is literally nothing for
the two encodings to disagree about: **the trit exponent buys range
(±13 binades) that the workload (8.32 binades) does not visit.**

**TNF-scale ties ue4m3 within resolution.** 17.8396 vs 17.8378 is 0.01%; at
40 windows this programme's own noise-floor lessons forbid ranking rows this
close. Call it a three-way tie among the mantissa-carrying codecs.

**TNF-scale beats e8m0** — 1.011x vs 1.575x over the floor — **but so does
every codec in the table that carries mantissa bits.** The win belongs to the
3 mantissa bits, not to the ternary exponent field. Nothing in this
measurement distinguishes TNF-scale from a plain binary ue5m3 except a
0.25-bit packing saving (216 codes vs 256) that exists only in a bit-packed
stream and vanishes in any byte-addressed one.

For the stop-rule: **no TNF win on the scale axis measured on perplexity.**
The axis stays closed the way the NRMSE measurement left it.

## The expected ue4m3 catastrophe did not happen — and the reason is measured

The 2026-08-09 NRMSE run predicted ue4m3 catastrophic (9.4×) on narrow
tensors. On the live model **ue4m3 is the best quantised-scale row by a hair**
and zero blocks collapse. The prediction does not transfer because the failure
region is never entered: the synthetic σ=0.002 tensor put block scales near
2^−11.6, below ue4m3's zero-collapse point (~2^−10); SmolLM2's real block
scales bottom out at 2^−7.68. Measured against ue4m3's normal range
(min normal 2^−6): only **0.170%** of blocks fall below it, into the codec's
pseudo-subnormal region, and **none** reach scale-zero. This is the
"perplexity may disagree" point realised in a specific form: the metric did
not overturn NRMSE — **the live weight distribution never visits the regime
the synthetic catastrophe was measured in.** (The σ=0.04 NRMSE row, 1.015,
was already a near-tie and is what the live model corroborates.)

Caveat attached: this row is the probe's bare ue4m3 codec. Deployed NVFP4
adds a per-tensor fp32 scale that renormalises block scales into E4M3's sweet
spot; that variant is not measured here and would only help ue4m3.

## e8m0's 1.575x carries a convention, and it must be named

This e8m0 is the probe's: `2^round(log2 s)` — round to **nearest**
power of two. Measured on the weights, that underscales **55.21%** of blocks
by up to √2, clipping each such block's maximum by up to 29%; the
mantissa-carrying codecs underscale at most 1/16. The 2026-08-10 pipeline's
E8M0 rows used ceil-based conventions that never underscale and landed at
21.94/22.50 (`MXFP4_SCALE_CONVENTION_2026-08-11.md` documents the 7.3%
convention spread). So: **e8m0 loses to the mantissa-carrying codecs under
every convention this programme has measured** (22.50 and 27.80 are both far
above 17.84), but the size printed here is convention-dependent and this
table's rows are comparable with each other, not digit-for-digit with the
2026-08-10 MXFP4 rows.

## What the floor row says

Scale quantisation with 3 mantissa bits costs **1.0–1.1%** on top of element
quantisation (17.65 → 17.84); the E2M1 element itself costs 21.9% over fp32.
On this axis the scale format is nearly a solved problem the moment the scale
carries any mantissa at all — which is IBM's diagnosis, reproduced on a live
model.

## Caveats

- One model (SmolLM2-135M), one dataset, 40 windows. The campaign's transfer
  results (`prop:transfer`) say perplexity margins do not transfer across
  models; the *functional identity* of TNF-scale and ue5m3, however, holds for
  any tensor whose block scales stay inside ±13 binades — that part is
  arithmetic, not statistics.
- The ue4m3-vs-ue5m3 ordering (0.01%) is below resolution and not claimed.
- Elements fixed at E2M1 throughout; scale-format × element-format interaction
  not measured.
- e8m0 convention sensitivity as above.
- No seed spread: the pipeline is deterministic end to end; the resolution
  limit is window count, not RNG.
