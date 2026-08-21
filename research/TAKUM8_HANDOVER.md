# takum8: the corrected pack, and the one step left

The rule is derived, tested and recorded. The generator exists. What remains is moving
the result into `t27`, and that step was **not** taken here — writing to another
repository is blocked in this environment, and it is the right thing to block: it
rewrites 124 published conformance vectors that other tooling consumes.

This file is the handover.

---

## What is settled

`takum8` decodes as the **high bits of a word at the reference width**, not at its
storage width. The rule comes from libtakum's own `src/codec.c`, whose field decode is
written over a `uint16_t` with `p = 16 − r − 5` and a 16-entry table whose smallest
entry is 4 — there is no `n = 8` path in it at all. That is a hypothesis, not a reading,
so it was tested:

```
takum_log8_to_float64(x) == takum_log16_to_float64(x << 8)     256 of 256, 0 differ
```

Sizing the fields at `n = 8` gives `p = 8 − r_eff − 5`, negative over half the code
space. Clamping that to zero is what the published pack does, and it is why 124 of its
254 comparable vectors are wrong by up to 26 orders of magnitude.

It also destroyed the format's signature property. takum's dynamic range does not shrink
with width, because a narrow takum's values are a strict subset of the wider grid. The
published pack spans 6.99e−56 … 1.43e+55 where libtakum spans 1.26e−52 … 7.91e+51.

| | published | regenerated |
|---|---|---|
| codes worse than 1e−9 vs libtakum | **124** | **0** |
| worst relative error | 1.14e+26 | **6.895e−15** |

6.895e−15 is the long-double noise ceiling in libtakum's own `pow`, and matches
takum16's 7.38e−15. There is nothing left to explain.

---

## To produce the file

```bash
python3 research/regenerate_takum8_pack.py --out takum8_conformance_v0.json
```

It reads the published pack, keeps its schema and metadata verbatim, and rewrites only
the vectors, the witness list and a `regenerated` note — so the diff against the
published file shows exactly what changed and nothing else.

```
vectors 256   unchanged 131   changed 124   NaR 1
```

Every value is the correctly rounded nearest double, decided against **both**
neighbouring doubles in exact arithmetic. `conformance/takum_log_ref.py` supplies
`ln|value|` as an exact `Fraction`; mpmath at 300 bits carries the exponential. No step
of the rounding decision depends on a float operation.

`--self-check` verifies the landmarks (0, +1, −1) and the count of codes carrying a
value, so a run that produces a file is distinguishable from one that produces a file
of zeros.

---

## To deliver it

Target: `gHashTag/t27`, path `gHashTag/t27/conformance/vectors/takum8_conformance_v0.json`, branch
off `master`.

Open it as a **pull request, not a direct push**. This changes published conformance
data; the diff is the argument, and 124 changed vectors deserve to be looked at by a
person before other tooling starts consuming them.

Suggested PR body: the two tables above, plus the `256 of 256` rule test. Everything in
it is reproducible from this repository with no board and no network.

---

## What this does not touch

`takum16` is correct on every finite code — median relative error 4.47e−16, max
7.38e−15, none worse than 1e−9, in **both** halves. The earlier "negative half diverges
on 32,766 codes" result was retracted in pass 146; it had been measured against
libtakum's *other* family, `takum<N>_to_float64`, where this corpus implements
`takum_log<N>`.

`takum32` follows the same rule and was checked at 40,000 pseudorandom codes: median
4.508e−16, max 7.393e−15, none worse than 1e−9.

`takum64` **cannot** be cross-validated on an arm64 host at any effort. libtakum stubs
it:

```c
#pragma message "Extended float format is too small to hold what takum_log64 \
                 offers, takum_log64 decoding is stubbed"
    return NAN;
```

guarded on `LDBL_MANT_DIG >= 64`, which arm64 macOS does not satisfy. An x86-64 host
with 80-bit long double would.
