# GF+8 has an oracle now, and it is conformant to a defective specification

`GF+8` was the last row of ours with no oracle, and the only width class in the
catalogue where one of our formats meets a competitor head-on and loses. Both
questions are settled; a third one opened.

## The container

GF+A is adaptive: a 2-bit header picks one of four pockets over a shared 8-bit
payload. **The decoder therefore sees 10 bits, not 8** — the container amortises
the selector over a group of K rows, which is why the storage column says 8.

| pocket | format | distinct values / 256 |
|---|---|---|
| 00 | φ-e3m4, (1,3,4) bias 3 | 255 |
| 01 | e2m5, (1,2,5) bias 1 | 255 |
| 10 | int8, symmetric fixed, scale 1/64 | 255 |
| 11 | declared logarithmic | **17** |

Implemented from those four parameter sets and compared against the module:
**1,024 of 1,024 exact, zero disagreements.** The decoder is correct.

## The fourth pocket is not

It emits $2^{-s}$ with the mantissa identically zero, $s = \lfloor\iota/16\rfloor
+ \lfloor\iota/32\rfloor$, $\iota = 127 - |w|$. A power-of-two ladder — **17
distinct values from 256 codes, 93% of the pocket's code space mapping onto
nothing new.** Its own comment declares scale $\iota\cdot8/127$ while the code
implements $\iota\cdot3/32$, half again as steep. Second time in this catalogue
that RTL contradicted the comment beside it.

**Proposition (conformance does not certify the specification).** If $D$
implements $f$ exactly, conformance establishes $D = \rho\circ f$ and says
nothing about $f$. $|f(C)|$ may be arbitrarily smaller than $|C|$, and a decoder
faithfully realising a degenerate $f$ is conformant and useless.

This is a new class for this work. Every previous finding was *the decoder
disagrees with the format*. This one is *the decoder agrees, and the format is
broken.* No conformance test can ever find it.

## The direction law, eleventh confirmation

Rebuilt pocket 11 as the `lns8` this repository already declares — signed 7-bit
log field, `frac_bits=3`, value $2^{L/8}$, 255 distinct values:

| pocket 11 | LUT | MHz | MHz/LUT |
|---|---|---|---|
| as published (17 values) | 170 | 313.38 | 1.8434 |
| as `lns8` (255 values) | 182 | 271.22 | 1.4902 |
| | **+7.1%** | **−13.5%** | **−19.2%** |

So GF+8's 0.1004 — already losing to `fp8 e4m3`'s 0.1254 by 19.9% in the only
head-to-head class in the catalogue — **is itself inflated by a pocket that
throws away most of its code space. Repaired, it loses by more.**

We report it because it is true, and because a number resting on a degenerate
component is the kind of claim this paper spends twenty-seven sections
dismantling in other people's work.

## Status

**Conformance now closed on 20 of 21 rows.** `minifloat` and `posit8` were the
two open; GF+8 closing brings it to 20 with one of those two remaining.
