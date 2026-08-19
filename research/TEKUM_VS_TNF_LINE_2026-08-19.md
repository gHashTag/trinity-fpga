# The tekum-vs-TNF line, complete — 2026-08-19

The honest record of every claim this repository made about TNF (Ternary
Network Floats) against tekum, what the 2026-08-18 audit removed, and what
measurement replaced it with. Every number below is quoted from the named
repo artifact; the two benches were re-run 2026-08-19 under their fixed seeds
and reproduced their recorded outputs exactly.

## 1. What was claimed before the audit, and what replaced it

Three claims carried this line. All three are withdrawn, each for a reason
verified by hand (`research/AUDIT_2026-08-18_TWO_PHASE.md`):

* **"GF-T16 beats tekum16 on accuracy at equal width"**
  (`research/GFT16_BEATS_TEKUM16_2026-08-05.md`). It was not at equal width —
  TNF16 as specified stores **17 bits** (four trits pack into seven binary
  positions, `1+7+9`), and it was not against tekum: `conformance/tekum_ref.py`
  decodes all 65,536 sixteen-bit codes **identically** to `takum_ref.py`. The
  model that was beaten is a linear binary model of takum's field layout.
* **"461 LC, below tekum16's 480–650"**
  (`research/GF_T_GOLD_STANDARD_LADDER_2026-08-05.md`). 461 is not a GF-T
  adder; the only adder then in the tree was **magnitude-only** — no sign, no
  subtraction, no rounding, no normalisation — set against a complete adder.
  The gap was feature asymmetry (`fpga/tef/FULL_ADDER.md`).
