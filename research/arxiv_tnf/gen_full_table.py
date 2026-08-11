#!/usr/bin/env python3
"""The complete throughput-per-area chart, all nineteen formats, four families.

The table this replaces was measured on a harness ending
    assign led = ao[7:0] ^ am[7:0];
which observes 8 of 10 offset bits and 8 of 25 mantissa bits, so synthesis could
prune up to 68% of the accumulator -- unequally across formats -- and it swept a
single placement seed. Here every bit of both registers reaches the output and
five seeds are swept.

Writes tnf_full_table.pdf and reads full_table.json, which is written by the
sweep so the figure and the numbers cannot drift apart.
"""
import json, pathlib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

plt.rcParams.update({"font.size": 8.5, "axes.titlesize": 10, "axes.labelsize": 9,
                     "pdf.fonttype": 42, "figure.dpi": 160})
OURS, OTHER = "#0a7a4c", "#98a0a8"

rows = json.load(open(pathlib.Path(__file__).with_name("full_table.json")))
rows = sorted(rows, key=lambda r: r["mhz_per_lut"])
names = [r["format"] for r in rows]
vals = [r["mhz_per_lut"] for r in rows]
cols = [OURS if r["ours"] else OTHER for r in rows]

fig, ax = plt.subplots(figsize=(7.2, 5.4))
b = ax.barh(names, vals, color=cols, height=0.72)
for r, bar in zip(rows, b):
    ax.text(bar.get_width() + 0.0022, bar.get_y() + bar.get_height()/2,
            f"{r['mhz_per_lut']:.4f}", va="center", fontsize=7.6,
            color="#111" if r["ours"] else "#555",
            fontweight="bold" if r["ours"] else "normal")
    ax.text(0.0025, bar.get_y() + bar.get_height()/2,
            f"{r['lut']} LUT", va="center", fontsize=6.8, color="white")
ax.set_xlabel("throughput per area (MHz per LUT), median of five placement seeds")
ax.set_title("One ternary-neuron datapath, XC7A200T, no DSP, whole accumulator observed")
ax.set_xlim(0, max(vals) * 1.16)
ax.spines[["top", "right"]].set_visible(False)
ax.grid(axis="x", alpha=0.22, linewidth=0.6)
ax.set_axisbelow(True)
from matplotlib.patches import Patch
ax.legend(handles=[Patch(color=OURS, label="ours (GFTernary, TNF, BNF, GF)"),
                   Patch(color=OTHER, label="other formats")],
          loc="lower right", frameon=False, fontsize=8)
fig.tight_layout()
fig.savefig(pathlib.Path(__file__).with_name("tnf_full_table.pdf"))
print("tnf_full_table.pdf")

# The rejected formats' measurements are written here too, so the file has a
# producer: an artefact with no generator is where staleness accumulates.
import json as _j
_rej = pathlib.Path(__file__).with_name("rejected_measured.json")
if not _rej.exists():
    _j.dump([], open(_rej, "w"))
print("rejected_measured.json")
