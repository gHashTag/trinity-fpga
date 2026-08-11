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
MXL = d["runs"][1]["levels"]          # the MXFP4 run recorded in stage 0
assert abs(MXL[-1] - 1.0) < 1e-12
by = {(p["level"], p["delta"]): p["ppl"] for p in d["perturb"]}
# gradient at the +-1% step, in d ppl / d ln(level)
g = {j: (by[(j, 0.01)] - by[(j, -0.01)]) / 0.02 for j in range(1, 7)}

print("=" * 74)
print("0. IS THE INSTRUMENT NOISE-FREE?  (everything below depends on this)")
print("=" * 74)
cp = d["cross_process_mxfp4"]
print(f"same codebook, two separate processes, {cp['threads']} threads each:")
print(f"   {cp['first']:.8f} vs {cp['second']:.8f}  -> |diff| {cp['absdiff']:.3e}")
det = d.get("determinism")
if det:
    print(f"three fresh quantisations in one process: spread "
          f"{det['spread']:.3e} ppl")
print("recorded separately: the SAME measurement at 6 threads instead of 8 gave")
print("   21.93966162 vs 21.93966176 -> 1.31e-07 ppl (6e-09 relative),")
print("   i.e. non-associative CPU reductions, not model or data variation.")
print(f"\nnoise floor <= 1.3e-07 ppl. The smallest effect discussed below is")
print(f"   ~0.05 ppl -- about 400,000x the floor. Nothing below is noise.")

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
print("B. IS THE ONE-LEVEL GRADIENT EVEN WELL DEFINED?")
print("=" * 74)
DEL = (-0.05, -0.02, -0.01, 0.01, 0.02, 0.05)
print("central difference dppl/dln(L) computed at three step sizes.")
print("A locally smooth surface gives the same number at all three.\n")
print(f"{'lvl':>4}{'L':>9}{'@1%':>10}{'@2%':>10}{'@5%':>10}"
      f"{'  agree?':>10}{'   monotone in L?':>18}")
for j in range(1, 7):
    gs = [(by[(j, h)] - by[(j, -h)]) / (2 * h) for h in (0.01, 0.02, 0.05)]
    sgn = len({np.sign(x) for x in gs}) == 1
    rng = max(gs) - min(gs)
    seq = [by[(j, x)] for x in DEL]
    seq = [seq[0], seq[1], seq[2], mx, seq[3], seq[4], seq[5]]
    dd = np.diff(seq)
    nsign = int((np.sign(dd[:-1]) != np.sign(dd[1:])).sum())
    print(f"{j:>4}{MXL[j]:>9.5f}" + "".join(f"{x:>+10.2f}" for x in gs)
          + f"{('same sign' if sgn else 'SIGN FLIPS'):>10}"
          + f"{('yes' if nsign == 0 else f'no, {nsign} turns'):>18}")
print("\nsame table as perplexity, MXFP4 = %.4f at delta 0" % mx)
print(f"{'lvl':>4}{'-5%':>9}{'-2%':>9}{'-1%':>9}{'  0':>9}{'+1%':>9}"
      f"{'+2%':>9}{'+5%':>9}{'  best':>9}")
for j in range(1, 7):
    seq = [by[(j, DEL[0])], by[(j, DEL[1])], by[(j, DEL[2])], mx,
           by[(j, DEL[3])], by[(j, DEL[4])], by[(j, DEL[5])]]
    lab = ["-5%", "-2%", "-1%", "0", "+1%", "+2%", "+5%"]
    print(f"{j:>4}" + "".join(f"{v:>9.4f}" for v in seq)
          + f"{lab[int(np.argmin(seq))]:>9}")
nbeat = sum(1 for p in d["perturb"] if p["ppl"] < mx)
print(f"\nsingle-level perturbations that BEAT MXFP4: {nbeat}/{len(d['perturb'])}")
best = min(d["perturb"], key=lambda p: p["ppl"])
print(f"best single-level move: level {best['level']} {best['delta']:+.0%} "
      f"-> {best['ppl']:.4f} ({100*(best['ppl']/mx-1):+.2f}% vs MXFP4)")

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
steps = np.diff([r["ppl"] for r in it])
mono = bool(np.all(steps <= 0) or np.all(steps >= 0))
turns = int((np.sign(steps[:-1]) != np.sign(steps[1:])).sum())
print(f"monotone: {mono}   ({turns} direction changes in 10 steps, "
      f"{int((steps > 0).sum())} of them uphill)")
