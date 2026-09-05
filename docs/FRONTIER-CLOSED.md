# The frontier closed at the top, and the sign flips (W942)

W941 priced every format as a truth table — fair at four to eleven bits,
impossible at nineteen, and carrying a declared but unmeasured bias. This closes
both gaps: a **structural** decoder generated from each `TNFFormat`'s own fields
(`sign_shift`, `exp_shift`, `exp_bits`, `mant_bits`, `exp_offset`, `offset_max`)
and **verified against the oracle over every code**.

| rung | physical bits | codes checked | mismatches | decoder | consumer |
|---|---:|---:|---:|---:|---:|
| TNF4 | 6 | 64 | **0** | 12.00 | **55.29** |
| TNF8 | 11 | 2,048 | **0** | 16.00 | **260.57** |
| **TNF16** | **19** | **524,288** | **0** | 27.00 | **450.29** |

## The method's bias, now measured rather than declared

| rung | truth table | structural | difference |
|---|---:|---:|---|
| TNF4 | 51.29 | 55.29 | table 7.2 % cheaper |
| TNF8 | 270.57 | 260.57 | table 3.8 % **dearer** |
| TNF16 | — (2¹⁹ codes) | 450.29 | table impossible |

The bias is under 8 % and **not one-directional** — the truth table flattered the
small alphabet and penalised the larger one. Every ratio below is quoted with that
band in mind.

## The frontier, and where TNF actually wins

| class | cheapest working option | TNF at that class | verdict |
|---|---|---|---|
| 16-bit | `binary16` **438.57** (16 bits) | TNF16 **450.29** (19 bits) | **TNF 2.7 % dearer**, three bits wider |
| 8-bit | `fp8 e4m3` **152.57** (8 bits) | TNF8 **260.57** (11 bits) | **TNF 1.71× dearer**, three bits wider |
| 4-bit | `fp4 e2m1` 19.14 — **loses 70 pp** | **TNF4 55.29** (6 bits), **−0.33 / −1.05 pp** | **TNF is the only one that works** |

**TNF wins at exactly one rung, and it wins there decisively.** TNF4 costs 55.29
cells against fp8 e4m3's 152.57 — **2.76× cheaper for fp8-class accuracy** — while
every 4-bit alternative collapses by seventy points. Above that rung, being three
bits physically wider than its name costs TNF the cost comparison at every class.

## Correction chain, and this is the third link

- **W940** priced TNF16 through `tnf16_decode` (16 bits): 386.57 cells.
- **W940b** corrected that to `tnf17_decode` (17 bits): 424.86, and concluded TNF16
  beat `binary16` at 438.57.
- **W942** finds the true width is **19** and the structural cost **450.29** — so
  **that conclusion inverts**: at its real width TNF16 is 2.7 % *dearer* than
  `binary16`, not 3 % cheaper.

Each correction was made from the previous one's own principle, and each moved the
number against the project's interest. The chain is the evidence that the method
works; the final number is the one to quote.

## Limits

Synthesis cells, `-nodsp`, one synthesiser, no place-and-route. The consumer is one
12×8 multiply. The comparison mixes structural TNF decoders against tree-RTL and
truth-table baselines; the ±8 % method band above bounds that mixing, and it does
not reach the 2.76× at four bits or the 1.71× at eight.

---

*φ² + φ⁻² = 3 | TRINITY*
