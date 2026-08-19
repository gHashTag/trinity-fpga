#!/usr/bin/env python3
"""Recompute Table `tab:field` and Table `tab:accuracy` from the shipped oracles.

The tables in the paper were transcribed by hand while TNF16 still carried M = 9.
The rung moved to M = 11 (t27#2005) and the figure, which derives its own data,
then disagreed with the table it illustrates. Rather than patch either number by
eye, both tables are recomputed here from `conformance/*_ref.py` with the same
workload the figure uses, and the overflow counts are counted, not remembered.

Workload: 6,000 values, |e| in [0, 38], random sign, uniform significand,
seed 20260809 -- the same construction and seed as gen_figures.py, so figure and
table cannot drift apart again.
"""
import sys
from fractions import Fraction as F

import numpy as np

sys.path.insert(0, "../../conformance")
import bf16_ref as B
import gf_ref as G
import lns_ref as L
import posit_ref as P
import takum_ref as K
import tnf_ref as T

BINS = [("|e| < 8", 0, 8), ("|e| 8-20", 8, 20), ("|e| 20-38", 20, 38)]

_rng = np.random.default_rng(20260809)
VALS = [float(s) * float(m) * 2.0 ** int(e) for s, m, e in
        zip(_rng.choice([-1, 1], 6000), _rng.uniform(1, 2, 6000),
            _rng.integers(-38, 39, 6000))]

_tnf = T.TNFFormat(4, 11)
_gf16 = G.FORMATS["gf16"]
_tk = K.TakumFormat("takum16", 16)
_po = P.FORMATS["posit16"]
_bf = B.FORMATS["bfloat16"]
_ln = L.FORMATS["lns16"]


def _num(x):
    """A finite float from an oracle result, or None if it is not a number."""
    if x is None:
        return None
    if isinstance(x, (int, float, F)):
        f = float(x)
        return f if np.isfinite(f) else None
    return None


def d_tnf(v):
    try:
        return _num(T.decode(_tnf, T.encode(_tnf, v)))
    except Exception:
        return None


def d_gf(v):
    try:
        return _num(G.decode(_gf16, G.encode(_gf16, v)))
    except Exception:
        return None


def d_tk(v):
    try:
        return _num(K.decode(_tk, K.encode(_tk, v)))
    except Exception:
        return None


def d_po(v):
    try:
        return _num(P.decode(_po, P.encode(_po, v)))
    except Exception:
        return None


def d_bf(v):
    try:
        return _num(B.decode(_bf, B.encode(_bf, v)))
    except Exception:
        return None


def d_b16(v):
    x = np.float16(v)
    return float(x) if np.isfinite(x) else None


def d_lns(v):
    """LNS16 round-trip.

    The stored quantity is log2|v| in fixed point, so the decoded value is in
    general irrational and the oracle refuses to fake a Fraction. The round-trip
    error is therefore measured in the value domain through the stored log, which
    is exactly what the format promises to hold.
    """
    try:
        raw = L.encode(_ln, v)
        lg = L.decode_log(_ln, raw)
        if lg is None:
            return None
        s = L.sign_of(_ln, raw)
        return (-1.0 if s else 1.0) * float(2.0 ** float(lg))
    except Exception:
        return None


ROWS = [
    ("TNF16", d_tnf),
    ("GF16", d_gf),
    ("takum16 / tekum16", d_tk),
    ("posit16", d_po),
    ("IEEE binary16", d_b16),
    ("bfloat16", d_bf),
    ("LNS16", d_lns),
]


def measure(dec):
    """Mean relative round-trip error per bin, and the count that overflowed.

    A value counts as overflowed when the decoder cannot return a finite number
    for it, or returns zero for a non-zero input: both mean the value left the
    format's range. Those are counted, never folded into the mean.
    """
    means, clips = [], []
    for _, lo, hi in BINS:
        tot, n, bad = 0.0, 0, 0
        for v in VALS:
            if not lo <= abs(np.log2(abs(v))) < hi:
                continue
            d = dec(v)
            if d is None or d == 0.0:
                bad += 1
                continue
            tot += abs(d - v) / abs(v)
            n += 1
        means.append(tot / n if n else float("nan"))
        clips.append(bad)
    return means, clips


def fmt(x):
    return "$%.2f\\mathrm{e}{%d}$" % tuple(
        (lambda m, e: (m, e))(*(lambda s: (float(s.split("e")[0]), int(s.split("e")[1])))("%.2e" % x)))


out = {}
for name, dec in ROWS:
    m, c = measure(dec)
    out[name] = (m, c)
    print(name, ["%.2e" % v for v in m], "clip", c)

# bin populations, so the overflow counts can be read as a fraction of the bin
pops = []
for _, lo, hi in BINS:
    pops.append(sum(1 for v in VALS if lo <= abs(np.log2(abs(v))) < hi))
print("bin populations:", pops, "total", sum(pops))

tnf = out["TNF16"][0]
tk = out["takum16 / tekum16"][0]
gf = out["GF16"][0]
print("takum/TNF ratios:", ["%.2f" % (a / b) for a, b in zip(tk, tnf)])
print("TNF vs GF ratios:", ["%.2f" % (a / b) for a, b in zip(gf, tnf)])

with open("field_table.tex", "w") as fh:
    for name, dec in ROWS:
        m, c = out[name]
        cells = []
        for v, k in zip(m, c):
            cell = fmt(v)
            if k:
                cell += " (%d)" % k
            cells.append(cell)
        label = "\\textbf{TNF16}" if name == "TNF16" else (
            "GF16 ($\\varphi$)" if name == "GF16" else name)
        fh.write("%-18s & %s \\\\\n" % (label, " & ".join(cells)))
print("wrote field_table.tex")
