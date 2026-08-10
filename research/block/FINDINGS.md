# Block-scaled 4-bit quantisation — what survived

Consolidated from `THEOREM_2026-08-09.md` (chronological, ~2000 lines). This page states only
what is still standing, with its evidence and its limits. Everything retracted is listed at the
end so it cannot be quoted by accident.

**Scope of all measurements:** SmolLM2-135M and Qwen2.5-0.5B, wikitext-2, 6–48 evaluation
windows, weights-only quantisation of linear layers, block size K=32 along the contraction axis.
Two small models is not a general result.

---

## 1. Methodological findings — highest confidence

### 1.1 Competitor formats must be implemented from their specification, never from memory

Five separate bugs, **all flattering us**, each found only by reading a spec or reference
implementation:

| # | format | error |
|---|---|---|
| 1 | MX shared scale | ceiling instead of `floor(log2 max) − emax` |
| 2 | **E2M1** | missing its subnormal — 7 magnitudes, not 8 |
| 3 | NF4 | a symmetric reconstruction substituted for the real 16-value table |
| 4 | E4M3 | reserved NaN encoding ignored — max 480 instead of 448 |
| 5 | E5M2 | reserved exponent ignored — max 114688 instead of 57344 |

Bug 2 alone accounted for **39 % of MXFP4's apparent error** and, with it, essentially the whole
advantage claimed for several cycles. Every table was internally consistent throughout; internal
consistency detected none of them.

**Practice adopted:** `competitors.py` holds every reference format with a source citation and an
assertion against a *published constant*, checked at import. It caught bugs 4 and 5 on its first
run. A format that fails its check stops the import rather than being handed out.

### 1.2 Sanity gates on the instrument, not just the result

Two measurements were caught before becoming claims by a gate that asked whether the *instrument*
was plausible: the fp32 perplexity ruler check (refuses to compare unless the baseline is sane
for the model size), and the GPTQ gate (refuses to use a GPTQ baseline that loses to
round-to-nearest at 4 bits — which the first implementation did).

### 1.3 A filter that shows only success makes failure look identical to silence

Three background runs produced **empty output files**, each indistinguishable from "still
running", each a different mechanism:

1. a script copied to `/tmp` whose `competitors` import failed — the traceback was swallowed by
   `sed -n '/RULER/,$p'`, which prints nothing when the start pattern never appears;
2. `gptq_gate.py` importing `gptq_baseline.py`, which had no `__main__` guard, so the import
   silently re-ran six full quantisation sweeps and then died on a `KeyError`;
3. output buffering through `sed` on a long run, where nothing appears until the process exits.

**Practice:** filter background output with `tail -N`, which always shows something, rather than a
success-pattern range. And guard every experiment behind `if __name__ == "__main__":` — a module
that runs work on import turns any future import into a silent, expensive failure.

This is the same class as the `done 1` false-successes and the partial-`.bit` file recorded
elsewhere: **a channel that reports only the happy path cannot distinguish failure from quiet.**

### 1.4 Bug blast-radius is bounded by import structure

Scripts that never reference a competitor cannot be affected by competitor bugs. Checking this by
grep took seconds and identified four load-bearing results as structurally immune, avoiding
unnecessary re-runs.

### 1.5 Layer selection must be pinned explicitly

Two MSE tables disagreed by 1.6× because one enumerated tensors by alphabetically-sorted keys and
the other by module order — `layers.10` sorts before `layers.2`, so "the held-out half" meant
different layers in each.

---

## 2. Findings about the problem itself

### 2.1 Unweighted MSE is close to uninformative about perplexity

Measured on both models by quantising one transformer block at a time:

| | SmolLM2 | Qwen |
|---|---|---|
| MSE ↔ perplexity-damage correlation | r = +0.128 | r = +0.139 |
| spread in per-layer summed MSE | 1.15× | small |
| spread in per-layer perplexity damage | **41.9×** | 8.2× |

MSE varies by 15 % across blocks while damage varies by 4190 %. The near-identical correlation
across two unrelated models makes this a property of transformers, not of one checkpoint.

This single fact explains four separate divergences observed earlier, where a codebook with lower
MSE had worse perplexity.

**Corollary that cost us:** the MSE-optimal codebook is the right answer to the wrong question.

