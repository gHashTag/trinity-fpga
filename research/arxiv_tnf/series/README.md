# The Trinity S³AI paper series

Four papers cut from one manuscript, `../tnf_paper.tex`, in five renderings.

| | file | pages | what it claims |
|---|---|---|---|
| **A** | `paper-a-methodology.tex` | 33 | **How a comparison fails.** Six ways an arithmetic-hardware result reports success while having failed. The format is the worked example, not the subject. |
| **B** | `paper-b-format.tex` | 49 | **Ternary Network Floats.** The multiplier is removed rather than cheapened; the algebra is closed and machine-checked; the enumeration singling out φ is exhaustive at degree two. |
| **C** | `paper-c-record.tex` | 151 | **The record version.** The manuscript entire, cut nowhere. A and B are honest only if what they defer to is obtainable. |
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
- `\seriesemergencystretch` — and a redefined `\fussy`, below.

`placeins` was in the original preamble and is deliberately absent:
`\FloatBarrier` is used zero times in 8,061 lines, so it was a dependency the
build could fail on and never use.

**The ISQED rendering does not load it.** That is not an oversight and not a
style choice — the whole purpose of `trinity-series.sty` is to put the author's
identity on the page, and that rendering is double-blind. `paper-d-series` loads
it like everything else.

### Fifteen lines were set into the margin, and the build was green

An overfull box is a warning among hundreds and the build **exits 0**, so a line
can run 66pt into the gutter and nothing goes red. Fifteen did, across A, B, C
and `paper-d-series` — and **the ISQED rendering was the only one set
correctly**, because the repair had been written as a venue deformation.

Two causes, two homes:

- **Eleven were artefact paths.** `research/frontier/WITHDRAWAL_FMAX_UNSOURCED_2026-08-10.md`
  is one unbreakable 54-character word: cmtt is loaded with `\hyphenchar=-1`, so
  TeX has nowhere to break it and sets it into the margin. `\allowbreak` after
  each separator gives it somewhere, and adds no character — a reader who copies
  the line has to get the path back. This lived inside `fit_two_columns`, on the
  theory that a 3.5-inch column was what made the path overhang. It was not: the
  same path overhangs the 6.5-inch measure too. It is now `break_long_paths`,
  applied to **every** rendering, and idempotent so that `fit_two_columns` may
  still call it.
- **Four were ordinary prose**, and `\emergencystretch` is the instrument for
  those. **Setting it in the preamble does nothing on its own.** `\fussy`
  restores *plain TeX's* defaults, one of which is `\emergencystretch=0pt`, so
  the single `\fussy` that closes a deliberate `\sloppy` in the record version
  silently discards the preamble's value for the remaining 4,500 lines — and
  both of that paper's survivors sit after it. Measured, not guessed: with
  `\fussy` untouched, raising the value to **20em changed neither count**. The
  house style therefore owns the parameter and redefines `\fussy` to restore it.
  Swept: 0.1em and 0.25em clear one of the two, **0.5em clears both**, 1em buys
  nothing more.

All five papers now build with **0 overfull boxes**, same page counts.

## The ISQED rendering: three venue constraints, three mechanisms

ISQED 2027 (submission portal `softconf.com/p/isqed2027`) imposes what the rest
of the series does not, and each constraint is enforced by something that fails
the build rather than by care:

