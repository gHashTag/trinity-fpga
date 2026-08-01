# How the suite was verified — ready to paste

A conformance paper is judged less on its vectors than on why anyone should believe
them. Both preprints describe *what* the corpus contains and neither describes *how it
was checked against the possibility of being uniformly wrong*. That is the more
interesting half, and it is already done — it just has not been written down for a
reader.

Everything below was re-run on 2026-08-02 rather than quoted from a log.

---

## 1. Two oracles cannot tell "both correct" from "both wrong the same way"

The natural way to verify an arithmetic implementation is to compare it against a
reference. If the reference was written by transcribing the implementation — which is
what a faithful RTL port is — then agreement proves the transcription, not the
arithmetic.

Both main operations therefore carry a **third** formulation that shares no code with
either of the other two.

| operation | O1 | O2 | O3 | result |
|---|---|---|---|---|
| **MUL** | Python port of `gf_mul_param.v` | `ref_fpmul` — exact integer product, single RNE | `Fraction` golden | **1,269,632 pairs, 0 divergences** |
| **ADD** | Python port of `gf_adder_param.v` | nearest-representable by bisection over the format's grid | `Fraction` golden | **971,216 pairs, 0 divergences** |

GF6 and GF8 are **exhaustive** in both — 4,096 and 65,536 pairs — and GF12 through GF24
are sampled at 300,000 each with every structural-boundary pair included.

O2 is the point in each case. For MUL it computes an exact integer product and rounds
once, where the DUT uses a guard-round-sticky path. For ADD it bisects the format's
grid of representable magnitudes and takes the nearer neighbour — no exponent
extraction, no alignment shift, no sticky bit, no leading-zero count. Neither can
inherit a defect from the implementation, because neither models it.

---

## 2. A verification that cannot fail is not a verification

Three oracles agreeing on the first run invites the question of whether the comparison
discriminates at all. Four faults are injected into O2 and each must be caught:

```
caught  ties-away-from-zero          gf6:424  gf8:5328  gf16:263
caught  overflow-never-Inf           gf6:0    gf8:0     gf16:30
caught  subnormals-flushed           gf6:586  gf8:2614  gf16:83
caught  zero-passthrough-before-NaN  gf6:0    gf8:0     gf16:20
```

Three are plausible ways to get rounding wrong. **The fourth is not hypothetical** — it
is the ordering defect that reached silicon in this project's own adder and was fixed
in commit `711f5d572`.

The zeroes are the correct reading rather than misses: `gf6` and `gf8` carry no Inf and
no NaN, so those two faults have nowhere to show in them.

---

## 3. A bit-exact hardware result bounds the vectors, not the cell

This is the finding worth a paragraph of its own, and it comes from this project's own
history rather than from a constructed example.

The gf16 adder is shared: `SUB(a,b)` is computed as `ADD(a, b XOR sign)`. So ADD and
SUB exercised **the same cell on the same silicon with 512 pairs each**. ADD reported
512/512 bit-exact. SUB reported 508/512 and exposed an IEEE-754 ordering defect —
zero-passthrough evaluated before the NaN branch, so a zero paired with a NaN returned
that NaN's raw payload instead of the canonical quiet NaN.

Why one suite was blind:

- gf16 ADD's vectors carry exactly one NaN, `0x7E01` — and `0x7E01` **is** gf16's
  canonical quiet NaN, so the defective path returned the correct value by coincidence.
- ADD's `b`-position set holds no NaN at all: two zeroes, two subnormals, four ordinary
  finites.
- gf16 SUB seeds `0xFFFF`, whose payload is **not** canonical. Against a zero, the
  defect is immediate.

Replaying the pre-fix behaviour over each suite's own vectors, with no board,
reproduces the silicon exactly: **ADD 0 failures, SUB 4.**

> The difference was not sample size, not the operation, and not the hardware. One
> vector set contained a NaN whose payload differed from the canonical quiet NaN and the
> other did not.

That is a transferable statement about conformance-vector design, and the caution it
implies belongs in any paper reporting bit-exact hardware results: **such a result
bounds the vectors, not the cell.**

---

## 4. The one sentence not to write

Do not say the arithmetic was *"verified in software and confirmed on hardware"* as
though those were two independent confirmations. The compute cores carry no expected
values — they are UART transponders — so the comparison happens on the host, and the
host takes its expected values from the same `gf_ref` module the software proofs use.
One definition, checked twice: once by reasoning, once by executing an RTL
implementation of it on silicon. Both are worth having and they are different claims.

---

## Provenance

| claim | re-derive with |
|---|---|
| MUL, three oracles | `python3 formal/verify_mul_oracle.py` |
| ADD, three oracles | `python3 research/verify_add_oracle.py --sample 300000` |
| the negative control | `python3 research/verify_add_oracle.py --self-check` |
| the vector-blindness reproduction | `python3 research/vector_blindness.py` |
| the shared-oracle reading | `conformance/*_conformance_ax7203.py` — 38 of 147 import `gf_ref` |
