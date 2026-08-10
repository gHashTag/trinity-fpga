# The ladder law over the whole one-adder family

The ladder law was measured over degrees 1--3 only, because those were the rungs
we had. T38 then showed that `r^d = r + 1` costs one addition at every degree,
so degrees 4, 5, 6 and 8 apply as cheaply as `phi` does. This measures the law
over all of them, as an ELEMENT codebook -- per-output-channel scale, codebook of
exactly `2^b` entries including zero and sign, SmolLM2-135M, wikitext-2, 12
windows. Baseline fp32 14.3607.

| ratio | degree | adds | span at 4b | 4 bits | 5 bits | 6 bits |
|---|---|---|---|---|---|---|
| 2.0000 shift | 1 | 0 | 64.0x | 76.8078 | 77.5223 | 77.5212 |
| **1.6180 phi** | 2 | 1 | 17.9x | **24.4280** | 22.7335 | 22.7361 |
| 1.3247 plastic | 3 | 1 | 5.4x | 55.0855 | 16.4571 | 16.3118 |
| 1.2207 r^4=r+1 | 4 | 1 | 3.3x | 2074.67 | 16.1662 | 15.3653 |
| **1.2365 r^5=r^3+1** | 5 | 1 | 3.6x | 886.60 | **15.9242** | 15.3636 |
| **1.1347 r^6=r+1** | 6 | 1 | 2.1x | 1873705 | 36.7554 | **14.8882** |
| 1.0970 r^8=r+1 | 8 | 1 | 1.7x | 2710365 | 679.65 | 15.4080 |

**The optimal degree rises with the budget**, now over degrees 2, 5 and 6 rather
than 1, 2 and 3: `phi` at four bits, `r^5 = r^3+1` at five, `r^6 = r+1` at six.
Every winner costs exactly one addition.

**At six bits the one-adder ladder reaches 14.8882 against an fp32 baseline of
14.3607 -- 3.7% -- with a six-bit element and a single adder.**

The failures are as instructive as the wins. At four bits `r^8 = r + 1` spans
`1.7x` and measures 2,710,365: a ladder fine enough to resolve anything and too
short to reach anything. Fineness without span is not precision, it is a very
accurate description of a narrow interval.

## Why this needed T38 first

Reading the hierarchy by degree, with each degree's cost taken as its minimal
ratio, degrees 4 and above looked expensive -- three adders at degree 4. Along
the family `r^d = r + 1` the adder count never grows, so the rungs that win at
five and six bits cost exactly what `phi` costs. The result was available all
along and the framing hid it.

*Second model pending.*
