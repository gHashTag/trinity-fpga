# Three questions about the sixteenth codeword, answered — and one of them answered against the way it was asked

Every headline below is the one that survived an adversarial audit. In all three
campaigns the first draft claimed more than the data carried, and the correction
is more useful than the claim.

## 1. Placement: the objective was the fix, not the jointness

`SIXTEENTH_CODEWORD_SPENT` found the placement choice unstable: selecting on
Pythia picks `TOP`, which **loses** to MXFP4 by +2.55 %. The proposed remedy was
joint selection over three models, by analogy with `JOINT-KL`.

Joint selection **does not stabilise the placement**: rotating the held-out model
gives **three distinct winners in four rotations** (NEAR0 twice, NEAR0N once,
MIDN once). The placement is still a property of which checkpoints are in the fit
set.

**🛑 The rest of this section was withdrawn on 2026-08-12** — see
`CLIPPING_ARM_CORRECTION_2026-08-12.md`. `MX-asym-TOP` is not a placement: it
extends the ladder to 16/12 and pays for the renormalisation by clipping the
negative extreme to −0.75. The T38 assertion said "BOTH tails" in its docstring
and compared `max(pos, neg)` in its code, so the clipping arm sat in the ranked
pool as `kind="sig"` through this whole campaign. The corrected instrument is in
`campaignA_books.check`; the corrected numbers, all from re-running this repo's
own scripts on the nine placements, are:

| protocol | with the clipping arm | placements only |
|---|---|---|
| select on one model **by perplexity** | 10 / 12, worst **+4.68 %** | **12 / 12, worst −1.41 %** |
| select on one model by KL | 12 / 12, worst −1.41 % | 12 / 12, worst −1.41 % |
| select jointly on three by KL | 4 / 4, worst −1.72 % | 4 / 4, worst −1.72 % |

**The claim "the objective was the fix, not the jointness" does not survive.**
It rested on one rotation: with the clipping arm in the pool, perplexity selects
it on Pythia and loses on two held-out models. Without it, perplexity selects
`NEAR0N` and wins all three. On the placements the two objectives are
indistinguishable — 12/12, worst −1.41 %, both.

The mechanism Spearmans go the same way: joint-KL against held-out margin was
+0.188 SmolLM2 and −0.030 Pythia, and on the placements is **+0.433** and
**+0.333**. No rotation carries zero rank information, so the sentence that
explained the instability was describing the clipping arm.

**What does survive.** The enumeration was **completed** — the four gap
placements the first campaign skipped, plus `NEAR0N`, were built and measured on
all four models, and none wins anything. The incomplete enumeration was not
hiding a better answer. And `NEAR0` is now selected by *more* rotations than
before, not fewer.

**A stated premise turned out false.** The mirror arms are not controls that land
on their twin: `NEAR0` and `NEAR0N` differ by 3.4 % of perplexity on SmolLM2 while
agreeing within 0.1 % on Pythia.

**And the honest deployment note.** With the reference books admitted to the same
pool, the same KL criterion picks **NF4** — over all four models and in three of
the four rotations. Our criterion does not prefer our codebook when the
competitor is allowed to enter.

## 2. Silicon: asymmetry costs one LUT, and the mechanism is not the one proposed

The question was whether dropping the sign path pays for a 16-entry table.
**The sign path is not asymmetry's to drop**: a flat 16-entry table removes the
sign-apply carry chain for the *symmetric* book too. Most of the saving belongs
to the encoding, not to the book.

Isolating one variable at a time:

| decoder | logic |
|---|---|
| E2M1 structural, 1/12, 5-bit — **the published incumbent** | 9 LUT + 2 CARRY4 |
| E2M1 **flat**, 1/12, 5-bit — the best symmetric implementation | **5 LUT + 0 CARRY4** |
| MX-asym-NEAR0 flat, 1/24, 6-bit | **6 LUT + 0 CARRY4** |

**Asymmetry itself costs exactly +1 LUT and zero CARRY4** against the strongest
symmetric implementation at equal encoding — and against MXFP4 as this project
published it, the asymmetric decoder is **strictly cheaper**: −3 LUT, −2 CARRY4.
Zero flip-flops either way.

**On a DSP-based lane — the deployment case — the DSP48 absorbs the multiply
entirely**, so the lane's LUT cost *is* the decoder's: 6 LUT asymmetric against
9 LUT + 2 CARRY4 for the incumbent. **No extra DSP for any arm.**

