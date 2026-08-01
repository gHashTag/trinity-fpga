# The one-ULP boundary — ready to paste

Two independent routes reached the same limit during verification of this corpus, and
a third is under caution — see below. Each was measured separately, none was looked
for, and together they say something a conformance-suite paper is in an unusually good
position to say: **bit-exactness is
attainable over the decidable class, and logarithmic evaluation is not in it.**

Neither preprint says this. It costs one paragraph and it strengthens the papers,
because it converts a limitation into a stated boundary with measurements behind it.

---

## The three routes, with their numbers

| route | what was measured | result |
|---|---|---|
| **third-party library** | the corpus's `takum32` pack against `libtakum` | **12 of 15** vectors differ by exactly one ULP — none by more. **See the caution below before using this row.** |
| **the field's own practice** | numpy 2.4.4, `_core/tests/data/umath-validation-set-*.csv` | **26,615** rows, 20 operations, tolerances 1–4 ULP; **0 rows claim zero error** |
| **silicon** | `lns16` decode on an AX7203, `--extended` conformance | `472/576 bit-exact, 104 known-limitation(s), 0 hard-fail(s)` — all 104 are 1-ULP subnormal-band residuals |

numpy's tolerance histogram, since the shape matters: 1 ULP on 12,001 rows, 2 on 8,455,
3 on 3,799, 4 on 2,355.

---

## The paragraph (English, for either paper's discussion section)

> Every format in this catalogue whose decode is a finite sequence of integer
> operations admits bit-exact conformance vectors, and the suite provides them. Formats
> whose decode requires a transcendental evaluation do not, and the boundary is sharp
> rather than gradual. We met it twice from independent directions during
> verification. numpy's own validation sets —
> 26,615 vectors across 20 transcendental operations, the closest artefact in the field
> to a conformance pack — state a tolerance of one to four ULP on every row and claim
> exactness on none. And on hardware, our `lns16` decode returns 472 of 576 vectors
> bit-exact with 104 disclosed one-ULP residuals in the subnormal band and no hard
> failures. The field's own practice and our silicon agree on where the line falls. We therefore make no claim of bit-exactness for logarithmic formats,
> and report their residuals rather than tightening a tolerance until they disappear.

---

## A caution about the takum row, added after the paragraph was drafted

`conformance/takum_ref.py` states in its own header that real takum is **logarithmic**
— `value = (-1)^S · exp(ell/2)`, so values are generally irrational and admit no exact
rational arithmetic — and that what the oracle implements is therefore a **working
structural model interpreted linearly**, reverse-engineered from `takum64_decode.v`.

That changes what the `libtakum` comparison means. The earlier reading was *"they
differ by one ULP because a logarithmic decode needs `exp()`"* — a rounding ceiling.
But the oracle is not attempting a logarithmic decode and falling short by a rounding;
it is computing a **different function**, and agreeing with `libtakum` to within one
ULP on 12 of 15 vectors is a much weaker and more surprising statement than a bound.
Fifteen vectors is also a small sample from which to say *"none by more"*.

**This caution is now partly resolved.** Pass 136 compared the published `takum8` pack
against the logarithmic definition directly: all 256 vectors agree to within
**1.02e−16**, the float64 rounding level, and `takum16`'s agree exactly. So the packs
are logarithmically correct and the linear oracle is not what produced them. The
`libtakum` comparison was therefore between two logarithmic implementations after all,
and the one-ULP reading stands on that count.

What remains unverified is only the sample size: fifteen vectors is a small basis for
*"none by more"*. Re-measure over a wider set before printing the row, but the reason to
doubt it has gone.

## The sentence that must accompany it

Do not let the paragraph read as a claim of superior rigour over numpy. The
corpus's own record already states the correct framing, and it should survive into
print:

> The corpus is exact because of the problem it chose, not because of superior rigour.
> numpy covers 20 operations this catalogue does not touch at all, and 26,615 vectors
> against our 5,075. On operation coverage it is the deeper artefact by a wide margin;
> on format coverage, 83 against 2, this one is. The comparison is complementary, not
> competing.

A reviewer who knows numpy will check this. Saying it first is both more accurate and
more persuasive than being corrected.

---

## Optional: a related-work sentence

If the related-work section mentions numpy at all, one sentence carries the whole
comparison:

> numpy's validation sets are the closest existing artefact to a conformance pack —
> fixed vectors, hexadecimal bit patterns, a stated error bound per row — and differ
> from this work in exactly the dimension each was built for: 20 operations over two
> formats there, one operation over 83 formats here.

---

## Provenance

Every figure above is re-derivable from the repository rather than quoted from a
summary:

- takum: pass 45, recorded in `specs/numeric/related_work_measured.t27`
  (`THE_SAME_BOUNDARY_SEEN_TWICE`)
- numpy: pass 50, `specs/numeric/related_work_measured.t27`
  (`measurement NUMPY_VALIDATION_SETS`), read from numpy 2.4.4's own CSV headers
- lns16: pass 96, the UART log quoted verbatim in `trinity-fpga` issue #199, with the
  four-link Tier-E chain (CI run, bitstream SHA-256, UART log at 160000 baud,
  IDCODE `0x13636093`)

The three were written up in three different passes for three different reasons. That
they converge is the finding; it was not the aim of any of them.
