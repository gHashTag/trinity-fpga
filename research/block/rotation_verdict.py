#!/usr/bin/env python3
"""Does a Hadamard rotation change the direction of the block-axis verdict?

`BLOCK_AXIS_VERDICT_2026-08-10.md` measured MXFP4 at 21.9397 and TNF4 at 36.7214
on SmolLM2-135M and concluded the element axis is decided against us. Those
numbers were taken on **unrotated** weights.

The 2026 state of the art rotates first. MR-GPTQ (*Bridging the Gap Between
Promise and Performance for Microscaling FP4 Quantization*, ICLR 2026,
arXiv:2509.23202) applies a block-wise Hadamard transform with the rotation fused
into the weights, and reports that this brings MXFP4 near NVFP4's accuracy. Our
own `heavy_tail_test.py` independently measures the effect on the distribution:
median excess-kurtosis change of -1.601, i.e. rotation makes weights lighter
tailed, exactly as QuaRot and QuIP intend.

So the distribution the verdict was measured on is not the distribution a 2026
deployment quantises. That scopes the verdict. Whether it *changes* it is the
open question this script answers, and there are three possible answers, only one
of which is good for us:

  - rotation helps both and the gap holds       -> verdict stands, now in scope
  - rotation helps MXFP4 more                   -> verdict stands harder
  - rotation helps TNF4 more                    -> the gap narrows, and by how much
    matters

Method
------
Block-wise Hadamard of exactly the quantisation block size, so the rotation and
the shared scale see the same 32 elements -- this is what "block-wise" means in
the paper, not a full-width rotation.

For a linear layer `y = x W^T`, QuaRot-style rotation computes
`(x H/sqrt(K)) @ Q(W H/sqrt(K))^T`. Rather than modify the forward pass, this
folds the inverse back into the weight:

    W_hat = Q(W H/sqrt(K)) @ H^T/sqrt(K)

which is algebraically the same contraction, because H H^T = K I. It isolates the
effect of rotation on **quantisation error** with no model surgery, so nothing
but the weights differs between the arms.

Instrument checks, before any comparison is read:
  1. the unquantised baseline must land in a plausible band, or nothing means
     anything (the same ruler check block_tnf.py uses);
  2. rotate-then-unrotate with NO quantisation must return the weights to
     within float tolerance -- if the transform is not an involution here, every
     rotated number below is measuring a broken transform rather than rotation;
  3. the measured kurtosis change must be negative, reproducing heavy_tail_test,
     or the rotation is not doing what the literature says it does.

The quantiser, the level tables, the scale rule, the perplexity loop and the
window count are taken **verbatim** from `block_tnf.py` by executing its source
up to its own driver, so this cannot drift from the numbers the verdict reports.

    python3 rotation_verdict.py
"""
import os
import sys

import numpy as np
import torch

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "block_tnf.py")

# Take the helpers from block_tnf.py itself rather than copying them. A copy
# drifts; an import is impossible because that file runs its driver at module
# level. Splitting on its own first driver line is exact and asserted.
MARKER = 'print("загружаю модель…", flush=True)'
_src = open(SRC, encoding="utf-8").read()
if MARKER not in _src:
    raise SystemExit(f"rotation_verdict: driver marker not found in {SRC} -- "
                     "the file changed shape and this split is no longer safe")
_ns = {}
exec(compile(_src.split(MARKER)[0], SRC, "exec"), _ns)

fp_levels = _ns["fp_levels"]
tnf_levels = _ns["tnf_levels"]
quant = _ns["quant"]
perplexity = _ns["perplexity"]
load_wikitext = _ns["load_wikitext"]
target_modules = _ns["target_modules"]
MODEL, K, SEQLEN = _ns["MODEL"], _ns["K"], _ns["SEQLEN"]

NWIN = 40  # the verdict's window count
torch.set_grad_enabled(False)


def hadamard(n):
    """Sylvester Hadamard, n a power of two. H @ H.T == n I."""
    if n & (n - 1):
        raise SystemExit(f"rotation_verdict: block size {n} is not a power of two")
    h = np.array([[1.0]])
    while h.shape[0] < n:
        h = np.block([[h, h], [h, -h]])
    return torch.tensor(h, dtype=torch.float64)


HN = hadamard(K) / np.sqrt(K)          # orthonormal: HN @ HN.T == I