On LUT-only fabric asymmetry is not free: **+16.8 %** against the best symmetric
lane, though still **−12.0 %** against the published incumbent. The mechanism is
measured and is *not* the table — the sixth weight bit widens the multiplier by
+24 LUT, while the asymmetric decode inside the lane is 4 LUT **cheaper** than
the best symmetric decode.

**The frequency collector was broken**, and every figure below is the corrected
one. `run_synth.py` appended nextpnr's `Max frequency for clock` line — which is
printed **twice per run**, post-placement and post-route — and then sliced the
last `len(SEEDS)` values, keeping a mixture of three post-route and two
post-placement figures from the last seeds only. `run_asym.py` `import`s
`run_synth`, so it inherited the same collector and the same defect; fixing the
one fixed both, and the blast radius was bounded by that import.

Corrected post-route medians over seeds 1–5, standalone decoders:

| arm | median MHz | [min, max] |
|---|---:|---|
| `ad_mx24fl` best symmetric, flat | 906.62 | [904.98, 1002.00] |
| `ad_mx12fl` symmetric, flat, 1/12 | 888.10 | [766.87, 946.07] |
| `ad_asymsr` | 849.62 | [776.40, 888.89] |
| `ad_asymmx` **the challenger** | 816.99 | [810.37, 914.91] |
| `ad_mxfp4` **the published incumbent** | 458.30 | [406.01, 509.16] |
| `ad_mx24st` symmetric, structural | 393.24 | [363.77, 402.25] |

The conclusion survives the correction: **every lane comparison still ties** under
the project's seed-spread rule, and the one separated pair is the asymmetric
decoder against the *structural* incumbent — 816.99 against 458.30, a gap that is
the sign-apply carry chain and **vanishes against the flat symmetric decoder**
(816.99 [810, 915] against 906.62 [905, 1002] overlap).

## 3. What predicts placement: the conjecture failed, and the classical answer is anti-correlated

Three candidate predictors were scored against the measured placement order.

**First, the target itself is not separated.** Every adjacent pair in the
measured ranking is a model-level **tie** (p = 0.217, 0.327, 0.706, 0.647), and
the per-model orders disagree violently — SmolLM2 ranks MIDN first, Qwen and OPT
rank NEAR0 first, Pythia ranks TOP first and MIDN last. A predictor was being
scored against an ordering whose internal steps the data does not assert.

| predictor | Spearman, n = 5 | p | leave-one-model-out | **n = 4, placements only** |
|---|---:|---:|---|---:|
| P1 bin mass | +0.700 | 0.117 | +0.70 → +0.40 without SmolLM2 | +0.400 |
| P2 mass × width² — the classical greedy step | +0.400 | 0.258 | +0.40 → **−0.80** without SmolLM2 | **−0.200** |
| P3 KL share | +0.900 | 0.042 | +0.90 → **+0.10** without SmolLM2 | **+1.000** |

The last column drops `MX-asym-TOP`, which is a clipping arm and not a placement
(`CLIPPING_ARM_CORRECTION_2026-08-12.md`). At n = 4 only a perfect order is
significant at all, so P3's `+1.000` is the floor of what this test can say
rather than a strong result — but P2's sign change is in the same direction as
the real-weight-space measurement below.

**No predictor is rotation-stable.** P3's apparent significance is carried
entirely by one model, and with three predictors tested `0.042 × 3 = 0.125`
survives no multiplicity correction. At n = 5 only a perfect order is significant
at all, so this test is "perfect or nothing" and should not be leaned on.

**The one defensible strong statement** is about the classical criterion, and it
needed the exact form the first draft did not compute —
`ΔSSE = Σ[(y − Q_MXFP4)² − (y − Q_book)²]`. In normalised codebook space it is a
null (ρ = +0.400). **In real weight space it is anti-correlated: pooled
ρ = −0.800, per-model −0.60 / −0.70 / −0.50 / −0.70, 0 of 4 argmax hits,
consistent on 4 of 4 models.** The greedy squared-error step points away from the
placement that wins.

That is `METRIC_DISAGREEMENT` again, in its sharpest form yet: not merely that
squared error fails to rank, but that in the space the hardware actually operates
in, it ranks backwards.

---

*Four models, wikitext-2, block 32, E8M0, `lm_head` excluded. Cross-model claims
carry model-level statistics; window-level appears only for within-model claims.
Every rotation of every selection protocol is reported, not the best one. Silicon:
yosys 0.65 + nextpnr-xilinx, xc7a200t, harness subtracted, logic cells rather
than nextpnr's SLICE_LUTX bel occupancy, median of five seeds with the collector
bug fixed and one value per seed asserted.*
