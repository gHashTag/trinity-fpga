# Withdrawal 15: subtracting a harness that is not the same size in every build

The trend theorem said the LNS number was still descending and that the remaining
confounds probably pushed the same way. Applied to our own result, it found a
third harness defect in as many iterations, and the number fell again.

## The defect

Replacing the single shared LFSR with four independent ones -- to remove the
correlation between overlapping input slices -- produced this:

| design | LUT | apparent net of a 176-LUT harness |
|---|---:|---:|
| harness (4 LFSRs) | 176 | — |
| `apot_requant` | 191 | **15** |

Fifteen LUTs for two priority encoders and a subtractor is impossible.
`apot_requant` consumes only `r0`, so `r1`, `r2` and `r3` have no path to an
output and synthesis removes them. **The harness in that build is one LFSR, not
four**, and the subtraction was against a harness that build never contained.

**T (harness subtraction requires harness invariance).** Net-of-harness figures
are valid only if the harness is present in full in every build. A design
consuming fewer harness outputs prunes the rest, so the subtrahend varies with
the design and the difference is not a measurement of anything.

**Fix.** Force every source live in every build by folding the unused ones into
the observed reduction: `tot = acc ^ (r0 ^ r1 ^ r2 ^ r3)`. The harness is then
identical everywhere and subtraction means what it says.

## Re-measured with the harness invariant

Harness: 169 LUT, 768.64 MHz.

| design | LUT | net | Fmax median | MHz/LUT |
|---|---:|---:|---:|---:|
| `zphi_add` | 335 | **166** | 207.64 | 0.620 |
| `lns32_t4096` | 598 | **429** | 84.10 | 0.141 |
| `phi_step` | 430 | **261** | 193.46 | 0.450 |
| `apot_requant` | 322 | **153** | 88.89 | 0.276 |

`zphi_add` against `lns32`: **2.58x on area, 2.47x on frequency, 4.4x on
throughput per area.**

`phi_step` against `apot_requant`: APoT **1.71x smaller**, `phi_step` **2.18x
faster**, 1.63x on throughput per area.

## The trend, updated

| instrument | LNS advantage |
|---|---:|
| synthesis area only | 8.6x |
| post-route, 4-bit observation | 14x |
| post-route, 16-bit observation | 11.5x |
| post-route, 32-bit observation | 5.5x |
| post-route, full observation, harness invariant | **4.4x** |

Four corrections, four moves in the same direction, decelerating: −18%, −52%,
−20%. The theorem's warning holds and the quantity is still not converged.

What has survived every correction is the **sign**: `Z[phi]` addition is cheaper
than an LNS adder on every instrument tried. What has not survived is any
particular figure. The result should be stated as a direction with a current
upper bound, not as a ratio.

**T (a claim's sign can converge while its magnitude does not).** Successive
instrument corrections may leave an ordering intact while halving the gap. An
ordering established across several instruments is stronger evidence than a
magnitude measured once on the best of them, and the two should be reported
separately.

## Count

Fifteen. Three consecutive iterations found harness defects: a shared component
on the critical path, an unequal observation window, and a non-invariant
subtrahend. None was visible in any individual number.
