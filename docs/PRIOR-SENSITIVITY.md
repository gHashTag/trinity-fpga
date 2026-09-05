# How much of the accuracy result is the sampling prior? (W937)

Every accuracy regenerator in the manuscript draws `_rng.integers(-38, 39)` —
**uniform over 77 binades** — and the word "prior" never appears in the paper in a
statistical sense. That draw is exactly the distribution under which a
flat-precision fixed field must beat a tapered format, because a taper spends its
precision near |e| = 0 by construction.

This re-runs **the same shipped oracles** (`conformance/*_ref.py`, imported
unchanged) and **the same round-trip relative error** over five priors. No format
code was written. Script `prior_sensitivity.py`, record
[`prior_sensitivity_w937.json`](prior_sensitivity_w937.json), 6,000 values per
prior, seed 20260809 — the paper's own seed.

## Median relative error, by prior

| prior | TNF16 | posit16 | TNF advantage | takum16 | TNF advantage |
|---|---:|---:|---:|---:|---:|
| **published** — uniform, 77 binades | 8.101e-05 | 1.185e-03 | **14.63×** | 8.801e-04 | 10.86× |
| standard normal | 8.184e-05 | 8.346e-05 | **1.02×** | 1.112e-04 | 1.36× |
| He init, fan-in 512 | 8.184e-05 | 1.349e-04 | 1.65× | 3.425e-04 | 4.19× |
| Student-t, df = 3 (heavy tails) | 8.471e-05 | 1.351e-04 | 1.59× | 3.332e-04 | 3.93× |
| log-uniform, 17 binades | 8.101e-05 | 1.131e-04 | 1.40× | 2.478e-04 | 3.06× |

## Three findings, and the first one favours the paper

**1. TNF16 is first under every prior tested, and its error is prior-invariant.**
Across five priors spanning six orders of magnitude of median magnitude, TNF16's
median relative error moves from 8.101e-05 to 8.471e-05 — a spread of **1.046×**.
That is what a flat field *should* do, and it is a stronger and more defensible
statement than any multiple: **the format's accuracy does not depend on the
workload's dynamic range.** No competitor here has that property.

**2. The published multiples are carried by the prior.** The advantage over
posit16 is **14.63× under the published draw and 1.02× under a standard normal** —
a statistical tie. Against takum16 it moves 10.86× → 1.36×. The ranking survives;
the numbers quoted for it do not. Any table stating "TNF is N× more accurate"
without naming its prior is reporting the prior.

**3. The published prior is outside the representable range of a listed
competitor.** Under uniform-77-binades, `binary16` fails to represent **1,786 of
6,000** values (overflow past 65,504) and is nonetheless tabulated. A workload
that a quarter of the field cannot hold is a workload chosen for the winner.

## Caveats, stated because they bound the table above

- **LNS16 is not measured here.** The shipped oracle refuses to return a rational
  for a logarithmic format, so 5,969 of 6,000 values return nothing through the
  generic round-trip path used in this script; the paper's own regenerator has a
  dedicated value-domain path for it. The LNS16 row of the JSON reflects only the
  ~31 values that survived and must not be quoted.
- These are **round-trip representation errors**, not task accuracy. They do not
  substitute for a top-1 on a named dataset, which is what every LUT-domain
  competitor reports and which this project still lacks entirely (`top-1`,
  `ImageNet`, `CIFAR`, `MNIST`: 0 hits in 7,858 lines).
- The four alternative priors are *plausible* weight distributions, not measured
  ones. The decisive experiment is still the empirical magnitude histogram of a
  real trained tensor; this bounds how much that experiment could change.

## What the paper should say instead

Not "TNF16 is 14.6× more accurate than posit16" — that is one prior's number.
Rather: **"TNF16's relative error is 8.1e-05 and varies by under 5 % across five
weight priors spanning six orders of magnitude, while posit16's varies by 14× and
takum16's by 8×."** Same data, same oracles, and it is the claim that holds.

---

*φ² + φ⁻² = 3 | TRINITY*
