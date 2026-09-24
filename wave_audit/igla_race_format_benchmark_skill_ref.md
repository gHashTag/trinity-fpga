# IGLA RACE: format benchmark (map of trios-*, two BPB cuts, honest frame)

## When to use
When Dmitrii/gHashTag asks about IGLA RACE, the top format for a task, BPB numbers,
the Format×Algorithm matrix, or "which numeric format trains better".

## Repository map (trios-*)
- **Core:** `gHashTag/trios-trainer-igla` (default `main`, **English-only**, rule of PR #65).
  SSOT training pipeline: JEPA-T + transformer + NCA, Rust-only, ASHA scheduler.
  Metric = BPB on tiny_shakespeare. The Format×Algorithm matrix = 351 cells
  (39 formats × 9 optimizers) in `ssot.bpb_samples`, auto-PR matrix_ledger.
  Topics: igla-race, jepa, transformer, training. Anchor φ²+φ⁻²=3.
- **Companions:** trios-railway, trios-mcp, trios-railway-mcp, trios-mcp-rag, trios-dwagent.

## TWO BPB CUTS — DO NOT CONFUSE (they diverge, scale decides)

### Cut A — Frozen champion (issue #181, hidden=828, frozen 2026-05-25)
All values = [open hypothesis] (sub-Challengilla, preliminarily):
- champion **binary32 = 2.1919**
- fp16 = **2.5501** > gf16 = **2.5725** > bf16 = **2.6135**
- gf8 = **2.9322** = posit8
- Only GF16 is actually measured + has FPGA-data (35/35 tb on Artix-7; no frequency claimed, 323 MHz withdrawn).
- Honest frame: "the method survives, phi does not (yet)".

### Cut B — Live matrix-ledger (PR #216, commit fab7d81, run 28643449889, hidden=96, step=3000)
⚠️ **ALL 88 rows have falsifier_2_hit=true** → smoke-scale, NOT champion. Top learnability (delta_dpb):
- fp8_e4m3 adamw delta **0.333** > int4 muon **0.304** > int8/fp8_e5m2 muon **~0.096**
  > floats fp32/fp16/fp80/posit16 **~0.05** (muon only) > gf16 muon **0.026**
- **nf4 is DEAD: bpb=7.0 exactly, delta=0** across all seeds/algorithms (untrained ceiling = log2 alphabet).
- adamw without muon = delta≈0 almost everywhere.

**Conclusion:** the frozen and live cuts DIVERGE → IGLA has no stable top-format.
Frozen champion — binary32; live top-learnability — fp8_e4m3/int4 under muon.

## Loop/falsifier statuses
- **Loop 11 (#183):** INSUFFICIENT_EVIDENCE (phi 5.9871 vs zoo 6.0454, overlapping CI,
  P(phi<zoo)=0.976 below threshold, n<11).
- **F2 proxy (#182):** ZOO WINS accuracy (mean_diff +0.67, p~1.6e-12); phi 0 lossy
  conversions vs zoo 1024 (breadth-moat, unproven).
- **falsifier_2** = anti-fake-pass guard (#103/#106) — flags invalid/plateau runs.

## Scientific background 2026 (for AI engineers)
- FP8 = the standard for train+inference, <0.5-1% MMLU loss (TensorRT-LLM).
- NVFP4 > MXFP4 (MXFP4 requires +36% tokens, NVIDIA).
- INT8 beats FP8 after RHT (HyperQuant, arXiv:2606.23406).
- takum = a "live threat" to GoldenFloat (Hunhold 2024, arXiv:2412.20273).

## API-fallback patterns (when the sandbox is dead)
- Issue body: `api.github.com/repos/<o>/<r>/issues/<n>`
- Comments: `.../comments?per_page=100&page=N`
- PR files/patch: `.../pulls/<n>/files`
- Raw file: `raw.githubusercontent.com/<o>/<r>/<branch>/<path>`
- GitHub Search API without a token = 403/uncrawlable → use the issue LISTING, not search.
- `fetch_url` works on these hosts WITHOUT a sandbox; memory_* too.
