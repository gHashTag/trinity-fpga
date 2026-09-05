# arXiv submission draft — NOT SUBMITTED

Nothing has been uploaded. This is the form, filled in, for you to check and send.

---

## 1. Title

```
Ternary Network Floats: a multiplier-free weight lattice, and what it does not buy
```

Alternatives, if you want the negative result further forward:

- `A multiplier-free ternary weight lattice, and a matched-width comparison that goes against it`
- `Ternary Network Floats: closure removes the multiplier; matched width removes the precision claim`

## 2. Authors

```
[ your name ], [ affiliation or "independent" ]
```

## 3. Abstract

Use the abstract **from the compiled `tnf_paper.tex`**, not `abstract_arxiv.txt` —
that file is stale (it says twenty formats where the paper says twenty-one, eight
ours where the paper says nine, five retractions where the paper says twenty-two,
and it carries no budget convention at all).

`abstract_arxiv.txt` should be regenerated from the `.tex` before submission or
deleted. It is currently a fourth version of the abstract, and the one a reader
meets first.

## 4. Categories

| | category | why |
|---|---|---|
| **primary** | `cs.AR` — Hardware Architecture | the result is a datapath and an FPGA measurement |
| cross-list | `cs.MS` — Mathematical Software | the oracles and the closure proof |
| cross-list | `cs.LG` — Machine Learning | the quantisation and training results |

`math.NA` / `cs.NA` is defensible instead of `cs.MS` if you want the numerical
analysis audience; posit and takum papers usually sit in `cs.AR` or `cs.MS`.

## 5. Comments field

```
146 pages, 89 figures, 61 tables. Reference implementations and the derivation
harness are released; every published figure is recomputed from committed records
by a single script (679 checks). Twenty-two retractions of the authors' own
claims are marked in place.
```

The retraction count is worth stating in the comments. It is unusual, it is true,
and a referee who sees it before the abstract reads the rest differently.

## 6. Licence

`CC BY 4.0` unless you have a reason otherwise. It is the default that lets the
reference implementations be reused, which is most of the point.

## 7. What is uploaded

Source package, not PDF-only — arXiv should compile it, so the source stays
checkable:

```
arxiv_submission/
  tnf_paper.tex          the paper, single file, no \input
  canon/*.png            80 plates, 8-bit greyscale, 200 dpi
  tnf_*.pdf              9 vector figures
```

**21.9 MB, against a 50 MB limit.** Verified: it compiles standalone with
tectonic to 146 pages and 22.46 MB, with no missing figure and no undefined
reference.

---

## Before you press submit

**1. The stale `abstract_arxiv.txt`.** Named above. It is the most likely thing
to embarrass you, because it is the file whose name says "this is the abstract".

**2. One takum code still disagrees.** Our oracle matches libtakum on 65,534 of
65,535 codes. The paper says so. If Hunhold replies to the letter before you
submit, the answer may be worth folding in; if not, the sentence stands as it is
and is honest.

**3. The endorsement.** arXiv `cs.AR` needs one if this is your first submission
in that archive. That is a separate conversation from the review request, and the
letter deliberately does not mix them.

**4. Read section `sec:matchedwidth` last, aloud.** It is the section a referee
will attack first, it was written in one pass, and it is the newest text in the
paper.

**5. The figures are 200 dpi.** That was to bring the PDF under 25 MB for email.
arXiv allows 50, so if you would rather submit at the original 270 dpi, the
plates are upstream in `research/arxiv_tnf/canon/` and the package rebuilds to
about 30 MB — still inside the limit. **This is a real choice, not a formality:
200 dpi is fine on screen and visibly soft in print.**
