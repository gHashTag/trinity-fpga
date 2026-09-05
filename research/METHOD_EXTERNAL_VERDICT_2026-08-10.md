# The external test, finished: zero confirmed defects

Two iterations ago the checklist was run over four abstracts and reported two
defects. Both have now been checked against their sources. **Neither survives.**

## Defect A, withdrawn

The claim -- "posit64 obtains up to 4 orders of magnitude lower MSE than doubles"
-- was flagged under T8 as a best case presented as a general result.

**First problem: I attributed it to the wrong paper.** It is not in
arXiv:2505.19096, which I had checked. The search output had aggregated it from
elsewhere. Located properly, it is Big-PERCIVAL (arXiv:2305.06946), and the paper
text reads:

> "This is up to 4 orders of magnitude lower MSE **depending on the benchmark**."

> "The trend in **every** benchmark is a significantly lower error when using
> posit64 or posit32 numbers in comparison to floats or doubles."

> "The accuracy improvements are maintained across the whole range of problem
> sizes."

Both qualifications I said were missing are present. The best case is labelled as
a best case, and the general trend is reported separately. The abstract also
carries the authors' own counter-findings: the quire limits operation order, and
the hardware cost of 64-bit posit is called significant.

**And our own theorem agrees with them, not against them.** The benchmarks --
GEMM, LU, Cholesky, conjugate gradient on PolyBench -- operate on data near
unity, inside the 52-binade crossover our T9 analysis computes. posit64 winning
there is what T9 predicts.

## Defect B, already reclassified

The frequency claim was a constraint met, not a maximum measured (T14). The
measurement is sound and the wording invites a stronger reading. That is a
remark about phrasing, and a mild one.

## Verdict

| claim | after abstract | **after source** |
|---|---|---|
| A -- posit64, four orders | defect (T8) | **withdrawn; misattributed, and the qualifications are present** |
| B -- area up, frequency unchanged | defect (T3) | **wording only (T14); measurement sound** |
| C -- 46.8% LUT reduction | open (T1) | unread |
| D -- posit adders cost more | confirms T11 | unread |

**Zero confirmed defects in external work.** The method's external test has, so
far, found nothing wrong with anyone else's papers and two things wrong with its
own application.

## Theorem

**T16 (a search summary is not a source).** An aggregated search result may
combine claims from several papers into wording that appears in none of them, and
may drop the qualifications each original carried. A defect found in such a
summary is not attributable until the source is located and read. Both external
flags raised here came from aggregated output, and both dissolved on contact with
the papers.

## What this leaves

The method transfers in the weak sense that it can be applied to external work.
It has **not** been shown to find real defects there. What it has demonstrated,
twice in two iterations, is that it catches its own author -- once for reading a
compressed source at full strength, once for attributing a claim to a paper that
did not make it.

That is a smaller result than "the checklist finds defects in the literature",
and it is the one the evidence supports. Two papers read, two of our own errors
found, none of theirs.
