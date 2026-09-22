# ISQED 2027 — submitted, paper 66

**Filed 22 September 2026, three days inside the deadline.** Everything the
softconf form asks for is written out below; it is kept as the record of what
was entered, because a revision before the deadline re-enters all of it.

## What was filed

| | |
|---|---|
| confirmation number | **66** |
| passcode | held by the owner, not written down here — it is the credential that revises the submission |
| title | as below, unchanged |
| authors, as the portal holds them | Dmitrii Vasilev |
| subject track | Design, Test and Verification (DTV) |
| subject topic | Hardware and software formal-, assertion-, and simulation-based design verification techniques |
| file | `paper-d-isqed.pdf`, **344894 bytes** |

The file was verified **after** upload rather than on the form's own report:
`getAttachment` returns `application/pdf`, `%PDF-1.7`, 344894 bytes — byte count
identical to the local artefact. A form that says `ok` and stores nothing is the
failure this paper is about, and it happened twice to the tooling that filled
this form, so no field was trusted until it was read back.

The abstract went in as **pure ASCII** — `--` for the em dash, `x` for `×`,
`^-0.648`, `R^2`. The portal is not UTF-8 clean: its own country list renders
Réunion as `RÃ©union`, so anything non-ASCII would reach reviewers mangled.

The track is the one revisable choice. It was picked because the headline result
is that on-die **assertions** are folded away by synthesis and the verdicts then
read PASS — that is assertion-based design verification, not EDA tooling. EDA
Tools and Methodologies was the alternative considered.

## Where

`https://softconf.com/p/isqed2027` — the account is `t27_dev`, created
2026-09-22. Softconf's user database is shared across every conference it hosts,
which is why the obvious usernames were already taken by strangers.

## When

| the source | the date |
|---|---|
| the live call for papers, read 2026-09-22 | **Sept. 25, 2026** |
| Ali Iranmanesh, by mail, 2026-09-20 | *"We will extend the deadline until mid October"* |

The original date was 17 September and it passed unsubmitted. The 25th already
*is* an extension. **Submitted against the 25th, on the 22nd.** The mid-October
extension is a promise from the general chair and is very probably real, but the
portal enforces whatever date is configured in it, not what is in the mail
thread, and submitting early cost nothing — the submission stays revisable until
the portal closes.

The submission page banners the conference as **April 14-16, 2027, San
Francisco** — one day narrower than the 14–17 April in the call for papers.

## The file

`paper-d-isqed.pdf` — build with `pdflatex paper-d-isqed` twice.

Checked on 2026-09-22 against the three things this venue can reject for:

- **10 pages**, against a stated minimum of 4 and maximum of 10.
- **Double-blind.** `pdftotext paper-d-isqed.pdf | grep -icE
  'trinity|t27|vasilev|dmitrii|ghashtag|orcid'` → **0**. This is checked on the
  rendered PDF and not on the sources, because the wordmark is drawn *inside*
  the figures by `canon_style.py` — a grep of the `.tex` files passes while
  page 3 reads `TRINITY S3AI` in extractable text.
- **0 overfull boxes, 0 undefined references, 0 undefined citations.**

## Title

> How an Arithmetic Comparison Fails While Every Measurement in It Is Correct

## Abstract

Paste from the PDF, or from `paper-d-isqed.tex`. It is one paragraph and it
carries the two measurements:

