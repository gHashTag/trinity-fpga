#!/usr/bin/env python3
"""Analysis of campaignC_sensitivity_*.json -- no new model evaluations.

Two things the raw table does not say on its own:

  A. LOCAL LINEARITY. If the perplexity surface is locally smooth, the measured
     one-level gradients predict the random 2%-RMS codebooks:
        ppl(MXFP4 * (1+eps)) ~= ppl(MXFP4) + sum_j (dppl/dln L_j) * eps_j
     Compare predicted against measured. A high R^2 means the surface is a smooth
     tilted plane locally -- steep, but not chaotic. A low R^2 means codebook
     comparisons are reading off a rough surface.

  B. WHAT THE SPREAD IS WORTH. Put the published margins next to the spread a
     random 2% perturbation produces, and next to the one-level gradients.
"""
import json
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
MDIR = os.environ.get("MDIR", "smollm2")
d = json.load(open(os.path.join(HERE, f"campaignC_sensitivity_{MDIR}.json")))

mx = d["baseline"]["MXFP4"]
g = {r["level"]: r["dppl_dlnlevel"] for r in d["gradients"]}
MXL = d["runs"][1]["levels"]          # the MXFP4 run recorded in stage 0
assert abs(MXL[-1] - 1.0) < 1e-12

print("=" * 74)
print("A. IS THE SURFACE LOCALLY LINEAR?  (gradient prediction vs measurement)")
print("=" * 74)
print(f"{'#':>3}{'measured':>11}{'predicted':>11}{'resid':>9}"
      f"{'meas %':>9}{'pred %':>9}")
mea, pre = [], []
for r in d["random"]:
    eps = [r["levels"][j] / MXL[j] - 1 for j in range(1, 7)]
    p = mx + sum(g[j + 1] * eps[j] for j in range(6))
    mea.append(r["ppl"])
    pre.append(p)
    print(f"{r['seed_idx']:>3}{r['ppl']:>11.4f}{p:>11.4f}{r['ppl']-p:>+9.4f}"
          f"{100*(r['ppl']/mx-1):>+8.2f}%{100*(p/mx-1):>+8.2f}%")
mea, pre = np.array(mea), np.array(pre)
ss_res = float(((mea - pre) ** 2).sum())
ss_tot = float(((mea - mea.mean()) ** 2).sum())
r2 = 1 - ss_res / ss_tot
corr = float(np.corrcoef(mea, pre)[0, 1])
print(f"\nR^2 of the linear (gradient) model = {r2:+.4f}")
print(f"correlation measured vs predicted  = {corr:+.4f}")
print(f"rms residual = {math.sqrt(ss_res/len(mea)):.4f} ppl "
      f"({100*math.sqrt(ss_res/len(mea))/mx:.2f}% of MXFP4)")
print(f"sd of measurements = {float(mea.std(ddof=1)):.4f} ppl")

print("\n" + "=" * 74)
print("B. CURVATURE ALONG EACH LEVEL  (is +-5% still on the tangent line?)")
print("=" * 74)
by = {(p["level"], p["delta"]): p["ppl"] for p in d["perturb"]}
DEL = (-0.05, -0.02, -0.01, 0.01, 0.02, 0.05)
print(f"{'lvl':>4}{'L':>9}" + "".join(f"{x:>+9.0%}" for x in DEL)
      + f"{'lin.err@5%':>12}")
for j in range(1, 7):
    lin5 = mx + g[j] * 0.05
    err = by[(j, 0.05)] - lin5
    print(f"{j:>4}{MXL[j]:>9.5f}"
          + "".join(f"{100*(by[(j,x)]/mx-1):>+8.2f}%" for x in DEL)
          + f"{err:>+12.4f}")

print("\n" + "=" * 74)
print("C. THE SPREAD AGAINST THE PUBLISHED MARGINS")
print("=" * 74)
s = d["random_stats"]
print(f"random 2% RMS perturbations of MXFP4, n={s['n']}:")
print(f"   mean {s['mean_pct']:+.2f}%   sd {s['sd_pct']:.2f}pp   "
      f"min {s['min_pct']:+.2f}%   max {s['max_pct']:+.2f}%   "
      f"span {s['range_pct']:.2f}pp")
print(f"   better than MXFP4: {s['n_better']}/{s['n']}")
print("\npublished margins vs MXFP4 on this same model/window set:")
rows = [("KL-optimised", d["baseline"]["KL"]),
        ("nSSE-equal", d.get("nsse_ppl")),
        ("Lloyd-Max", d["baseline"]["Lloyd"])]
for nm, p in rows:
    if p is None:
        continue
    z = (100 * (p / mx - 1) - s["mean_pct"]) / s["sd_pct"]
    print(f"   {nm:<14}{p:>10.4f}{100*(p/mx-1):>+9.2f}%   "
          f"= {z:+.1f} sd of the random-2% spread")

print("\n" + "=" * 74)
print("D. THE PATH FROM LLOYD-MAX TO KL")
print("=" * 74)
it = d["interp"]
print(f"{'t':>5}{'ppl':>11}{'step':>10}{'vs MXFP4':>11}")
prev = None
for r in it:
    st = "" if prev is None else f"{r['ppl']-prev:+10.4f}"
    print(f"{r['t']:>5.1f}{r['ppl']:>11.4f}{st:>10}"
          f"{100*(r['ppl']/mx-1):>+10.2f}%")
    prev = r["ppl"]
p0, p1 = it[0]["ppl"], it[-1]["ppl"]
lin = [p0 + (p1 - p0) * r["t"] for r in it]
dev = [r["ppl"] - l for r, l in zip(it, lin)]
print(f"monotone: {d['interp_monotone']}")
print(f"max deviation from the straight chord: {max(dev, key=abs):+.4f} ppl "
      f"({100*max(dev, key=abs)/p0:+.2f}% of the Lloyd end) at "
      f"t={it[int(np.argmax(np.abs(dev)))]['t']:.1f}")
steps = np.array(d["interp_steps"])
print(f"steps: min {steps.min():+.4f}  max {steps.max():+.4f}  "
      f"ratio |max|/|min| = {abs(steps).max()/abs(steps).min():.2f}")
# how far apart are the two codebooks, in the same units as the random draws?
rms_lk = math.sqrt(float(np.mean([(it[-1]["levels"][j] / it[0]["levels"][j] - 1) ** 2
                                  for j in range(1, 7)])))
print(f"\nLloyd->KL distance = {100*rms_lk:.2f}% RMS relative "
      f"(the random draws sat at 2.00%)")
print(f"perplexity moved {100*(p1/p0-1):+.2f}% over that distance")
print(f"=> {100*(p1/p0-1)/(100*rms_lk):+.3f}% ppl per 1% RMS along that line; "
      f"random 2% RMS gave sd {s['sd_pct']:.2f}pp "
      f"(= {s['sd_pct']/2:.3f}%/1% RMS, undirected)")
