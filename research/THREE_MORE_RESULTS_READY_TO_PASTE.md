# Three more results, ready to paste

Section 5 of the checklist lists these as *"what the papers could claim and don't"*.
They are measured, they are in the repository, and neither preprint mentions any of
them. Each is one paragraph.

Every figure below was re-run on 2026-08-02 rather than quoted from a log — the last
two passes each caught a number written from recollection that turned out to be the
wrong one.

---

## 1. The P3109 cross-walk maps a layout, not values — and that is a stronger result

Paper B's abstract says the cross-walk maps each pack to its **corresponding**
standards-track configured format. It does not, and cannot: every `binaryKpP` value is
exactly **twice** its same-layout IEEE or OCP counterpart, because the working group
chose a different exponent bias.

This is not a caveat to bury. It is the strongest single piece of evidence that the
decode law is right.

> The IEEE P3109 working group's Interim Report is normative on this point: *"For
> signed formats, the exponent bias shall be B = 2^(K−P−1). For unsigned formats, the
> exponent bias shall be B = 2^(K−P)"*, and Annex A.5 states plainly that *"This
> differs from IEEE-754"*. We confirm the convention holds across **all 252
> configurations** published in their tables — 119 signed and 133 unsigned — against
> IEEE 754's `2^(e−1) − 1`. Comparing our packs against those tables directly,
> **258,524 finite codes differ, every one of them by the same factor of two, with a
> single distinct ratio across the whole comparison.** A decoder defect scatters; a
> constant offset against an independently generated standards-body table is two
> correct decoders reading two conventions. The cross-walk therefore maps layout, and
> the agreement on layout across a quarter of a million codes is what it demonstrates.

**Cost in the abstract: one word.** *"corresponding"* → *"same-layout"*.

---

## 2. Three exactness techniques, where most catalogues have one

The corpus does not carry a single notion of exactness. It carries three, chosen per
format family, and the third one closes on the papers' own algebraic anchor.

> Decode references in this catalogue return exact carriers rather than floating-point
> approximations, and use three distinct techniques according to what the format
> requires: exact rational arithmetic for the binary, decimal, integer and legacy
> families; the log domain where the format is logarithmic; and, for the ternary
> family, an algebraic ring **ℚ[φ]** in which values are exact by construction —
> closing on the same anchor `φ² = φ + 1` from which the catalogue's width law is
> derived. Sampling across **12 oracle modules and 19,110 values**, every carrier is
> exact and every denominator admissible.

The honest bound, which should travel with the claim: `extended` reports two formats
and zero values sampled, and `gf_mx` reports none. The result is **sampled, not
exhaustive**, and the repository says so in the same line that reports it.

---

## 3. Wide formats serialise as dyadic strings — an answer to a real problem

`gf1024` has a 632-bit mantissa. No IEEE double can hold one of its values, so the
usual way of publishing conformance vectors — a decimal literal a reader parses into a
`double` — fails outright above about 53 bits of significand.

> Vectors for formats wider than a double are published as exact dyadic strings of the
> form `A·2^B`, with an explicit `value_encoding` field naming the convention. This
> keeps every published value exact and machine-checkable at widths where a decimal
> literal parsed into a binary64 would already have lost the value — `gf1024` carries a
> 632-bit mantissa. We are not aware of another conformance corpus that states an
> encoding convention for values it cannot represent in a host float.

That last sentence is worth checking before printing. It is a claim about the
literature, and the literature scan behind it is in
`LITERATURE_SCAN_2024_2026.md`; soften it to *"we did not find another"* if the check
has not been repeated recently.

---

## Provenance

| result | re-derive with | figures |
|---|---|---|
| P3109 bias law | `python3 research/p3109_bias_law.py` | 252 configurations, 119 signed + 133 unsigned |
| P3109 cross-walk | `python3 research/crossval_p3109.py` | 258,524 finite codes, one distinct ratio, = 2 |
| exactness carriers | `python3 research/verify_oracle_exactness.py` | 12 oracles, 19,110 values, all exact |

The wide-format serialisation is a property of the published packs, which live in the
**`t27`** repository rather than this one: `value_encoding` appears in 22 files there
and in none here, because `conformance/` here holds the scripts and not the vectors.
A first draft of this line pointed at `conformance/vectors` in this repository, which
would have sent a reader looking for a field that is not there.
