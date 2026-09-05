# The tekum specification, finally read — and what it does to our oracle

`conformance/tekum_ref.py` has said since it was written that the full paper was
unavailable and its model was reverse-engineered from takum's field layout. The
paper's HTML (arXiv:2512.10964) is fetchable, and Definition 8 was extracted on
2026-08-18. Two facts in it make the existing oracle unsalvageable as a tekum
model — not approximately wrong, but a different object.

## What the paper says (extracted quotes)

**Layout** (Definition 8): a tekum is trits `r ++ e ++ f` after anchoring, with

* regime `r`: 3 trits, `r := int3(r) ∈ {−7,…,7}`
* exponent: `c := max(0, |r| − 2)` trits, `c ∈ {0,…,5}`
* fraction: `p := n − c − 3` trits

**Value**: `θ_n(t) := s · (1 + f) · 3^e` with `f = 3^(−p) · int_p(f) ∈ (−0.5, 0.5)`,
`e = int_c(e) + b`, and the bias table

| \|r\| | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 |
|---|---|---|---|---|---|---|---|---|
| b | 0 | 1 | 2 | 4 | 10 | 28 | 82 | 244 |

(`b := sign(r)·⌊3^(|r|−2) + 1⌋`, signed by the regime.)

**Sign**: no sign trit. `s := sign(int_n(t))` — balanced ternary negates by
digit inversion, so negation is exact and free.

**Width**: `n ∈ 2ℕ₁, n ≥ 8`, counted in **trits**. "tekum16" is 16 trits.

**Specials**: all-T is NaR, all-0 is zero, all-1 is ∞.

**Anchor**: `anc_n(t) = |t| − 1T⋯1T`. Worked example from the paper's Table 3:
`t = 1T1T` anchors to zero, giving `r = c = e = f = 0` and the value exactly 1.0.

## Why the existing oracle cannot be repaired into this

1. **The base is 3.** The real value is `(1+f)·3^e`. Our model computes
   `(1+m)·2^c`. No reinterpretation of binary fields lands on powers of three.
2. **The code space is 3^n, not 2^n.** tekum16 has 3^16 = 43,046,721 codes.
   Our "tekum16" enumerates 65,536 binary words — 0.15% of the real code space,
   and none of them is a trit string.
3. **The width unit is trits.** tekum16 carries 16·log2(3) ≈ 25.4 bits of code
   space. Every comparison "GF-T16 (17 bits) vs tekum16 (16)" was mis-widthed in
   BOTH directions at once: our side was wider than named, and the opponent —
   had it been real — would have been wider still.
4. **Negation is digit inversion**, not a sign bit and not takum's complement.
   The value set is exactly symmetric and the sign costs zero storage.

Everything measured against "tekum16" in this repository was measured against a
linear binary model of takum's field layout (see #606 for that model's own
correction). It shares with tekum neither base, nor code space, nor width unit,
nor sign convention.

## What blocks a true oracle, precisely

One construction: the anchor function. `anc_n(t) = |t| − 1T⋯1T` subtracts the
trit string `1T` repeated from the absolute value, and the paper's surrounding
text (how the anchored integer is re-split into `r ++ e ++ f`, and how the
{−7..7} regime range follows from 3 trits that could hold [−13,13]) did not
survive HTML extraction unambiguously. Implementing around that gap is how the
last wrong oracle happened, so it is left as the single named blocker rather
than guessed at. The two extractions above are consistent with each other on
every other point.
