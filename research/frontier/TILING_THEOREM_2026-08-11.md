# A ternary exponent never tiles a binary field — and we were standing on the worst rungs

Last iteration ended on a dilemma: rung A's offset field holds 128 values and its
four trits name 81, so either 37% of the word lies outside the format and must be
guarded (costing 15.1% and the IEEE comparison), or the exponent is not really
ternary. **The dilemma had a structural cause, and naming it dissolved the case
rather than choosing a side.**

## Theorem (no exact tiling)

For $k,m\geq1$, $3^k \neq 2^m$ — unique factorisation. So every rung's offset
field of width $\lceil k\log_2 3\rceil$ has capacity strictly greater than the
$3^k$ offsets it holds, and

$$w(k) = 1 - \frac{3^k}{2^{\lceil k\log_2 3\rceil}} = 1 - 2^{-(1-\{k\log_2 3\})} > 0$$

**at every rung, always.** The waste is not a defect of a particular design; it
is a property of putting a power of three inside a power of two.

## Corollary: the waste is wildly uneven, and we picked badly

| $E_t$ | waste | built here |
|---|---|---|
| 3 | 15.6% | TNF8 |
| **4** | **36.7%** | TNF16, TNF16a |
| **5** | **5.1%** | ← **never built until now** |
| 6 | 28.8% | TNF32 |
| **7** | **46.6%** | TNF64 — the worst in range |

The ladder had taken $E_t \in \{3,4,6,7\}$ — three of them poor — and had never
taken $E_t=5$, the best in the range **by a factor of three**.

## The rung we had skipped

$E_t=5$ needs 8 offset bits, so $1+8+7=16$: a third 16-bit candidate, never
considered. Built, checked exhaustively: **62,208 of 62,208 in-spec codes exact,
all 3,328 out-of-spec flagged, zero errors.**

| | LUT | MHz | MHz/LUT | vs `binary16` |
|---|---|---|---|---|
| rung A, unguarded | 502 | 69.87 | 0.1392 | +14.7% |
| rung A, reserved | 549 | 64.86 | 0.1181 | −2.6% |
| rung C, unguarded | 509 | 66.11 | 0.1299 | +7.1% |
| **rung C, reserved** | **527** | **67.20** | **0.1275** | **+5.1%** |

**Rung A's guard costs 15.1% and takes the format below IEEE half. Rung C's
costs 1.8% and leaves it above.**

## The claim that survives

**At equal storage, with every code either defined or flagged, +5.1% against
IEEE half.** Smaller than the 14.7% first reported — and unlike it, not resting
on an unchecked field.

Against the research formats at 16 bits, rung C guarded: `takum16` +70.7%,
`LNS16` +95.0%, `posit16` +131.4%.

## What this says about the rest of the ladder

Every existing rung sits at a $k$ we did not choose for this reason. $E_t=7$
(TNF64) wastes 46.6% of its offset field; $E_t=6$ (TNF32) wastes 28.8%. **The
ladder should be rebuilt on the $k$ where $w(k)$ is least — 3, 5, 8, 10, 15 —
and each of those rungs' guards will be correspondingly cheap.** That is the
next measurement, not a claim.
