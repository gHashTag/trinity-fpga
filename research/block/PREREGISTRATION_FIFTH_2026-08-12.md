# Pre-registration: four checkpoints from families this campaign has never measured

**Written and committed before any new checkpoint was loaded.** The only numbers
in this file that come from measurement are the OLD-four figures quoted as the
basis of the predictions; every new-checkpoint number is a prediction.

Everything the block campaign still asserts is *within* a checkpoint. Its four
checkpoints have each been used for selection at least once, and they are four
variations on one decoder-only theme. The fix is checkpoints no decision in this
project has touched, chosen for architectural distance rather than convenience,
with the hypotheses and the analysis fixed **before** the data exists.

---

## 1. The checkpoints, and why each

| tag | checkpoint | params | what it brings that the pool does not have |
|---|---|---:|---|
| `gpt2` | `gpt2` (OpenAI GPT-2 small) | 124M | Projections stored as `transformers` **`Conv1D`, shape `[in, out]`** — every other checkpoint in the pool is `nn.Linear` `[out, in]`. The block axis has to be *chosen* rather than assumed. WebText corpus. |
| `gptneo` | `EleutherAI/gpt-neo-125m` | 125M | **Alternating local (window 256) and global attention** layers. No checkpoint in the pool has a windowed/sparse attention pattern. Pile corpus. |
| `bloom` | `bigscience/bloom-560m` | 559M | **ALiBi** — no positional-embedding table at all, position enters as an attention bias. **250,880-token multilingual vocabulary**, 5× the pool's largest, so the same English text becomes a completely different token stream. ROOTS corpus. |
| `mamba` | `state-spaces/mamba-130m-hf` | 129M | **Not a transformer.** Selective state-space, **zero attention**. If the sixteenth-codeword result is a property of trained weight distributions it must survive here; if it is an artefact of attention, this is where it breaks. |

### Two corrections to the premises this line was handed

1. **"GPT-2 brings learned positional embeddings — nothing else here has them" is
   false.** `OPT-125M`, already in the pool, uses `OPTLearnedPositionalEmbedding`.
   Learned absolute positions are not what `gpt2` adds; the `Conv1D` weight
   layout and the WebText corpus are.
2. **"gpt2 has never been used by any campaign here" is false as stated.**
   `align_u.py` measured `gpt2` (SEQLEN 1024, 40 windows) for the *alignment
   constant* line and left `align_u_gpt2.json` on disk; `flatness.py`,
   `u_atoms.py`, `depth_mechanism.py`, `u_predicted.py` and `u_eval_floor.py`
   also name it. That line is a different axis — where the block scale is
   aligned, not what the codebook is — and **no codebook or placement decision
   in campaigns A–D was taken on `gpt2`.** So `gpt2` is virgin for *this*
   question and not virgin for this repository. Recorded because a
   pre-registration that repeats a false premise is worth nothing.

### Rejected, ex ante, with the reason

* `google/gemma-2-2b`, `facebook/MobileLLM-125M` — gated.
* `cerebras/Cerebras-GPT-111M` — not resolvable from this environment.
* `allenai/OLMo-1B-hf`, `TinyLlama/TinyLlama_v1.1`, `microsoft/phi-1_5`,
  `stabilityai/stablelm-2-1_6b` — 1.1–2.7B parameters; twelve arms × 40 windows
  each costs an estimated 2–4 CPU-hours per checkpoint on this machine.
  **Dropped for compute, before measuring.**

**Consequence, declared now rather than discovered later:** the new four span
124M–559M, so this test does **not** expand the scale axis. The eight-checkpoint
pool stays ≤ 0.56B. Whatever clears here is a claim about small checkpoints
across many families, never a claim about scale.

---

## 2. Protocol — identical to the existing one, with two forced deviations

Same wikitext-2 test parquet joined with `"\n\n"`, block **32** along the
contraction axis, **E8M0** shared scale, **`lm_head` excluded**, every codebook
normalised to `max|level| = 1.0` on both tails, 4.25 bits/element. Measurement
code is `block_tnf.py`'s own `quant` / `perplexity` / `target_modules` /
`load_wikitext`, executed out of its source; codebooks are `campaignA_books`;
the signed quantiser is `campaignC_books.make_quant_signed`.

