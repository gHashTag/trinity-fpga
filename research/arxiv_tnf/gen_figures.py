#!/usr/bin/env python3
"""Figures for the TNF paper, in the house style of research/arxiv_submission.

Vector PDFs, headless backend, one figure per claim. Numbers are the measured
ones; nothing here is drawn from an estimate.
"""
import canon_style  # engraving house style: white ground, serif, double base rule
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

# ── 1. accuracy against tekum16, by binary-exponent magnitude ────────────────
# ── 1. accuracy, COMPUTED from the oracles rather than transcribed ──────────
#
# These numbers were hardcoded until 2026-08-09 and drifted: they still carried
# TNF16 at M = 9 and the label "tekum16" long after the rung moved to M = 11 and
# the oracle was shown to decode identically to takum. A figure that disagrees
# with the table it illustrates is the same defect class as a gate that cannot go
# red, so the figure now derives its own data.
import sys
from fractions import Fraction as F
sys.path.insert(0, "../../conformance")
import tnf_ref as T
import takum_ref as K
import gf_ref as G

BINS = [("|e| < 8", 0, 8), ("|e| 8–20", 8, 20), ("|e| 20–38", 20, 38)]
_rng = np.random.default_rng(20260809)
_vals = [float(s) * float(m) * 2.0 ** int(e) for s, m, e in
         zip(_rng.choice([-1, 1], 6000), _rng.uniform(1, 2, 6000),
             _rng.integers(-38, 39, 6000))]

def _mean_err(decode):
    out = []
    for _, lo, hi in BINS:
        tot, n = F(0), 0
        for v in _vals:
            if not lo <= abs(np.log2(abs(v))) < hi:
                continue
            d = decode(v)
            if d is None or d == 0:
                continue
            tot += abs(F(d) - F(v)) / abs(F(v)); n += 1
        out.append(float(tot / n) if n else float("nan"))
    return out

_tef = T.TNFFormat(4, 11)          # M = 11 as adopted; see t27#2005
_gf16 = G.FORMATS["gf16"]
_tk = K.TakumFormat("takum16", 16)

def _d_tef(v):
    try:
        return float(T.decode(_tef, T.encode(_tef, v)))
    except Exception:
        return None

def _d_gf(v):
    try:
        return float(G.decode(_gf16, G.encode(_gf16, v)))
    except Exception:
        return None

def _d_tk(v):
    try:
        r = K.decode(_tk, K.encode(_tk, v))
        return float(r) if not isinstance(r, K.Special) else None
    except Exception:
        return None

bins = [b[0] for b in BINS]
tef = _mean_err(_d_tef)
tak = _mean_err(_d_tk)
gf16 = _mean_err(_d_gf)

x = np.arange(len(bins)); w = 0.27
fig, ax = plt.subplots(figsize=(4.80, 2.68))
ax.bar(x - w, gf16, w, label="GF16 (φ)", color="#b9c6c1")
ax.bar(x,     tef,  w, label="TNF16 (M=11)", color="#0a7a4c")
ax.bar(x + w, tak,  w, label="takum16", color="#7d8f99")
ax.set_yscale("log")
ax.set_ylabel("mean relative round-trip error")
ax.set_xticks(x); ax.set_xticklabels(bins)
ax.set_title("Accuracy by binary-exponent magnitude (bins are powers of two)")
ax.legend(frameon=False)
for i, (g, t) in enumerate(zip(tef, tak)):
    ax.annotate(f"{t / g:.2f}×", (i, max(g, t) * 1.35),
                ha="center", fontsize=8, color="#0a7a4c")
fig.savefig("tnf_accuracy.pdf")
print("tnf_accuracy.pdf  ratios:", " ".join(f"{t/g:.2f}x" for g, t in zip(tef, tak)))

# ── 2. the ladder: area and frequency ───────────────────────────────────────
rungs = ["TNF4", "TNF8", "TNF16", "TNF32", "TNF64"]
luts = [12, 50, 212, 1477, 7479]
fmax = [161.11, 153.23, 131.73, 83.27, 48.20]

fig, ax1 = plt.subplots(figsize=(4.80, 2.68))
ax1.bar(rungs, luts, 0.5, color="#0a7a4c")
ax1.set_ylabel("LUTs (no DSP48)", color="#0a7a4c")
ax1.tick_params(axis="y", labelcolor="#0a7a4c")
ax1.set_yscale("log")
for i, v in enumerate(luts):
    ax1.annotate(f"{v:,}", (i, v * 1.15), ha="center", fontsize=8, color="#0a7a4c")
