# Withdrawal 17: a taper's slope is a property of the fitting window

Re-measuring the seven untraceable figures confirmed three and exposed something
larger about four.

## Three confirmed, and they now have a source

The extended-format figures had no data file because they had been computed and
never written down. Re-measured on the same oracles:

| format | paper | re-measured | difference |
|---|---:|---:|---:|
| double-double | 106.68 | **106.46** | 0.2% |
| quad-double | 215.90 | **216.10** | 0.09% |
| x87 80-bit | 63.04 | **62.93** | 0.17% |

All within the sampling noise of a 60-draw probe. They were never stale; they
were merely unrecorded.

TNF16's by-band row is confirmed too: measured 8.86, 8.98, 8.97, 8.96 across
binades 1 to 24 against the paper's 8.99, 8.99, 9.00, 9.01 -- constant, as the
precision law requires.

## The four taper slopes are not single numbers

Measuring `M_eff` by binade and fitting a line gives a different slope depending
on how far out the fit runs:

| format | window 1..9 | window 1..20 | in the paper | crossover spread |
|---|---:|---:|---:|---:|
| posit16 | 0.2610 | 0.2458 | 0.254 | 7.7 -- 8.2 (**1.05x**) |
| posit32 | 0.2600 | 0.2544 | 0.247 | 10.3 -- 10.8 (**1.05x**) |
| **takum16** | 0.2410 | **0.1605** | **0.113** | 4.9 -- 9.3 (**1.90x**) |

**A taper's `M_eff` is not strictly linear in `|e|`**, so its "slope" is defined
only together with the window it was fitted over. The crossovers reported in
this work were stated as single numbers with no window named.

## Theorem

**T18 (a slope is a property of the window, not of the curve).** If a quantity is
not strictly linear in a parameter, its slope is defined only jointly with the
fitting window. Quoting a slope without its window is the same defect as quoting
a ratio without saying what is held equal (T7).

**Corollary.** A crossover computed from such a slope inherits the window
dependence. The well-posed form is a crossover **with its window named**, or a
range of crossovers over reasonable windows.

## What this does and does not damage

**posit16 and posit32 survive intact**: their crossovers move by 5% across
windows, which is inside every other uncertainty in this work. Those two are
close to linear and the single-number form was accidentally safe.

**takum16 does not**: its crossover ranges from 4.9 to 9.3 binades, a factor of
1.9, depending purely on how far the fit reaches. Any statement of the form
"TNF16 overtakes takum16 at N binades" needs the window attached.

The pattern is familiar by now: the measurement was correct at each window and
the comparison across them was never posed. This is the seventeenth time.

## Reporting standard adopted

Every slope in this work is now quoted with its fitting window, and every
crossover derived from one carries the range across windows 1..9 and 1..20. Where
those differ by more than 10%, the crossover is reported as a range rather than a
number.