**Deviation 1 — `gpt2` context length.** GPT-2's learned positional table is
`n_positions = 1024`; SEQLEN 2048 is unavailable to it at any price. `gpt2` is
therefore measured at **SEQLEN 1024 × 80 windows**, which covers **81,920
tokens — the same span as 40 × 2048** everywhere else. The pool already varies
window count per checkpoint (`qwen` is 20 × 2048), and every comparison here is
*paired within a checkpoint*, so the context length cancels out of each margin.

**Deviation 2 — `gpt2` weight layout.** `Conv1D` weights are transposed to
`[out, in]` before quantisation and back after, so blocks run along the
contraction axis on all eight checkpoints.

### Gates that abort before any number prints

* **G1** targets non-empty; on Conv1D-free checkpoints the extended selector is
  asserted *tensor-for-tensor identical* to `block_tnf.target_modules`; the
  fraction of parameters the block rule reaches is recorded, not assumed.
* **G2** the harness reproduces all four published rulers (14.4874/21.9397,
  12.6999/15.4374, 25.9561/47.6504, 27.5678/30.7871) to < 5e-4 relative **before
  any new checkpoint is loaded.** If it does not, it is not this campaign's
  instrument and nothing it says about a new checkpoint counts.
* **G3** `quant_signed` bit-exact against `block_tnf.quant` in the measuring
  process, on each checkpoint's own tensors.
* **G4** every arm must actually change the weights (`max|Δw| > 0`). This is the
  gate that catches the specific way this file could fail silently: on GPT-2 the
  unmodified `nn.Linear` filter matches only `lm_head`, which is then excluded,
  and all twelve arms would report the fp32 number.
* **G5** on a new checkpoint no published ruler exists, so the assertable
  statement is that MXFP4 must *cost* perplexity relative to fp32. New rulers
  are recorded as new rulers.

### Arms measured (12 forward sweeps per checkpoint)

`fp32`, `MXFP4`, the **nine placements** of the sixteenth codeword
(`MX-asym-` `NEAR0`, `NEAR0N`, `MIDN`, `MID`, `G12`, `G23`, `G34`, `G68`,
`MID2`), and `NF4`. `MX-asym-TOP` is a **clipping arm**, not a placement
(+1.000/−0.750), and stays out, exactly as `campaignA_books.candidates()` has it.

---

## 3. The analysis, fixed now so it cannot be chosen later

**Replicate unit: the checkpoint.** Each checkpoint contributes exactly one
number — `d̄_m = mean over its windows of (nll_arm,i − nll_ref,i)`, so
`ppl_arm/ppl_ref = exp(d̄_m)` exactly. Margin % = `100(exp(d̄)−1)`; negative =
the arm beats the reference. Windows replicate the *text*, never the family;
they are never pooled across checkpoints in any cross-model row.

**Statistic:** `campaignC_stats.paired` — one-sample two-sided t on the vector of
model-level `d̄`, n = 4 new checkpoints, df = 3. Verdict by
`campaignC_stats.verdict`.

**Tie rule:** a margin whose 95 % CI contains zero is a **TIE**, whatever its p.
A p that fails its multiplicity correction is a **TIE**.

**Multiplicity:** H1, H2, H3 are a pre-registered primary family of three →
**Bonferroni × 3**, α = 0.0167. The per-arm nine-placement matrix is *secondary
and exploratory* and carries **Bonferroni × 9**, as in the existing records.

**Reporting:** old-four, new-only, and combined figures are reported
**separately and always all three**. The combined n = 8 row is flagged as
*contaminated* — four of its eight checkpoints took part in choosing the arm —
and is never the headline.

**No checkpoint may be added or dropped after the first new number is seen.**
Four are registered; four will be reported, including any that fails.

### The three hypotheses

