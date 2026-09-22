# ISQED 2027 — the submission, ready except for the login

Everything the softconf form asks for is written out below, so that the portal
session is a copy-and-paste job rather than a drafting session. **An agent
cannot do this step**: the portal is behind a login, and registering an account
or typing a password is the owner's action, not an agent's.

## Where

`https://softconf.com/p/isqed2027` — register first if there is no account
(there is no softconf mail anywhere in the mailbox, so assume there is not).

## When

| the source | the date |
|---|---|
| the live call for papers, read 2026-09-22 | **Sept. 25, 2026** |
| Ali Iranmanesh, by mail, 2026-09-20 | *"We will extend the deadline until mid October"* |

The original date was 17 September and it passed unsubmitted. The 25th already
*is* an extension. **Submit against the 25th.** The mid-October extension is a
promise from the general chair and is very probably real, but the portal
enforces whatever date is configured in it, not what is in the mail thread, and
submitting early costs nothing.

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

## Two answers already in hand, so they need not be asked again

- **Remote presentation.** Ali Iranmanesh, 2026-09-20: *"Yes you can present
  remotely through zoom."* Worth noting in the submission comments.
- **Concurrent submission.** There is none. Microprocessors and Microsystems
  declined the parent manuscript (MICPRO-D-26-00839) on 2026-09-20, editorially
  and without external review. The Elsevier-footnote arrangement Paul Wesling
  proposed is therefore moot and its own fallback applies: the IEEE footer and
  the ordinary Xplore deposit.

## What this does *not* do

An accepted ISQED paper yields a resolving IEEE Xplore DOI. arXiv's moderators
(MOD-102933, 1 September 2026) will consider an appeal *"if and only if this
manuscript (or a revised version) is accepted for publication in a peer
reviewed journal"*, with a resolving DOI. A refereed conference is stronger
evidence than Zenodo but is **not** a literal match for "journal", so an appeal
on an ISQED acceptance is an argument and not a formality. The same letter
warns that resubmitting without one *"may result in loss of submission
privileges"* — so nothing should go to arXiv until there is something to show.
