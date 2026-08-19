#!/usr/bin/env python3
"""Generator for weight_ranges_2026-08-20.json — the weight-derived range
numbers the range-provenance sweep (research/RANGE_PROVENANCE_2026-08-20.md,
rows 50-51 and addendum) left UNCHECKED-EXPENSIVE.

Backs, from the cached checkpoints directly (no model forward):

1. Block-scale occupancy (paper: "Over 3,317,760 block scales the range
   actually occupied is 8.32 binades on SmolLM2-135M and 9.12 on
   Qwen2.5-0.5B"): ideal block scales s = amax/6 over K=32 blocks of every
   quantisable linear — the block_scales() convention of
   conformance/ppl_scale_axis.py, whose --diagnose mode reproduces the
   SmolLM2 number independently.  NOTE the paper's block count 3,317,760 is
   SmolLM2's alone; Qwen2.5-0.5B has 11,182,080 blocks.

2. Channel dynamic range (paper: "268.95x median over 155,520 channels"):
   per-output-channel max|w| / p1|w| (1st percentile of the row's
   magnitudes, zeros included, numpy linear interpolation), median over all
   rows of the SmolLM2 quantisable linears.  The p1 convention is the one
   research/block/block_ladder.py used (np.quantile(..., 0.01));
   max/min-nonzero gives 2800.7x and max/p0.1 gives 1408.6x — neither
   reproduces the printed number.

3. Per-tensor scale span across the 210 quantisable linear tensors of
   SmolLM2-135M, in octaves — the measurable content behind
   thm:barrelrange's "210 layers ... 3.15 octaves", whose own provenance
   the paper's untraced-figures subsection concedes.  Measured here:
   span of per-tensor rms = 3.1510 octaves (matches the printed 3.15 at
   printed precision), span of per-tensor amax = 3.8972 octaves.  Both are
   below four octaves, so the theorem's two-bit-selector conclusion
   survives under either reading; this record does NOT claim which quantity
   the original figure was computed from.

Deterministic: no randomness anywhere in the path.
Models (local HF cache, offline):
  HuggingFaceTB/SmolLM2-135M  snapshot 93efa2f097d58c2a74874c7e644dbc9b0cee75a2
  Qwen/Qwen2.5-0.5B           snapshot 060db6499f32faf8b98477b0a26969ef7d8b9987
Run: python3 gen_weight_ranges.py   (from this directory; ~2 min, CPU)
"""
import hashlib
import json
import math
import os

import numpy as np
import torch
from safetensors.torch import load_file

SMOL = os.path.expanduser(
    "~/.cache/huggingface/hub/models--HuggingFaceTB--SmolLM2-135M/"
    "snapshots/93efa2f097d58c2a74874c7e644dbc9b0cee75a2/model.safetensors")
QWEN = os.path.expanduser(
    "~/.cache/huggingface/hub/models--Qwen--Qwen2.5-0.5B/"
    "snapshots/060db6499f32faf8b98477b0a26969ef7d8b9987/model.safetensors")
K = 32
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   "weight_ranges_2026-08-20.json")


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 22), b""):
            h.update(chunk)
    return h.hexdigest()


def quantisable(sd):
    """conformance/ppl_scale_axis.py convention: 2-D, not embed, not norm."""
    return [(n, w) for n, w in sd.items()
            if w.ndim == 2 and "embed" not in n and "norm" not in n]


