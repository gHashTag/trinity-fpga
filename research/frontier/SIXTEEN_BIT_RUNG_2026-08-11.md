# A rung at exactly sixteen bits: we win the fair class, and the win has a price

Iteration 83 found that our nearest rung to the 16-bit competitors was 17 bits,
so every same-width claim in the paper carried a one-bit apology. That is now
fixed, and the answer is better than expected in one direction and worse in
another.

## Two candidates, both built, both checked

A rung's stored width is $1 + \lceil E_t\log_2 3\rceil + M$. Exactly two
assignments reach sixteen:

| | $E_t$ | offset bits | $M$ | range |
|---|---|---|---|---|
| **A** | 4 | 7 (81 offsets) | 8 | $2^{\pm39}$ |
| **B** | 3 | 5 (27 offsets) | 10 | $2^{\pm12}$ |

Which is *the* 16-bit member is a measurement, not a preference. Both built,
both checked exhaustively against the ladder reference: **65,534 of 65,534
exact, each.**

## Rung A wins its width class outright — including against IEEE

| **TNF16a** (16b) versus | |
|---|---|
| `binary16` | **+14.7%** |
| `takum16` | **+86.3%** |
| `LNS16` | **+112.8%** |
| `posit16` | **+152.6%** |

A: 502 LUT, 69.87 MHz, **0.1392 MHz/LUT** — rank 3 in the full table.
B: 540 LUT, 61.76 MHz, 0.1144.

**This is the first same-width win against IEEE in the catalogue** and it is
exactly the result iteration 83 said the paper did not have.

## The price, printed beside it

Four trits give 81 offsets; their binary field holds 128. **37.5% of rung A's
offset codes lie outside the format.** Counting representable values, rung A
uses 40,960 of 65,536 codes — **15.32 effective bits where `binary16` delivers
close to 16.**

**The win is +14.7% throughput for −0.68 bits of code space.**

## The mechanism, which is the same one twice

Proposition (output-space pruning) from iteration 83 predicts this: a decoder
whose image is smaller needs less logic, and downstream logic may specialise to
that image. **An image can be small because the input is narrow, or because the
format discards codes.** Same mechanism, different cause.

| | codes discarded | MHz/LUT advantage |
|---|---|---|
| `GF+8` pocket 11 as published | 93.4% | +19.2% |
| **TNF16a** vs `binary16` | 37.5% | +14.7% |
| **TNF16b** vs `binary16` | 18.8% | −5.7% |

Three points do not establish a law and are not offered as one — at $n=3$ the
$r=+0.81$ carries no significance. **The claim rests on the mechanism, which is
deductive; the points are consistent with it.**

## What this means for reading the table

**A throughput metric rewards a format for discarding code space.** No ranking
on MHz/LUT alone is a ranking of format quality.

Our first place is unaffected: `GFTernary` uses all four of its codes and
discards nothing. **Rung A's third place is bought in part with codes it does
not spend, and saying so is the difference between a result and an
advertisement.**
