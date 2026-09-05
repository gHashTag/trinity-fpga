# What 153 claims looked like when only claims were audited

A first audit of `fpga/phiscale/` told its verifiers to "default to withdraw when
uncertain". They applied it to table data rows, and a third of the output was
noise about statements that were never claims. It returned **1 stands out of
115** — a verdict so uniform it carried no information.

This run splits the question in two. A cheap pass classifies every numeric
statement; only the ones that are actually **claims** reach the expensive one.

## What the numeric statements actually are

| kind | count |
|---|---:|
| data-row | 182 |
| **claim** | **153** |
| method | 145 |
| self-disclosed-cost | 125 |
| citation | 35 |

**153 of 640 — 24%.** The other 76% never reach verification. That is the noise
the single-phase run spent its budget on.

## What the claims did

| verdict | count |
|---|---:|
| stands | **64** |
| needs-qualification | 73 |
| withdraw | 12 |
| cannot-verify | 4 |

**64 of 153 stand — 42%, against 1% before.** The instruction to default to
withdraw was removed at the same time, and both changes matter: the filter stops
the pass wasting itself on non-claims, and dropping the default lets it
discriminate.

## The finding that outranks the rest

`GFT16_BEATS_TEKUM16_2026-08-05.md` — the document memory records as this
project's gold-standard result — has three faults, each verified by hand:

* **17 bits, not 16.** Four trits need 7 binary positions: `1 + 7 + 9 = 17`.
  `conformance/tnf16_ref.py` says "17-bit canonical raw" in its own header, and
  `tnf_ref.LADDER[16].sign_shift == 16`. tekum16 is 16.
* **The competitor is takum, not tekum.** All 65,536 codes decoded through both
  oracles: **0 differences**. `tekum_ref`'s docstring flags the balanced-ternary
  exponent `# TODO: verify from full paper` — the feature that distinguishes
  tekum is absent from the model that was beaten.
* **The exponent range is 79 values, not 81** — offset 0 is zero and offset 80
  is Inf/NaN, so `e ∈ [−39, +39]`.

The accuracy measurement itself reproduces. What does not survive is that it was
at equal width, or against tekum.

## Other withdrawals worth naming

* `GF_T_GOLD_STANDARD_LADDER`: **"461 LC, below tekum16's 480–650"** — 461 is not
  a GF-T adder. The only one in the tree synthesises to 108 LUT, and it is
  magnitude-only: no sign, no subtraction, no rounding, no normalisation. The
  13× gap against tekum's full adder is feature asymmetry, not format cost.
* `README.md`: **"`-abc9` is mandatory: 70% → 19%"** — the arrow changes two
  variables and two denominators. On one GF64 design, changing only that flag:
  49.4% with it, 19.2% without.
* `README.md`: **"everything reproducible from a pinned image digest"** — 57
  workflow files use `regymm/openxc7:latest` (113 occurrences); 6 pin a digest.
* `PARAMETER_GOLF_RESULTS`: **"BF16 loses 0.54 BPB (67× worse)"** — no source in
  the tree produces either number. BF16+SR is 0.027 behind GF16+SR.

## A fault in this audit's own instructions

The doctrine handed to the verifiers said "nothing in this project has touched
silicon". That is true of `fpga/phiscale/` and **false of the repository**, which
holds AX7203 bitstreams and a Tier-E proof from sessions when boards were
attached. Two verdicts cite the line; both were re-checked and survive on their
other ground — that no *ternary* fabric exists anywhere — but the sentence was
wrong and is recorded here rather than quietly fixed.