> Two conditions decide whether a published FPGA arithmetic comparison means
> what it appears to mean, and both are usually left unmeasured. First, on-die
> assertions are the standard defence against a design that routes and is
> wrong, and synthesis silently removes them: a census of twenty-eight clauses
> across seven wrappers finds fourteen folded to constants, and a clause that
> has become a constant reads PASS in every build, including the failing ones.
> Repairing one wrapper so that its clauses survive raises it from 452 to 696
> LUT — thirty-five per cent of the routed design was absent from the area that
> had been published for it. Marking cells `(* keep *)` does not fix this;
> making the operands structurally distinct while carrying equal values does.
> Second, achieved frequency is largely a function of size: over eleven designs
> placed and routed across five seeds each and spanning a 39.6× range of area,
> F_max = 4397 · LUT^-0.648 with R² = 0.920, so a throughput-per-area ratio
> divides a quantity by a second that is already a function of it and restates
> a ranking by size. Neither result invalidates a frequency measurement; both
> invalidate figures built from them. We then give six ways an evaluation
> reports success while having failed, worked through a case in which every
> individual measurement is correct and the comparison is not, and state which
> of our own published claims each one withdraws.

## Index terms

FPGA arithmetic · design evaluation · synthesis optimisation · assertion
coverage · reproducibility · figure of merit

## Author, for the portal's own fields and not for the manuscript

Dmitrii Vasilev · ORCID 0009-0008-4294-6159 · admin@t27.ai

The manuscript itself carries none of this, by design. Put it only in the
portal fields, which reviewers do not see.

## Correspondence

Questions go to `ali1@isqed.org`, and the confirmation number belongs in every
letter. Notification is 22 January 2027.

## Two answers already in hand, so they need not be asked again

- **Remote presentation.** Ali Iranmanesh, 2026-09-20: *"Yes you can present
  remotely through zoom."* Worth noting in the submission comments.
- **Concurrent submission.** There is none. Microprocessors and Microsystems
  declined the parent manuscript (MICPRO-D-26-00839) on 2026-09-20, editorially
  and without external review. The Elsevier-footnote arrangement Paul Wesling
  proposed is therefore moot and its own fallback applies: the IEEE footer and
  the ordinary Xplore deposit.

## One question still open, and it blocks the Zenodo deposit

**May the record version be posted publicly while paper 66 is under blind
review?** The call for papers says reviewing is blind and that authors must keep
names and affiliations out of *the manuscript and abstract* — which is satisfied
and was checked. It says nothing about preprints.

The risk is not the manuscript, it is the match. The Zenodo record carries the
author's name and ORCID, and both of paper 66's headline constants — `4397` and
`0.648` — appear in it. One search on either number identifies the author of a
blind submission.

IEEE's own policy would settle this — preprints are explicitly *not* prior
publication there — but it names arXiv, TechRxiv and not-for-profit servers
approved by the PSPB, and Zenodo's presence on that list is not established.
More to the point, **ISQED is produced by the International Society for Quality
Electronic Design and not by IEEE**, so the IEEE carve-out does not automatically
reach it. That distinction is the one the 3 September letter to Ali and Paul was
written to settle, and it was settled only for the copyright question.

Ali has answered every question put to him inside a day. Asking costs one
sentence; guessing wrong costs the submission. Nothing about the deposit expires
— notification is 22 January 2027 — so it waits for the answer. Draft
**22894804** is created, the file uploaded and verified by MD5, the metadata
written and read back; only `publish` remains, and `publication_date` in
`zenodo-deposit.json` needs moving to the day it is actually pressed.

**The question went out on 22 September 2026 at 17:56**, to Ali on all three of
his addresses with Paul Wesling copied, and was read back from the Sent folder to
confirm it left. The letter is `letter-ali-preprint.md`. Until he answers, the
deposit stays a draft — that is a decision, not an oversight.

## What this does *not* do

An accepted ISQED paper yields a resolving IEEE Xplore DOI. arXiv's moderators
(MOD-102933, 1 September 2026) will consider an appeal *"if and only if this
manuscript (or a revised version) is accepted for publication in a peer
reviewed journal"*, with a resolving DOI. A refereed conference is stronger
evidence than Zenodo but is **not** a literal match for "journal", so an appeal
on an ISQED acceptance is an argument and not a formality. The same letter
warns that resubmitting without one *"may result in loss of submission
privileges"* — so nothing should go to arXiv until there is something to show.
