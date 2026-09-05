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
import canon_style  # engraving house style: white ground, serif, hatched fills
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# canon_style turns these two colours into two stable hatches.
OURS, OTHER = "#0a7a4c", "#98a0a8"

rows = json.load(open(pathlib.Path(__file__).with_name("full_table.json")))
rows = sorted(rows, key=lambda r: r["mhz_per_lut"])
names = [r["format"] for r in rows]
vals = [r["mhz_per_lut"] for r in rows]
cols = [OURS if r["ours"] else OTHER for r in rows]

fig, ax = plt.subplots(figsize=(4.80, 3.60))
b = ax.barh(names, vals, color=cols, height=0.72)
for r, bar in zip(rows, b):
    # One label per bar. Two separate texts collided at every bar width, and an
    # in-bar label has to fight the hatch that marks our rows.
    ax.text(bar.get_width() + 0.0025, bar.get_y() + bar.get_height()/2,
            f"{r['mhz_per_lut']:.4f}  ({r['lut']} LUT)", va="center",
            fontsize=6.8, fontweight="bold" if r["ours"] else "normal")
ax.set_xlabel("throughput per area (MHz per LUT), median of five placement seeds")
ax.set_title("One ternary-neuron datapath, XC7A200T, no DSP, whole accumulator observed")
ax.set_xlim(0, max(vals) * 1.42)
ax.set_axisbelow(True)
# No colour legend: in the engraved style ours are the rows whose value is set
# in bold, which is stated in the caption. A hatch legend at this size is not
# reliably distinguishable in print.
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
