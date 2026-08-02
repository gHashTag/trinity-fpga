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

## `takum8_conformance_v0.json`

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

## `takum16_conformance_v0.json`

```json
{
  "kind": "libtakum_c_parity",
  "oracle": "libtakum takum_log16_to_float64, exhaustive over all 65,536 codes, compared by relative error",
  "result": "65,534 finite codes. Median relative error 4.47e-16, maximum 7.38e-15, 0 codes worse than 1e-9 -- in BOTH halves of the code space. An earlier claim that the negative half diverged on 32,766 codes was retracted: it had been measured against libtakum's other family, takum16_to_float64, where this corpus implements takum_log16.",
  "reproduce": "conformance/takum_log_ref.py against a libtakum checkout"
}
```

## `lns8_conformance_v0.json`

```json
{
  "kind": "representation_error_measurement",
  "oracle": "exact log-domain reference; the stored value is compared against the exact quantity the code denotes, not against a round trip",
  "result": "representation error in the range 1.8e-17 to 6.8e-17 across the code space -- below half an ULP of a double, so every stored value is the correctly rounded nearest double",
  "reproduce": "research/measure_lns_true_error.py in gHashTag/trinity-fpga"
}
```

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