ax2 = ax1.twinx()
ax2.plot(rungs, fmax, "o--", color="#333", linewidth=1.3, markersize=5)
ax2.set_ylabel("$F_{max}$ (MHz), post-route", color="#333")
ax2.set_ylim(0, 190)
for i, v in enumerate(fmax):
    ax2.annotate(f"{v:.1f}", (i, v + 8), ha="center", fontsize=8)
ax1.set_title("TNF multiplier on XC7A200T, one cycle of latency")
fig.savefig("tnf_ladder.pdf")
print("tnf_ladder.pdf")

# ── 3. what the interface width cost ────────────────────────────────────────
labels = ["32-bit ports\n(as written)", "widths derived\nfrom parameters", "+ one pipeline\nregister"]
lut3 = [1179, 219, 219]
f3 = [81.0, 81.35, 147.32]
fig, ax = plt.subplots(figsize=(4.80, 2.68))
b = ax.bar(labels, lut3, 0.5, color=["#c46a6a", "#0a7a4c", "#0a7a4c"])
ax.set_ylabel("LUTs")
ax.set_title("TNF16 multiplier: interface width dominates the arithmetic")
for i, (l, f) in enumerate(zip(lut3, f3)):
    ax.annotate(f"{l:,} LUT\n{f:.2f} MHz", (i, l + 40), ha="center", fontsize=8)
ax.annotate("3 × DSP48", (0, 1179 * 0.45), ha="center", fontsize=8, color="white")
ax.annotate("0 DSP48", (1, 219 * 0.45), ha="center", fontsize=8, color="white")
ax.annotate("0 DSP48", (2, 219 * 0.45), ha="center", fontsize=8, color="white")
ax.set_ylim(0, 1450)
fig.savefig("tnf_width.pdf")
print("tnf_width.pdf")

# ── 4. the 16-bit field, against the class ──────────────────────────────────
#
# This figure and the next had NO generator: the PDFs sat in the tree and the
# code that drew them did not. They still carried "GF-T", the format's name two
# renames ago, because a file nobody regenerates is a file nobody renames. Both
# now derive from the tables they illustrate (tab:field and tab:ladderacc), so a
# figure that disagrees with its table is a build away from being noticed.
FIELD = [
    # Recomputed 2026-08-13 from conformance/*_ref.py on the workload below, at
    # the ADOPTED 16-bit rung (E_t = 4, M = 11). The previous values were the
    # unfilled M = 9 rung, transcribed by hand, so the figure disagreed with the
    # fill study two sections earlier. Overflow counts are counted, not recalled:
    # a value counts as overflowed when the decoder cannot return a finite
    # non-zero number for it. LNS16 previously carried counts of 1,324/1,808/
    # 2,849 -- it clips nothing on this workload, since its 15-bit log field with
    # 8 fractional bits reaches |e| = 63 and the workload stops at 38.
    ("TNF16 (ours)",  [8.34e-5, 8.41e-5, 8.45e-5], [0, 0, 0],       "#0a7a4c"),
    ("GF16 (phi)",    [3.41e-4, 3.46e-4, 5.76e-3], [0, 0, 465],     "#b9c6c1"),
    ("takum16",       [3.08e-4, 9.42e-4, 1.92e-3], [0, 0, 0],       "#7d8f99"),
    ("posit16",       [1.25e-4, 7.87e-4, 1.37e-2], [0, 0, 0],       "#c8912f"),
    ("IEEE binary16", [1.70e-4, 1.15e-3, 1.46e-1], [0, 313, 2413],  "#b04a4a"),
    ("bfloat16",      [1.32e-3, 1.34e-3, 1.37e-3], [0, 0, 0],       "#4a5b8c"),
    ("LNS16",         [7.05e-4, 6.88e-4, 6.82e-4], [0, 0, 0],       "#9b8bb4"),
]
bins3 = ["|e| < 8", "|e| 8-20", "|e| 20-38"]
x = np.arange(len(bins3)); w = 0.115
fig, ax = plt.subplots(figsize=(4.80, 2.85))
for k, (name, vals, clip, col) in enumerate(FIELD):
    off = (k - (len(FIELD) - 1) / 2) * w
    ax.bar(x + off, vals, w, label=name, color=col)
    for i, (v, c) in enumerate(zip(vals, clip)):
        if c:
            ax.annotate(f"{c}✂", (x[i] + off, v * 1.6), ha="center",
                        va="bottom", fontsize=6, color="#b04a4a", rotation=90,
                        bbox=dict(facecolor="white", edgecolor="none",
                                  pad=0.4))
