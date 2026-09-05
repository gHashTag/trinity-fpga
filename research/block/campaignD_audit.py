#!/usr/bin/env python3
"""Campaign D self-test: is the repair mask selecting the bin it claims?

P3 measures a bin's KL share by restoring the fp32 value of every weight that
lands in that bin.  The first run produced two results that a mask bug would
also produce: mirror bins +6/-6 differing 2.8x on near-identical mass, and a
repair that made the model WORSE.  Neither is trustworthy until the mask is
checked against an instrument that shares no code with it.

So the bin membership is recomputed here from scratch in NUMPY -- own E8M0, own
brute-force nearest-level search with an explicit round-toward-zero tie rule --
and compared position by position with what `campaignD_kl.repaired` actually
restored.  A disagreement of one element fails the test.

The check is not vacuous: a naive signed bucketize (ties toward -inf) is run as
a decoy and must DISAGREE, otherwise the test cannot see the bug it is for.
"""
import os

import numpy as np
import torch

HERE = os.path.dirname(os.path.abspath(__file__))
os.environ.setdefault("MDIR", "smollm2")
import campaignD_kl as KL
import campaignD_pred as P
import campaignC_books as C

W = KL.W
K = KL.K
MX = np.array(C.MXFP4, dtype=np.float64)
SIGNED = np.array(sorted(set(list(-MX[1:]) + [0.0] + list(MX[1:]))))


def brute_bins(w):
    """Independent reimplementation: E8M0 per block, nearest signed level by
    exhaustive search, ties broken toward ZERO.  Returns signed bin index."""
    n = (w.shape[1] // K) * K
    head = w[:, :n].reshape(-1, K).astype(np.float64)
    amax = np.abs(head).max(axis=1)
    s = np.exp2(np.ceil(np.log2(np.maximum(amax, 1e-30))))
    s = np.maximum(s, 1e-30)
    y = head / s[:, None]
    d = np.abs(y[..., None] - SIGNED[None, None, :])
    # ties toward zero: order candidates by (distance, |level|) and take first
    key = d + 1e-9 * np.abs(SIGNED)[None, None, :]
    j = key.argmin(axis=-1)
    lev = SIGNED[j]
    mag_idx = np.zeros_like(j)
    for k in range(1, len(MX)):
        mag_idx = np.where(np.isclose(np.abs(lev), MX[k]), k, mag_idx)
    return np.where(mag_idx == 0, 0, mag_idx * np.sign(lev).astype(int)), n


def naive_bins(w):
    """The decoy: signed bucketize with ties toward -inf."""
    n = (w.shape[1] // K) * K
    head = w[:, :n].reshape(-1, K).astype(np.float64)
    amax = np.abs(head).max(axis=1)
    s = np.maximum(np.exp2(np.ceil(np.log2(np.maximum(amax, 1e-30)))), 1e-30)
    y = head / s[:, None]
    bnd = (SIGNED[:-1] + SIGNED[1:]) / 2
    j = np.searchsorted(bnd, y, side="left")
    lev = SIGNED[j]
    mag_idx = np.zeros_like(j)
    for k in range(1, len(MX)):
        mag_idx = np.where(np.isclose(np.abs(lev), MX[k]), k, mag_idx)
    return np.where(mag_idx == 0, 0, mag_idx * np.sign(lev).astype(int)), n


def main():
    from transformers import AutoModelForCausalLM
    path = os.path.join(W, os.environ["MDIR"])
    model = AutoModelForCausalLM.from_pretrained(path, dtype=torch.float32).eval()
    mods = KL.target_modules(model)
    # a few real tensors, capped so the O(15) brute force stays affordable
    picks = [mods[0], mods[len(mods) // 2], mods[-1]]

    bad = 0
    for name, m in picks:
        w = m.weight.detach()[:96].clone()
        ref, n = brute_bins(w.numpy())
        dec, _ = naive_bins(w.numpy())
        ties = int((ref != dec).sum())

        for b in [-7, -6, -1, 0, 1, 4, 6, 7]:
            got = KL.repaired(w, b)
            wq = KL.quant(w, C.MXFP4)
            restored = (got[:, :n] != wq[:, :n]).numpy()
            want = (ref == b).reshape(w.shape[0], n)
            # a weight already exact under MXFP4 is restored to the same value,
            # so it is invisible in a value diff; compare only where it can show
            visible = (w[:, :n].numpy() != wq[:, :n].numpy())
            diff = int((restored != (want & visible)).sum())
            bad += diff
            if diff:
                print(f"  MISMATCH {name} bin {b:+d}: {diff} positions")
        print(f"{name:<40} n={n:>5}  brute-vs-naive tie disagreements={ties:>6}"
              f"  {'(decoy differs: test is not vacuous)' if ties else '(DECOY AGREES - TEST IS VACUOUS)'}")
    print(f"\nTOTAL mask mismatches against the independent instrument: {bad}")
    print("MASK OK" if bad == 0 else "MASK BROKEN")


if __name__ == "__main__":
    main()
