# Weight-derived numbers: the record-backed pass — 2026-08-20

Completion of the range-provenance sweep (`research/RANGE_PROVENANCE_2026-08-20.md`,
rows 50–51 and addendum): every weight-derived number the sweep left
UNCHECKED-EXPENSIVE is now either backed by a measurement record produced from
the locally cached checkpoints, or reported as it stands. Nothing was silently
fixed; where a definition had to be *recovered* to make a number reproduce, the
recovery is stated as such and the rejected alternatives are recorded.

Line numbers refer to `research/arxiv_tnf/tnf_paper.tex` on branch
`fix/paper-range-provenance` (7,863 lines).

## Instruments

All measurements run offline from the local HF cache. Checkpoints, pinned in
every record by snapshot id and sha256 of `model.safetensors`:

| model | snapshot | sha256 (first 16) |
|---|---|---|
| HuggingFaceTB/SmolLM2-135M | `93efa2f097d58c2a74874c7e644dbc9b0cee75a2` | `80521b40281d6ce7` |
| Qwen/Qwen2.5-0.5B | `060db6499f32faf8b98477b0a26969ef7d8b9987` | `88c142557820ccad` |

Data for the perplexity rerun: Salesforce/wikitext wikitext-2-raw-v1 test
parquet, dataset snapshot `b08601e04326c79dfdd32d625aee71d232d685c3` —
byte-identical (sha256) to the `wikitext2-test.parquet` the original
`research/block/four_families.py` run used.

Tensor set everywhere below: every 2-D weight whose name contains neither
`embed` nor `norm` — the quantisable-linear convention of
`conformance/ppl_scale_axis.py`. On SmolLM2-135M that is 210 tensors,
155,520 output channels, 3,317,760 blocks of 32.

## Results

