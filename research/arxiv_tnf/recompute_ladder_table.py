#!/usr/bin/env python3
"""SUPERSEDED -- this script regenerates a table the paper no longer contains.

It emits decades 8, 26, 80, 242; the paper's ladder table prints 2, 8, 24, 73,
and 26, 80 and 242 occur ZERO times anywhere in tnf_paper.tex. The difference is
the source: this script reads the SPECIFICATION's field widths and the paper now
takes the ORACLE's throughout. The table's own caption records the repair --
"Mixing the two sources in one table is the defect being repaired: the rows are
now the oracle throughout".

Use `recompute_ladder_exact.py`, which owns the tab:ladderacc table. Running this
one against the current paper reports a table's worth of false differences, which
is what two separate audit passes saw and could not account for.
"""

"""Recompute Table `tab:ladderacc` from the shipped TNF oracle.

Two configurations of the 16-bit rung were in the paper at once: the fill study
adopts $E_t=4$, $M=11$ and the accuracy figure derives its data from it, while
this table and the field table still carried the numbers of the unfilled $M=9$
rung. One rung cannot have two errors, so the 16-bit row is recomputed at the
adopted width and every other rung is taken from `tnf_ref.LADDER` unchanged --
the fill was applied to the 16-bit rung only, which is a fact about the code and
is stated as such in the text rather than smoothed over here.

Same workload as the field table: 6,000 values, |e| in [0,38], seed 20260809.
"""
import math
import sys

import numpy as np

sys.path.insert(0, "../../conformance")
import tnf_ref as T

BINS = [(0, 8), (8, 20), (20, 38)]
_rng = np.random.default_rng(20260809)
VALS = [float(s) * float(m) * 2.0 ** int(e) for s, m, e in
        zip(_rng.choice([-1, 1], 6000), _rng.uniform(1, 2, 6000),
            _rng.integers(-38, 39, 6000))]

# Adopted 16-bit rung: the fill study's winner. Everything else as shipped.
RUNGS = dict(T.LADDER)
RUNGS[16] = T.TNFFormat(4, 11)


def decades(fmt):
    """Binary decades the exponent field spans, as the paper counts them."""
    return 2 * fmt.exp_offset


def row(fmt):
    means, bad = [], []
    for lo, hi in BINS:
        tot, n, b = 0.0, 0, 0
        for v in VALS:
            a = abs(math.log2(abs(v)))
            if not lo <= a < hi:
                continue
            try:
                d = float(T.decode(fmt, T.encode(fmt, v)))
            except Exception:
                b += 1
                continue
            if d == 0.0 or not np.isfinite(d):
                b += 1
                continue
            rel = abs(d - v) / abs(v)
            if rel > 0.5:          # the value left the rung's range
                b += 1
                continue
            tot += rel
            n += 1
        means.append(tot / n if n else float("nan"))
        bad.append(b)
    return means, bad


for w in sorted(RUNGS):
    f = RUNGS[w]
    m, b = row(f)
    print("TNF%-5d M=%-4d dec=%-6d" % (w, f.mant_bits, decades(f)),
          ["%.2e" % v for v in m], "outside", b)