**H1 — `MX-asym-NEAR0` beats `MXFP4` on the new checkpoints.**
Model-level, **new four only**, n = 4. Direction: **negative**.
Clears only if the 95 % CI excludes zero *and* p × 3 < 0.05.

**H2 — `MX-asym-NEAR0` vs `NF4`.**
Model-level, new four only, n = 4. **Predicted direction: negative** —
`MX-asym-NEAR0` better than `NF4`. Basis: on the old four it is −0.92 %
[−6.62, +5.13], p = 0.66, better on 3 of 4.

**H3 — the nine-placement ORDER replicates.**
Spearman ρ between the nine placements' mean model-level margin vs MXFP4 on the
**new four** and on the **old four**. n = 9 arms. **Predicted direction:
positive.** Governing p is the **exact permutation p over all 9! rankings**;
`scipy.stats.spearmanr`'s asymptotic p is reported alongside but does not
govern.

The old-four order this is tested against, fixed here (mean margin vs MXFP4,
model-level, n = 4 — recomputed from `campaignB_*.json` + `campaignA_ppl_*.json`
after asserting their `fp32` and `MXFP4` per-window vectors are bit-identical):

| rank | placement | old-four mean |
|---:|---|---:|
| 1 | `NEAR0` | −4.76 % |
| 2 | `NEAR0N` | −3.61 % |
| 3 | `MIDN` | −2.70 % |
| 4 | `MID` | −2.08 % |
| 5 | `G12` | −2.05 % |
| 6 | `G68` | −1.64 % |
| 7 | `MID2` | −1.56 % |
| 8 | `G34` | −0.52 % |
| 9 | `G23` | −0.50 % |

---

## 4. Predictions — written as numbers, before any new model was run

| # | quantity | prediction | predicted verdict |
|---|---|---:|---|
| P1 | H1 mean margin, new four | **−3.0 %** | **TIE** (CI includes 0; fails ×3) |
| P2 | H1 sign pattern, new four | **4 of 4 negative** | — |
| P3 | H1 uncorrected p, new four | **≈ 0.05** (0.02–0.15) | — |
| P4 | H1 mean margin, combined n = 8 | **−3.9 %** | **BEATS** uncorrected, but contaminated |
| P5 | H2 mean margin, new four | **−1.0 %** | **TIE**, 3 of 4 negative |
| P6 | H3 Spearman ρ | **+0.75** | **positive, exact p < 0.05** |
| P7 | H3 detail | `NEAR0` still rank 1 or 2 on the new four; `G23`/`G34` still the two worst | — |
| P8 | `mamba` — the non-transformer | `NEAR0` beats MXFP4 there too; **not the outlier** | — |

**Reasoning behind P1, recorded so the prediction can be judged and not just
scored.** The old-four in-sample figure is −4.76 %, but `NEAR0` was the argmin of
a nine-arm pool taken on those same four checkpoints; the rotation-honest
estimate of the same protocol is −2.46 %, and the measured selection optimism in
this pool is 2.30 pp of the 4.76 pp headline. A checkpoint that took no part in
the selection should therefore land near −2.5 %; −3.0 % allows for the
possibility that some of the effect is real and shared. The CI is predicted to
contain zero because the old four's between-model spread (−2.73 % to −8.07 %)
gives a standard error near 1.3 pp at n = 4, which a −3 % mean cannot clear.

**What each outcome means, agreed now:**

* H1 clears → the first cross-model result this campaign has earned, on
  checkpoints that took no part in choosing the arm.
* H1 ties → **that is the headline**, and the standing within-model claim is all
  there ever was.
* H1 reverses (mean ≥ 0) → the placement result is an artefact of the original
  four checkpoints and must be recorded as refuted.
* H3 ties or reverses → the nine-placement *ranking* does not transport, which
  would make every "best placement" statement in this repository a per-pool
  statement.

---

*Protocol: wikitext-2, block 32, E8M0, `lm_head` excluded, 4.25 b/elem.
Cross-model claims carry model-level statistics; n = checkpoints, never windows.
Records stay in-repo.*
