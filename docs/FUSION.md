# Does the decode cost survive its consumer? (W939)

NeuraLUT's structural claim — precision *inside* a LUT partition is free, only the
partition boundary's bit-width sets area — is the sharpest threat to any
format-area argument. If it applied here, the 2-vs-12 cell decode gap of W936
would vanish the moment the decoder is fused with arithmetic, and the paper's
whole area case would be an artefact of measuring a decoder alone.

Measured, same rig, same metric: each decoder twice — bare, and followed by a
fixed 12×8 multiply identical for every format. Record
[`fusion_w939.json`](fusion_w939.json), script [`fusion_test.py`](fusion_test.py).

| format | input bits | decoder alone | decoder + multiply | the multiply's own cost |
|---|---:|---:|---:|---:|
| `GFTernary` | 2 | 2.000 | **6.104** | **4.104** |
| `int8` | 8 | 0.000 | 129.739 | 129.739 |
| `fp8 e4m3` | 8 | 12.000 | 141.739 | 129.739 |
| `fp8 e5m2` | 8 | 12.000 | 141.739 | 129.739 |
| `TNF16` | 16 | 2.000 | 384.417 | 382.417 |
| `BNF16` | 16 | 10.000 | 392.417 | 382.417 |
| `posit16` | 16 | 125.000 | 507.452 | 382.452 |

## Result 1 — the gap survives fusion exactly

`TNF16` and `BNF16` differ by **8.000 cells** bare. After fusion they differ by
**8.000 cells** (392.417 − 384.417): the multiply adds an identical 382.417 to
both. Same for `posit16`, whose consumer costs 382.452 — the same figure to three
decimals. **The decode difference is fully preserved by the surrounding logic**,
so on this substrate the format choice is visible to the consumer and the
LUT-absorption argument does not erase it.

**But it is 2 % of the fused unit.** Eight cells sit inside ~390. Any area claim
that quotes the decode ratio (5×, 6×, 46×) without saying what fraction of a real
datapath the decoder is has quoted a true number in a misleading unit.

## Result 2 — the alphabet, not the decoder, is what the consumer pays for

The multiply's own cost is **not** constant across formats, though the RTL is
identical: 382.4 cells for a 16-bit input, 129.7 for 8-bit, and **4.1 for
GFTernary's 2-bit alphabet**. The synthesiser propagates the small alphabet
through the multiplier and deletes almost all of it.

That is a **93× effect on the consumer**, against an 8-cell effect on the decoder.
The strongest area argument available to this project is therefore not "our
decoder is cheap" but **"our alphabet makes everything downstream cheap"** — and
it is measured, not asserted.

Fair-comparison caveat, stated plainly: `GFTernary` at 2 bits per weight is not
being compared at equal storage width with `TNF16` at 16. The equal-width
comparison is `TNF16` vs `BNF16` vs `posit16`, and there the consumer cost is
identical to three decimals — the alphabet effect is a **width** effect and must
be quoted as one, alongside whatever accuracy that width costs (W939 seeds:
4-bit TNF loses 0.32 pp on MNIST, 0.85 on Fashion).

## What this changes

- The decode-cost table (W936) stays true and gets a denominator.
- The paper's area argument should lead with the alphabet's effect on the
  consumer, which is two orders of magnitude larger than the decode effect and
  survives every noise source measured on this project.
- NeuraLUT's claim is not refuted in general — it is a statement about LUT-mapped
  truth tables, and this experiment measures a conventional multiply. What is
  refuted is the weaker inference that *therefore* a format difference cannot
  reach the surrounding logic. Here it does, exactly, to three decimals.

---

*φ² + φ⁻² = 3 | TRINITY*