def rotate(w, back=False):
    """Block-wise rotation along the contraction axis, in blocks of K."""
    orig = w.shape
    n = (orig[1] // K) * K
    if n == 0:
        return w
    m = HN.T if back else HN
    head = w[:, :n].double().reshape(-1, K)
    out = w.clone()
    out[:, :n] = (head @ m).reshape(-1, n).to(w.dtype)
    return out


def excess_kurtosis(w):
    x = w.double().flatten()
    x = x - x.mean()
    s = x.std()
    if s == 0:
        return 0.0
    return float(((x / s) ** 4).mean() - 3.0)


def apply_quant(model, orig, levels, rotated):
    """Write quantised weights into the model. levels=None leaves them alone."""
    for name, mod in target_modules(model):
        w = orig[name]
        if levels is None:
            mod.weight.copy_(rotate(rotate(w), back=True) if rotated else w)
            continue
        if rotated:
            mod.weight.copy_(rotate(quant(rotate(w), levels), back=True))
        else:
            mod.weight.copy_(quant(w, levels))


def main():
    print("loading model…", flush=True)
    from transformers import AutoModelForCausalLM, AutoTokenizer
    tok = AutoTokenizer.from_pretrained(MODEL)
    model = AutoModelForCausalLM.from_pretrained(MODEL, dtype=torch.float32)
    model.eval()
    ids = tok(load_wikitext(), return_tensors="pt").input_ids
    orig = {n: m.weight.detach().clone() for n, m in target_modules(model)}
    print(f"  {len(orig)} linear layers, block K={K}, {NWIN} windows of {SEQLEN}")

    # ---- instrument check 1: the ruler -----------------------------------
    base = perplexity(model, ids, NWIN)
    print(f"\nRULER  unquantised baseline = {base:.4f}", flush=True)
    if not (10.0 < base < 60.0):
        raise SystemExit("RULER BROKEN — baseline outside a plausible band. Stop.")

    # ---- instrument check 2: the rotation is an involution ---------------
    worst = 0.0
    for name, w in orig.items():
        rt = rotate(rotate(w), back=True)
        worst = max(worst, float((rt - w).abs().max()))
    print(f"RULER  rotate→unrotate max |Δw| = {worst:.3e}", flush=True)
    if worst > 1e-4:
        raise SystemExit("RULER BROKEN — the rotation is not an involution. Stop.")

    # ---- instrument check 3: rotation lightens the tails -----------------
    deltas = [excess_kurtosis(rotate(w)) - excess_kurtosis(w) for w in orig.values()]
    med = float(np.median(deltas))
    print(f"RULER  median excess-kurtosis change from rotation = {med:+.3f}", flush=True)
    if med >= 0:
        raise SystemExit("RULER BROKEN — rotation did not lighten the tails. Stop.")

    # ---- and, with no quantisation, rotation must change nothing ---------
    apply_quant(model, orig, None, True)
    rt_base = perplexity(model, ids, NWIN)
    print(f"RULER  rotated, unquantised = {rt_base:.4f} (must equal the baseline)", flush=True)
    if abs(rt_base - base) > 0.01:
        raise SystemExit("RULER BROKEN — rotation alone moved perplexity. Stop.")

    ARMS = [
        ("MXFP4  E2M1 + E8M0", fp_levels(2, 1)),
        ("TNF4   E_t=1 packed", tnf_levels(4, 1)),
        ("MXFP6  E2M3 + E8M0", fp_levels(2, 3)),
        ("TNF6   E_t=2 packed", tnf_levels(6, 2)),
    ]

    print(f"\n{'format':<22} {'unrotated':>10} {'rotated':>10} {'Δ':>8} {'vs fp32':>9}")
    results = {}
    for label, lv in ARMS:
        if lv is None:
            print(f"  {label:<20} not realisable")
            continue
        row = {}
        for rotated in (False, True):
            apply_quant(model, orig, lv, rotated)
            row["rot" if rotated else "raw"] = perplexity(model, ids, NWIN)
        results[label] = row
        d = row["rot"] - row["raw"]
        print(f"{label:<22} {row['raw']:>10.4f} {row['rot']:>10.4f} "
              f"{d:>+8.4f} {row['rot'] / base:>8.3f}x", flush=True)

    # ---- the question the script exists to answer ------------------------
    print()
    for a, b, bits in (("MXFP4  E2M1 + E8M0", "TNF4   E_t=1 packed", 4),
                       ("MXFP6  E2M3 + E8M0", "TNF6   E_t=2 packed", 6)):
        if a not in results or b not in results:
            continue
        raw_gap = results[b]["raw"] - results[a]["raw"]
        rot_gap = results[b]["rot"] - results[a]["rot"]
        verdict = ("NARROWS" if abs(rot_gap) < abs(raw_gap) else "WIDENS")
        if rot_gap * raw_gap < 0:
            verdict = "FLIPS"
        print(f"{bits}-bit gap (ours minus MX): unrotated {raw_gap:+.4f} → "
              f"rotated {rot_gap:+.4f}   {verdict}")
    print("\nSCOPE: one model, one calibration-free rotation, no GPTQ error "
          "compensation. MR-GPTQ combines rotation WITH GPTQ; this isolates the "
          "rotation alone, which is the part that changes the distribution.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
