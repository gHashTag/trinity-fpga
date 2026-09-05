#!/usr/bin/env python3
"""Is u* a property of the model, or of the 40 windows it was measured on?

WHY THIS EXISTS
---------------
The campaign reported that the alignment optimum u* differs across families and concluded the
constant does not transfer.  Two instrument faults were then found in that conclusion:

  1. `depth` -- the statistic used to decide whether an optimum was real -- was the gap from the
     minimum to the NEAREST GRID POINT.  It therefore measured the grid.  smollm2 was swept on
     8 points over [0, 0.9]; the others on 13 over [0, 0.55]; pythia's minimum happened to have
     a neighbour 0.015 away while gpt2's neighbours were 0.05 away.  Ranking models by that
     number ranked their grids.  The verdict it produced -- "1 of 4 sharp, 3 undetermined" --
     is withdrawn.

  2. Replacing it with the interpolated interval at the measured tie-rule floor said the
     opposite: all four optima narrow, and their intervals mutually DISJOINT.  But inflating
     the floor by only k = 5 makes pythia's interval swallow the whole swept range and a
     universal alignment survives.  The tie-rule floor measures ONE nuisance source.

So neither "flat" nor "sharp" is established, and the argument now hangs on a floor nobody
measured.  This script measures it -- and does so in a way that needs no floor at all.

THE MEASUREMENT
---------------
Split the evaluation text into F DISJOINT folds of NW windows each and run the whole u-sweep
independently on every fold.  Then:

  * spread of ppl at fixed u across folds        = the evaluation nuisance floor, directly.
  * spread of u* itself across folds             = whether the argmin is determined AT ALL.

The second needs no floor, no curvature, no grid-difference argument.  If a single model's own
u* moves between two halves of the same corpus, then comparing u* BETWEEN models is measuring
sampling noise, and every conclusion drawn from that comparison -- including the refutation of
the alignment law -- rests on nothing.

PRE-REGISTERED OUTCOMES, both reported whichever happens:

  A. u* is STABLE within a model (fold-to-fold spread <= one grid step) and DIFFERS between
     models by more than that.  -> the disagreement is real; the alignment law is dead for a
     strong reason, and the tie-rule floor was an adequate proxy after all.

  B. u* MOVES within a model by as much as it moves between models.  -> the cross-family
     comparison is noise, and the campaign's central negative result is unsupported.  It would
     not make the law true; it would mean nothing has been shown either way and the sweep needs
     far more evaluation data before it can say anything.

gpt2 and pythia are measured first because that single pair carries the empty intersection:
their optima sit 0.15 apart, further than any other pair, so if any disagreement survives it is
theirs.

Quantiser, grid, tie rule and perplexity all come from align_u.py, which imports them from
scale_settled.py -- 21 + 9 self-tests still guard every number below.  Nothing is
reimplemented here except the fold split, which has its own gates.
"""
import json
import os
import sys
import time

import numpy as np
import torch

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import scale_settled as S       # noqa: E402
import align_u as A             # noqa: E402

torch.set_grad_enabled(False)

NW = A.NW                       # 40 windows per fold -- the campaign's operating point
FOLDS = int(os.environ.get("FOLDS", "3"))
TAGS = [a for a in sys.argv[1:] if not a.startswith("--")] or ["gpt2", "pythia"]


def fold_ids(ids, seqlen, nw, nfolds):
    """Disjoint blocks of `nw` windows. Returns a list of token tensors, one per fold.

    Gates, because a silently overlapping or short fold would manufacture agreement:
      F1  every fold has exactly nw full windows
      F2  folds are disjoint by construction AND verified by content hash
      F3  the FIRST fold is bitwise the slice align_u.ppl_at would have used, so fold 0
          reproduces the stored sweep exactly rather than merely resembling it
    """
    per = seqlen * nw
    have = ids.numel() // per
    n = min(nfolds, have)
    if n < 2:
        raise SystemExit(f"only {have} disjoint folds of {nw}x{seqlen} available, need >= 2")
    out = [ids[i * per:(i + 1) * per] for i in range(n)]
    for i, f in enumerate(out):
        S.check(f.numel() == per, f"F1 fold {i} has exactly {nw} windows of {seqlen}",
                f"{f.numel()} tokens")
    hs = {hash(f.numpy().tobytes()) for f in out}
    S.check(len(hs) == n, "F2 folds are distinct", f"{len(hs)} distinct of {n}")
    S.check(torch.equal(out[0], ids[:per]), "F3 fold 0 is the slice the stored sweep used")
    return out


def sweep_fold(m, tg, orig, tokens, seqlen):
    """Full u-grid on one fold. Returns dict u -> ppl."""
    return_ = {}
    for u in A.U_GRID:
        A.quantise_model_u(tg, orig, u)
        return_[u] = A.ppl_at(m, tokens, seqlen, NW)
    for nm, mod, _ in tg:
        mod.weight.copy_(orig[nm])
    return return_


print("Is u* a property of the model, or of the 40 windows it was measured on?", flush=True)
S.selftests_global()
A.selftests_u()
S.abort_if_failed()