| the rule | the mechanism |
|---|---|
| minimum 4 and **maximum 10** pages, IEEE template, ≥10pt | `STRIP_FIGURES` drops the 78 canon plates (not one is `\ref`'d anywhere in 7,924 lines); the shared bibliography is pruned to what D actually cites, **31 of 94** entries at submission (97 since 2026-09-27, none of the three new ones cited by D); `fit_two_columns` makes tables written for a 6.5-inch line survive a 3.5-inch measure (`\footnotesize` plus `\adjustbox{max width=\columnwidth}`) |
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

## Two figures that were unsourced, and are now settled

Both were marked `\todo`: they appeared in the record version's abstract and
were derived nowhere in its 7,924-line body. **Settled 2026-09-22 against the
artefacts**, and the correction landed in the source manuscript, so the whole
series now prints one pair.

| the abstract said | it now says | the file |
|---|---|---|
| fifteen of twenty-eight clauses folded | **fourteen** of twenty-eight | `measurements/clauses_w983.json` |
| `3174·LUT^-0.648` over a 41× span | **`4397·LUT^-0.648`** over **39.6×** | `measurements/decoder_seed_spread_2026-08-19.json` |

The census carries a per-wrapper breakdown, `0+1+2+2+3+3+3`, which sums to
fourteen and agrees with its own totals block. Nothing in the tree carries
fifteen.

The frequency artefact holds twelve designs, eleven of which routed —
`d_posit8` failed synthesis — and those eleven span `396/10 = 39.6×`, with no
twelfth routed row to widen it to 41×. Four row sets were fitted looking for
3174: medians give `4397 / -0.6479 / 0.9203`, all 55 seed points give
`4343 / -0.6460 / 0.9212`, per-design means `4348`, the slowest seed `4073`.
The published exponent and R² fall out of the medians **exactly**, which is why
the coefficient stood unexamined for so long; no set reaches 3174, and the most
pessimistic one is still 28% above it. Across the repository `3174` occurs
sixteen times in the measurement files and every one is a digit substring of an
unrelated float.

Papers A and D already shipped the corrected pair — the correction was to the
record version, which is the one that had never derived them.

## A result that is the corollary, measured (2026-09-27)

Section `sec:t27block` ("A 27-level element on a trit substrate, measured") is
new in the manuscript, so it is in **B** and **C**, and one paragraph each in
the record abstract and in B's own abstract. It reports the pre-registered
trit-storage run of `specs/numeric/ternary_storage_search_v2.t27` (sha256
prefix `88fcf517`, committed at `49a84ade5`, verdict at `d31d8523c`).

| element | ppl, SmolLM2-135M | trits/32 | bits/32 |
|---|---:|---:|---:|
| T27 | 16.2892 | 101 | 161 dense |
| NVFP4 | 17.4697 | 106 | 144 |
| MX+ | 17.9780 | 106 | 141 |
| MXFP4 | 21.9353 | 102 | 136 |

**It is written as a measurement of an existing corollary, not as a new
advantage**, and the section says why in its own text:

- In bits T27 costs 161 against NVFP4's 144, and it lies 0.0037 below the
  NVFP4–E2M2 chord: level with binary formats that already exist. That is
  `cor:slackartefact` in perplexity. The corollary is stated for an exponent
  field; its proof only counts trits against the bits that hold them, so it
  carries over.
- On silicon it pays only if one native trit cell costs less than
  144/101 = 1.43 bit cells. The ternary compute-in-memory work it cites stores
  a trit in two.
- It is not TNF. T27 is a codebook with no exponent field, and TNF4_7 gives
  36.76 on the same run.

**Not in A, D or the ISQED rendering.** Their bodies changed only in the
`% ---- tnf_paper.tex lines A-B` header comments, because the line ranges
moved. Paper 66 is not revised.

`bibliography.tex` is now **generated** from the manuscript's
`thebibliography` block. It used to be a hand copy, and a hand copy is one more
place to forget an entry. `--check` fails if it drifts.

## The matched-width table, corrected (2026-09-27)

`tab:matchedwidth` counted TNF words that do not exist. `tnf_ref.decode` reads
an exponent field above the special row as an ordinary power of two, but
`tnf_ref.encode` sends every such magnitude to infinity. So no rounding and no
arithmetic ever produces those words. Enumerating all codes, as W991 did,
counted them anyway.

| rung | values (W991 → W993) | binades (W991 → W993) |
|---|---:|---:|
| TNF16, 19 bits | 516,096 → 323,584 | 127.0 → 79.0 |
| TNF8, 10 bits | 960 → 800 | 31.0 → 25.0 |
| TNF4, 6 bits | 56 → 28 | 14.6 → 6.6 |

- The source of the corrected figures is `measurements/matched_width_w993.json`
  (`python3 matched_width.py --write`). It supersedes the TNF rows of
  `compare_w991.json` and reproduces W991 exactly when every code is counted.
- The step column and the posit and takum rows do not change.
- "Unreachable" was quoted as 8,190. That is posit19's value count minus
  516,096, not a count of words. The words above the special row number 47 × 4,096
  = **192,512**. With the zero and special rows, **200,704** carry no finite
  non-zero value; that is paper B's figure.
- `verify_numbers.py` passed the old figure because its relative allowance
  overrode `tol=0`. `tol=0` is now exact. The same 3 earlier divergences remain,
  and no other check flipped.
- The conclusion gets stronger:
  - posit with es=2 still weakly dominates at every width;
  - at 10 and 6 bits posit with es=1 now dominates on every column.
- The manuscript says all this in a new paragraph, "A correction, and an instance
  of this paper's own failure mode".

**Where it lands.**

| rendering | what changed |
|---|---|
| A, C and D (series) | table, prose and the correction paragraph |
| C's abstract | 192,512 instead of 8,190 |
| B | the wording of its abstract only: "without a finite non-zero value" instead of "unreachable" |

**The ISQED rendering is frozen.** `make-series.py` now holds the sha256 of the
submitted `paper-d-isqed-body.tex` and `paper-d-isqed-newsection.tex` in
`FROZEN`. It checks both files against those hashes and does not write them.
`bibliography-anon.tex` and the double-blind gate read the frozen text, and the
build prints how many lines a fresh rendering would change.

Paper 66 therefore still carries the old table. Whether to send the venue an
erratum, or fix it at camera-ready, is the owner's call.

## Where these go

`paper-d-isqed` goes to ISQED 2027. Paper C is the citable record, for Zenodo.
`paper-d-series` is how D reads inside the series.

An accepted ISQED paper produces a resolving IEEE Xplore DOI, which is what arXiv's
moderators asked for before they will consider the appeal on ticket MOD-102933
(1 September 2026) — with one caveat that should not be glossed: their letter
requires acceptance **in a peer-reviewed journal**, and a refereed *conference*
DOI is stronger than Zenodo but is not a literal match. **A Zenodo DOI does not
satisfy that condition at all.**

**`paper-d-isqed` was submitted to ISQED 2027 on 22 September 2026 — paper 66**,
under Design, Test and Verification, topic *assertion- and simulation-based
design verification*. The uploaded file was verified by reading it back off the
portal (344894 bytes, `application/pdf`), not by believing the upload form. The
submission is revisable until the deadline; the details are in
`SUBMISSION-ISQED-2027.md`.

Nothing else here has been deposited or sent. Paper C still has no Zenodo DOI,
and nothing has gone back to arXiv.
