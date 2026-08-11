# I computed a caveat instead of measuring it, and it was false

Last iteration this work published that rung A's win over `binary16` was bought
with code space: four trits give 81 offsets where the binary field holds 128, so
37.5% of the codes are discarded and the rung delivers 15.32 effective bits.

**That number was computed from the specification, not read off the silicon.**

Sweeping every code through the RTL: **64,518 distinct values of 65,536 codes,
98.4% utilisation**, against `binary16`'s 100%. The out-of-specification offsets
are not discarded — the decoder gives each a distinct value. The same-width win
over IEEE half costs **1.6% of code space, not 37.5%**, and our result is
stronger than the paper claimed.

## Three withdrawals, one of them about our own headline

| published | measured |
|---|---|
| TNF16a discards 37.5%, 15.32 effective bits | **98.4% utilisation** |
| "GFTernary uses all four of its codes and discards nothing" | **75% — three values in two bits** |
| discarding code space buys throughput (n=3, r=+0.81) | **n=23, r=+0.173, t=0.80, not significant, opposite sign** |

The two least efficient formats in the catalogue — `GF+8` at 44.3% and IBM hex32
at 52.8% — sit at ranks **17 and 22**, not at the top. The hypothesis predicted
the reverse.

Proposition (output-space pruning) remains true as stated: a smaller image does
permit specialisation. **The inference that discarded codes therefore buy
measurable throughput does not survive twenty-three measurements.** Three points
agreed with it. That is the entire reason to measure a caveat rather than
compute one.

## Measured utilisation, all 23 rows

Lowest: `GF+8` 44.3%, IBM hex32 52.8%, **GFTernary 75.0%**, minifloat 88.7%,
takum16 93.6%, TNF16b 93.8%, TNF8 94.3%.
Highest: `binary16`, `binary32`, `GF10`, `GF14`, fp8 ×2, posit ×3, `LNS16` all
at or indistinguishable from 100%.

`TNF16a`/`TNF16`/`BNF16` all sit at 98.4%.

## A different defect, now in view

**The ladder decoders do not reserve out-of-specification offsets.** Rung A has
47 offset codes outside its 81, and each decodes to a plausible finite value
rather than a signal. A corrupted offset field is indistinguishable from a valid
one. No test in this work would have found it: *a decoder that answers every
input answers every test.*

## The gates

- `tools/measure_code_use.py` — sweeps every format's RTL, exhaustive to 2^18,
  sampled at 200,000 above, sweep kind recorded so a partial sweep never reads
  as complete.
- `tools/check_code_use.py` — every table row must carry a utilisation produced
  by that sweep, and the table must not drift from `code_use.json`.

**Both errors had one shape: a property of the silicon asserted from the
specification instead of read off the silicon.** That is now an exit code.
