# Pre-registration: does the corner-density diagnosis generalise past E2M1?

Committed **before** the run.

## The claim being tested

`thm:latticeexp` says a lattice-minimised objective costs `O(h²)` against a
smooth minimum and `O(h)` against a corner, and the paper's diagnosis is that a
block format's scale-ladder exponent crosses over to Bennett's `p = 2` at the
ladder spacing that resolves one smooth arc, i.e. at `N ≈ D`, the corner density
per octave.

**On E2M1 this held**: `D = 46.5` by counting alone, `p = 2.030` at `N = 64→128`.

**One codebook is an anecdote.** If the diagnosis is a statement about codebooks
rather than about E2M1, it must track `D` across codebooks with very different
boundary geometry — and `D` is computable without evaluating the error once,
which is what would make it a *design* tool: count corners, know the return on
scale resolution, before quantising anything.

## Measured first, by counting only

| codebook | levels | non-zero boundaries | log span | boundary density |
|---|---|---|---|---|
| **e3m0** — pure exponent, 1,2,4,…,64 | 15 | 14 | 6.58 oct | **2.13 /oct** |
| **e2m1** — MXFP4's own | 15 | 14 | 4.32 oct | **3.24 /oct** |
| **nf4** — QLoRA NormalFloat4, asymmetric | 16 | 15 | 4.44 oct | **3.38 /oct** |
| **int4** — linear 0…7, bunched in log | 15 | 14 | 3.70 oct | **3.78 /oct** |

## The prediction

**Ordinal, and it is the one that counts:**

> crossover N must order as **e3m0 < e2m1 < nf4 < int4**

A cardinal hit would be luck at this level of modelling. A cardinal miss with the
ordering intact still leaves the diagnosis usable as a design tool.

**Falsified if** the crossovers do not follow `D` — in which case E2M1's
agreement was a coincidence, the diagnosis is about one codebook rather than
about codebooks, and `thm:latticeexp`'s application in this paper needs
narrowing to the format it was derived on.

## Note on NF4, which is the interesting case

NF4 is **asymmetric**: 15 distinct magnitudes where every symmetric 4-bit
codebook has 8. A corner exists at `t = log₂(v/m)` only when element and
boundary share a sign, so asymmetry contributes corners the magnitude count
alone would not predict. If the diagnosis is real it should handle this without
special-casing — the counting instrument already respects the sign condition.

## Prior on predictions in this campaign

Registered predictions so far: the three-horn ordering **failed on both axes**;
the Bennett cardinal prediction at N=2 and N=4 **failed low on both**, while its
ordinal half **held**. Two for four, with the ordinal halves surviving. That is
the base rate this one should be read against.