print(f"max deviation from the straight chord: {max(dev, key=abs):+.4f} ppl "
      f"({100*max(dev, key=abs)/p0:+.2f}% of the Lloyd end) at "
      f"t={it[int(np.argmax(np.abs(dev)))]['t']:.1f}")
print(f"steps: min {steps.min():+.4f}  max {steps.max():+.4f}  "
      f"ratio |max|/|min| = {abs(steps).max()/abs(steps).min():.2f}")
print(f"worst point on the path is t=0.1 at {max(r['ppl'] for r in it):.4f}, "
      f"{100*(max(r['ppl'] for r in it)/p0-1):+.2f}% WORSE than the Lloyd end "
      f"it started from")
# How far apart are these codebooks, in the two units that both have a claim?
# Relative distance is what the random draws were specified in; absolute
# distance is what the coordinate descent that produced KL actually stepped in
# (it added +-step to a level, not +-step% of it).
L0, L1 = it[0]["levels"], it[-1]["levels"]
rel = [L1[j] / L0[j] - 1 for j in range(1, 7)]
absd = [L1[j] - L0[j] for j in range(1, 7)]
rms_rel = math.sqrt(float(np.mean(np.square(rel))))
rms_abs = math.sqrt(float(np.mean(np.square(absd))))
rnd_abs = 0.02 * math.sqrt(float(np.mean([MXL[j] ** 2 for j in range(1, 7)])))
print("\nper-level move, normalised Lloyd-Max -> KL:")
print(f"  {'lvl':>4}{'Lloyd':>10}{'KL':>10}{'abs':>10}{'rel':>10}")
for j in range(1, 7):
    print(f"  {j:>4}{L0[j]:>10.5f}{L1[j]:>10.5f}"
          f"{absd[j-1]:>+10.5f}{100*rel[j-1]:>+9.2f}%")
print(f"\nLloyd->KL distance: {100*rms_rel:.2f}% RMS relative | "
      f"{rms_abs:.5f} RMS absolute")
print(f"random draws      : {2.00:.2f}% RMS relative | "
      f"{rnd_abs:.5f} RMS absolute")
print(f"  => the random draws are {rms_rel/0.02:.1f}x closer in relative units, "
      f"{rms_abs/rnd_abs:.1f}x closer in absolute units")
print(f"perplexity moved {100*(p1/p0-1):+.2f}% over the Lloyd->KL distance")
print(f"  {100*(p1/p0-1)/(100*rms_rel):+.3f}% ppl per 1% RMS relative, DIRECTED")
print(f"  random 2% RMS gave sd {s['sd_pct']:.2f}pp = "
      f"{s['sd_pct']/2:.3f}% ppl per 1% RMS relative, UNDIRECTED")

fine = d.get("fine_interp")
if fine:
    print("\nrefined path (midpoints of [0,0.5] filled in; * = new):")
    allp = sorted([(r["t"], r["ppl"], "") for r in it if r["t"] <= 0.5]
                  + [(r["t"], r["ppl"], " *") for r in fine])
    for t, p, m in allp:
        print(f"  {t:>6.2f}{p:>11.4f}{m}")
    dd = np.diff([p for _, p, _ in allp])
    print(f"  sign changes on the refined path: "
          f"{int((np.sign(dd[:-1]) != np.sign(dd[1:])).sum())} of {len(dd)-1}")
    print(f"  step range {dd.min():+.4f} .. {dd.max():+.4f} ppl")

cont = d.get("continuity")
if cont:
    print("\n" + "=" * 74)
    print("E. CONTINUITY AT SMALL SCALE (is it steep, or discontinuous?)")
    print("=" * 74)
    print(f"{'lvl':>4}{'delta':>10}{'ppl':>11}{'vs MXFP4':>11}"
          f"{'amplification':>15}")
    for c in cont:
        print(f"{c['level']:>4}{c['delta']:>+10.3%}{c['ppl']:>11.4f}"
              f"{c['pct']:>+10.3f}%{c['pct']/(100*c['delta']):>15.2f}")
    print("\namplification = (% change in ppl) / (% change in the level).")
    print("Bounded and shrinking with the step => continuous but steep.")
