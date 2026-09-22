# Draft — to Ali Iranmanesh, on posting a preprint

Not sent. Claude drafts, the owner sends.

- **To:** ali@isqed.org, ali1@isqed.org
- **Cc:** p.wesling@ieee.org
- **Subject:** Re: ISQED 2027 — concurrent submission policy

Ali has answered both previous questions within a day, in two lines each. This
one is kept to a single question for the same reason. The confirmation number
belongs in the letter because the thread predates the submission.

---

Ali,

Thank you — the Zoom answer and the extension are exactly what I needed, and I
submitted on 22 September. The confirmation number is **66**.

One last question, and then I will stop.

The paper submitted to you is a ten-page cut of a much longer manuscript. I
would like to post that longer manuscript publicly, under my own name, as a
citable record with a DOI — the shorter papers refer to material a reader
currently cannot obtain, and that bothers me.

Since ISQED reviews blind, I do not want to do this without asking. The
manuscript I sent you carries no name or affiliation anywhere, and I checked
that. But the longer version would carry mine, and it contains the same
measurements, so a reviewer who searched a phrase from it would find me.

Is posting it acceptable, or should it wait until notification on 22 January?

I am happy either way — I simply do not want to discover in January that I
should have waited.

Dmitrii Vasilev, Trinity S3AI
ORCID 0009-0008-4294-6159 — github.com/gHashTag

---

## If the answer is yes

```bash
cd research/arxiv_tnf/series && python3 zenodo-deposit.py publish 22894804
```

Move `publication_date` in `zenodo-deposit.json` to that day first. Then record
the minted DOI in `README.md` (the line that reads *"Paper C still has no Zenodo
DOI"*) and in `SUBMISSION-ISQED-2027.md`.

## If the answer is wait

Nothing to do. The draft keeps; drafts on Zenodo do not expire. Revisit after
**22 January 2027**.
