# The Trinity S³AI paper series

Three documents cut from one manuscript, `../tnf_paper.tex`.

| | file | pages | what it claims |
|---|---|---|---|
| **A** | `paper-a-methodology.tex` | 33 | **How a comparison fails.** Six ways an arithmetic-hardware result reports success while having failed. The format is the worked example, not the subject. |
| **B** | `paper-b-format.tex` | 47 | **Ternary Network Floats.** The multiplier is removed rather than cheapened; the algebra is closed and machine-checked; the enumeration singling out φ is exhaustive at degree two. |
| **C** | `paper-c-record.tex` | 149 | **The record version.** The manuscript entire, cut nowhere. A and B are honest only if what they defer to is obtainable. |

Build any of them with `pdflatex <name>` twice.

## One generator, not three hand-cuts

`make-series.py` is the only place the cut is written down — line ranges, the
canon-plate conversion, and the cross-paper reference table. `--check`
regenerates into memory and fails if the files on disk have drifted, so the
bodies cannot be edited by hand without the next run saying so.

```bash
python3 make-series.py          # regenerate the three bodies
python3 make-series.py --check  # fail if disk differs from generated
```

The three `paper-*-body.tex` files and `paper-c-abstract.tex` are **generated**.
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
the log. Current state: **0 undefined references in all three papers.**

## The house style is one file

`trinity-series.sty` holds the shared identity, because three preambles would
drift and the drift would be invisible until two papers disagreed in print.

- `\seriesplate{TITLE}{SUBTITLE}` — the common title page. Every paper opens
  with the same wordmark, the same logo and the same author block; only the two
  arguments differ.
- `\triptych{file}{caption}{label}` — the canon plates are three-panel
  engravings sharing one footer. 98 of them across the series, set identically.
- `\companion{…}` / `\record{…}` — the cross-paper pointers above.
- `\graphicspath` — the nine generated plots live one directory up. Without it
  pdflatex substitutes an empty draft box per missing plot and **still exits 0**.

`placeins` was in the original preamble and is deliberately absent:
`\FloatBarrier` is used zero times in 7,924 lines, so it was a dependency the
build could fail on and never use.

## Two figures the author must settle before anything is deposited

Both are marked `\todo` in `paper-a-newsection.tex` and in
`paper-c-record.tex`. They are stated rather than smoothed over.

| the abstract says | the artefact says | file |
|---|---|---|
| fifteen of twenty-eight clauses folded | **fourteen** of twenty-eight | `measurements/clauses_w983.json` |
| `3174·LUT^-0.648` over a 41× span | exponent and R² reproduce exactly; the coefficient is **4397** over **39.6×** | `measurements/decoder_seed_spread_2026-08-19.json` |

Neither result was derived anywhere in the 7,924-line body — both existed only
as assertions in the abstract. Paper A now derives them, with the files named.

## Where these go

Paper A is the one most likely to survive review, and therefore the one that
produces the resolving DOI arXiv's moderators require before they will consider
an appeal (ticket MOD-102933, 1 September 2026). **A Zenodo DOI does not satisfy
that condition** — the letter requires acceptance in a peer-reviewed journal.
Paper C is the citable record, for Zenodo.
