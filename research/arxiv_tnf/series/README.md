# The Trinity S³AI paper series

Four papers cut from one manuscript, `../tnf_paper.tex`, in five renderings.

| | file | pages | what it claims |
|---|---|---|---|
| **A** | `paper-a-methodology.tex` | 33 | **How a comparison fails.** Six ways an arithmetic-hardware result reports success while having failed. The format is the worked example, not the subject. |
| **B** | `paper-b-format.tex` | 47 | **Ternary Network Floats.** The multiplier is removed rather than cheapened; the algebra is closed and machine-checked; the enumeration singling out φ is exhaustive at degree two. |
| **C** | `paper-c-record.tex` | 149 | **The record version.** The manuscript entire, cut nowhere. A and B are honest only if what they defer to is obtainable. |
| **D** | `paper-d-series.tex` | 27 | **How a comparison fails, while every measurement is correct.** A without its revision notes: the two measurements, the six failure modes, the worked example. |
| | `paper-d-isqed.tex` | 10 | **The same paper for ISQED 2027.** The same cut under the three constraints that venue imposes. |

Build any of them with `pdflatex <name>` twice.

## One style, because it is one body of work

**Every paper opens with the same title plate, the same logo and the same
triptych plates.** Three documents that looked like three projects would read as
three, and the series has one claim to make, not four.

The ISQED rendering is the sole exception and it is a *rendering*, not a
judgement that the house style was wrong: the venue is double-blind, and the
whole purpose of a title plate is to say who wrote the thing. `paper-d-series`
and `paper-d-isqed` are one cut and one rewrite list, generated together, so the
conference version cannot quietly become a different paper.

A paper id in `make-series.py` therefore names a rendering. `CUT` maps it to its
line ranges, `WRAPPERS` lists the files it is assembled from — listed and not
globbed, because `paper-d-*.tex` matches the ISQED rendering's files too, and a
gate that reads one document while reporting on another is the defect this
paper is about.

## One generator, not four hand-cuts

`make-series.py` is the only place the cut is written down — line ranges, the
canon-plate conversion, and the cross-paper reference table. `--check`
regenerates into memory and fails if the files on disk have drifted, so the
bodies cannot be edited by hand without the next run saying so.

```bash
python3 make-series.py          # regenerate the four bodies
python3 make-series.py --check  # fail if disk differs from generated
```

The five `paper-*-body.tex` files, `paper-c-abstract.tex`,
`paper-d-isqed-newsection.tex` and `bibliography-anon.tex` are **generated**.
Edit `make-series.py` or the source manuscript, never them.

## Why cross-references are a program and not a search-and-replace

Splitting a document breaks every `\ref` whose `\label` went elsewhere. LaTeX
sets those as `??`, prints a warning among hundreds of others, and **exits 0** —
so a split silently degrades its own text and the build still passes.

There were 83 such references. Each is rewritten into a named pointer:

> …the no-survivors corollary of **the taper-catalogue section of the companion
> paper *Ternary Network Floats*** does not survive being restated…

The destination is decided by what the assembled document actually defines, not
by a static table, so moving a section between A and B moves its pointers with
it. A label the table does not cover is reported as an error rather than left to
the log. Current state: **0 undefined references in all four papers.**

One pointer per reference is right; seven in a row is not. The source wrote
"Theorem 3, Theorem 5, Theorem 7" — short, because a number is short — and the
substitution that reads well once produced twelve identical words seven times in
a single sentence. `collapse_pointer_runs` strips the qualifier from every item
of a list but the last, because English already distributes a trailing qualifier
over a list.

## The house style is one file

`trinity-series.sty` holds the shared identity, because five preambles would
drift and the drift would be invisible until two papers disagreed in print.

- `\seriesplate{TITLE}{SUBTITLE}` — the common title page. Papers A, B, C and D
  open with the same wordmark, the same logo and the same author block; only the
  two arguments differ.
- `\triptych{file}{caption}{label}` — the canon plates are three-panel
  engravings sharing one footer. 108 of them across the series, set identically.
- `\companion{…}` / `\record{…}` — the cross-paper pointers above.
- `\graphicspath` — the nine generated plots live one directory up. Without it
  pdflatex substitutes an empty draft box per missing plot and **still exits 0**.

`placeins` was in the original preamble and is deliberately absent:
`\FloatBarrier` is used zero times in 7,924 lines, so it was a dependency the
build could fail on and never use.

**The ISQED rendering does not load it.** That is not an oversight and not a
style choice — the whole purpose of `trinity-series.sty` is to put the author's
identity on the page, and that rendering is double-blind. `paper-d-series` loads
it like everything else.

