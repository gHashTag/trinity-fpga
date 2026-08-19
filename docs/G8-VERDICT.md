# G8 verdict: the sixteen untraced frequencies, measured on CI (run 32263875250)

Instrument: `tnf-format-throughput` (#618, hardened by #620/#622). All 19
tnet tract arms ROUTED on xc7a200tfbg484-2 — the first post-route rows this
gate has ever had. Comparison band: the audited seed dispersion for this
toolchain, 1.6–41.7 %; "reproduced" below means WITHIN-NOISE, never equality.

## The verdict, row by row

**14 of 15 instrumented rows reproduce within the band** (CI/published
0.90×–1.32×): binary16 1.00×, int8 0.97×, binary32 0.97×, VAX F 0.93×,
GF10 0.95×, GF14 0.90×, GFTernary 0.90×, fp8 e4m3 1.06×, fp8 e5m2 1.09×,
takum16 1.09×, IBM hex32 1.11×, posit8 1.14×, posit16 1.19×, posit32 1.32×.

**WITHDRAWN (W935): "LNS16 does not reproduce" was not established.** The
sentence that stood here said the published 43.04 MHz has no in-tree record and
that MATRIX.md's corrected rerun does not include LNS16. Both halves are false.
`fpga/tnet/MATRIX.md:35` lists LNS16 at **43.11 MHz**, 0.16% from the published
value. The verdict read a blank cell off its own instrument: the workflow's REF
table carried `None` for six formats MATRIX.md does list (takum16, posit8,
LNS16, posit16, posit32, IBM hex32) — fixed in the same change as this
withdrawal.

Two agreeing numbers therefore stand against one CI row, and the arithmetic that
called that row an outlier used a denominator the band was never defined with.
The band 1.6–41.7% is `(max − min) / median` over per-seed sets. Applied to the
LNS16 pair by its own definition, |62.66 − 43.04| / 52.85 = **37.1%, inside the
band**; the 45.6% quoted before came from `(CI − published) / published`.

What remains true and is worth the author's attention: the CI row disagrees with
two agreeing in-tree numbers by more than a third, and LNS16 is the most
configuration-sensitive design in the audited set (4.66× best-to-worst across
placer/router pairs — the largest of all 21). The likeliest explanation is the
configuration confound fixed in #630, not a defect in the paper's row. This
needs one re-measurement under the reference configuration, not author input.

**One row is uninstrumented: "plastic 16-bit, 318.47 MHz"** — a
tab:hierarchy design, not a tnet tract; no harness in the sweep.

Correction to G8-INSTRUMENT-MAP.md: IBM hex32 DOES have an in-tree harness
(`s_ibmhfp.v`) — it routed at 51.72 MHz, 1.11× of the published 46.78.

## What this does to the gate

G8 asked for post-route evidence behind sixteen published frequencies that
had none. Fifteen now have CI-sourced rows; fourteen agree within the
toolchain's own measured noise. The remaining asks are narrow and named:
LNS16 (one number, author or supersede) and plastic-16bit (one harness).
The gate's status moves from "unsourced" to **measured-with-two-exceptions**.
