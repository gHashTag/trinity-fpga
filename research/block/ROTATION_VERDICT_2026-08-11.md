# Rotation does not rescue us — it widens the gap

`BLOCK_AXIS_VERDICT_2026-08-10.md` decided the element axis against us on
**unrotated** weights, and the 2026 state of the art rotates first. That left the
verdict scoped to a distribution nobody deploys, which
`COMPETITIVE_LANDSCAPE_2026-08-11.md` recorded as an open scope question rather
than a defence. This measures it.

`rotation_verdict.py`, SmolLM2-135M, wikitext-2, 40 windows of 2048, block of 32,
E8M0 shared scale — the verdict's own setup, using the verdict's own quantiser,
level tables, scale rule and perplexity loop, taken from `block_tnf.py` by
executing its source rather than copying it.

## The instrument, before the result

| check | required | measured |
|---|---|---|
| unquantised baseline | plausible band | **14.4874** |
| rotate → unrotate, no quantisation | returns the weights | max \|Δw\| **2.4e-07** |
| rotation lightens the tails | Δkurtosis < 0 | **−0.469** median |
| rotated but unquantised perplexity | equals the baseline | **14.4874** |

And the unrotated arms reproduce the verdict to four decimals — 21.9397,
36.7214, 14.7269, 18.0275 — which is the check that matters most, because it
says this script and that document are measuring the same thing.

The kurtosis figure deserves a note: `heavy_tail_test.py` reported **−1.601** and
this reports **−0.469**. Both are real and they are not in conflict — that test
rotates full-width, this rotates in blocks of 32 to match the quantisation block,
which is what "block-wise Hadamard" means in the paper. A 32-wide mix moves less
mass than a full-width one. The sign is what the check needed, and the sign
agrees.

## The result

| format | unrotated | rotated | Δ | vs fp32 |
|---|---:|---:|---:|---:|
| MXFP4 E2M1 + E8M0 | 21.9397 | 23.7476 | +1.8080 | 1.639× |
| TNF4 E_t=1 packed | 36.7214 | 42.3269 | **+5.6054** | 2.922× |
| MXFP6 E2M3 + E8M0 | 14.7269 | 14.8488 | +0.1220 | 1.025× |
| TNF6 E_t=2 packed | 18.0275 | 20.9353 | **+2.9078** | 1.445× |

**Rotation alone makes every arm worse, and ours worse by more.**

| gap, ours minus MX | unrotated | rotated | |
|---|---:|---:|---|
| 4 bits | +14.7818 | **+18.5793** | widens |
| 6 bits | +3.3006 | **+6.0865** | widens |

## What this settles, and what it does not

**Settled: the verdict is not an artefact of measuring unrotated weights.** That
was the live scope objection to our own conclusion, and it is now answered by
measurement in the direction least convenient for us. The element axis is
decided against us on both distributions, and the rotated one is worse.

**Not settled: whether MR-GPTQ helps MXFP4.** This isolates the rotation. MR-GPTQ
is rotation *plus* GPTQ error compensation, and the compensation is the part that
repairs what the transform costs — a rotation redistributes error within a block
but does nothing to correct it, so measuring the transform alone is expected to
look worse than the published combination. Nothing here contradicts that paper,
and nothing here should be quoted as though it did.

**Why rotation hurts here at all** is not established. The plausible mechanism is
that a Hadamard mix within a 32-element block raises the typical magnitude
relative to the block maximum that sets the shared scale, so more elements land
in the coarse part of the codebook — but that is a hypothesis, not a measurement,
and it is written here as one.

## Consequence

The scope note added to the proof page on 2026-08-11 — that the element-axis
comparison was measured on unrotated weights — can now say what the rotated
measurement showed instead of leaving it open. The honest form is that the gap
widens, so the scope was never a way back in, which is what that note already
predicted on general grounds and now rests on a number.

---

*Method note: rotation is folded into the weight as `W_hat = Q(W·H/√K)·Hᵀ/√K`,
algebraically identical to rotating the activations, so nothing but the weights
differs between the arms and no forward pass was modified.*