| # | paper (line) | claim | measured | verdict |
|---|---|---|---|---|
| 1 | tab:blockpct L2995–2998 | within-block span at block 32: p50 1.89 / p90 2.45 / p99 3.04 / p99.9 3.75 binades | 1.8908 / 2.4534 / 3.0415 / 3.7471 (SmolLM2-135M) | **REPRODUCES** — `arxiv_tnf/measurements/blockpct_2026-08-20.json` |
| 2 | tab:blockpct E\*/element column | E\* = ceil(log2 span) → 1/2/2/2 → E1M2, E2M1, E2M1, E2M1 | identical from the measured spans | **REPRODUCES** (same record; `recompute_blockpct_table.py` passes cell for cell) |
| 3 | L3013 (prose) | span "1.89 binades at the median and 3.04 at the 99th percentile" | 1.8908 / 3.0415 | **REPRODUCES** (same record) |
| 4 | L3873–3874 | "Over 3,317,760 block scales the range actually occupied is 8.32 binades on SmolLM2-135M" | 8.3183 binades over 3,317,760 blocks; independently confirmed by re-running `conformance/ppl_scale_axis.py --diagnose` (port self-checks pass, prints 8.32) | **REPRODUCES** — `arxiv_tnf/measurements/weight_ranges_2026-08-20.json` |
| 5 | L3874–3875 (also L3936–3937, L4386) | "and 9.12 on Qwen2.5-0.5B" | 9.1200 binades (Qwen2.5-0.5B, 11,182,080 blocks) | **REPRODUCES** (same record) — but see mismatch M1 on the block count and M3 on the sweep doc's label |
| 6 | L4433–4435 | "the weights' channel dynamic range — 268.95× median over 155,520 channels" | 268.9469× median over 155,520 channels (SmolLM2-135M) | **REPRODUCES** (same record; definition recovered, see below) |
| 7 | L3322–3323 | regret sweep: "E=1 giving 4.5 million and E=2 giving 288" | BNF8 E=1 → 4,574,409.00 (paper's own record prints 4,574,409); E=2 → 288.5224 | **REPRODUCES** — `arxiv_tnf/measurements/regret_sweep_2026-08-20.json`, full rerun |
| 8 | L3323 | "E=4 costs 0.3% and E=5 costs 6%" | E=4/E=3 = +0.32%, E=5/E=3 = +6.17% | **REPRODUCES** (same record) |
| 9 | L3317–3319 | width rule named BNF8 E=4 / TNF8 Et=3; measured winners E=3 (14.6130 vs 14.6592) and Et=2 (14.7012 vs 15.5147) | estimator 13.37 binades → predicts E=4/Et=3; measured 14.6130 / 14.6592 / 14.7012 / 15.5147, winners E=3 and Et=2 | **REPRODUCES** (same record; fp32 baseline 14.4874 exact) |
| 10 | thm:barrelrange L4834–4835 | "Across the 210 layers measured here that range is 3.15 octaves" | 210 tensors confirmed; per-tensor **rms** span = 3.1510 octaves (= 3.15 at printed precision); per-tensor **amax** span = 3.8972 octaves | **MEASURABLE-MATCH, PROVENANCE STILL OPEN** — see below; the untraced-figures concession (L5847) stands |
| 11 | L5858–5860 | the two-bit conclusion "survives any span below four octaves" | both measured readings (3.1510, 3.8972) are below 4; ceil(log2 span) = 2 bits either way | **REPRODUCES** (the robust version is now measured, not just asserted) |

## Definitions that had to be recovered (and how sure the recovery is)

The paper prints these numbers without stating the estimator. Each was
identified by measuring candidate definitions against the printed values; the
records name the winning convention *and* the rejected ones, so the
identification is falsifiable.

* **Within-block span (tab:blockpct)** = `log2(max|w| / lower-median|w|)` per
  block of 32 along the contraction axis, lower-median = 16th of 32 sorted
  magnitudes (the `torch.median` convention for even counts). Recovered by
  search first — four independent percentiles match at 2-decimal precision
  simultaneously, while the numpy interpolated median gives 1.84/2.39/2.96/3.67
  and is excluded — and then found to be the convention of a script the tree
  already ships: `research/block/block_tnf.py` computes
  `-log2(median(|w|/amax))` per block via `torch.median` and prints exactly
  these four percentiles. The table's generating computation therefore exists
  and is now named in the record. The paper's prose never names the model; the
  lineage (`block_tnf.py`, `research/block/BLOCK_AXIS_VERDICT_2026-08-10.md`,
  `research/block/kkt_element.py`) and this reproduction pin SmolLM2-135M.
* **Channel dynamic range (268.95×)** = per-output-channel
  `max|w| / p1|w|` (1st percentile of the row's magnitudes, zeros included),
  median over channels — the `np.quantile(…, 0.01)` convention of
  `research/block/block_ladder.py`. Matches to five significant digits
  (268.9469). Rejected: max/min-nonzero (2800.68×), max/p0.1 (1408.62×).
  Note the *prose* at L3326 ("span from the 0.1st percentile to the maximum")
  describes the E-sweep's span estimator, a different instrument from this
  channel ratio; the two must not be conflated.
* **Regret-sweep span estimator** = median over layers of
  `log2(amax / q0.001 of nonzero |w|)` — copied from
  `research/block/four_families.py`, not recovered; measures 13.37 binades and
  predicts exactly the falsified E=4/Et=3.

## The 3.15-octave figure (thm:barrelrange)

The paper's untraced-figures subsection (L5763–5766, table L5847) concedes
that 3.15 traces to no file, and this pass does **not** manufacture a
provenance for it. What it does establish, from the checkpoint:

* the "210 layers" count is real: exactly 210 quantisable linear tensors on
  SmolLM2-135M;
* the span of per-tensor **rms** across those 210 tensors is **3.1510
  octaves**, which equals the printed 3.15 at printed precision — a candidate
  origin, recorded as a candidate only (single number, three significant
  digits: weaker evidence than the four-way blockpct match);
* the span of per-tensor **amax** is **3.8972 octaves**;
* both readings are below four octaves, so the two-bit-selector conclusion of
  thm:barrelrange — which the paper already argued "survives any span below
  four octaves" — now rests on a measured quantity instead of an untraced one.
  The 3.15 literal itself should stay marked untraced until a generating file
  is found or the theorem's sentence is re-pointed at the recorded
  measurement.

## Mismatches

* **M1 (paper L3873, wording).** "Over 3,317,760 block scales … 8.32 … and
  9.12 on Qwen2.5-0.5B" — 3,317,760 is the SmolLM2-135M block count alone;
  the Qwen2.5-0.5B occupancy is over 11,182,080 blocks. Both occupancies
  reproduce; only the count's attachment to both models is loose. Suggested
  fix: attach the count to SmolLM2 explicitly (or print both counts).
* **M2 (paper, tab:blockpct context).** The table and its prose never name
  the model or tensor set being measured ("a trained network's weights").
  Every number reproduces from SmolLM2-135M under the conventions above;
  the paper should say so, since the same statistic on another checkpoint
  would legitimately differ.
* **M3 (audit trail, `research/RANGE_PROVENANCE_2026-08-20.md` row 50).**
  The sweep's own row labels the 9.12-binade occupancy "(GPT-2)"; the paper
  (L3874) and the measurement say **Qwen2.5-0.5B**. The sweep doc's label is
  wrong, not the paper.
* **No numeric mismatches.** Every printed weight-derived value checked in
  this pass reproduces at printed precision from the cached checkpoints.

## Records written (all machine-written, generator named inside each)

| file | backs |
|---|---|
| `arxiv_tnf/measurements/blockpct_2026-08-20.json` + `gen_blockpct.py` | tab:blockpct (all four rows) |
| `arxiv_tnf/recompute_blockpct_table.py` | tab:blockpct as a view of the record (passes) |
| `arxiv_tnf/measurements/weight_ranges_2026-08-20.json` + `gen_weight_ranges.py` | 8.32 / 9.12 occupancy; 268.95× channel range; 210-tensor scale spans |
| `arxiv_tnf/measurements/regret_sweep_2026-08-20.json` + `gen_regret_sweep.py` | the E=1…E=5 / Et=1…Et=3 sweep sentence and the falsified predictions |

The regret sweep is a full rerun (fp32 baseline + 8 quantised arms, 40 windows
of 2048 tokens each, ~20 min CPU), not a record-view: the original
`research/block/four_families.py` addresses its weights through a
session-scratchpad symlink, so the rerun addresses the HF-cache snapshot
directly — same bytes, verified by sha256.
