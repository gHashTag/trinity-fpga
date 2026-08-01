# Start here

This directory holds work on the two GoldenFloat preprints —
[arXiv:2606.05017](https://arxiv.org/abs/2606.05017) and
[arXiv:2606.09686](https://arxiv.org/abs/2606.09686). It has grown across many
sessions and now holds about fifty documents. Most of them are working notes. **Eight
are meant for you**, and this page says which, in what order, and what each costs.

---

## If you have ten minutes

Read **[`SUBMISSION_CHECKLIST.md`](SUBMISSION_CHECKLIST.md)** and nothing else. It is
one page, ordered by value-per-effort, and every line names where to verify it. Its
§7 says which claims were re-checked recently and which were not, so you can tell
fresh evidence from old.

## If you are preparing a replacement

In this order:

| # | file | what it is | cost to apply |
|---|---|---|---|
| 1 | [`SUBMISSION_CHECKLIST.md`](SUBMISSION_CHECKLIST.md) | the decisions, ranked | reading |
| 2 | [`ARXIV_ABSTRACTS_READY_TO_PASTE.md`](ARXIV_ABSTRACTS_READY_TO_PASTE.md) | replacement abstract text | paste |
| 3 | [`BIBLIOGRAPHY_FIXES.md`](BIBLIOGRAPHY_FIXES.md) + [`CORRECTED_BIBITEMS.tex`](CORRECTED_BIBITEMS.tex) | **20 reference defects** — 8 in Paper A, 12 in Paper B — with the LaTeX to replace them | paste |
| 4 | [`ARXIV_BODY_FIXES_READY_TO_PASTE.md`](ARXIV_BODY_FIXES_READY_TO_PASTE.md) | body corrections — **line numbers point into `main_ru.tex`**, not the preprint | paste, then re-locate |
| 5 | [`RELATED_WORK_READY_TO_PASTE.md`](RELATED_WORK_READY_TO_PASTE.md) | related-work paragraphs, measured rather than asserted | one section |

## If you want to make the papers stronger rather than only correct

Two results are finished, verified and absent from both preprints. Each is one
paragraph.

- **[`ONE_ULP_BOUNDARY_READY_TO_PASTE.md`](ONE_ULP_BOUNDARY_READY_TO_PASTE.md)** — three
  independent routes (a third-party library, numpy's own validation sets, and silicon)
  reach the same limit. Turns an apparent weakness into a stated boundary.
- **[`VERIFICATION_METHOD_READY_TO_PASTE.md`](VERIFICATION_METHOD_READY_TO_PASTE.md)** —
  how the suite was checked against being *uniformly* wrong: three structurally
  distinct oracles per operation, a negative control, and the reproduction showing why
  a 512/512 bit-exact hardware result bounded the vectors rather than the cell.
- **[`THREE_MORE_RESULTS_READY_TO_PASTE.md`](THREE_MORE_RESULTS_READY_TO_PASTE.md)** —
  the P3109 cross-walk (**one word** in Paper B's abstract, and the change *strengthens*
  the claim), the three exactness techniques, and how vectors wider than a `double` are
  published at all.

## If a claim is disputed

**[`VERIFICATION_DOSSIER.md`](VERIFICATION_DOSSIER.md)** carries the evidence for each,
and **[`README.md`](README.md)** says how to re-run every script that produced a
number, what it should print, and what it needs installed.

---

## What the rest of this directory is

About forty other documents, from earlier sessions and other lines of work — LUT
comparisons, format leaderboards, session reports, competitive scans, draft papers.
Some are current, some are superseded, and **their currency has not been checked**.
They are not part of the seven above and nothing here depends on them.

Two ways to tell what you are looking at:

- Anything a checklist line points to is current, because §7 records when each was
  last verified.
- `git log -1 --format=%ad -- research/THE_FILE.md` gives the last time a document was
  touched. The seven above are the recently-touched ones.

---

## The honest summary

The science holds. Across many passes of checking, nothing in the results was found to
be wrong. The defects are in **citations** and in **things left unsaid** — a reference
list where nine of twelve arXiv identifiers resolve to different works than the titles
claim, an abstract reporting the central contribution at about seven per cent of its
actual coverage, and several strong results that appear nowhere in either paper.

That is a good position to be in, and it is worth one replacement round.