def scale_occupancy(sd):
    scales = []
    for _, w in quantisable(sd):
        n = (w.shape[1] // K) * K
        if n == 0:
            continue
        a = w[:, :n].reshape(-1, K).double().abs().amax(dim=1)
        scales.append(a[a > 0] / 6.0)
    s = torch.cat(scales)
    lo, hi = math.log2(float(s.min())), math.log2(float(s.max()))
    return {"n_blocks": int(s.numel()), "log2_lo": round(lo, 4),
            "log2_hi": round(hi, 4), "occupied_binades": round(hi - lo, 4)}


def main():
    rec = {
        "record": "weight-derived range numbers: block-scale occupancy, "
                  "channel dynamic range, per-tensor scale span",
        "date": "2026-08-20",
        "generator": "research/arxiv_tnf/measurements/gen_weight_ranges.py",
        "models": {
            "SmolLM2-135M": {
                "snapshot": "93efa2f097d58c2a74874c7e644dbc9b0cee75a2",
                "model_safetensors_sha256": sha256(SMOL)},
            "Qwen2.5-0.5B": {
                "snapshot": "060db6499f32faf8b98477b0a26969ef7d8b9987",
                "model_safetensors_sha256": sha256(QWEN)},
        },
        "tensor_set": "2-D weights, name contains neither 'embed' nor 'norm' "
                      "(= conformance/ppl_scale_axis.py quantisable set)",
    }

    smol_sd = load_file(SMOL)
    qwen_sd = load_file(QWEN)

    # 1. block-scale occupancy (s = amax/6, K=32; ppl_scale_axis convention)
    occ_s = scale_occupancy(smol_sd)
    occ_q = scale_occupancy(qwen_sd)
    rec["block_scale_occupancy"] = {
        "definition": "log2 span of ideal block scales s = amax/6, K=32 "
                      "along the contraction axis (= block_scales() of "
                      "conformance/ppl_scale_axis.py, whose --diagnose mode "
                      "independently reproduces the SmolLM2 row)",
        "SmolLM2-135M": {**occ_s, "paper_prints": 8.32,
                         "matches": round(occ_s["occupied_binades"], 2) == 8.32},
        "Qwen2.5-0.5B": {**occ_q, "paper_prints": 9.12,
                         "matches": round(occ_q["occupied_binades"], 2) == 9.12},
        "note": "the paper's '3,317,760 block scales' is the SmolLM2 count "
                "alone; the Qwen2.5-0.5B occupancy is over 11,182,080 blocks",
    }

    # 2. channel dynamic range, SmolLM2
    ratios = []
    for _, w in quantisable(smol_sd):
        a = w.double().abs().numpy()
        mx = a.max(axis=1)
        p1 = np.percentile(a, 1.0, axis=1)
        ok = (mx > 0) & (p1 > 0)
        ratios.append(mx[ok] / p1[ok])
    r = np.concatenate(ratios)
    med = float(np.median(r))
    rec["channel_dynamic_range"] = {
        "model": "SmolLM2-135M",
        "definition": "per output-channel (row) max|w| / p1|w|, p1 = 1st "
                      "percentile of the row's magnitudes, zeros included, "
                      "numpy linear interpolation; median over channels "
                      "(the np.quantile(...,0.01) convention of "
                      "research/block/block_ladder.py)",
        "n_channels": int(r.size),
        "median_ratio": round(med, 4),
        "paper_prints": 268.95,
        "matches": round(med, 2) == 268.95,
        "rejected_definitions": {
            "max/min-nonzero median": 2800.68,
            "max/p0.1 median": 1408.62,
        },
    }

    # 3. per-tensor scale span, SmolLM2 (thm:barrelrange's 210 layers)
    amaxes, rmses = [], []
    for _, w in quantisable(smol_sd):
        a = w.double().abs()
        amaxes.append(float(a.max()))
        rmses.append(float((a ** 2).mean().sqrt()))
    amaxes, rmses = np.array(amaxes), np.array(rmses)
    span_amax = math.log2(amaxes.max() / amaxes.min())
    span_rms = math.log2(rmses.max() / rmses.min())
    rec["per_tensor_scale_span"] = {
        "model": "SmolLM2-135M",
        "n_tensors": int(amaxes.size),
        "paper_claims_layers": 210,
        "layer_count_matches": int(amaxes.size) == 210,
        "span_per_tensor_rms_octaves": round(span_rms, 4),
        "span_per_tensor_amax_octaves": round(span_amax, 4),
        "paper_prints_octaves": 3.15,
        "rms_span_matches_printed": round(span_rms, 2) == 3.15,
        "both_below_four_octaves": bool(span_rms < 4 and span_amax < 4),
        "note": "the paper's untraced-figures subsection concedes 3.15 has "
                "no generating file; this record states what IS measurable "
                "from the checkpoint (rms-span equals 3.15 at printed "
                "precision, amax-span is 3.90) without claiming which "
                "quantity the original figure came from. thm:barrelrange's "
                "two-bit conclusion needs only span < 4 octaves, which both "
                "measured readings satisfy.",
    }

    with open(OUT, "w") as f:
        json.dump(rec, f, indent=2)
    print(json.dumps({k: rec[k] for k in
                      ("block_scale_occupancy", "channel_dynamic_range",
                       "per_tensor_scale_span")}, indent=2))
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
