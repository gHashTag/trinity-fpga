# The staircase taxonomy prescribes a comparison method for every form

T19 showed the classification prescribes the comparison for two of its four
forms. Asking the remaining two closes it.

## The four forms, and what each requires

| form | `M_eff` behaviour | correct comparison |
|---|---|---|
| **constant** (TNF, binary, bfloat) | independent of `\|e\|` | compare the constants -- no window, no crossover |
| **arithmetic** (posit) | linear in `\|e\|` | linear crossover `(p−m)/s + 1`, window-independent |
| **geometric** (takum, tekum) | linear in `log\|e\|` | closed form `2^(p−m)`, no window |
| **wobble** (IBM hex, radix 16) | **periodic** in `\|e\|` | **duty cycle over the period, not a crossover** |

## The wobble measurement

IBM hexadecimal 32, measured binade by binade:

```
21.03 21.75 22.94 19.95 | 20.89 22.11 22.90 20.07 | 21.04 22.14 22.94 19.87
```

Amplitude **3.07 bits**, period **4 binades** -- exactly `log2(16)`, as the radix
requires. This is the textbook hexadecimal wobble, recovered from measurement
rather than assumed.

Against TNF32 at `M_eff = 25.08` the whole band sits below, so the answer is a
plain verdict. **The interesting case is when the constant lies inside the band.**
Packed TNF32 at `Et=6, M=21` measures `21.32`, inside IBM's `[19.94, 23.11]`:

```
binade  1  2  3  4  5  6  7  8  9 10 11 12 13 14 15 16
winner  T  I  I  T  T  I  I  T  T  I  I  T  T  I  I  T
```

**Duty cycle 50/50, period 4.** There is no crossover: no single binade separates
the winners, because the winner alternates forever.

## Theorem

**T20 (a wobble admits no crossover).** If a format's `M_eff` is periodic in
`|e|` with amplitude `A` and period `P`, and a constant-form competitor's `m` lies
strictly inside the band, then no `x` exists such that one leads for all
`|e| < x` and the other for all `|e| > x`. The well-posed statistic is the duty
cycle -- the fraction of each period on which each leads -- together with `P`.

**Corollary (the taxonomy is prescriptive).** Each of the four staircase forms
determines the *shape* of a well-posed comparison against a constant format:
a difference, a linear crossover, an exponential crossover, or a duty cycle. A
classification that only labelled formats could not do this, and for most of this
work we used it only to label.

## Why this matters beyond the arithmetic

Every comparison in the number-format literature we have read reports a verdict
or a ratio. For two of the four forms in this taxonomy that shape is wrong: a
geometric taper needs `2^(p−m)` rather than a fitted line, and a wobble admits no
crossover at all. **The form of the answer is not a stylistic choice -- it is
determined by the competitor's staircase.**