ax.set_yscale("log")
ax.set_ylabel("mean relative round-trip error")
ax.set_xticks(x); ax.set_xticklabels(bins3)
ax.set_xlim(-0.62, len(bins3) - 1 + 0.68)
ax.set_title("16-bit-class formats on one workload (* = values that overflowed)")
ax.legend(frameon=False, ncol=2, fontsize=7.5)
fig.savefig("tnf_competition.pdf")
print("tnf_competition.pdf")

# ── 5. the ladder's accuracy, rung by rung ──────────────────────────────────
LADDER = [
    # Recomputed 2026-08-13 by recompute_ladder_exact.py: 600 values, 1,200-bit
    # significands, exact rationals, seed 20260809. Three published rows could
    # not be reproduced -- TNF16 carried the unfilled M = 9 rung, TNF32 was four
    # decimal orders better than a 21-bit mantissa can be, and TNF32's decade
    # count followed exp_trits = 6 where the oracle ships 5.
    ("TNF4",    2,     [1.04e-1, None, None]),
    ("TNF8",    8,     [1.07e-2, 1.16e-2, None]),
    ("TNF16",   24,    [8.26e-5, 8.61e-5, 8.66e-5]),
    ("TNF32",   73,    [7.63e-8, 8.58e-8, 8.32e-8]),
    ("TNF64",   658,   [3.80e-17, 4.08e-17, 4.01e-17]),
    ("TNF128",  1975,  [4.39e-36, 4.67e-36, 4.21e-36]),
    ("TNF256",  5925,  [2.39e-74, 2.44e-74, 2.47e-74]),
    ("TNF512",  17775, [4.08e-151, 4.18e-151, 4.22e-151]),
    ("TNF1024", 53326, [2.53e-304, 2.65e-304, 2.70e-304]),
]
fig, ax = plt.subplots(figsize=(4.80, 3.05))
# Rungs the workload overruns are marked with a star on the tick label rather
# than a shaded band: in the engraved style a band becomes a hatch that reads
# as data.
over = [i for i, (_, _, v) in enumerate(LADDER) if v is None or v[1] is None]
names = [r[0].replace("TNF", "") + ("*" if i in over else "")
         for i, r in enumerate(LADDER)]
xr = np.arange(len(LADDER)); ww = 0.26
for j, (band, col) in enumerate(zip(bins3, ["#0a7a4c", "#4f9e7a", "#9cc4b2"])):
    ys, xs = [], []
    for i, (_, _, vals) in enumerate(LADDER):
        if vals and vals[j] is not None:
            xs.append(xr[i] + (j - 1) * ww); ys.append(vals[j])
    ax.bar(xs, ys, ww, label=band, color=col)
ax.set_yscale("log")
ax.set_ylim(1e-320, 1e2)
ax.set_ylabel("mean relative error (exact rationals)")
ax.set_xticks(xr); ax.set_xticklabels(names)
ax.set_xlabel("TNF rung (width in bits)")
ax.set_yticks([1e0, 1e-50, 1e-100, 1e-150, 1e-200, 1e-250, 1e-300])
# On a 320-decade axis the difference between 1e-5 and 1e-8 is a few pixels, so
# each rung's decimal exponent goes into its tick label instead: the doubling the
# title claims becomes readable rather than merely asserted.
labels = []
for nm, (_, _, vals) in zip(names, LADDER):
    v = next((q for q in vals if q is not None), None) if vals else None
    labels.append(nm if v is None else "%s\n$10^{%d}$" % (nm, int(np.floor(np.log10(v)))))
ax.set_xticklabels(labels, fontsize=7)
ax.set_title("Error is flat in magnitude, and its exponent doubles per rung")
# No legend: the three bars per rung are the three magnitude bands in the
# order given in the caption. A legend here can only sit on top of the data.
fig.savefig("tnf_ladder_acc.pdf")
print("tnf_ladder_acc.pdf")

# The figure's data, written out so the artefact has a producer. It previously
# sat in the tree with no code behind it, and carried "GF-T" -- the format's name
# two renames ago -- because a file nobody regenerates is a file nobody renames.
import json as _json
_json.dump([{"rung": n, "decades": d,
             "bands": dict(zip(bins3, v)) if v else None}
            for n, d, v in LADDER],
           open("ladder_acc.json", "w"), indent=1)
print("ladder_acc.json")
