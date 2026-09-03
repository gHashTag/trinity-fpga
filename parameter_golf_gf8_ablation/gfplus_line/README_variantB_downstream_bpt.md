# Variant B — downstream-BPT measurement of the GF+A / intra-pocket composition axis (loop 29.07.2026b)

Status tags: CPU-proxy = `[measured — SW proxy, CPU]`; full pod = `[REQUIRES USER ACTION]`.
seed = 20260729 (CPU-proxy) / 42 (model). Date: 29.07.2026.

## Why (the boundary we are closing)

Invariant #26 (Variant B implementation of the previous loop) proved by SW ablation
`selector_vs_intrapocket.py` that the **composition** of two orthogonal selection axes
(axis1 = GF+A catalog-select BETWEEN formats; axis2 = intra-pocket (e,m)-refinement
INSIDE the minifloat family, dMX-style) is by construction **≥ each axis alone by the
selection MSE-metric** — invariant violations: 0 out of 20 cells.

But invariant #18 (BINDING) warns: **SQNR/MSE of a layer = a surrogate**, which may
NOT pay off in downstream model bits-per-token. Therefore the "end-to-end downstream
composition" remained an `[open hypothesis]`. This measurement moves it (partially, at
micro-scale) into `[measured — SW proxy, CPU]`.

## What was done

Two implementations of one methodology:

1. **`research/gfplus_line/webterm_composition_bpb.py`** (in the `trinity-fpga` root) — a pod-ready harness on
   a 29M-transformer + FineWeb sp1024, mirroring the methodology of inv. #18
   (`research/gfplus_line/webterm_gfplus_v2bpb.py`): quantizes Linear weights in three ways
   (FP32 / axis1 GF+A / composition GF+A∘intra-pocket), runs a real forward pass on
   an independent val-stream, measures bits-per-token. Launch:
   ```
   curl -s https://raw.githubusercontent.com/gHashTag/trinity-fpga/main/webterm_composition_bpb.py -o /tmp/cb.py
   STEPS=3000 python3 /tmp/cb.py
   ```
   Requires a GPU pod → `[REQUIRES USER ACTION]`.

2. **`composition_bpt_cpu_proxy.py`** (this folder) — a CPU-proxy on a micro-LM
   (4 layers, d=128, vocab=256, order-2 Markov stream with a shared transition matrix
   for train/val). The same trio of configurations, real forward pass, bits-per-token.
   Run in a sandbox WITHOUT a GPU.

## CPU-proxy result `[measured — SW proxy, CPU]`

| Bitwidth | FP32 | axis1 GF+A | composition | ΔBPT (composition − axis1) | Significance (threshold 0.0195 BPT) |
|---|---|---|---|---|---|
| 4-bit | 0.12735 | 0.12744 | 0.12744 | **+0.00000** | <threshold (insignificant) |
| 6-bit | 0.12735 | 0.12735 | 0.12735 | **+0.00000** | <threshold (insignificant) |
| 8-bit | 0.12735 | 0.12735 | 0.12735 | **+0.00000** | <threshold (insignificant) |

(Parameter Golf significance threshold = 0.005 BPB = 0.0195 BPT at a coefficient of 3.9 bytes/token)

## Honest conclusion (BINDING)

- **ΔBPT = 0.00000 at all three bit-widths** — at micro-scale the SW-proxy gain of the
  composition (0/20 MSE violations) does NOT translate into model loss. This is a direct
  confirmation of invariant #18: a layer's SQNR/MSE is a surrogate that downstream does
  not pay off.
- Moreover: even the FP32 → 4-bit transition costs downstream ≈ +0.0001 BPT on this
  micro-task — the quantization loss budget is tiny, and the difference between axis1 and
  the composition is completely lost within it.
- **The axes remain ORTHOGONAL** (composition ≥ each one by MSE, inv. #26), but on the
  downstream-metric at this bit-budget the composition **yields no gain** — superiority is
  NOT claimed for either axis, nor for the composition.

## Boundaries (BINDING)

- Micro-scale (4 layers, vocab=256), NOT 29M — the numbers give the DIRECTION of the effect
  (ΔBPT≈0), NOT the magnitude on large models. Generalization is NOT established.
- The composition header overhead (+0.18 bits/element, inv. #26) is NOT subtracted from BPT —
  the comparison is NOT bit-aligned in favor of the composition; at zero ΔBPT this only
  strengthens the "does not pay off" conclusion.
- bits-per-token is the primary metric; BPB = BPT/3.9 `[proxy coefficient]` (the sp1024 stream
  cannot be decoded by the 8192-BPE tokenizer, inv. #18).
- The full GPU measurement on the 29M-model (`research/gfplus_line/webterm_composition_bpb.py`) remains open —
  that is exactly where invariant #18 previously showed that deep FFN layers give the greatest
  sensitivity; it is possible that on 29M the composition's ΔBPT becomes non-zero (but, per
  inv. #18, most likely remains <threshold). This is the MAIN recommendation for the next loop.
