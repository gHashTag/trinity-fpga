# The last two competitor defects were real, and one had been reported all along

Iteration 81 left four decoder defects: two withdrawn as comparison artefacts,
two real. Both real ones are now repaired and both decoders are exact.

## posit16 — two off-by-ones, four codes

Wrong at exactly the saturation codes `0x0001`, `0x7fff`, `0x8001`, `0xffff`,
each by $2^{\pm2}$ — one step of an $es=2$ exponent field.

1. `regime_total` was capped at 14. When the regime plus its terminator fills
   all 15 bits there is no exponent field, but the cap left the terminator
   sitting in the exponent slot, so `e` read as 2 instead of 0. minpos came out
   4x too large.
2. The all-zero branch of the leading-count set `lzc = 14`, giving $k=13$. A run
   of fifteen identical bits with no terminator is $k = 15-1 = 14$. **The
   comment on that very line said `k=+14`.** maxpos came out 4x too small.

After: **65,535 of 65,535 exact.** 712 → 667 LUT, 40.38 → 36.75 MHz.

## posit32 — one malformed literal, 48 codes

One `casez` pattern was written 32 characters wide in a 31-bit case:

    31'b000000000001????????????????????: lzc = 5'd11;

Verilog truncates from the left. The surviving 31 characters are
character-for-character the `lzc=10` arm above it, so the `lzc=11` arm was
**unreachable** and every code with exactly eleven leading zeros fell to the
default. Misdiagnosed as regime arithmetic for two iterations because the
failures clustered at long regimes, which is exactly what a regime bug looks
like.

Rebuilt the whole `casez` by generation rather than by hand-repair — the same
class of typo was in three more arms, and a second copy of the file in
`fpga/openxc7-synth/` carried eleven of them.

After: **40,000 of 40,000 exact.** 953 → 967 LUT, 28.16 → 29.55 MHz.

## The channel nobody read

iverilog printed this on every run, for as long as the file has existed:

    warning: Extra digits given for sized binary constant.

The harness sent compiler output to a log and read the log only on failure.
**A warning nobody reads is not a warning.** It is an instrument whose output is
disconnected — the same defect as an instrument inside the failure domain, and
harder to notice, because this instrument is working perfectly.

`tools/check_literal_widths.py` makes it an exit code: 188,021 sized literals
checked, the measured path gated, and the 41 remaining occurrences in TF3 test
benches **printed rather than hidden** — a bounded gate that does not say what
it bounded reads as "covered everything".

## Block RAM, measured across all 21 rows

`takum16` uses **57 RAMB36 tiles. Every other format uses zero.** The throughput
table now carries a BRAM column, so the one format buying its speed with block
memory can no longer be compared on LUTs alone.

## Where the ten defects came from

| found in | count |
|---|---|
| our own modules | 6 |
| competitors' modules | 4 |
| ...of which the compiler had already reported | 1 |
| ...of which the module's own comment contradicted the code | 1 |

Every one of the ten made its module smaller or faster before repair. That is
now ten for ten, and it is not a coincidence: **an unimplemented case is
unsynthesised logic.**
