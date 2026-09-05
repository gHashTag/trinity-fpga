# Four families, one live network, one metric

SmolLM2-135M on wikitext-2, 40 windows of 2048 tokens, per-tensor scale,
baseline perplexity 14.4874 verified in band before any comparison. The
prediction was printed **before** the perplexities were computed.

| candidate | magnitudes | ppl | vs fp32 |
|---|---:|---:|---:|
| fp32 reference | — | 14.4874 | 1.000x |
| **GF8** E=3 — golden ratio, binary | 129 | **14.6130** | 1.009x |
| GF-T8 E_t=3 — golden ratio, ternary | 109 | 15.5147 | 1.071x |
| BNF8 E=1 — width rule | 129 | 4 574 409 | 315750x |
| BNF8 E=2 | 129 | 288.5224 | 19.9x |
| **BNF8 E=3** | 129 | **14.6130** | 1.009x |
| BNF8 E=4 ← predicted | 129 | 14.6592 | 1.012x |
| BNF8 E=5 | 129 | 15.5147 | 1.071x |
| TNF8 E_t=1 | 97 | 270 015 | 18638x |
| **TNF8 E_t=2** | 73 | **14.7012** | 1.015x |
| TNF8 E_t=3 ← predicted | 109 | 15.5147 | 1.071x |

## The result worth keeping: the two axes coincide

**GF8 E=3 and BNF8 E=3 return 14.6130 — the same number, not a close one.**
The golden-ratio rule `E = round((N-1)/phi^2)` and the width rule
`1 + E + M = N` were derived independently, for unrelated reasons, and at
eight bits on this workload they name the *identical* format: E=3, M=4.

This is not "one axis wins". It is that at this width the two derivations
agree, which is a stronger statement than either alone and one neither
predicted.

## Self-caught defect #12: the range estimator, not the rule

The width rule's prediction was **falsified twice**: it named BNF8 E=4 and
TNF8 E_t=3, and the measured winners were E=3 (14.6130 against 14.6592) and
E_t=2 (14.7012 against 15.5147). Both predictions were one step too wide.

The rule's *form* survives intact and is visible in the sweep: there is a
single optimum, both directions from it hurt, and the penalty is asymmetric
exactly as the regret theorem states. Under-sizing is catastrophic —
BNF8 E=1 gives 4.5 million, E=2 gives 288 — while over-sizing is mild:
E=4 costs 0.3%, E=5 costs 6%.

What was wrong is the **estimator of the visited range**, not the rule that
consumes it. We measured the span from the 0.1st percentile to the maximum,
which credits a tail carrying almost no energy. The correct input is the span
that carries the loss, and the fix is to weight the percentile by energy
rather than by count. Recorded rather than quietly re-tuned: a rule that
names its winner before the measurement can be wrong, and this one was.

## Ternary loses again on binary fabric, for the third independent time

GF-T8 carries **109** magnitudes where GF8 carries **129**, and pays 15.51
against 14.61. TNF8 E_t=2 carries 73. The packing remainder is not a detail
at eight bits.

Three independent measurements now agree: BNF16 vs TNF16 within 1% in
placed silicon; GF8 vs GF-T8 here; MXFP4 vs TNF4 on the block axis. The
ternary exponent earns on positions and pays on bits, and this fabric
charges in bits.
