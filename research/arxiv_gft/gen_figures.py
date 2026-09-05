#!/usr/bin/env python3
"""Figures for the GF-T paper, in the house style of research/arxiv_submission.

Vector PDFs, headless backend, one figure per claim. Numbers are the measured
ones; nothing here is drawn from an estimate.
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

plt.rcParams.update({
    "font.size": 9, "axes.titlesize": 10, "axes.labelsize": 9,
    "legend.fontsize": 8, "figure.dpi": 150, "savefig.bbox": "tight",
})

# ── 1. accuracy against tekum16, by binary-exponent magnitude ────────────────
bins = ["|e| < 8", "|e| 8–20", "|e| 20–38"]
gft = [3.56e-4, 3.52e-4, 3.53e-4]
tek = [3.27e-4, 1.00e-3, 1.95e-3]
gf16 = [3.43e-4, 3.57e-4, 6.98e-3]

x = np.arange(len(bins)); w = 0.27
fig, ax = plt.subplots(figsize=(5.2, 2.9))
ax.bar(x - w, gf16, w, label="GF16 (φ)", color="#b9c6c1")
ax.bar(x,     gft,  w, label="GF-T16",   color="#0a7a4c")
ax.bar(x + w, tek,  w, label="tekum16",  color="#7d8f99")
ax.set_yscale("log")
ax.set_ylabel("mean relative round-trip error")
ax.set_xticks(x); ax.set_xticklabels(bins)
ax.set_title("Accuracy by binary-exponent magnitude (bins are powers of two)")
ax.legend(frameon=False)
# The measured ratios, not ratios recomputed from the rounded values plotted —
# otherwise the figure and the table disagree in the last digit.
RATIOS = [None, "2.84×", "5.53×"]
for i, (g, t, r) in enumerate(zip(gft, tek, RATIOS)):
    if r:
        ax.annotate(r, (i, max(g, t) * 1.35), ha="center", fontsize=8, color="#0a7a4c")
ax.annotate("GF16 clips 479/2857\nabove |e|≈31", (2 - w, 6.98e-3 * 1.6), ha="center", fontsize=7, color="#5b6f68")
fig.savefig("gft_accuracy.pdf")
print("gft_accuracy.pdf")

# ── 2. the ladder: area and frequency ───────────────────────────────────────
rungs = ["GF-T4", "GF-T8", "GF-T16", "GF-T32"]
luts = [12, 50, 212, 1477]
fmax = [161.11, 153.23, 131.73, 83.27]

fig, ax1 = plt.subplots(figsize=(5.2, 2.9))
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
ax1.set_title("GF-T multiplier on XC7A200T, one cycle of latency")
fig.savefig("gft_ladder.pdf")
print("gft_ladder.pdf")

# ── 3. what the interface width cost ────────────────────────────────────────
labels = ["32-bit ports\n(as written)", "widths derived\nfrom parameters", "+ one pipeline\nregister"]
lut3 = [1179, 219, 219]
f3 = [81.0, 81.35, 147.32]
fig, ax = plt.subplots(figsize=(5.2, 2.9))
b = ax.bar(labels, lut3, 0.5, color=["#c46a6a", "#0a7a4c", "#0a7a4c"])
ax.set_ylabel("LUTs")
ax.set_title("GF-T16 multiplier: interface width dominates the arithmetic")
for i, (l, f) in enumerate(zip(lut3, f3)):
    ax.annotate(f"{l:,} LUT\n{f:.2f} MHz", (i, l + 40), ha="center", fontsize=8)
ax.annotate("3 × DSP48", (0, 1179 * 0.45), ha="center", fontsize=8, color="white")
ax.annotate("0 DSP48", (1, 219 * 0.45), ha="center", fontsize=8, color="white")
ax.annotate("0 DSP48", (2, 219 * 0.45), ha="center", fontsize=8, color="white")
ax.set_ylim(0, 1450)
fig.savefig("gft_width.pdf")
print("gft_width.pdf")
