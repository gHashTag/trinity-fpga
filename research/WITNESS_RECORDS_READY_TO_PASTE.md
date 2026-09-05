# Three witness records, ready to paste into their packs

`catalog_coverage_delta.t27` records the survey: **70 packs declare `bitexact: true`, 10
record a witness, 60 record none.** Pass 151 said the campaign could close "many" of the
60 from work already done. Pass 152 checked that against the list and it is wrong — the
campaign can close **three**. The other 57 need new work.

Why the rest of the campaign's verification does not land here:

| work | formats | why it is not one of the 60 |
|---|---|---|
| `ml_dtypes`, 66,224 codes | bfloat16, fp8_e4m3, fp8_e5m2 | their packs are `bf16_golden`, `fp8_e4m3fn`, `fp8_e5m2` — **none declares `bitexact: true`** |
| by-construction checks | bfloat24, bfloat32, pdp11_float, x87_48bit, mxint8 | **none has a pack in the catalogue** |
| three-oracle ADD and MUL | the GF formats | those *are* among the 60 — but they witness **arithmetic**, and the packs are **decode** conformance |

That last row is the one worth being strict about. An ADD oracle agreeing over 971,216
pairs says nothing about whether a decode vector carries the right value. This campaign
has been caught merging two claims before, and the fix is not to do it again quietly.

---

## `gHashTag/t27/conformance/vectors/takum8_conformance_v0.json`

> **Note:** paste this only alongside the regenerated vectors — see
> `research/TAKUM8_HANDOVER.md`. The witness describes the corrected pack, and the
> published one fails it on 124 of 254 codes.

```json
{
  "kind": "libtakum_c_parity",
  "oracle": "libtakum (Hunhold, ISO C99 reference implementation) takum_log8_to_float64, built from source and compared over all 256 codes by relative error rather than bit equality, since these values are irrational and libtakum evaluates them with pow in long double",
  "result": "254 comparable codes (1 NaR, 1 zero). Median relative error 4.36e-16, maximum 6.89e-15, 0 codes worse than 1e-9. The ceiling is long-double rounding noise in libtakum's own pow and matches takum16's 7.38e-15.",
  "reproduce": "research/regenerate_takum8_pack.py in gHashTag/trinity-fpga, against a libtakum checkout"
}
```

## `gHashTag/t27/conformance/vectors/takum16_conformance_v0.json`

```json
{
  "kind": "libtakum_c_parity",
  "oracle": "libtakum takum_log16_to_float64, exhaustive over all 65,536 codes, compared by relative error",
  "result": "65,534 finite codes. Median relative error 4.47e-16, maximum 7.38e-15, 0 codes worse than 1e-9 -- in BOTH halves of the code space. An earlier claim that the negative half diverged on 32,766 codes was retracted: it had been measured against libtakum's other family, takum16_to_float64, where this corpus implements takum_log16.",
  "reproduce": "conformance/takum_log_ref.py against a libtakum checkout"
}
```

## `gHashTag/t27/conformance/vectors/lns8_conformance_v0.json`

```json
{
  "kind": "representation_error_measurement",
  "oracle": "exact log-domain reference; the stored value is compared against the exact quantity the code denotes, not against a round trip",
  "result": "representation error in the range 1.8e-17 to 6.8e-17 across the code space -- below half an ULP of a double, so every stored value is the correctly rounded nearest double",
  "reproduce": "research/measure_lns_true_error.py in gHashTag/trinity-fpga"
}
```

---

## `posit8`, `posit16`, `posit32` — added pass 153

SoftPosit is the posit reference implementation, and all three packs match it exactly.
Use `research/crossval_softposit.py` to reproduce.

```json
{
  "kind": "softposit_c_parity",
  "oracle": "SoftPosit (Cerlane Leong, gitlab.com/cerlane/SoftPosit), the posit reference implementation, built from source. Entry point convertPX2ToDouble -- the positX family at es = 2, per Posit Standard 2022, with the code left-aligned in a 32-bit container. NOT convertP8ToDouble, whose posit8_t is the legacy es = 0 type from the pre-standard draft.",
  "result": "posit8: 255 of 255 comparable codes bit-identical, exhaustive over the whole code space, 1 NaR. posit16 and posit32: 8 of 8 curated vectors bit-identical each. Zero differences at any width.",
  "reproduce": "research/crossval_softposit.py in gHashTag/trinity-fpga, against a SoftPosit checkout"
}
```

`posit64` gets **no** such record. SoftPosit's `positX` family uses a 32-bit container,
so es = 2 at width 64 is out of its reach, and `posit64_t` is the legacy es = 0 type.
The pack remains without an independent witness, and the record should say that rather
than let the family look finished.

---

## The historical formats: "no witness exists, and here is why"

`afp`, `cray_float`, `ms_mbf32`, `ms_mbf64`, `ibm_hfp32/64/128`, `vax_d/f/g/h` and
`x87_fp80` have no maintained reference implementation to compare against. That is a
fact about the world, not a gap in the corpus, and honesty rule #10 is better served by
saying so than by leaving the field empty — an empty field reads as "not yet done".

A record of this shape is itself a witness record:

```json
{
  "kind": "no_independent_reference_exists",
  "searched": "no maintained implementation of this format is available. The format is defined by hardware that is no longer manufactured and by documentation rather than by a reference library.",
  "what_supports_the_pack_instead": "the decode is implemented directly from the published field layout, and the vectors are exact under that layout. This is a single-source claim and is labelled as one.",
  "what_would_change_this": "a period-correct emulator, a surviving machine, or a second independent implementation written from the same documentation by someone else"
}
```

The last field is the important one. It converts "we could not find a witness" into a
statement about what a witness would have to be, which is checkable by a reader and
actionable by anyone who has one.

---

## What the other 57 would need

Not a sweep. Each needs a **second implementation of that format**, independent of the
one that generated the pack, and for most of the 57 no such implementation is to hand:
`afp`, `cray_float`, `ms_mbf32/64`, `ibm_hfp*`, `vax_*` and `x87_fp80` are historical
formats with no maintained reference, and `gf*` is this project's own.

Three routes exist, in descending order of strength:

1. **A third-party library**, as libtakum was for takum. Available for `posit*`
   (SoftPosit) and arguably for `decimal*` (Intel DFP, IBM decNumber).
2. **By construction**, where the format is a documented transformation of one already
   verified — how `bfloat24`, `bfloat32`, `pdp11_float` and `x87_48bit` were done.
3. **An exact-arithmetic oracle structurally independent of the generator**, which is
   the weakest of the three and should say so in the record.

Writing "no independent witness exists for this format, and here is why" is itself a
witness record worth having. It is what honesty rule #10 asks for when the answer is
that there is nothing to compare against.

---

# Design-property records — added pass 172

A reader of `decimal32` sees `bitexact: true` and a table of vectors. What they do not
see is that its code order is not its value order, that this is a property of BID rather
than a defect, and that somebody checked. `verify_intrinsic_invariants.py` flagged nine
formats; pass 161 opened all nine and found eight behaving exactly as specified.

Those eight findings live in a spec. They belong in the packs, where the reader is.

Each record below carries a **measured** figure, not a description. The sampling is
exhaustive below 2^16 and a 4,000-point stride above, which is why the wide formats show
round numbers.

## `lns8`, `lns16` — the stored logarithm is signed

```json
{
  "kind": "code_order_is_not_value_order",
  "observed": "1 decrease over the positive half (lns8: of 14 comparable pairs; lns16: of 126)",
  "why": "the stored logarithm is signed, so the positive half of the code space runs through positive and negative exponents alike. lns8 code 56 decodes to 2^7 = 128 and code 72 to 2^-7; lns16 goes 2^63 to 2^-63 at the same boundary. The single decrease is the exponent sign turning over.",
  "not_a_defect": "monotonicity in code order is not a property this encoding claims"
}
```

## `ibm_hfp32`, `ibm_hfp64` — unnormalised hexadecimal float

```json
{
  "kind": "code_order_is_not_value_order",
  "observed": "126 decreases over 3,968 sampled pairs, at each width",
  "why": "the fraction need not carry a leading one, so a larger exponent with a much smaller fraction gives a smaller value. Exponent 1 with fraction 0xFBE734 is followed by exponent 2 with fraction 0x04185A, and the value falls from 1.36e-76 to 3.54e-77.",
  "also": "222 of 4,001 sampled codes do not survive a value round trip, for the same reason: several codes denote one value and encode() returns the normalised one"
}
```

## `decimal32`, `decimal64` — BID interleaves exponent and coefficient

```json
{
  "kind": "code_order_is_not_value_order",
  "observed": "192 decreases over 3,749 pairs at 32 bits; 218 over 3,372 at 64",
  "why": "the combination field encodes exponent and coefficient together, so consecutive codes do not denote consecutive values. Zero repeats -- the values differ, they are simply not sorted.",
  "contrast": "a format whose flag comes from a zero band shows the opposite shape: repeats and no decreases"
}
```

## `cray_float`, `x87_48bit` — unnormalised representations

```json
{
  "kind": "value_round_trip_is_not_injective",
  "observed": "1,050 of 2,125 sampled codes re-encode to a different code; 0 decreases in value order",
  "why": "both formats admit unnormalised representations, so several codes denote one value and encode() returns the normalised one. Opened one of each: the decoded value is a tiny nonzero rational with a ~4,940-digit denominator, and its normalised code differs.",
  "not_a_defect": "no value-based round trip can distinguish codes that denote the same value; that is what an unnormalised representation is for"
}
```

## `bcd` — and this one is a question, not a record

156 of 256 codes fail the value round trip. **That is exactly the count of invalid packed
BCD bytes**: a valid one has both nibbles in 0–9, so 100 of 256 are valid and 156 are
not.

`conformance/int_ref.py` decodes them anyway, as `sum(nibble * 10^i)` with no digit
check — `0x0A` becomes 10, `0x0F` becomes 15 — and `encode()` returns the canonical code,
so the trip closes elsewhere. The 7 monotonic decreases are the same thing seen from the
other side, at the nibble boundaries.

The corpus is internally consistent: `int_ref.py` records that it matches
`bcd_decode_conformance_ax7203.py` and `fpga/openxc7-synth/bcd_decode.v`, so oracle,
golden and silicon agree. **The question is what the pack claims.** It declares bit-exact
BCD, and a reader who knows BCD expects those 156 codes rejected.

Either the pack says it implements an extension accepting all 256 codes, or they decode
to a special. Recorded for the author in `catalog_coverage_delta.t27`; nothing here is
guessed, and the 156 is now measured rather than argued.

