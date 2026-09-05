# G8 instrument map: which workflow can reproduce the sixteen untraced frequencies (W920)

The first two `tnf-cost-sweep` dispatches after #612/#615 landed proved the
PIPELINE (generate + 104 yosys arms + pnr + refit, all green) and one honest
limit: the five default P&R arms are `routing-pending` on xc7a200tfbg484-2 —
the workflow's own documented fabric limit, "not a zero, not a defect".

But the sweep CANNOT close G8 even in principle: `tab:untraced`'s sixteen
frequencies are **format-comparison designs** (posit8/16/32, takum16,
binary16/32, fp8 e4m3/e5m2, LNS16, IBM hex32, VAX F, GF10/14, GFTernary,
int8, plastic 16-bit), not (E_t, M) ladder arms. Different experiment,
different tops.

## What exists

- The format HARNESSES are in-tree: `fpga/tnet/s_posit16.v`,
  `s_takum16.v`, `s_bin16.v`, `w_gfternary.v`, `w_vaxf.v`, … (verified for
  posit16, takum16, binary16, LNS16 (`fpga/phiscale/`), GFTernary, VAX F;
  IBM hex32 has no in-tree harness — flagged).
- `ax7203-format-cost.yml` synthesizes only GF8/FP8/INT8 in a UART wrapper —
  three formats, wrapper-dominated critical path; not the sixteen.

## The missing instrument

A `tnf-format-throughput` workflow, modeled on `tnf-cost-sweep.yml`, whose
arms are the `fpga/tnet/` tops, reporting per-format LUT/FF/Fmax from
yosys + nextpnr on the same fabric, `routing-pending` recorded honestly.
Its output row set compares DIRECTLY against the sixteen published numbers —
the first instrument that can turn G8 green (or honestly red) on CI alone.

Until it exists (or the author's original logs surface), the G8 verdict
remains **NO-GO: post-route evidence absent**, now with the reason narrowed
from "no CI path" to "CI path exists for the wrong experiment".
