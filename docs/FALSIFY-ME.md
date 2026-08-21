# Falsify this in one run

Every number this project now claims about the φ-lattice at six bits came from one
machine, one operator and one set of hands. This page exists so that someone else
can refute it cheaply. Each claim below states the experiment, the expected
outcome, and **what result would kill it**.

Everything referenced is committed: rigs in `research/arxiv_tnf/*.py`, records in
`research/arxiv_tnf/measurements/*.json`, and `verify_numbers.py` recomputes every
headline figure from those records (**27 checks**, including the stability tallies
below, which are derived here rather than quoted).

**To run any of it on your machine**, nothing needs to match ours:

```bash
python3 research/arxiv_tnf/verify_numbers.py          # records found beside the script
T27_WORK=/path/with/datasets \
T27_CONFORMANCE=$PWD/conformance \
TASK=mnist EPOCHS=30 python3 research/arxiv_tnf/stability.py
```

`T27_RECORDS` overrides where `verify_numbers.py` looks; `T27_WORK` is where
`stability.py` finds the idx-format datasets and writes its record;
`T27_CONFORMANCE` points at the shipped oracles. Until W948d these rigs carried
the author's absolute paths, which made this page's own invitation impossible to
accept.

---

## Claim 1 — recipe-insensitivity

> At six physical bits, TNF4 trains successfully in **40 of 40** runs — eight
> configurations of five seeds, spanning four quantiser recipes, three tasks and
> three training lengths. `fp6 e3m2` manages **16 of 40** and `fp6 e2m3` **12 of 40**.

*All counts on this page are **successes out of runs**. The same tallies appear as
failure counts elsewhere in this repository (28/40 and 24/40); they are the same
measurement in the opposite polarity, and mixing the two is how an off-by-one
entered three published documents in W948. `verify_numbers.py` now recomputes
these tallies from the records, in one polarity, so the arithmetic cannot drift
from the evidence again.*

**Run it:** `research/arxiv_tnf/stability.py`, environment
`TASK ∈ {mnist, fashion, kmnist}`, `EPOCHS ∈ {3, 10, 30}`, `INIT_PCT` unset (max
scale) or `0.999` (percentile), five seeds `20260820, 7, 1337, 424242, 99991`, MLP
784-256-256-10, weights **and** activations quantised, LSQ with the gradient factor.

**Failure counted as** final test accuracy below 60 % (MNIST, Fashion) or 40 %
(KMNIST) — the runs that fail land near chance, so the threshold is not delicate.

> **W950 — THIS CLAIM HAS NOW BEEN KILLED BY ITS OWN TEST.** Replace the learned
> scale with the one the OCP microscaling formats specify — a **computed
> power-of-two** shared scale, never learned — and **all three formats train in
> 5/5 runs, at block 32 and at per-tensor granularity alike**. `fp6 e2m3` goes from
> **28/40 failures to 0/5** with the granularity unchanged. The letter of the claim
> survives (TNF4 has failed nothing, ever); its meaning does not, because the float
> is not fragile under the recipe the field actually deploys — and paired over five
> seeds at per-tensor granularity TNF4 is **worse** by −0.376 pp (t = −7.24, 0/5
> seeds favour it). See `blockquant.py`, `blockquant_w950.json`.

**This claim dies if:** any recipe you choose brings either fp6 grid to ≤ 2 failures
in 20 across the same three tasks, **or** TNF4 fails at all under a recipe that is
standard rather than adversarial. A recipe hand-tuned per task does not count; the
claim is about one recipe surviving three tasks.

**Report it as five numbers, not one.** A threshold count and a mean each hide a
different thing, and at 30 epochs they hide the most important thing here: by the
60 % rule `fp6 e3m2` *passes* three of five runs (71.9, 65.6, 55.5, 71.4, 59.3),
while TNF4's **worst** run is 97.6 — the two sets do not overlap, and the gap
between the competitor's best and our worst is 25.7 pp. Neither the mean nor the
pass rate shows that; the five numbers do.

## Claim 2 — ~~the mechanism is range~~ **WITHDRAWN (W949): we do not know the mechanism**

> ~~Under a max-rule scale the narrow grids zero everything below 1.7 % (e2m3) or
> 0.22 % (e3m2) of the tensor peak, against TNF4's 0.0041 %.~~

Those three thresholds are `min(grid)/max(grid)` — they assume the tensor peak is
mapped onto the format's **largest representable value**. **Every training run in
this project instead mapped the peak onto grid value 1.0**, and the grids peak at
3072 (TNF4), 28 (`fp6 e3m2`) and 7.5 (`fp6 e2m3`). Under the convention actually
used the thresholds are **12.50 %, 6.25 % and 12.50 %**: TNF4 zeroed **twice as
much** as the competitor it beat, and held **7** usable levels against that
competitor's **12** — and won 40/40 regardless.

