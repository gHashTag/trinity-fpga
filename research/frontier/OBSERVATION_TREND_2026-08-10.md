# The gate caught my own hour-old work, and the LNS number has halved twice

## The gate finds 83 partial-observation harnesses, including the fix

`tools/check_harness.py` scans harness files for a design output driving a
narrower observed port without a full reduction in between. It reports **83**
across the tree -- and among them the files written one iteration earlier to
*correct* this exact defect. The "full observation" harness of withdrawal 14
folded four nibbles into the LED port: sixteen of thirty-two bits.

A gate that catches the author's own correction an hour after it was written is
doing what a gate is for.

## Re-measured with all thirty-two bits observed

| design | LUT | net of harness (80) | Fmax median | MHz/LUT |
|---|---:|---:|---:|---:|
| harness | 80 | — | 879.51 | — |
| `phi_step` | 303 | 223 | 209.60 | 0.692 |
| `apot_requant` | 217 | **137** | 83.88 | 0.387 |
| `zphi_add` | 240 | **160** | **220.60** | 0.919 |
| `lns32_t4096` | 499 | 419 | 82.96 | 0.166 |

`phi_step` against `apot_requant`: APoT is **1.63x smaller**, `phi_step` is
**2.50x faster**, so 1.79x on throughput per area -- against 2.2x measured at
half observation.

`zphi_add` against `lns32`: **2.62x on area and 2.66x on frequency, 5.5x on
throughput per area.**

## The trend is the finding

| measurement | LNS advantage claimed |
|---|---:|
| synthesis LUT only, no routing | 8.6x on area |
| post-route, 4-bit observation | **14x** |
| post-route, 16-bit observation | **11.5x** |
| post-route, 32-bit observation | **5.5x** |

**Every confound removed has moved this number in the same direction.** A
quantity that only ever falls as the instrument improves is not converged, and
the honest reading is that 5.5x is an upper bound rather than a measurement. The
conclusion -- that `Z[phi]` addition is cheaper than an LNS adder -- has survived
three instrument corrections, but its magnitude has been halved twice and should
be quoted as "several times", not as a figure.

**T (a monotone response to instrument improvement is a warning).** If successive
corrections to a measurement all move a result the same way, the remaining
uncorrected confounds are more likely to move it that way too. A result stable
under correction wanders; one that only descends is still descending.

## Count

Three iterations, three harness defects, each found by looking for the previous
one's class. None was visible in the numbers: every design synthesised, routed
and reported plausible figures at every stage.