## The ISQED rendering: three venue constraints, three mechanisms

ISQED 2027 (submission portal `softconf.com/p/isqed2027`) imposes what the rest
of the series does not, and each constraint is enforced by something that fails
the build rather than by care:

| the rule | the mechanism |
|---|---|
| minimum 4 and **maximum 10** pages, IEEE template, ≥10pt | `STRIP_FIGURES` drops the 78 canon plates (not one is `\ref`'d anywhere in 7,924 lines); the shared bibliography is pruned to what D actually cites, **31 of 94** entries; `fit_two_columns` makes one-column material survive a 3.5-inch measure |
| **double-blind** — *"Manuscripts identifying author names and/or affiliations will be rejected without review"* | `IDENTIFYING` is grepped over the body, the wrapper, the bibliography **and the rendered PDF**; a hit is an error, not a warning |
| it stands alone | `STANDALONE` routes every departing reference to `\extended` — *"the extended version of this work"* — which is true, checkable after acceptance, and says nothing about who wrote it |

Under double-blind, "see the companion paper" identifies the author as surely as
a signature: there is no companion in the reviewer's hands, so the phrase can
only mean *another paper by us*.

### The gate that passed while the PDF named the project

The source gate was green on a manuscript whose page 3 read, in extractable
text:

> TRINITY S3AI — the cognitive stack rooted in the identity φ²+φ⁻² = 3

Two independent holes, both worth keeping written down because the paper the
gate protects is *about* checks that cannot fail:

1. **It read the wrong artefact.** The wordmark is drawn *inside* the figures by
   `canon_style.py`, so it is vector text in an included plot — invisible to any
   grep of the `.tex` files and perfectly visible to a reviewer, to `pdftotext`,
   and to a moderator's search. `pdf_gate()` now reads the PDF, and reports a
   missing PDF instead of passing quietly, because a gate that goes silent when
   its input is absent is the folded-clause defect from Section II of the paper
   itself.
2. **The patterns were case-sensitive.** `/Trinity\s*S3AI/` matches neither
   `Trinity S\textsuperscript{3}AI` (how the sources write it) nor
   `TRINITY S3AI` (how the figures draw it) — it matched no form that actually
   occurs. A name is the same name in any case.

`make-anon-figures.py` fixes the figure at the point the line is drawn
(`CANON_ANON=1`), and takes the figures **the ISQED rendering's own body asks
for** rather than a hardcoded list. It runs the real generator and restores the
originals afterwards, so the anonymous plot cannot drift from the one in A, B, C
and `paper-d-series`, and so the papers that are *supposed* to carry the
wordmark keep it.

```bash
python3 make-anon-figures.py          # write series/anon/*.pdf
python3 make-anon-figures.py --check  # fail if they are stale
```

The two self-citations are kept and anonymised rather than deleted: public prior
work may be cited under double-blind — a non-author would cite it the same way —
but a personal repository URL is not a citation, it is a signature.

## Two figures the author must settle before anything is deposited

Both are marked `\todo` in `paper-a-newsection.tex` and in
`paper-c-record.tex`. They are stated rather than smoothed over.

| the abstract says | the artefact says | file |
|---|---|---|
| fifteen of twenty-eight clauses folded | **fourteen** of twenty-eight | `measurements/clauses_w983.json` |
| `3174·LUT^-0.648` over a 41× span | exponent and R² reproduce exactly; the coefficient is **4397** over **39.6×** | `measurements/decoder_seed_spread_2026-08-19.json` |

Neither result was derived anywhere in the 7,924-line body — both existed only
as assertions in the abstract. Paper A now derives them, with the files named.

**Both renderings of D ship the artefact-correct numbers.** D is a new paper to
a new reader, so it is the one place where the choice is free of an erratum; if
the author settles the disagreement the other way, D's abstract must change with
it — in both files, which is why the two share one generator and one cut.

## Where these go

`paper-d-isqed` goes to ISQED 2027. Paper C is the citable record, for Zenodo.
`paper-d-series` is how D reads inside the series.

An accepted ISQED paper produces a resolving IEEE Xplore DOI, which is what arXiv's
moderators asked for before they will consider the appeal on ticket MOD-102933
(1 September 2026) — with one caveat that should not be glossed: their letter
requires acceptance **in a peer-reviewed journal**, and a refereed *conference*
DOI is stronger than Zenodo but is not a literal match. **A Zenodo DOI does not
satisfy that condition at all.**

Nothing here has been submitted, deposited or sent.