**So the explanation is inverted by its own experiment and is withdrawn.** The
grid spans (14.6 / 8.8 / 5.9 binades) are correct and reproducible in ten lines
(`tri grid`). What is not established is that they are why TNF4 trains.

**What replaces it:** nothing yet. That is the honest state, and the first thing an
outside replication should attack.

**This claim is already dead**; what would revive a range-based explanation is a
demonstration that the failing runs underflow *under the convention they ran in* —
`stability_*.json` logs the per-epoch scales, and in every failure the layer-2
activation scale falls monotonically (0.81 → 0.29 → 0.0065), which is consistent
with underflow but does not by itself identify the cause.

## Claim 2a — the scaling convention decides the competitor, not us

> Changing only the scale initialisation — `s = max|x|` → `s = max|x|/max(grid)` —
> moves `fp6 e3m2` from **0/5 failures to 5/5** on MNIST. TNF4 moves **0.10 pp** and
> fails nothing.

**Run it:** `research/arxiv_tnf/scaleconv.py`, five seeds, three epochs. The
`peak2one` arm must reproduce the W946 record (96.70) or the comparison is invalid.

**This claim dies if:** TNF4 fails under any standard scale initialisation, **or**
either fp6 grid is stable under both conventions on the same three tasks.

## Claim 2b — and the advantage may not survive block scaling at all

> At the OCP microscaling block size (**32**), on heavy-tailed activations: TNF4
> zeroes **0.01 %** of values against `fp6 e2m3`'s 2.51 % — but TNF4's relative RMS
> error is **3.46× worse**, and is the worst of the three six-bit grids at *every*
> block size. The advantage is confined to **per-tensor scaling of heavy-tailed
> data**, where `fp6 e2m3` zeroes 44 % and collapses.

**Run it:** `research/arxiv_tnf/blockscale.py`. No training, no datasets.

**MEASURED, W950 — and it was not the block size.** `fp6 e2m3` at block 32 trains
0/5 failures — but so does it **per-tensor**, under the same computed power-of-two
scale. The block granularity explains nothing; the **learned scale** was the whole
effect. The mechanism agrees: failures are saturation driven by a collapsing learned
scale (T799), and a computed scale cannot collapse.

**What remains true of range:** TNF4's underflow is negligible at every block size,
and `fp6 e2m3` still zeroes 44 % of heavy-tailed values under a per-tensor max rule.
**What is refuted:** that this ever mattered to whether a network trains.

## Claim 3 — parity on cost

> At six physical bits: TNF4 **51.29** consumer cells, `fp6 e2m3` and `fp6 e3m2`
> **50.29** — TNF4 is **2 % dearer**, not cheaper.

**Run it:** `research/arxiv_tnf/oracle_rtl.py` (truth-table decoders generated from
each format's own oracle) or `structural.py` (structural decoders verified against
the oracle over every code), then synthesise with `yosys`, `synth_xilinx -nodsp`,
counting LUT1–6 + CARRY4, fitting `cells(N) = fixture + cost·N` over N = 1,2,4.

**This claim dies if:** a fair implementation of either format changes the ordering
by more than the ±8 % method band we measured between truth-table and structural
decoders — for instance a hand-optimised TNF decoder that lands below 50.29 while
the floats are built the same way.

## Claim 4 — parity on accuracy

> When both train, TNF4 − `fp6 e3m2` is **+0.11 pp** (MNIST, t 2.2) and **+0.17 pp**
> (Fashion, t 1.2 — **not significant**), and **−0.42 pp** with quantised
> activations on Fashion.

**Run it:** `research/arxiv_tnf/lsq_width_matched.py`, five seeds, paired.

**This claim dies if:** a paired test over five or more seeds shows |difference| >
0.5 pp in either direction at matched width and matched recipe.

## Claim 5 — the eight-bit null

> At 8 and 16 bits no format difference reaches the task: five 8-bit formats within
> **0.06 pp** with weights *and* activations quantised, across MLP and CNN, two
> tasks, two network sizes, five seeds.

**Run it:** `accuracy_seeds.py`, `activations.py`, `conv.py`.

**This claim dies if:** any 8-bit format shows a drop exceeding the binomial
standard error of the test set (0.16–0.25 pp here) reproducibly across seeds.

---

## What this project has already withdrawn about itself

Eight corrections in seven waves, none prompted by an outside reviewer: four
comparisons at unmatched width, a variance read as a mixture when all five runs had
failed, an enumeration missing a sign bit, a frontier priced by module name, and a
quantiser missing the gradient term of the paper it cited. Details in
`REFEREE-PAGE.md` and the ledger.

If your run disagrees with any table here, that disagreement is the most valuable
thing this project can receive. Open an issue with the seeds and the record.

---

*φ² + φ⁻² = 3 | TRINITY*
