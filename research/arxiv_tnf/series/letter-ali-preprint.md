# To Ali Iranmanesh, on posting a preprint — **sent 22 September 2026, 17:56**

Sent by Claude at the owner's explicit instruction, through the live Zoho session
rather than the mail MCP: that grant is read-only by construction, and
`grant_type=refresh_token` never widens one. Read back from the Sent folder
afterwards — 1013 characters, identical to the text below.

- **To:** isqedisqed@gmail.com, ali@isqed.org, ali1@isqed.org
- **Cc:** p.wesling@ieee.org
- **Subject:** Re: ISQED 2027 - concurrent submission policy

Two things about it are worth knowing, because neither is what was planned:

- **It is a new message, not a reply.** The reading pane was closed and no
  Reply-All control could be found in the DOM, so it went out from *New Mail*
  with the subject typed by hand. There is no `In-Reply-To` and no quoted
  original — most clients will still thread it on the subject, and Ali's own
  letter is two days old, so he will know the thread. But it is not a true reply.
- **The subject carries a hyphen where the thread has an em dash**, for the same
  reason the softconf abstract went in as ASCII.

The confirmation number is in the first line precisely because the thread
predates the submission and the letter no longer carries its own headers.

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
