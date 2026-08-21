# Ready-to-paste README section — how the corpus achieves exactness

> Produced 2026-07-31, pass 43. Third in the ready-to-paste series, after
> `ARXIV_ABSTRACTS_READY_TO_PASTE.md` and `ARXIV_BODY_FIXES_READY_TO_PASTE.md`.
>
> **Why this exists.** Five verified properties of the corpus appear in **no
> document anywhere** — not in arXiv:2606.05017, not in arXiv:2606.09686, not in
> `gHashTag/t27/conformance/vectors/README.md` (326 lines), not in the t27 root README (726
> lines). They were measured during a 43-pass verification campaign and live only
> in `specs/numeric/`.
>
> **Target:** `gHashTag/t27/conformance/vectors/README.md`, after *Shared row schema*. That file
> is the natural home — it already documents the schema, SHA-256 and provenance,
> and it is what a consumer of the packs reads.
>
> Every number below is measured; the spec holding each measurement is named.

---

## Exactness: how each family avoids approximating

A conformance pack is only as good as the reference that produced it. Some numeric
formats have values that **cannot** be written as a finite decimal or a float
without loss, so "bit-exact" needs a carrier that can actually hold them. This
corpus uses three, chosen per family rather than one applied everywhere.

| carrier | families | why |
|---|---|---|
| **Exact rational** — `fractions.Fraction` | IEEE-like, GF, int, fp8, mxfp, posit, decimal, legacy — 12 oracles | their values are `(1 + M/2^m)·2^c` or `k/10^n`, so a rational holds them exactly. posit qualifies too: `useed^k · 2^e · (1+f)` is all powers of two |
| **Exact in the logarithmic domain** | LNS | `value = ±2^L` is irrational for most `L`. Instead of approximating it, the oracle returns the exact `log2(|value|)` as a `Fraction` — the stored field is dyadic — and carries the sign separately |
| **Exact in an algebraic ring** | GFTernary | values are `{−φ, 0, +φ}`, and φ is irrational. `PhiVal` holds `a + b·φ` with rational `a, b`; multiplication closes in ℚ[φ] via `φ² = φ + 1`, so a product of exact elements is again exact |

Verified: **19,106 sampled codes across the 12 rational-carrier oracles produced
zero float returns and zero inadmissible denominators.**
(`specs/numeric/oracle_fidelity_map.t27`)

Where a value genuinely cannot be represented, the oracle says so rather than
rounding quietly — the LNS decode returns a `special:irrational` marker, which is
why that family reports fewer finite codes than its width suggests.

## Values wider than a double

Six GoldenFloat rungs exceed what IEEE binary64 can hold. `gf128` already has
M = 78 against binary64's 52, and `gf1024` carries a 632-bit mantissa — a binary64
lowering **would round**. Their packs therefore carry the value as a string with an
explicit `value_encoding` field rather than as a JSON number, in one of two forms:

| `value_encoding` | form | vectors |
|---|---|---|
| **`dyadic`** | an exact literal `A*2^B` — no rounding possible | **2046** |
| `decimal` | a decimal expansion | 35 |

`dyadic` is the dominant and the stronger form: it keeps the value exactly, since
every finite GoldenFloat value is an exact dyadic rational. `gf256` uses it
exclusively; the other five rungs use both.

A JSON number would silently become a float64 in most parsers and lose the value.
Consumers must read `value_encoding` and parse accordingly.

This is the corpus's answer to a question the field has generally left open: how to
publish bit-exact conformance vectors for formats wider than a double.

## Multi-limb formats

`double_double` and `quad_double` are error-free expansions — a value is the exact
sum of 2 or 4 binary64 limbs (Bailey / Hida / Briggs / Dekker). The property that
makes such an expansion well-formed is **non-overlap**: each limb must not intrude
on its predecessor's significand, `|limb[i+1]| ≤ ulp(limb[i]) / 2`. Overlapping
limbs still sum to the right value but are not canonical — one value gains many
representations and round-trip stops being well defined.

Verified on a constructed stress set (separations from 2^20 to 2^200, values
needing more than 53 and more than 106 bits, near-ties at a power of two): both
formats hold non-overlap, with exact round-trip.
(`specs/numeric/oracle_fidelity_map.t27`)

Not exhaustive — 2^128 and 2^256 cannot be enumerated.

## Cross-validation against a third party

The packs are cross-validated against **ml_dtypes 0.5.4** (Google/JAX) for every
format both sides implement. The check is **exhaustive, not sampled**: all
**66,224** codes across bfloat16, fp8 E4M3FN, fp8 E5M2, fp4 E2M1, fp6 E2M3, fp6
E3M2, int4 and uint4 — **zero divergences**.
(`specs/numeric/ml_dtypes_crossval.t27`)

One limitation worth stating: the oracles decode to `fractions.Fraction`, which
cannot represent −0.0, so **signed-zero semantics are outside what these packs can
attest to**. Fourteen zero codes are affected, and they are counted separately
rather than reported as agreement.

---

### Notes for whoever applies this

- The three-carrier table is the part most worth keeping if space is tight. It is
  the corpus's most distinctive engineering decision and currently invisible.
- `takum` and `tekum` are deliberately **not** listed under any carrier above.
  Their oracles document themselves as linear structural models rather than
  implementations of the logarithmic formats, so they belong in a separate
  sentence if one is added — see `specs/numeric/oracle_fidelity_map.t27`.
- The signed-zero limitation is included on purpose. Omitting it would leave the
  cross-validation claim stronger than the evidence.
