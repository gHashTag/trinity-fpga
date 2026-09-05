#!/usr/bin/env python3
"""Predict u* from the weights alone and see whether it matches the measured u*.

WHY THIS IS THE RIGHT NEXT HYPOTHESIS
-------------------------------------
Three parameter-free statistics of the block maxima have now failed to explain anything about the
alignment optimum: the clamp fraction, the kurtosis, and the non-uniformity of frac(log2 amax).
The last was pre-registered and refuted outright (Spearman = 0.000).

All three were BETWEEN-block statistics -- they describe where the block maxima sit relative to
one another. But the alignment constant does not act between blocks. Write the rule out:

    s = g^floor(log_g(amax / c)),        c = max_norm / g^(1-u)

Raising u lowers c, which lowers s, which does two things at once and in opposite directions:

    * the codebook [0, max_norm]*s covers a SMALLER absolute range   -> MORE clipping of the
      largest weights in each block
    * the quantisation step is s * (grid step)                       -> FINER resolution for
      every weight that is not clipped

That is a clip-versus-resolution trade, and it is settled entirely by how the weights inside a
block are distributed RELATIVE TO THAT BLOCK'S OWN MAXIMUM. A block holding one dominant outlier
and 31 small values loses a great deal by clipping and little by coarsening; a block whose values
all sit near its maximum is the reverse. Nothing about where the block's maximum falls on the
number line enters at all -- which is why the three between-block statistics found nothing, and
the reason to expect a within-block trade to be the actual mechanism.

THE PREDICTION IS EXACT AND UNFITTED
------------------------------------
argmin_u (total weight MSE) is computed with THE SAME quantiser the perplexity sweep used --
align_u.quantise_tensor_u, guarded by 30 self-tests -- so it is a genuine per-model point
prediction of the alignment optimum from weights only, with no forward pass and no fitted
constant.

  !! A shortcut was written first and thrown away, and the reason is worth keeping. The plan was
  !! to precompute v = |w|/amax once and evaluate a closed form sum_b s_b^2 sum_w (Q(v t_b)-v t_b)^2
  !! at every u. That is algebraically right but NOT the same experiment: S.scale() with nlev
  !! confines the exponent to a field anchored at THE TENSOR'S OWN MINIMUM, so calling it on the
  !! concatenation of every projection's maxima anchors the field globally instead of per tensor.
  !! The planned gate compared closed form against the real quantiser ON ONE TENSOR, where the
  !! concatenation does not arise -- it would have passed while the full computation was wrong.
  !! A gate that tests one unit does not test the aggregation over units. Doing it the direct way
  !! removes the shortcut, the gate, and the whole class of error, and costs a minute per model.

PRE-REGISTERED, both reported:

  A. predicted u* matches measured u* on every model (to one grid step).
     -> the alignment optimum IS determined by weight statistics; the mechanism is the
        within-block clip/resolution trade. This would be the first positive mechanism the
        alignment line has produced, and it must then be reconciled with the r = +0.13 per-layer
        result and with unweighted weight-MSE picking the wrong 4-bit ladder on both checkpoints.

  B. predicted u* does not match.
     -> a fourth independent confirmation, and the sharpest, that weight-space error does not
        determine loss response: an exact unfitted point prediction, not a rank correlation over
        four points. It would also mean no weight-only criterion can choose an alignment
        constant -- a limit on the practice of picking format parameters from weight histograms.

The campaign's own prior points at B. Measuring it anyway is worthwhile precisely because an
exact point prediction failing says far more than a weak correlation, and because A would
overturn the campaign's central negative result.
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
TAGS = [a for a in sys.argv[1:] if not a.startswith("--")] or ["gpt2", "pythia", "opt", "smollm2"]

# measured argmin of PERPLEXITY, from the stored sweeps. smollm2's comes from a different grid;
# it is flagged rather than silently pooled -- that pooling is the fault that produced the
# retracted `depth` table.
MEASURED = {"gpt2": (0.2500, "align_u 13pt [0,0.55]"),
            "pythia": (0.4000, "align_u 13pt [0,0.55]"),
            "opt": (0.2500, "align_u 13pt [0,0.55]"),
            # re-swept on the common grid 2026-08-19 (align_u_smollm2.json); the old
            # 0.3410 came from the 8pt [0,0.90] scale_settled grid and is superseded.
            "smollm2": (0.3500, "align_u 13pt [0,0.55]")}


def total_mse(tg, orig, u):
    """Total squared quantisation error over every target projection, at alignment u.

    Per tensor, exactly as the perplexity sweep does it -- so the scale field is anchored per
    tensor, not globally. Returns (sse, nelem, clamped_block_fraction).
    """
    sse = 0.0
    nel = 0
    nsat = nblk = 0
    for nm, mod, tr in tg:
        w = orig[nm]
        q, st = A.quantise_tensor_u(w, tr, u)
        sse += float(((q.double() - w.double()) ** 2).sum())
        nel += int(w.numel())
        nsat += st["nsat"]
        nblk += st["nblk"]
    return sse, nel, nsat / nblk


print("Can the alignment optimum be predicted from the weights alone?\n", flush=True)
S.selftests_global()
A.selftests_u()
S.abort_if_failed()

OUT = {}
for tag in TAGS:
    f = A.FAM[tag]
    t0 = time.time()
    m, _ = A.load(tag)
    tg = A.targets(m)
    A.guard_targets(tag, tg, f["nlayer"] * f["per_layer"])
    orig = {nm: mod.weight.data.clone() for nm, mod, _ in tg}
    del m

    # G1 -- the error must be zero-free and must respond to u at all. A quantiser that silently
    #       did nothing would give a constant MSE and a meaningless argmin.
    e0, nel, _ = total_mse(tg, orig, 0.0)
    e1, _, _ = total_mse(tg, orig, A.U_OCP)
    S.check(e0 > 0 and e1 > 0, f"G1 {tag} MSE positive at both anchors", f"{e0:.6e} / {e1:.6e}")
    S.check(e0 != e1, f"G1 {tag} MSE responds to u", f"u=0 {e0:.6e}  u=OCP {e1:.6e}")
    S.abort_if_failed()

    print(f"  === {tag}: {len(tg)} projections, {nel:,} weights quantised "
          f"({time.time() - t0:.0f}s to load) ===", flush=True)
    print(f"  {'u':>9}{'c':>9}{'clamp%':>9}{'MSE/elem':>16}{'vs min':>10}", flush=True)
    rows = []
    for u in A.U_GRID:
        t1 = time.time()
        e, n, cl = total_mse(tg, orig, u)
        rows.append((u, e / n, cl))
        print(f"  {u:9.4f}{A.c_of_u(u):9.4f}{100 * cl:9.2f}{e / n:16.6e}"
              f"{'':>10}   ({time.time() - t1:.0f}s)", flush=True)
    emin = min(r[1] for r in rows)
    print(f"\n  {'u':>9}{'MSE/elem':>16}{'vs min':>10}", flush=True)
    for u, e, cl in rows:
        print(f"  {u:9.4f}{e:16.6e}{e / emin:10.4f}", flush=True)

    upred = min(rows, key=lambda r: r[1])[0]
    umeas, src = MEASURED[tag]
    step = float(min(np.diff(A.U_GRID)))
    hit = abs(upred - umeas) <= step + 1e-9
    OUT[tag] = dict(u_pred=upred, u_meas=umeas, meas_source=src, grid_step=step, match=bool(hit),
                    rows=[dict(u=u, mse_per_elem=e, clamp=cl) for u, e, cl in rows])
    print(f"\n    PREDICTED u* (weights only, exact) = {upred:.4f}", flush=True)
    print(f"    MEASURED  u* (perplexity)          = {umeas:.4f}   [{src}]", flush=True)
    print(f"    {'MATCH' if hit else 'MISS'} (one grid step = {step:.4f}, "
          f"|delta| = {abs(upred - umeas):.4f})   total {time.time() - t0:.0f}s\n", flush=True)
    del orig, tg

print("\n  ================ VERDICT ================", flush=True)
print(f"  {'model':<10}{'predicted':>11}{'measured':>10}{'delta':>9}", flush=True)
for tag, o in OUT.items():
    print(f"  {tag:<10}{o['u_pred']:>11.4f}{o['u_meas']:>10.4f}"
          f"{o['u_pred'] - o['u_meas']:>+9.4f}    {'MATCH' if o['match'] else 'MISS'}", flush=True)
nm_ = sum(1 for o in OUT.values() if o["match"])
print(f"\n  {nm_} of {len(OUT)} models predicted within one grid step.", flush=True)
if nm_ == len(OUT):
    print("  OUTCOME A: weight statistics DO determine the alignment optimum. The mechanism is the\n"
          "  within-block clip/resolution trade. This must be reconciled with the r = +0.13\n"
          "  per-layer result and with weight-MSE picking the wrong 4-bit ladder on both models.",
          flush=True)
else:
    print("  OUTCOME B: an EXACT, unfitted, per-model point prediction from the weights misses.\n"
          "  Fourth independent confirmation, and the sharpest, that weight-space error does not\n"
          "  determine loss response -- and no weight-only criterion can choose an alignment\n"
          "  constant.", flush=True)
print("\n  Grid caveat RESOLVED 2026-08-19: smollm2 re-swept on the common 13pt [0,0.55] grid\n"
      "  (align_u_smollm2.json): u* = 0.35, consistent with the superseded 0.3410 from the old\n"
      "  8pt grid. All four measured u* now come from the same grid.", flush=True)
json.dump(OUT, open(os.path.join(HERE, "u_predicted.json"), "w"), indent=1)
print(f"\n  wrote u_predicted.json", flush=True)
