# T41 — a clipping arm is the parent book on dilated data, and on a float ladder the dilation gives the gain straight back

`MX-asym-TOP` extends E2M1's ladder to 16/12 and pays for the rung by
reconstructing the largest-magnitude **negative** element of every block at
0.75×. `CLIPPING_ARM_CORRECTION_2026-08-12.md` removed it from the placement
pool. It left the structural question the campaign never asked: **when is that
trade worth making?** It swings 13 points across four checkpoints — −8.27 % on
Pythia, +4.68 % on SmolLM2 — and no placement shows anything like that spread.

## 🛑 Literature first, and it is not empty

Three days ago NF4 turned out to have beaten MXFP4 in this harness since 2023,
and the sixteenth-codeword observation turned out to be
[arXiv:2607.08779](https://arxiv.org/abs/2607.08779). The field was checked
**before** any derivation here. Most of the trade is published.

| what | where | what it already covers |
|---|---|---|
| distortion = **granular + overload**, and a loading factor trading them | classical scalar-quantisation theory — textbook material, read here only through secondary summaries | the entire decomposition, in general form |
| clipping loss + quantisation loss, closed-form optimum under a continuous prior | **ACIQ** ([arXiv:1810.05723](https://arxiv.org/abs/1810.05723)); **LAPQ** ([arXiv:1911.07190](https://arxiv.org/abs/1911.07190)); PACT | that an interior clipping threshold beats the max, and how to derive it — for a **uniform, per-tensor** quantiser |
| "expected quantisation error is a sum of the rounding error and the clipping error" | Nagel et al. white paper ([arXiv:2106.08295](https://arxiv.org/abs/2106.08295)) | the statement in the LLM-quantisation idiom |
| **per-block** choice between mapping the block max to 6 or to 4 in FP4, picked by MSE | **Four Over Six** ([arXiv:2512.02010](https://arxiv.org/abs/2512.02010)) | exactly this trade in a block-scaled format — **but chosen by search, and the paper states no analytic criterion** |
| **analytic, calibration-free, distribution-independent** optimal scaling boundary `Qmax = 7.25` for E2M1, from the periodicity of power-of-two scales | **MXAttention / UOS** ([arXiv:2607.24377](https://arxiv.org/abs/2607.24377)) | a derived optimum that *deliberately clips above the format max*, using the same E8M0 phase T38 is about — **applied to attention activations, not weights** |
| the scale factor as a dominant MXFP4 error source; a "pre-scale" fix | MXFP benchmark ([arXiv:2601.09555](https://arxiv.org/abs/2601.09555)) | that contracting before quantising is a known remedy |
| which **tail** gets the alphabet's extra representable value | [arXiv:2607.08779](https://arxiv.org/abs/2607.08779); **BOF4-S** signed-absmax normalisation ([arXiv:2505.06653](https://arxiv.org/abs/2505.06653)) | the asymmetry decision, from the integer and block-float sides |

**So the honest position before deriving anything:** that clipping buys
granularity, that the optimum lies strictly inside the block max, and that this
holds in block-scaled FP4 with a power-of-two scale, are all published. UOS in
particular already answers "when is clipping favourable" analytically for E2M1:
its `Qmax = 7.25` sits **above** the format's own top level of 6 — so some
clipping is optimal — and **below** the OCP rule's effective 8, so the
specification's default clips too much.

**What is not covered, and is what T41 is about:** every one of those results
clips **both tails symmetrically**. The arm here clips **one tail only** and
spends the freed reach on an extra codeword for the other, so its positive side
pays no clipping at all. None of the above treats a one-sided clip, and Four Over
Six explicitly leaves the analytic criterion open. Whether *that* asymmetric
trade is favourable, and what decides it, is the open question — and, as recorded
below, this document does **not** close it.

Corollary 3 below sharpens the relationship to the published work considerably:
the arm's clipped tail turns out to be **the OCP MX specification's own MXFP4**
on every block whose max is not an exact power of two (0.1–0.9 % of real blocks
are the exception — see the corollary), so the only genuinely unusual thing is that
the specification's rule is applied to one tail and this repository's rule to the
other.

---

## Setup

Parent book **B** (MXFP4/E2M1): magnitudes `0 = ℓ₀ < ℓ₁ < … < ℓ₇ = 1`, in units
of 1/12 the ladder `1,2,3,4,6,8,12`, applied with a sign.

Clipping arm **A** with contraction `c = T₋/T₊ ∈ (0,1)`: positive levels
`cℓ ∪ {1}`, negative levels `−cℓ`, and zero. `MX-asym-TOP` is `c = 3/4`, read off
the book rather than assumed — its negative ladder is bit-identically `0.75·ℓ`
and its positive ladder is `0.75·ℓ` plus one rung at 1.

Both books carry `max|level| = 1.0`, so both take the **same** E8M0 block scale
`s = 2^⌈log₂ a⌉` for block max `a` — T38 phase `φ = 0` for both, and the
comparison is not confounded by headroom. Write `y_i = w_i/s` and
`u = a/s = max|y_i| ∈ (½, 1]`.

## Proposition 1 (the dilation identity)

*Let `β = (1 + c)/2` be the midpoint between A's top two positive rungs. Then for
every `y ∉ (β, 1]`,*

    e_A(y) = c · e_B(y/c),

*where `e_X(y) = Q_X(y) − y` and `Q_B` is extended past its top by saturation.*

**Proof.** A nearest-level quantiser's decision boundaries are the midpoints of
its levels, and midpoints commute with the dilation `z ↦ cz`. A's negative levels
are exactly `−cℓ` and its positive levels below `β` are exactly `cℓ`, so on
`y ≤ 0` and on `0 ≤ y ≤ β` the level chosen by A at `y` is `c` times the level
chosen by B at `y/c` — including where `|y| > c`, at which point `|y/c| > 1` and
B saturates at `±1`, giving `Q_A(y) = ∓c`. Subtract `y = c·(y/c)`. ∎

Checked in `verify_clipping_theorem.py` on 124,000 grid points with the block
scale pinned to 1: off the rung interval `(0.875, 1]` the identity holds at
**exactly 4 of 116,251 points to worse than 1e-12**, and those four are
`−0.625, −0.4375, +0.4375, +0.625` — decision-boundary ties, where the harness's
round-toward-zero rule decides and the reference rounds the other way. There is
no interval of disagreement, only isolated ties of measure zero.

> **This is the whole content of the theorem.** A clipping arm is not a new
> codebook. It is *the parent codebook applied to data dilated by 1/c, with all
> of its errors shrunk by c.*

## Proposition 2 (granular and overload, exactly)

*Split a block into `S = {i : y_i < −c}` (saturated) and `R` (the rest). Then*

    D_A − D_B = X − Y,
    X = Σ_S (e_A² − e_B²)   the clipping cost,
    Y = Σ_R (e_B² − e_A²)   the granular gain,

*and the arm is favourable in block squared error **iff X < Y**.*

**Proof.** Definition, plus Proposition 1 to identify the two regimes: on `S`,
`e_A = −c − y` so `|e_A| = |y| − c`, the classical overload term; on `R`,
`e_A = c·e_B(y/c)`, a granular term at a dilated argument. ∎

## Corollary 1 (contracting a float ladder buys nothing)

*Write `h(z)` for B's local step. In the granular regime `e_B(z)² ≈ h(z)²/12`, so
the per-element gain factor is*

    1 − c² · ( h(|y|/c) / h(|y|) )² .

- **uniform ladder** (`h` constant) → gain `1 − c² = 7/16 = 0.4375`, the naive answer;
- **scale-invariant ladder** (`h(z) ∝ z`, the defining property of a float) → the
  step ratio is `1/c` and the gain is **exactly 0**. A logarithmic ladder
  contracted is the same ladder;
- **across a binade** (step doubles) → `1 − 4c² = −5/4`, a **loss**.

E2M1 is uniform below `4/12` (step `1/12`) and float above it (`2/12`, then
`4/12`). Its error power lives mostly in the float region, so the prediction is
`Y/G ≪ 7/16`, with the gain coming disproportionately from below `4/12`.

**Measured, four checkpoints, weights only, nothing fitted:**

| model | `Y/G` measured | closed form from the ladder | share of the gain from the uniform region | share of granular error there |
|---|---:|---:|---:|---:|
| Pythia-160M | 0.0710 | 0.0823 | 59.0 % | 43.3 % |
| SmolLM2-135M | 0.0877 | 0.0991 | 75.9 % | 46.9 % |
| Qwen2.5-0.5B | 0.0886 | 0.1018 | 76.2 % | 47.0 % |
| OPT-125M | 0.1199 | 0.1239 | 79.5 % | 53.0 % |

The naive `7/16` overstates the granular gain by **3.6× to 6.2×**. The closed
form, which uses only the ladder's step function and the measured `|y|`,
reproduces the measurement to 3–16 % relative. And the last two columns are the
sharp form of the prediction: the uniform region carries **43–53 %** of the
granular error but supplies **59–79 %** of the gain, on every checkpoint. The
gain does come disproportionately from where the ladder stops being a float.
**Corollary 1 holds.**

Both limits are checked directly in `verify_clipping_theorem.py`, on synthetic
ladders with no model involved:

* a **uniform** 8-level ladder gives gain `0.438268` against the predicted
  `0.4375` — 0.18 % relative, against a seed-to-seed spread of `1.3e-3`;
* a **geometric** ladder gives gain **exactly `+0.000000`**, to `<1e-12`.

The geometric case is not approximately zero, it is zero — and the one residual
that appears when the sample is allowed below the ladder's smallest rung
(`+4.93e-4` sampling from 0.02 against a smallest rung of `0.03168`) is the gap
`0 → c¹²`, which is the one part of a geometric ladder that is not geometric.
That residual vanishes the moment the sample starts above the rung, which is the
diagnosis rather than a tolerance chosen to pass.

## Corollary 2 (the break-even is β, not c — and T38 gates it)

*A saturated element at scaled magnitude `m ∈ (c, 1]` costs the arm more than the
parent iff `m > β = (1 + c)/2`, provided `β` exceeds the parent's own top
decision boundary `(1 + ℓ₆)/2`.*

**Proof.** The arm reconstructs every such element at `c`, error `m − c`. Split
`(c, 1]` at the parent's top decision boundary `(ℓ₆ + 1)/2`, which is `5/6` for
E2M1. *Above it* the parent reconstructs at 1 with error `1 − m`; both errors are
positive, so `(m − c)² > (1 − m)² ⟺ m > (1 + c)/2 = β`. *Below it* the parent
reconstructs at `ℓ₆` with error `m − ℓ₆`, and the arm is better iff
`m > (c + ℓ₆)/2`, which for E2M1 is `0.7083 < c` — so the arm is better on the
whole of `(c, 5/6]`. The sign therefore changes exactly once on `(c, 1]`, at `β`,
provided `β > (ℓ₆ + 1)/2`. For E2M1, `0.875 > 0.8333`. ∎

Two consequences, both exact:

1. **Saturation is mostly a benefit.** Elements in `(c, β)` are reconstructed
   *better* by the arm than by the parent — the arm's rung at `c = 0.75` sits
   closer to them than the parent's nearest rung at `2/3` or `1`. Only elements
   in `(β, 1]` pay.
2. **T38's headroom phase gates the cost.** A block can hold an element above `β`
   only if `u = a/s > β`. Under T38 Proposition 3's log-uniform phase,
   `P(u > β) = −log₂ β = 0.1926`.

**Measured:**

| model | `X` above β | `X` below β | net `X` | blocks with `u > β` | log-uniform predicts |
|---|---:|---:|---:|---:|---:|
| Pythia-160M | +95.94 | −101.45 | **−5.50** | 0.2000 | 0.1926 |
| SmolLM2-135M | +3394.36 | −3178.59 | **+215.77** | 0.2219 | 0.1926 |
| Qwen2.5-0.5B | +112.41 | −113.41 | **−1.00** | 0.1715 | 0.1926 |
| OPT-125M | +72.77 | −75.79 | **−3.02** | 0.1715 | 0.1926 |

The clipping cost is a near-cancellation of two large opposed sums, which is why
the "penalty" is numerically negligible — and on three of four checkpoints
**negative**, i.e. saturating the negative tail *reduces* squared weight error on
net. The phase-gate numbers bracket the log-uniform prediction in exactly the
pattern `GRID_OPTIMALITY_THEOREM`'s 2026-08-12 measurement found: right on
average across models, wrong for each one.

## Corollary 3 — the clipped tail is not exotic. It is the OCP MX rule, exactly

This does not come from Proposition 1 — it is arithmetic on the two scale rules —
but it is the most useful thing in the document, and it was found only because
Proposition 1 forced the arm to be written as a contraction of its parent.

Two scale rules are in play (T38). This harness uses **rule A**, aligning the
codebook top to the block max, `s = 2^⌈log₂ a⌉`, which never saturates. The OCP
MX specification uses its own, `s_OCP = 2^(⌊log₂ a⌋ − 2)`, aligning a power of
two to E2M1's `e_max`, which **does** saturate. For `a` not an exact power of
two, `s = 8·s_OCP` — and 8 is exactly the factor between `MX-asym-TOP`'s negative
ladder and E2M1's, because TOP's rungs in E2M1 units are `0.5 … 6` positive
**plus 8**, and its negative ladder stops at 6 while the scale reaches 8.

*Therefore the negative half of `MX-asym-TOP` is bit-identical to MXFP4 under the
OCP MX specification's own scale rule, and its positive half is rule A plus one
rung.*

**🛑 The "bit-exact" measurement was made on synthetic data where its own stated
exception cannot occur.** The 512,033 negative elements were `torch.randn(4000,
256)` in float32, on which a block max that is an exact power of two has
probability about `2⁻²³` — so "no block of 32,000 hit the exception" is a
property of the generator, not evidence about the rule. On the real checkpoints
the exception is common, because bf16 weights land on exact powers of two far
more often than a continuous Gaussian does:

| model | blocks whose max is an exact power of two | negative elements affected | max deviation |
|---|---:|---:|---:|
| SmolLM2-135M | 29,746 / 3,317,760 — **0.897 %** | 137,137 | 0.50 |
| Qwen2.5-0.5B | 86,738 / 11,182,080 — 0.776 % | 409,121 | 0.25 |
| OPT-125M | 4,382 / 2,654,208 — 0.165 % | 20,804 | 0.25 |
| Pythia-160M | 2,990 / 2,654,208 — 0.113 % | 13,483 | 0.25 |

So the corollary is: **TOP's negative half equals OCP-rule MXFP4 on every block
whose max is not an exact power of two, and differs on every block whose max
is** — between one block in a thousand and one in a hundred, depending on the
checkpoint. "Bit-identical" without that qualifier is withdrawn, and so is the
claim that anything measured here about the OCP rule transfers directly.

On positives the two differ by up to 1.000, as designed.

So the "clipping arm" is not a novel object at all: **it is the OCP
specification's own MXFP4 applied to one tail, and this repository's rule applied
to the other.** `MXFP4_SCALE_CONVENTION_2026-08-11.md` already measured the OCP
rule on *both* tails of SmolLM2 — **23.5380 against rule A's 21.9397, +7.29 %** —
and TOP, which pays that rule on one tail while gaining a rung on the other,
costs `+4.68 %` on the same model. Same sign, smaller magnitude, as one tail
against two. That is a consistency check, not a derivation, and is not offered as
one.

## Theorem T41

*A one-sided clipping arm with contraction `c`, applied under a block scale
normalised to the **unclipped** tail, is exactly the parent book applied to data
dilated by `1/c` with its errors shrunk by `c`. Consequently its effect on block
squared error decomposes, with no approximation, as `ΔD = X − Y`, where*

* *`Y` is a **granularity gain** worth `1 − c²·(h(|y|/c)/h(|y|))²` per in-range
  element — `1 − c²` on a uniform ladder, and **exactly zero** wherever the
  parent ladder is scale-invariant;*
* *`X` is an **overload cost** borne only by clipped-tail elements above
  `β = (1 + c)/2`, and gated by the E8M0 headroom phase, since a block can hold
  such an element only when `u = a/s > β`;*

*and the arm is favourable in squared error iff `X < Y`.*

The three quantities `c`, `β` and `h` are read off the codebook. Nothing in the
statement is fitted, and the two per-model inputs — the `|y|` histogram and the
phase — are measured, not assumed.

---

## The prediction, and it is refuted

**T41's own crossover is `X < Y`.** Aggregated over a checkpoint that is
`ΔD = D_A − D_B`, and its scale-free form is `ΔD / D_B`. This is the theorem's
prediction, fixed before the perplexities were looked at, with no free parameter
and no fitting: *lower `ΔD/D_B` ⇒ the arm should do better.*

| model | `X` clipping cost | `Y` granular gain | `ΔD = X − Y` | `ΔD / D_B` | T41 says | measured Δppl |
|---|---:|---:|---:|---:|---|---:|
| Pythia-160M | −5.50 | +120.56 | −126.07 | −6.80 % | favourable | **−8.27 %** ✓ |
| Qwen2.5-0.5B | −1.00 | +171.67 | −172.67 | −8.17 % | favourable | −1.15 % ✓ |
| OPT-125M | −3.02 | +182.44 | −185.46 | −11.32 % | favourable | +2.33 % ✗ |
| SmolLM2-135M | +215.77 | +4429.56 | −4213.79 | −7.60 % | favourable | **+4.68 %** ✗ |

**Every one of the four has `X < Y`.** T41 therefore predicts the clipping arm is
favourable on **all four models**. It is favourable on **two**. The rank
correlation against the measured order is **ρ = −0.400** (exact two-sided
permutation p = 0.750), and the sign is wrong on two of four.

The measured effects are not noise. Re-measured in this session's own process,
with the rulers reproduced first and every per-window NLL identical to campaign
B's stored values at `0.00e+00`:

| model | ppl MXFP4 | ppl TOP | Δ | 95 % CI (windows) | t | windows won |
|---|---:|---:|---:|---:|---:|---:|
| Pythia-160M | 47.6504 | 43.7086 | **−8.27 %** | [−9.82, −6.70] | −10.27 | 38/40 |
| Qwen2.5-0.5B | 15.4374 | 15.2594 | −1.15 % | [−1.96, −0.34] | −2.97 | 14/20 |
| OPT-125M | 30.7871 | 31.5037 | +2.33 % | [+1.64, +3.03] | +6.85 | 5/40 |
| SmolLM2-135M | 21.9397 | 22.9662 | **+4.68 %** | [+1.33, +8.13] | +2.85 | 15/40 |

Every interval excludes zero, in both directions. The 13-point spread the
predictor has to explain is real; it is the predictor that is not. (Those CIs are
window-level and therefore **within-model only** — windows replicate the text,
not the model family, so they say each effect is real and say nothing about the
cross-model comparison, which is the n = 4 test above.)

**T41's prediction fails.** Not marginally, and not because of noise: the arm
lowers squared weight error by 6.8–11.3 % on every checkpoint while raising
perplexity on two of them.

> **One post-hoc observation, flagged as post-hoc.** Of the two halves of
> `ΔD`, the clipping half **alone** — `X/G`, without the granular gain — ranks
> the models at ρ = **+0.800** (`−0.00324`, `−0.00052`, `−0.00199`, `+0.00427`
> for Pythia, Qwen, OPT, SmolLM2), missing only the Qwen/OPT adjacent pair. That
> was found by inspecting the components *after* the primary predictor failed, it
> is one of **eleven** quantities examined, its exact permutation p is 0.167
> one-sided (0.333 two-sided) before any multiplicity correction, and at n = 4
> nothing below a perfect order can reach 0.05. It is
> recorded as a hypothesis for a larger model set, **not** as a result, and it is
> not what T41 predicts — T41 predicts `X − Y`, and `Y` is the term that spoils
> it.

## Which assumption breaks

Not Proposition 1 — verified exactly off its own stated exception. Not
Proposition 2 — an identity. Not Corollary 1, whose two limits come out at
`0.18 %` and `0.000000`. Not Corollary 2, whose break-even is located at `0.875000`
by brute force. Not Corollary 3, whose "bit-exact" evidence was synthetic and is
now stated with its measured 0.1–0.9 % exception rate on real checkpoints. Every
mathematical claim in the derivation survives.

What breaks is the step from the theorem to the test: **the identification of
summed squared weight error with model quality.** That is the wall
`METRIC_DISAGREEMENT_2026-08-11.md` hit — one intervention, four instruments,
three wrong by sign, a 46 % improvement in logit L2 alongside an 8 % perplexity
degradation — and the wall `PLACEMENT_AND_ASYMMETRY_2026-08-12.md` hit when the
greedy `ΔSSE` criterion came out anti-correlated in real weight space, and the
wall `campaignD`'s P2 hit when it went `+0.400 → −0.200` on removal of the
clipping arm. T41 is a correct statement about `D`, and `D` is not the objective.

And Proposition 1 says *why*, which is more than "MSE disagrees". Squared error
is blind to the **sign** of an error. The arm's error is not sign-blind:

* every saturated element is pulled **toward zero** — a one-sided shrinkage;
* the contraction `c` moves every reconstruction toward zero as well.

For a linear layer with input mean `μ` and variance `v` per feature, the expected
squared output error of a row is **exactly**

    E[(Σⱼ dwⱼ xⱼ)²]  =  (Σⱼ dwⱼ μⱼ)²  +  Σⱼ dwⱼ² vⱼ
                          coherent          incoherent

Squared weight error is the second term with `v ≡ 1`. The first term is invisible
to it. Measuring the row-sum coherence `κ = Σ_r (Σⱼ dw_rⱼ)² / Σ dw²` — `κ ≈ 1`
for incoherent error, `≈ n_in` for perfectly coherent:

| model | `κ` MXFP4 | `κ` TOP | coherent channel, A/B | incoherent channel `Σdw²`, A/B |
|---|---:|---:|---:|---:|
| Pythia-160M | 0.993 | 1.647 | **×1.546** | **×0.932** |
| SmolLM2-135M | 0.998 | 1.568 | **×1.451** | **×0.924** |
| Qwen2.5-0.5B | 0.999 | 1.766 | **×1.624** | **×0.918** |
| OPT-125M | 1.092 | 1.671 | **×1.358** | **×0.887** |

MXFP4's error is incoherent to within 9 % on every checkpoint — `κ ≈ 1` — exactly
as a symmetric quantiser's should be. The clipping arm's is **1.57 to 1.77×
coherent**. On all four checkpoints the arm **lowers the incoherent channel and
raises the coherent one.**

**So the two channels move in opposite directions on every model, and the weight
that decides between them — `μ²` against `v` — is a property of the
activations, not of the weights.** No statistic computed from weights alone can
settle the sign, which is why T41's crossover cannot and does not predict the
order. That is a structural limitation of the derivation, not a missing constant.

## Closing the gate with the quantity the derivation names

The activation moments are measurable, and measuring them is not fitting: there
is no free parameter, only the term `D` omits. Per-feature `μ` and `v` were taken
from the unquantised model on one 2048-token calibration window and the exact
row expression above evaluated.

| model | coherent `(Σ dw μ)²` | incoherent `Σ dw² v` | **gated total** | measured Δppl |
|---|---:|---:|---:|---:|
| Pythia-160M | ×1.541 | ×1.113 | **×1.293** | **−8.27 %** |
| Qwen2.5-0.5B | ×0.981 | ×0.930 | **×0.947** | −1.15 % |
| OPT-125M | ×1.066 | ×1.047 | **×1.051** | +2.33 % |
| SmolLM2-135M | ×0.921 | ×0.697 | **×0.756** | **+4.68 %** |

**It fails too, and it fails by inverting.** ρ = **−0.800** (exact two-sided
permutation p = 0.333 over all 24 orderings — not significant, and n = 4 could
not have made it so). The gate ranks Qwen and OPT correctly and puts the two
extremes exactly the wrong way round: the arm's *largest* predicted output-error
increase, Pythia at ×1.29, is its *largest* perplexity win, and its largest
predicted improvement, SmolLM2 at ×0.76, is its largest loss.

Splitting the gate does not rescue it: its coherent channel alone and its
incoherent channel alone **both** give ρ = −0.800 as well, so the inversion is
not an artefact of how the two were combined.

Three error proxies of increasing sophistication — summed squared weight error,
row-coherence, activation-gated layer output error — give ρ = −0.400, −0.600 and
−0.800. **They do not merely fail to predict; they get monotonically worse the
more carefully the output error is modelled.** At n = 4 none of those
coefficients is significant, and none is claimed as a finding; what is claimed is
that the derivation's own crossover was tested three ways and survived none.

> `PLACEMENT_AND_ASYMMETRY_2026-08-12.md` also reports **ρ = −0.800**, for the
> greedy `ΔSSE` criterion in real weight space. **That is a different axis** —
> ranking *books within* a model, n = 5 — and this one ranks *models* for a fixed
> book, n = 4. Spearman on four or five points takes only a handful of discrete
> values, so the numerical agreement is arithmetic, not corroboration, and it is
> recorded here so that a later reader does not mistake it for a replication.

## The leave-one-out rotation, in full

Nothing here was chosen on the data, but the rule in this campaign is that the
rotation is reported whole rather than at its best rotation, so here it is. At
n = 3 a Spearman is `±1` or `±0.5` by construction, so only the **sign pattern**
is readable — the magnitudes carry no information.

| predictor | drop Pythia | drop Qwen | drop OPT | drop SmolLM2 |
|---|---:|---:|---:|---:|
| **T41 primary, `ΔD/D_B`** | +0.50 | −0.50 | −0.50 | **−1.00** |
| `Y/G` alone | +0.50 | −0.50 | −0.50 | −1.00 |
| mean negative-tail ratio per block | +0.50 | −0.50 | −0.50 | −1.00 |
| fraction of blocks saturating | +0.50 | +0.50 | +0.50 | −1.00 |
| saturated elements per block | +1.00 | +0.50 | +0.50 | −0.50 |
| coherence ratio | −0.50 | −0.50 | −0.50 | −0.50 |
| `κ_TOP` | −1.00 | −0.50 | −0.50 | +0.50 |
| **activation-gated total** | −0.50 | **−1.00** | **−1.00** | −0.50 |
| its coherent channel alone | −0.50 | −1.00 | −1.00 | −0.50 |
| its incoherent channel alone | −0.50 | −1.00 | −1.00 | −0.50 |
| *`X/G` (post-hoc)* | *+0.50* | *+1.00* | *+1.00* | *+0.50* |

The primary predictor changes sign across rotations — it is not merely weak, it
is unstable. The activation gate is negative in all four, which is the sharpest
statement available: **it is consistently, not accidentally, backwards.** The
post-hoc `X/G` is positive in all four, which is why it is worth a larger model
set and why it is still not a result at n = 4.

## What this does and does not license

**Does.** Proposition 1 is exact and is the useful object: any clipping arm
reduces to its parent on dilated data, so a clipping choice never needs its own
codebook analysis. Corollary 1 is a design rule with teeth — **contracting a
float ladder to buy granularity is close to self-defeating**, because a
logarithmic ladder is nearly scale-invariant; the naive `1 − c²` overstates the
gain by up to 6× here, and the gain that survives comes almost entirely from the
ladder's uniform low end. Corollary 2 says where a clipping arm's cost actually
sits — above `β = (1+c)/2`, gated by T38's headroom phase — and that below `β`
saturation is a *benefit*, which is why the measured net clipping cost is
approximately zero and sometimes negative. Corollary 3 is the one to keep: it
identifies the arm's clipped tail with the OCP MX specification's own rule
bit-for-bit, which means anything this repository ever measures about that rule
transfers directly, and it removes "clipping arm" as a separate category of
object.

**Does not.** It does not predict which model the clipping arm helps; that
prediction was made, tested, and failed, and the failure is reported above rather
than repaired. It does not license any claim that `MX-asym-TOP` is a good arm —
it is not a placement and it is not in `candidates()`. It says nothing about
symmetric clipping, where UOS ([arXiv:2607.24377](https://arxiv.org/abs/2607.24377))
already has a derived answer for E2M1, and nothing about activations beyond the
first-order proxy used above.

**The open question, stated precisely.** By Corollary 3 the arm's negative tail
sits at `Qmax = 8` — the OCP MX rule's own upper boundary — while UOS derives
`7.25` as optimal. The arm is therefore **over-clipped on the negative tail by
construction**, and it is over-clipped by exactly the amount UOS says the OCP
specification itself is. Its positive tail is not clipped at all. Whether a
one-sided arm at the UOS boundary behaves differently is falsifiable and
unanswered here: it needs its own codebook and its own four perplexity runs, and
`c = 6/7.25 = 0.8276` is not a 16-codeword integer book, so it is not a drop-in
member of this family.

---

*Four models (SmolLM2-135M, Qwen2.5-0.5B, Pythia-160M, OPT-125M), wikitext-2,
block 32, E8M0, `lm_head` excluded. Rulers reproduced in this session's own
process before any number here was quoted, per-window NLL identical to campaign
B's stored values at `0.00e+00`; the signed quantiser was re-proved bit-exact
against `block_tnf.quant` in-process at `0.000e+00`. Weight statistics are exact
sums over every quantised element — no sampling. Cross-model claims are
model-level with n = 4 and exact permutation p-values over all 24 orderings;
`verify_clipping_theorem.py` checks Proposition 1 against the quantiser the
project actually runs, both of Corollary 1's limits on synthetic ladders,
Corollary 2's break-even located by brute force rather than assumed, and
Corollary 3 against an independently written OCP-rule quantiser — all four pass;
at n = 4 even a perfect order is p = 0.0417, so this design can refute a
predictor and cannot confirm one. External claims are from the linked abstracts
and, where stated, full texts read 2026-08-12; ACIQ's numerical clipping
constants are deliberately not quoted because two sources disagreed on their
normalisation and the full derivation was not re-checked.*
