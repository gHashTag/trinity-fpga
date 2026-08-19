#!/usr/bin/env python3
"""Regenerate Table `tab:blockpct` from its measurement record.

Method as in `recompute_rungthr_table.py`: the table is a VIEW of a record,
not a re-measurement, so either the four rows come back cell for cell or they
do not.

Record: measurements/blockpct_2026-08-20.json, produced by
measurements/gen_blockpct.py from the SmolLM2-135M checkpoint (snapshot
93efa2f0, sha256 in the record). Until 2026-08-20 this table had NO record:
the range-provenance sweep (research/RANGE_PROVENANCE_2026-08-20.md, addendum)
listed its four spans as UNCHECKED-EXPENSIVE, and the paper's prose does not
even name the model ("a trained network's weights"). The record pins it:
SmolLM2-135M, 210 quantisable linear tensors, 3,317,760 blocks of 32 along
the contraction axis.

WHERE EACH COLUMN COMES FROM.
    column               source
    percentile           record key (50/90/99/99.9, numpy linear interp)
    span, binades        percentiles[p].span_binades, rounded to 2 decimals
    E*                   ceil(log2 span) -- recomputed here from the span,
                         NOT read from the record's own Estar field, so the
                         rule and the record are checked against each other
    element              E*=1 -> E1M2, E*=2 -> E2M1 (N=4: 1+E+M=4)

THE DEFINITION IS PART OF THE CLAIM. The span of one block is
log2(max|w| / lower-median|w|), lower-median = 16th of 32 sorted magnitudes
(the torch.median convention for even counts). The numpy interpolated median
gives 1.84/2.39/2.96/3.67 and does NOT reproduce the printed table; the
generator records the convention explicitly, and this script asserts the
record states it.

Exits nonzero on any cell mismatch.
"""
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REC = os.path.join(HERE, "measurements", "blockpct_2026-08-20.json")

# tab:blockpct as printed (percentile, span, E*, element)
PAPER = [
    ("p50", 1.89, 1, "E1M2"),
    ("p90", 2.45, 2, "E2M1"),
    ("p99", 3.04, 2, "E2M1"),
    ("p99.9", 3.75, 2, "E2M1"),
]
# the paragraph after the table repeats two of the spans
PROSE = {"p50": 1.89, "p99": 3.04}

rec = json.load(open(REC))
assert "lower-median" in rec["span_definition"], \
    "record must state the lower-median convention; without it the table is " \
    "not reproducible (interpolated median gives 1.84/2.39/2.96/3.67)"
assert rec["n_tensors"] == 210 and rec["n_blocks"] == 3317760

fails = 0
print(f"{'pct':>6} {'record':>10} {'paper':>7} {'E*':>3} {'element':>8}")
for key, span_p, estar_p, elem_p in PAPER:
    r = rec["percentiles"][key]
    span_r = round(r["span_binades"], 2)
    estar_r = math.ceil(math.log2(r["span_binades"]))
    elem_r = {1: "E1M2", 2: "E2M1"}[estar_r]
    ok = (span_r == span_p) and (estar_r == estar_p) and (elem_r == elem_p)
    if key in PROSE:
        ok = ok and (span_r == PROSE[key])
    print(f"{key:>6} {r['span_binades']:>10.4f} {span_p:>7.2f} {estar_r:>3}"
          f" {elem_r:>8}  {'OK' if ok else 'MISMATCH'}")
    fails += not ok

if fails:
    sys.exit(f"{fails} cell(s) do not reproduce")
print("tab:blockpct reproduces cell for cell from the record.")
