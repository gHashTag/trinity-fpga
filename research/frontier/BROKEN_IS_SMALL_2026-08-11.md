# A wrong decoder is small for a reason, demonstrated on our own module in a day

Yesterday's conformance note ended with the sentence *a decoder that is wrong is
small for a reason*. Today the module that sentence was written about was mine.

The specification-conformant TNF8 was generated with a signed exponent wire
seven bits wide and a slice `e[7:0]` taken from it. The eighth bit does not
exist, so **960 of its 1,024 codes produced undefined output**, and synthesis
pruned the logic that fed them.

| TNF8 | LUT | $F_{\max}$ | MHz/LUT | rank |
|---|---|---|---|---|
| with the undefined slice | $493$ | $75.69$ | $0.1535$ | **3** |
| corrected | $545$ | $62.13$ | $0.1140$ | **15** |

**Ten percent smaller and twenty-two percent faster while producing nothing.**
It entered the table at rank three on that basis, and the oracle caught it
within the hour --- which is the whole argument for having the oracle.

## Where the four TNF rungs stand, checked

| rung | codes checked | mismatches | MHz/LUT | rank |
|---|---|---|---|---|
| TNF32 | 9,997 sampled | 0 | $0.1176$ | 12 |
| TNF16 | all 131,072 | 0 | $0.1173$ | 13 |
| TNF64 | sampled | 0 | $0.1143$ | 14 |
| TNF8 | all 1,024 | 0 | $0.1140$ | 15 |

The ladder is mid-pack, and it is mid-pack *measured at its own specification
and verified against it*, which is the first time any of that has been true at
once. Against posit at matched width the advantage is $1.39\times$ at 8 bits,
$2.07\times$ at 16 and $3.99\times$ at 32 --- down from the $3.1\times$ and
$5.6\times$ this paper claimed on the unverified modules.

What holds rank one is **GFTernary**, the two-bit alphabet, agreeing with its
reference on all four of its codes.

## Ranks three and four are still unverified

BNF16 at $0.1447$ and GF+8 at $0.1428$ have no reference. That is the same
position TNF32 and TNF64 held yesterday at ranks three and four, and it did not
survive contact with one. The next thing to build is their references, not
another measurement.