* **"TNF16 beats takum16"** (the paper's accuracy table). The takum oracle it
  was measured against negated wrongly on **every negative code**; fixed in
  #606, it now matches libtakum on 65,534/65,535 codes
  (`research/arxiv_tnf/tnf_paper.tex`, "Erratum (2026-08-18)").

What replaced them:

* `conformance/tekum_true_ref.py` — tekum as published (arXiv:2512.10964,
  Definitions 7–8, extracted in `research/TEKUM_SPEC_EXTRACT_2026-08-18.md`):
  base **3**, code space **3^n**, width counted in **trits** (tekum16 = 16
  trits ≈ 25.4 bits — it never was a 16-bit competitor), negation by digit
  inversion. Selftest: the paper's worked example decodes to exactly 1.0;
  symmetry and strict monotonicity on all 6,559 finite tekum8 codes.
* `conformance/tnf_ref.py` **WIDTH NOTICE** + **TRUE_LADDER** — the ladder
  names lie on every rung (TNF8 stores 10 bits, TNF16 17, TNF32 30, TNF64 65,
  TNF1024 1025). The exact-width rungs are TNF(2,3) at 8 bits, **TNF(4,8) at
  16**, **TNF(4,24) at 32**; every equal-width comparison must use those.
  Measured consequence of the misnaming: the sign of the "advantage" over
  takum followed the sign of the width excess (+2 bits: 484×; +1: 2×; −2:
  0.08×), and at true width it is 1.00×.

## 2. Accuracy: a three-way tie at both widths

`conformance/tekum_true_bench.py` — 64-term accumulation, ±3 decades,
seed 11; 60 trials in the 16-bit class, 40 in the 32-bit class. Reproduced
2026-08-19; recorded in `research/arxiv_tnf/README.md` and the tex erratum.

| class | format | stored bits | mean rel err |
|---|---|---:|---:|
| 16-bit | tekum10 (true base-3) | 15.85 | 8.561e-03 |
| 16-bit | takum16 | 16.00 | 5.697e-03 |
| 16-bit | TNF(4,8) | 16.00 | **5.323e-03** |
| 32-bit | tekum20 | 31.70 | 1.434e-07 |
| 32-bit | takum32 | 32.00 | 1.264e-07 |
| 32-bit | TNF(4,24) | 32.00 | **1.203e-07** |

All within 1.6× at 16 bits and 1.19× at 32. TNF is slightly ahead, tekum
slightly behind — and tekum gives up 0.15 (resp. 0.30) bits to the other two,
which is the direction that gap points. **No format wins by more than the
width it gives up.** Caveats from the bench itself: one band, one seed,
accumulation only; the specials ambiguity in `tekum_true_ref` affects two
codes and none of these samples.

## 3. Hardware: the only measured asymmetry in the line

All counts: yosys 0.65, `synth_xilinx -family xc7`, last stat block,
post-synthesis, family-level, no place-and-route, no board.

From `fpga/tekum/TEKUM_HW.md` (`-nodsp` unless stated):

| circuit | LUT | CARRY4 | verified |
|---|---:|---:|---|
| `tekum8_decode` — anchor, trits, tapered fields, base-3 ladder | **542** | 96 | all 6,558 finite tekum8 codes + 3 specials, 0 errors |
| `tnf10_decode` — TNF(2,3): field slice + one subtract | **1** | 1 | — |
| `tekum8_add` — full datapath, 8 trits, true base-3 | **15,251** | 2,063 | 3,600 oracle vectors, 0 errors |
| `tef_add_full` @ TNF(4,8) — 16 bits, full feature set | **397** | 45 | 1,500 oracle-encode vectors, 0 errors (`fpga/tef/FULL_ADDER.md`) |
| `tekum8_encode` (codec closure: round-trip all 6,558 codes, 0 errors) | 1,006 | 329 | — |

That is **38× LUT for the smaller format** (tekum8 carries 12.68 bits against
TNF(4,8)'s 16). With DSP inference on, `tekum8_add` still needs **9,956 LUT +
57 DSP48E1**. The reason is structural, not an implementation accident: the
3^k alignment and the candidate values are **genuine multiplications**, where
TNF's alignment is a **shift**. Entry cost alone — ~542 LUT per operand decode
— exceeds TNF's entire full adder before tekum's arithmetic begins.

The adjacent fixed-vs-tapered datapoint stays bounded to what it is
(`fpga/tef/FULL_ADDER.md`): `tef_add_full` @ TNF(4,8) at 397 LUT against
`tekum16_adder` at 1,182 LUT is **2.98×**, but the opponent implements the
*linear takum model* — the real takum is logarithmic and the real tekum is
base-3, and neither published format has adder RTL here. TNF(4,24) at 32 bits:
1,226 LUT / 106 CARRY4.

## 4. The two adder findings (`fpga/tekum/TEKUM_HW.md`, `fpga/tekum/tekum8_add.v`)

* **Ties exist — exactly at window boundaries.** Inside one window the grid
  step is odd and twice the numerator even, so a tie is impossible. Across a
  boundary the step changes by 3× and the midpoint of the gap is
  representable — measured: `3213 + (−3215)` lands on one exactly. The oracle
  resolves ties **toward the larger value**, so the RTL builds both boundary
  candidates, compares exact integer distances, and breaks ties the same way.
  At |e| ≥ 123 (regime p = 0, fmax = 0) the window's *single* code is both
  edge codes at once, so the cross-boundary direction must come from the
  **sign of the residual**, not the sign of F. Mutation controls prove the
  bench sees this: inverted tie-break → 35 errors, `<=` in the candidate
  compare → 22 errors.
* **The far threshold is provably d ≥ 13.** At d = 13 the low operand (≤ 364
  in res units) cannot move the rounding: the distance from the aligned high
  operand to any rounding midpoint is a nonzero multiple of 3^13 (parity:
  2(hg−243) is even, (2F+1)·3^k is odd). The RTL's d ≥ 14 cutoff is
  conservative by exactly one and functionally equivalent — the d > 12 mutant
  passes all 3,600 vectors.

One lesson paid three times in one day (`fpga/tekum/tekum8_add.v` header,
`TEKUM_HW.md`): Verilog concatenations are **unsigned**, and one unsigned
operand poisons the whole expression — `pow3(13 + {{2{mm[3]}}, mm})` computed
pow3(72) instead of pow3(8) and 796 of 3,600 additions rounded on a garbage
step; all thirteen sign-extension sites are now wrapped in `$signed`.

## 5. The block axis: the stop-rule holds

Two independent measurements, same verdict.

**Perplexity** (`research/block/BLOCK_AXIS_VERDICT_2026-08-10.md` —
SmolLM2-135M, wikitext-2, 40 windows of 2,048 tokens, block 32 along the
contraction axis, E8M0 shared scale, baseline 14.4874): **MXFP4 21.9397 vs
TNF4 36.7214** at 4 bits; MXFP6 14.7269 vs TNF6 (best split, E_t=2) 18.0275
at 6 bits. Structural reason: 3^Et never divides 2^k, so a ternary exponent
packed into a short binary word wastes codes — TNF4 uses 7 of 8 magnitudes
and covers less range than E2M1 at the same time.

**Per-block relative error + flush rate**
(`conformance/block_axis_tef_vs_mxfp4.py`, re-run 2026-08-19: fixed seeds,
one shared E8M0 scale convention for every candidate, all spot checks against
the exact oracles passing; real tensors are GPT-2 from the local HF cache,
offline, blocked along the contraction axis):

| dataset | MXFP4 E2M1 (4.25 b) | TNF(1,1) (4.25 b) | TNF(2,1) (6.25 b) |
|---|---:|---:|---:|
| normal(0,1), 4096 blocks | 2.3446e-01 / 10.76% fl | 8.3424e-01 / 70.15% | 1.0486e-01 / 1.35% |
| heavy-tailed 1%×16 | 3.4498e-01 / 21.73% | 8.6607e-01 / 76.34% | 1.2706e-01 / 3.18% |
| gpt2 h.0.attn.c_attn | 2.5992e-01 / 12.78% | 8.5390e-01 / 74.19% | 1.0838e-01 / 1.63% |
| gpt2 h.5.mlp.c_fc | 2.3929e-01 / 11.08% | 8.3810e-01 / 71.27% | 1.0544e-01 / 1.39% |

At equal bits (4+0.25) **TNF(1,1) loses to MXFP4 on 4 of 4 datasets**, and
its flush profile (70–76% of nonzero weights to zero) is that of a
near-fixed-point code, not a float. TNF(2,1) does score below MXFP4 — but it
is a **6-bit code against a 4-bit one**: the win is the width, not the
format, and at 6 bits its honest opponent is MXFP6, which already won.
**The stop-rule keeps publication closed** — TNF does not beat MXFP4 on the
block axis at equal bits by either measurement.

## 6. What would change the verdict

* **A ternary fabric.** Every hardware number in §3 is the cost of base 3 in
  a *binary* fabric — the eight compare-subtract trit stages and the 3^k
  multiplications are exactly the work a ternary substrate would do in wiring,
  the way TNF's field slice costs 1 LUT here. On such a fabric the 542-vs-1
  and 38× results do not carry (`fpga/tekum/TEKUM_HW.md`, closing section).
  No such fabric exists to measure on.
* **A workload where tekum's range matters.** The accuracy tie was measured
  on one ±3-decade band. TNF(4,8)'s exponent spans e ∈ [−39, +39] binades
  (~12 decades) and then hard-clips; tekum8's tapered exponent reaches
  e ∈ [−365, +365] in powers of **3** (`fpga/tekum/tekum8_add.v` range
  check), roughly ±174 decades. A workload actually occupying that span
  would find TNF overflowing where tekum degrades gracefully — that is the
  trade Theorem 12's taper bound prices, and no benchmark in this line has
  exercised it.
* **On the block axis**, the stop-rule states its own reversal condition: a
  TNF configuration beating MXFP4 at equal bits, on measurement. Nothing
  measured to date does.

## Postscript 2026-08-19: perplexity closes both remaining axes

* **16-bit trio, end task** (`research/PPL_16BIT_TRIO_2026-08-19.md`,
  SmolLM2-135M / wikitext-2, the 2026-08-10 pipeline): all three formats are
  indistinguishable from FP32 — every row within 0.0009 of ppl 14.4874, some
  below baseline, ordering flipping between scopes, i.e. noise. The tie
  survives on a live model in the strongest form. The one real separation is
  weight NRMSE, and it ranks TNF **last** (TNF(4,8) 8.21e-4, takum16
  3.22e-4, tekum10 2.19e-4 at 0.15 fewer stored bits) — reversed from the
  accumulation ranking of §2 and reported precisely because the direction is
  against us; it never reaches the task metric.
* **Scale axis, end task** (`research/PPL_SCALE_AXIS_2026-08-19.md`):
  TNF-scale (3 trits + 3 mantissa bits) ties ue5m3 **exactly** — a functional
  identity, not a measurement: over all 3,317,760 block scales the two codecs
  emit the identical quantised scale, because the model's occupied range
  (8.32 binades) sits inside their shared ±13-binade region. It beats only
  e8m0, which any 3-mantissa-bit codec does. The NRMSE-predicted ue4m3
  catastrophe does not transfer (0.170% of blocks below its normal range,
  none collapse).

Both perplexity axes point the same way as §5: no measured basis for a TNF
superiority claim; the stop-rule stays closed.
