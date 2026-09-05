# Draft letter to Laslo Hunhold — NOT SENT

**Status:** draft only. Nothing has been sent. Edit freely; the bracketed slots are yours.

**Suggested subject:** `A takum bug report, a width observation on tekum, and a request for criticism`

---

Dear Dr Hunhold,

I am writing with two things you may find useful and one request.

**A bug, in our implementation of your format.** We built a takum oracle to
compare against, and it negated wrongly on every negative code — we had missed
that negation in takum flips the exponent sign. Since the fix it agrees with
libtakum on 65,534 of the 65,535 codes we sweep. **The remaining disagreement is
at a single code and we have not been able to decide whether it is ours or a
boundary case in the reference; if it would help, I can send the code and both
decodings.** Every takum figure in our paper is stated post-fix, and the earlier
ratios are gone rather than corrected in place.

**A width observation on tekum.** We implemented the base-3 tekum of
arXiv:2512.10964 (Definitions 7–8) directly from the paper; it is exact on your
worked example and monotone on all 6,559 tekum8 codes. In doing so we noticed
that tekum's widths count **trits**, so tekum16 stores 16 trits — about 25.4
bits. Any table putting tekum16 beside a 16-bit binary format is therefore not
width-matched.

I raise this with some embarrassment, because we then found exactly the same
defect in our own format and it was worse: our ladder names count storage
*symbols*, so what we had been calling TNF16 is one sign, four exponent trits and
eleven mantissa bits — **19 bits**. Since our naming sequence is 4/8/16/32/64,
which is the IEEE width sequence, every "TNF16 against binary16" row read as
matched and was not. We have renamed the ladder by bit width and redone the
comparison; at matched physical width posit holds more representable values than
we do at every rung, and posit with es=2 weakly dominates us on both range and
precision. That result is now in the paper as a section rather than a footnote.

**The request.** The attached draft is a first version and has not been
submitted. It is largely a parity and negative result: our format's case is
multiplier removal by ring closure, decoder cost, and the very low precisions
where nothing else trains — not precision per bit, where it loses. takum beats it
in several of our own measurements, including near unity at 32 bits and on range,
where takum reaches ±255 binades and never leaves range where we do.

I would value your criticism precisely because you have no reason to be gentle
about it. If you have time for only one question, this is the one I would ask:

> **Is the matched-physical-width comparison the right frame at all,** or does it
> understate what a tapered format is for? Our table compares representable
> values and the local step at 1.0. You may consider that the wrong figure of
> merit, and if so I would rather hear it before submission than after.

Two smaller questions, if you have more time: whether our takum RTL cost figures
(taken from your Takum-Codec-RTL) are being used the way you intended, and
whether the tekum trit-width point above is already stated somewhere I missed.

[ *Your paragraph here: the endorsement, and the earlier work that went through
him. It should be in your words, not mine.* ]

With thanks for the formats and for the reference implementations, which made all
of this checkable,

[ your name ]
[ affiliation, if any ]
[ repository / preprint link ]

---

## Notes for you before sending

- **The one-code takum disagreement is a real open item.** It is worth resolving
  before the letter goes, or being ready to send the code and both decodings the
  moment he asks. Quoting "65,534 of 65,535" invites exactly that question.
- **Attach the PDF, not a link to a private repo.** He should be able to read it
  without asking for access.
- **Do not ask for an endorsement in this letter.** Ask for criticism. If the
  criticism goes well, the endorsement conversation is a separate message and a
  much easier one.
- **The letter concedes that his format beats ours in several places.** That is
  deliberate and it is also true. A reviewer who finds the concession himself
  reads everything else more sceptically.
