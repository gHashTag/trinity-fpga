# Literature check on the block section's winning arm — null result

## What I went looking for

The block section's best arm is a $2^{k/8}$ scale ladder: eight points per
binade in the same eight-bit field MXFP4 spends on E8M0. A search turned up that
**NVFP4 replaces E8M0 with an FP8-E4M3 scale**, and E4M3 carries three mantissa
bits — also eight points per binade. On the face of it, the section's winning
resolution is prior art shipped in Blackwell silicon, and the paper would be
claiming novelty for something NVIDIA already sells.

## What I found instead

**The paper already has this, and in more detail than the search gave me.**

- Table `tab:frontier` measures `NVFP4-like E4M3 8b/16` and `E4M3 8b/32` on both
  models, and states plainly that above 4.25 bits per weight *the frontier
  belongs to scales carrying a mantissa* — i.e. concedes the region to NVFP4.
- Table `tab:geoscale` isolates exactly the residual question — **placement at
  fixed resolution** — and measures geometric against E4M3 at 7 and 8 bits on
  both models. Geometric wins all four.
- The section already refuses the model-dependent over-reading: on SmolLM2 a
  geometric grid at 4.25 b/w beats the NVFP4-like configuration at 4.50 — cheaper
  and better — and *on Qwen it is cheaper and worse*, and the paper says so
  rather than quoting the favourable model.
- `\bibitem{nvfp4}` is cited.

## The lesson, which is the point of writing this down

I was one command away from "correcting" the paper with something it says better
than I was about to. **Check what the document already claims before treating a
search result as a finding about it.** The failure mode is the same shape as the
thirteen withdrawals — asserting a comparison without first reading both sides —
and it does not stop being that shape when the thing unread is my own paper.

## The residual, which is real

`tab:geoscale` tests placement on **perplexity over 40 windows**. The
monotonicity table on the RMSE axis — 14.9 million blocks — has no E4M3 row at
all. So the placement claim rests on the smaller sample and the coarser
instrument. An `e4m3` arm has been added to
`research/block/verify_block_rmse.py`, which will give the same claim on the
larger sample from independently written code. That is worth having; it is not
a correction.
