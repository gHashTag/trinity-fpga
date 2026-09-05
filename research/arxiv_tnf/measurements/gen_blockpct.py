#!/usr/bin/env python3
"""Generator for blockpct_2026-08-20.json — the record behind tab:blockpct.

The paper (tab:blockpct and the two paragraphs around it) prints the
within-block span of a trained network's weights at block 32:
median 1.89 binades, p90 2.45, p99 3.04, p99.9 3.75.  Until 2026-08-20 no
measurement record backed those four numbers; the prose does not even name
the model.  The lineage docs that first printed 1.89/3.04
(research/block/BLOCK_AXIS_VERDICT_2026-08-10.md, research/block/kkt_element.py)
pin the workload to SmolLM2-135M, and this generator reproduces all four
percentiles from that checkpoint.

DEFINITION — the convention of the generating computation, which turned out
to ship in the tree: research/block/block_tnf.py ("ЧТО БЛОК РЕАЛЬНО
ПОСЕЩАЕТ") computes spread = -log2(median(|w|/amax)) per block via
torch.median and prints exactly these four percentiles (50/90/99/99.9).
This generator reproduces it from the checkpoint directly:
  * tensors: every 2-D weight of the checkpoint whose name contains neither
    "embed" nor "norm" — the same quantisable-linear set as
    conformance/ppl_scale_axis.py and block_tnf.py's nn.Linear-except-lm_head
    (210 tensors, 3,317,760 blocks).
  * blocks: K=32 along the contraction (last) axis.
  * span of one block, in binades:  log2( max|w|  /  lower-median|w| ),
    where lower-median is the 16th of the 32 sorted magnitudes — the
    torch.median convention for even counts, i.e. block_tnf.py's
    y.median(dim=1).  (The numpy interpolated median gives 1.84/2.39/2.96/3.67
    instead and does NOT reproduce the printed table.)
  * percentiles over blocks: numpy linear interpolation.

Blocks whose lower-median is zero contribute an infinite span and are
excluded; their count is recorded.

Deterministic: no randomness anywhere in the path.
Model: HuggingFaceTB/SmolLM2-135M snapshot 93efa2f097d58c2a74874c7e644dbc9b0cee75a2
       (sha256 of model.safetensors recorded in the output).
Run:   python3 gen_blockpct.py          (from this directory; ~1 min, CPU)
"""
import hashlib
import json
import os

import numpy as np
import torch
from safetensors.torch import load_file

MODEL_DIR = os.path.expanduser(
    "~/.cache/huggingface/hub/models--HuggingFaceTB--SmolLM2-135M/"
    "snapshots/93efa2f097d58c2a74874c7e644dbc9b0cee75a2")
K = 32
PAPER = {"p50": 1.89, "p90": 2.45, "p99": 3.04, "p99.9": 3.75}
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   "blockpct_2026-08-20.json")


def main():
    st = os.path.join(MODEL_DIR, "model.safetensors")
    sha = hashlib.sha256(open(st, "rb").read()).hexdigest()
    sd = load_file(st)
    names, chunks = [], []
    for name, w in sd.items():
        if w.ndim != 2 or "embed" in name or "norm" in name:
            continue
        n = (w.shape[1] // K) * K
        if n == 0:
            continue
        names.append(name)
        chunks.append(w[:, :n].reshape(-1, K).double().abs())
    b = torch.cat(chunks).numpy()
    amax = b.max(axis=1)
    lower_med = np.sort(b, axis=1)[:, K // 2 - 1]
    with np.errstate(divide="ignore", invalid="ignore"):
        span = np.log2(amax / lower_med)
    finite = np.isfinite(span)
    s = span[finite]

    rows = {}
    for q in (50, 90, 99, 99.9):
        v = float(np.percentile(s, q))
        estar = int(np.ceil(np.log2(v)))
        rows[f"p{q}"] = {
            "span_binades": round(v, 6),
            "paper_prints": PAPER[f"p{q}"],
            "matches_at_printed_precision": round(v, 2) == PAPER[f"p{q}"],
            "Estar_ceil_log2_span": estar,
            "element": {1: "E1M2", 2: "E2M1"}.get(estar, f"E{estar}M?"),
        }

    rec = {
        "record": "within-block span percentiles behind tab:blockpct",
        "date": "2026-08-20",
        "generator": "research/arxiv_tnf/measurements/gen_blockpct.py",
        "model": "HuggingFaceTB/SmolLM2-135M",
        "snapshot": "93efa2f097d58c2a74874c7e644dbc9b0cee75a2",
        "model_safetensors_sha256": sha,
        "tensor_set": "2-D weights, name contains neither 'embed' nor 'norm' "
                      "(= conformance/ppl_scale_axis.py quantisable set)",
        "n_tensors": len(names),
        "block": K,
        "block_axis": "contraction (last) axis",
        "n_blocks": int(b.shape[0]),
        "n_blocks_excluded_zero_lower_median": int((~finite).sum()),
        "span_definition": "log2(max|w| / lower-median|w|), lower-median = "
                           "16th of 32 sorted magnitudes (torch.median "
                           "convention for even counts; = the spread "
                           "computation of research/block/block_tnf.py)",
        "percentile_method": "numpy linear interpolation over blocks",
        "generating_computation": "research/block/block_tnf.py prints these "
                                  "same four percentiles from the same "
                                  "definition; this record reproduces them "
                                  "checkpoint-side without the model forward",
        "percentiles": rows,
        "note": "the paper's prose does not name the model for this table; "
                "the lineage (research/block/block_tnf.py, "
                "research/block/BLOCK_AXIS_VERDICT_2026-08-10.md, "
                "research/block/kkt_element.py) and this reproduction pin it "
                "to SmolLM2-135M",
    }
    with open(OUT, "w") as f:
        json.dump(rec, f, indent=2)
    print(json.dumps(rec["percentiles"], indent=2))
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
