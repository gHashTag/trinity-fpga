# T40 — the whole of NF4's margin is one codeword, not the shape of its curve

Yesterday NF4 beat MXFP4 in this harness by 6.50 % and the conclusion drawn was
that a Gaussian-quantile codebook from 2023 outclasses a hand-designed float.
That conclusion was wrong about *why*, and the correction is a cleaner result
than the observation it replaces.

## The arithmetic nobody had done

Every arm here costs **4.250 bits per element**: a 4-bit element index — sixteen
codewords — plus an E8M0 shared scale, 8 bits over a 32-element block.

But a **symmetric** codebook of 8 magnitudes with a sign bit represents
`+0` and `−0` with two different codewords, and they denote the same number. One
of the sixteen is wasted. Such a book has **15 distinct representable values**.

An **asymmetric** codebook — 8 positive magnitudes, 7 negative, one zero — spends
all sixteen.

| codebook | construction | distinct values |
|---|---|---:|
| MXFP4, Lloyd-Max, KL-opt, nSSE, JOINT-KL, **NF4-sym** | 8 magnitudes + sign | **15** |
| **NF4**, BOF4 | 8 positive, 7 negative, zero | **16** |

Like for like in bits. Not like for like in levels. Every comparison in this
repository, and the one published this morning, put a 15-value book against a
16-value book and attributed the difference to the curve.

## The decomposition, and it is exact

`bitsandbytes` ships the switch itself: `create_normal_map(use_extra_value=False)`
gives **NF4-sym**, the identical Gaussian-quantile construction with the extra
codeword turned off.

| comparison | pooled, four models | verdict |
|---|---|---|
| **NF4-sym vs MXFP4** | **+0.33 % [−0.55, +1.23], t = +0.75, p = 0.46** | **TIE** |
| NF4 vs NF4-sym | −4.43 % [−5.22, −3.63], t = −10.81, p = 3.8e-20, 121/140 windows | NF4 wins |
| NF4 vs MXFP4 | −4.11 % [−4.98, −3.23], t = −9.06 | NF4 wins |

And the two factors compose exactly:

    (+0.335 %) × (−4.429 %) = −4.109 %      residual 0.00e+00

(means of log ratios over the same windows, so the product is an identity rather
than an approximation).

**T40.** *At a fixed 4-bit index, the normal-quantile shape is worth nothing
measurable against E2M1 — the entire NF4 advantage is the codeword that a
symmetric book spends on a second zero.*

**The qualifier that keeps it honest:** sixteen levels is necessary, not
sufficient. BOF4 also has sixteen and still loses to MXFP4 by +1.50 % out of
sample. Spending the codeword is what makes an improvement *possible*; it does
not deliver one.

## What this costs yesterday's headline

**NF4's −6.50 % was pooled over three families.** OPT-125M had never been run. On
OPT, **NF4 loses to MXFP4 by +2.14 %** (t = +8.23, p = 4.7e-10, better in 5 of 40
windows). Over all four families NF4 is −4.11 %, not −6.50 %. The −6.50 % figure
reproduces digit for digit when the same three families are pooled, so nothing
was miscomputed — the sample was simply smaller than the claim.

**Two more pooling corrections, the same class of error as the one fixed the day
before**, both surfaced by that third unseen family:

- BOF4 was recorded as "indistinguishable from MXFP4" (+0.81 %, p = 0.235, over
  Qwen + Pythia). Over all three unseen families it **loses**: +1.50 %
  [+0.64, +2.36], p = 0.0008. The tie does not survive.
- Lloyd-Max was +8.80 % over two unseen families; over three it is +6.60 %.

## Where our own work stands, restated against both references

`JOINT-KL` — the codebook fitted against three models at once — is the only arm
of eight that beats **both** references out of sample: −1.31 % against MXFP4 and
−3.38 % against NF4 (CI [−4.08, −2.68], t = −9.60, p = 8.1e-12, 39 of 40 windows,
Bonferroni-corrected p = 5.7e-11 over the seven arms tested).

**But it beats NF4 on exactly one family — OPT — and that is the one family where
NF4 itself fails.** On the three families JOINT-KL was fitted against, NF4 beats
it on two and ties on the third. The honest sentence is not "we beat NF4"; it is
"NF4 is not uniform across model families, and our codebook happens to hold up on
the family where NF4 does not".

Everything else fitted here — KL-opt, nSSE-equal — loses to both references, and
so does the strongest published learned codebook we could implement.

## The design consequence, which is the useful part

A symmetric magnitude table with a sign bit is the natural way to build a
quantiser and it silently forfeits 1/16 of the code space. Nothing in the
comparison literature this repository has read — NF4's own paper included —
states the effect size of that forfeit. Measured here it is **4.43 %** of
perplexity at four bits, larger than any codebook-shape effect measured in this
line all week.

The cheapest available improvement to any symmetric 4-bit quantiser is therefore
not a better curve. It is to stop paying for a second zero.

---

*Four models (SmolLM2-135M, Qwen2.5-0.5B, Pythia-160M, OPT-125M), wikitext-2,
block 32, E8M0, `lm_head` excluded, published window counts. All codebooks
normalised to top = 1.0 so every arm sits at headroom phase φ = 0 (T38). Paired
per-window NLL throughout; pooled out-of-sample rows include only models an arm
never saw. Rulers reproduced before any new number was quoted.*