RESULT = {}
for tag in TAGS:
    f = A.FAM[tag]
    seqlen = f["seqlen"]
    t0 = time.time()
    m, ids = A.load(tag)
    tg = A.targets(m)
    A.guard_targets(tag, tg, f["nlayer"] * f["per_layer"])
    orig = {nm: mod.weight.data.clone() for nm, mod, _ in tg}
    folds = fold_ids(ids, seqlen, NW, FOLDS)
    S.abort_if_failed()
    print(f"\n  === {tag}: {len(folds)} disjoint folds x {NW} windows x {seqlen} tokens "
          f"= {len(folds) * NW * seqlen:,} tokens, {len(tg)} projections ===", flush=True)

    # fold 0 must reproduce the stored sweep, or the folds are not the same experiment
    stored = None
    p = os.path.join(HERE, f"align_u_{tag}.json")
    if os.path.exists(p):
        d = json.load(open(p))
        stored = {float(r["u"]): float(r["ppl"]) for r in d["rows"]}

    curves = []
    for i, tk in enumerate(folds):
        t1 = time.time()
        c = sweep_fold(m, tg, orig, tk, seqlen)
        curves.append(c)
        us = min(c, key=c.get)
        print(f"    fold {i}: u* = {us:.4f}   ppl* = {c[us]:.4f}   "
              f"({time.time() - t1:.0f}s)", flush=True)
        if i == 0 and stored:
            worst = max(abs(c[u] - stored[u]) for u in c if u in stored)
            S.check(worst < 5e-4, f"F4 {tag} fold 0 reproduces the stored sweep",
                    f"max |delta| = {worst:.2e} over {len(c)} u values")
            S.abort_if_failed()
    del m

    print(f"\n  {'u':>9}" + "".join(f"{'fold ' + str(i):>12}" for i in range(len(curves)))
          + f"{'spread':>10}", flush=True)
    spreads = []
    for u in A.U_GRID:
        v = [c[u] for c in curves]
        sp = max(v) - min(v)
        spreads.append(sp)
        mark = "  <- OCP" if abs(u - A.U_OCP) < 1e-9 else ""
        print(f"  {u:9.4f}" + "".join(f"{x:12.4f}" for x in v) + f"{sp:10.4f}{mark}", flush=True)

    ustars = [min(c, key=c.get) for c in curves]
    step = min(np.diff(A.U_GRID))
    RESULT[tag] = dict(ustars=ustars, curves=[{str(k): v for k, v in c.items()} for c in curves],
                       eval_floor=float(np.median(spreads)),
                       eval_floor_max=float(max(spreads)), grid_step=float(step),
                       nfolds=len(curves), seqlen=seqlen, windows=NW)
    print(f"\n    u* per fold            : {ustars}", flush=True)
    print(f"    u* spread across folds : {max(ustars) - min(ustars):.4f}   "
          f"(one grid step = {step:.4f})", flush=True)
    print(f"    evaluation floor       : median {np.median(spreads):.4f}  "
          f"max {max(spreads):.4f} ppl", flush=True)
    print(f"    tie-rule floor (stored): "
          f"{ {'pythia': 0.5358, 'opt': 0.0667, 'gpt2': 0.0003, 'smollm2': 0.2398}.get(tag)}",
          flush=True)
    print(f"    total {time.time() - t0:.0f}s", flush=True)

print("\n\n  ================ VERDICT ================", flush=True)
for tag, r in RESULT.items():
    within = max(r["ustars"]) - min(r["ustars"])
    print(f"  {tag:<9} u* moves {within:.4f} across folds of ITS OWN corpus "
          f"(grid step {r['grid_step']:.4f});  eval floor {r['eval_floor']:.4f} ppl "
          f"vs tie floor {{'pythia':0.5358,'opt':0.0667,'gpt2':0.0003,'smollm2':0.2398}}[tag]"
          .replace("{'pythia':0.5358,'opt':0.0667,'gpt2':0.0003,'smollm2':0.2398}[tag]",
                   f"{ {'pythia':0.5358,'opt':0.0667,'gpt2':0.0003,'smollm2':0.2398}[tag]:.4f}"),
          flush=True)
if len(RESULT) >= 2:
    a, b = TAGS[0], TAGS[1]
    wa = max(RESULT[a]["ustars"]) - min(RESULT[a]["ustars"])
    wb = max(RESULT[b]["ustars"]) - min(RESULT[b]["ustars"])
    between = abs(np.mean(RESULT[a]["ustars"]) - np.mean(RESULT[b]["ustars"]))
    print(f"\n  within-model spread : {a} {wa:.4f}   {b} {wb:.4f}")
    print(f"  between-model gap   : {between:.4f}")
    print(f"\n  OUTCOME {'A' if between > max(wa, wb) else 'B'}: "
          + ("the between-model gap exceeds the within-model spread -- the disagreement "
             "survives resampling."
             if between > max(wa, wb) else
             "the within-model spread is as large as the between-model gap -- the "
             "cross-family comparison is sampling noise and every conclusion drawn from "
             "it is unsupported."))
json.dump(RESULT, open(os.path.join(HERE, "u_eval_floor.json"), "w"), indent=1)
print(f"\n  wrote u_eval_floor.json", flush=True)
