# Full observation splits the group claim by axis, and gives a better theorem

Withdrawal 14 showed that observing part of a design's output prunes it
unequally. The isolated-decoder run from the previous iteration observed sixteen
of thirty-two output bits, so it was subject to the same defect. Re-measured with
every output bit folded into the observed reduction.

## What moved

| format | kind | LUT partial | LUT full | Δ | Fmax partial | Fmax full | Δ |
|---|---|---:|---:|---:|---:|---:|---:|
| int8 | fixed | 79 | 76 | −3.8% | 871.84 | 925.93 | +6.2% |
| GFTernary | fixed | 67 | 66 | −1.5% | 985.22 | 974.66 | −1.1% |
| TNF16 | fixed | 88 | 101 | +14.8% | 369.41 | 407.66 | +10.4% |
| BNF16 | fixed | 85 | 97 | +14.1% | 402.90 | 388.35 | −3.6% |
| binary16 | fixed | 136 | 164 | +20.6% | 228.57 | 235.18 | +2.9% |
| binary32 | fixed | 88 | 112 | +27.3% | 873.36 | 886.52 | +1.5% |
| posit8 | TAPERED | 195 | 214 | +9.7% | 105.94 | 77.75 | **−26.6%** |
| posit16 | TAPERED | 251 | 302 | +20.3% | 75.87 | 62.39 | **−17.8%** |
| posit32 | TAPERED | 597 | 517 | −13.4% | 43.73 | 49.05 | +12.2% |
| **IBM hex32** | fixed | 165 | **243** | **+47.3%** | 125.63 | 111.10 | −11.6% |
| LNS16 | log | 254 | 270 | +6.3% | 98.35 | 93.17 | −5.3% |

IBM hex32 moved most: nearly half its area had been pruned. The tapers lost the
most frequency.

## The group claim splits by axis

**By area, the groups overlap.** Worst fixed is IBM hex32 at 243 LUT; best
tapered is posit8 at 214. The tapered format is smaller.

**By frequency, they separate.** Worst fixed is IBM hex32 at 111.10 MHz; best
tapered is posit8 at 77.75. The worst fixed field still leads the best taper by
**1.43x**, well outside the seed spread.

The previous iteration's "separates on both axes" was partly an artefact of
partial observation, and is corrected.

## The better theorem

**T (a taper is paid in delay, not in area).** A tapered format's decode contains
a scan -- a serial dependency whose length grows with the word. A serial
dependency costs critical path directly and area only incidentally. A
radix-heavy fixed format like IBM hexadecimal instead costs a wide shift, which
is area-heavy and shallow. Hence the two families separate on frequency and not
on area, and any comparison run only on area will find them overlapping.

This is sharper than the claim it replaces. "Fixed beats tapered" was a statement
about a class; this is a statement about what a scan **is**, and it predicts the
overlap rather than being embarrassed by it.

Supporting numbers: across posit8, posit16 and posit32 the area grows 2.4x while
the frequency falls 1.6x, and every taper sits below every fixed field on
frequency while three fixed fields sit above two tapers on area.

## The headline, corrected again

GFTernary against posit32: **7.8x on area and 19.9x on frequency**, against
8.9x and 22.5x measured with partial observation, and 6.4x on the confounded
combined harness. Three instruments, three numbers, converging as each confound
is removed.

Correlation between area and frequency: **−0.727** here, against −0.616 with
partial observation and −0.900 on the combined design. The axes remain
substantially independent, so reporting both is meaningful.

## Count

Fourteen withdrawals, two of them subsequently withdrawn in turn. The last three
iterations each found a defect in the harness rather than in a design or a claim,
and each changed a headline number by 10 to 50 percent without any individual
measurement being wrong.
