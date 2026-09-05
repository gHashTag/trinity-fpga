#!/usr/bin/env python3
"""Regenerate every data figure in the canon-plate engraving style.

Runs the existing generators unchanged, with canon_style imported first so the
ink is engraved rather than coloured. No datum is touched here.

Also draws tnf_radix.pdf, which had no generator in the tree and shipped as an
empty page: kappa(r) = (r-1)^2 / (r ln r), the function named in Theorem 21.
"""
import canon_style  # noqa: F401  (style is applied on import)
import runpy
import numpy as np
import matplotlib.pyplot as plt

for script in ("gen_figures.py", "gen_full_table.py"):
    print("==", script)
    runpy.run_path(script, run_name="__main__")

# ── kappa(r) against the scale radix ────────────────────────────────────────
kappa = lambda r: (r - 1.0) ** 2 / (r * np.log(r))
r = np.linspace(1.05, 17.0, 2000)
fig, ax = plt.subplots(figsize=(4.80, 2.49))
ax.plot(r, kappa(r), "-")
pts = [2, 4, 8, 16]
ax.plot(pts, [kappa(p) for p in pts], "s", markersize=5, linestyle="none")
for p in pts:
    dx, dy = ((-30, 4) if p == 16 else (4, 6))
    ax.annotate(f"$r={p}$\n{kappa(p):.4f}", (p, kappa(p)),
                textcoords="offset points", xytext=(dx, dy), fontsize=7)
ax.annotate("only $r=2^{k}$ is implementable\nby a shift; the marked points\nare the whole set",
            (9.2, 1.15), fontsize=7)
ax.set_xlabel("scale radix $r$")
ax.set_ylabel(r"$\kappa(r)=(r-1)^2/(r\ln r)$")
ax.set_title("Only $r=2^{k}$ scales by a shift,\n"
             r"and on that set $\kappa$ is strictly increasing", fontsize=9)
ax.set_xlim(1.0, 17.0)
ax.set_ylim(0, 5.9)
fig.savefig("tnf_radix.pdf")
print("tnf_radix.pdf  kappa:", " ".join(f"{kappa(p):.4f}" for p in pts))