### 2.2 `p_eff` is layer-invariant, which blocks a whole class of methods

The density seen by the quantizer after block-max normalisation has essentially the same *shape*
in every layer. Consequence, verified: re-weighting layers by their sensitivity (a **39.5×**
spread) changes the derived codebook by **0.0001**. **Codebook shape is structurally incapable of
exploiting a per-layer effect.** This is a mechanism, not an observation.

### 2.3 Block-max normalisation removes most of the activation-outlier problem

`k_tensor` and `k_block` (mean within-block excess kurtosis) diverge enormously on activations —
`down_proj` goes from **154.09 to 4.46**. The famous activation outliers live largely *between*
blocks, not within them, which is why block scaling works at all.

The same mechanism makes whole-tensor kurtosis a **worse-than-baseline** predictor of which
codebook wins (42.9 % accuracy against a 93.7 % base rate), while within-block kurtosis reaches
95.8 %.

### 2.4 The winning 4-bit codebook is a function of tail weight

Crossovers located on synthetic data and frozen before testing: ours vs NF4 at excess kurtosis
**1.27**, ours vs E2M1 at **8.12**. Verified out-of-sample at model level — SmolLM2 (+1.12) → ours
wins; Qwen (+1.51) → NF4 wins. Both landed as predicted.

**Honest limit:** the rule is correct but *non-discriminative on weights*, beating a trivial base
rate by only 2.1 points, because every weight tensor sits in the same regime.

---

## 3. The one positive result

**Promote-only bit allocation.** Add a bit to the most sensitive layers; never remove one.

| | SmolLM2 | Qwen |
|---|---|---|
| share of the 4→5-bit gain captured, at 33.3 % of the bit cost | **54.1 %** | **50.4 %** |
| MSE-ranked control | 39.6 % | 29.8 % |
| arbitrary control | 30.3 % | — |
| last-N-blocks control | — | **41.8 %** |

Replicated on two models, held-out windows, controls that fail as intended, matched bit cost.

**Two hard limits:**
- **Cross-model transfer buys nothing.** A profile transferred from another model scores 41.6 %,
  indistinguishable from the free "promote the last N blocks" heuristic (41.8 %). Only a model's
  *own* profile is worth the ~9 extra points.
- **The baseline is round-to-nearest, which nobody deploys.** Whether this survives against GPTQ
  is unresolved: our GPTQ implementation failed its sanity gate and is being fixed.

**No working predictive model exists.** Two were proposed and both falsified by their own data —
the classical 6 dB/bit criterion and a measured-asymmetry criterion. Constant-width swapping fails
at every granularity from 1 to 10 swaps, including a swap with a 42:1 damage ratio. The rule
stands on measurement alone.

---

## 4. Retracted — do not quote

| claim | fate |
|---|---|
| "derived codebook beats MXFP4 by 41–65 % (MSE)" | measured against E2M1 missing its subnormal; **+19.3 %** corrected |
| "58–63 % of MXFP4's perplexity degradation recovered" | same cause |
| "beats E2M1 by 42–53 % on activations" | entirely the subnormal bug |
| "E2M1 is heavy-tail-tuned; activations are its home ground" | rested on the fake NF4; real NF4 wins on every activation layer type |
| "free 24.8 % improvement to MXFP4's scale rounding" | measured against a ceiling rule that is not the MX spec; the real rule is within 0.15 % of optimal |
| "scale shrinkage r\* ≈ 0.955 is a usable lever" | shrinkage and log-domain offset are the same knob; does not reproduce in perplexity |
| "the format beats both incumbents" | wins on SmolLM2, **loses to NF4 on Qwen** |
| "promote-only works even better on top of GPTQ (60.4 %)" | the GPTQ baseline was invalid |

**The format claim is dead.** No codebook derived here leads on both models.

---

## 5. Publication status

**🛑 The stop-rule stands and has been vindicated twice.** The failure it guards against — shipping
a headline that is an artefact — would have occurred at several points in this programme, and was
caught each time by checking a competitor against its source rather than by any internal check.

Nothing here is a format that leads the world. What exists is a set of methodological practices,
four findings about why block quantisation behaves as it does, and one modest allocation result
whose baseline is still being validated.
