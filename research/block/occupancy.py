#!/usr/bin/env python3
"""Block-normalised occupancy of the intervals two codebooks actually differ in.

PREREGISTRATION_OCCUPANCY_2026-08-12.md, written before any of this was
computed. The claim it tests: a MOMENT of the block-normalised distribution is
absorbed by the E8M0 scale (SCALE_ABSORBS_THE_TAILS, range 0.190 where the raw
statistic spans 14.6x), but a moment integrates over the whole support and is
dominated by the bulk. Two codebooks differing by one level differ ONLY where
that level changes the nearest-neighbour assignment, so what matters is the
LOCAL mass there -- which a moment cannot see.

The altered interval, derived rather than eyeballed: inserting level x between
neighbours a < x < b moves the decision boundaries from (a+b)/2 to (a+x)/2 and
(x+b)/2, so exactly the magnitudes in [(a+x)/2, (x+b)/2] are reconstructed
differently. That interval is computed from the books themselves, per placement,
so it cannot drift from what the codebooks do.

    python3 occupancy.py            all eight checkpoints -> occupancy_all.json
"""
import json
import os
import sys

import numpy as np
import torch

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import campaignA_books as A                                      # noqa: E402
import provenance as PV                                          # noqa: E402

SRC = {"smollm2": "HuggingFaceTB/SmolLM2-135M", "qwen": "Qwen/Qwen2.5-0.5B",
       "pythia": "EleutherAI/pythia-160m", "opt": "facebook/opt-125m",
       "gpt2": "gpt2", "gptneo": "EleutherAI/gpt-neo-125m",
       "bloom": "bigscience/bloom-560m", "mamba": "state-spaces/mamba-130m-hf"}
MXFP4 = [0.0, 1 / 12, 2 / 12, 3 / 12, 4 / 12, 6 / 12, 8 / 12, 1.0]


def altered_interval(levels):
    """[lo, hi] of |y| whose nearest level differs between MXFP4 and this book.

    Both books are compared on MAGNITUDE: the placements insert one positive or
    one negative level, and the interval is where the assignment changes.
    """
    pos = sorted({abs(float(x)) for x in levels})
    base = sorted(MXFP4)
    extra = [x for x in pos if not any(abs(x - b) < 1e-12 for b in base)]
    if len(extra) != 1:
        return None
    x = extra[0]
    below = max(b for b in base if b < x)
    above = min(b for b in base if b > x)
    return [(below + x) / 2, (x + above) / 2]


def widest_cells():
    """MXFP4's two widest reconstruction cells, for O4."""
    b = sorted(MXFP4)
    edges = [(b[i] + b[i + 1]) / 2 for i in range(len(b) - 1)]
    cells = [(0.0, edges[0])] + [(edges[i], edges[i + 1])
                                 for i in range(len(edges) - 1)] + [(edges[-1], 1.0)]
    w = sorted(cells, key=lambda c: c[1] - c[0], reverse=True)[:2]
    return w


def norm_mags(mods):
    """|w|/amax over blocks of 32 along the contraction axis, as float32."""
    out = []
    for w in mods:
        x = w.flatten()
        n = x.numel() // 32 * 32
        b = x[:n].view(-1, 32)
        amax = b.abs().amax(1, keepdim=True).clamp_min(1e-30)
        out.append((b / amax).abs().flatten())
    return torch.cat(out)


def main():
    from transformers import AutoModelForCausalLM
    from transformers.pytorch_utils import Conv1D

    books = {n: [float(x) for x in lv] for n, k, lv in A.candidates()}
    iv = {n: altered_interval(lv) for n, lv in books.items()}
    bad = [n for n, v in iv.items() if v is None]
    if bad:
        print(f"ABORT: no single inserted level found for {bad}")
        return 3
    cells = widest_cells()
    print("  altered intervals, derived from the books:")
    for n, v in sorted(iv.items(), key=lambda t: t[1][0]):
        print(f"    {n:<16} [{v[0]:.5f}, {v[1]:.5f}]  width {v[1]-v[0]:.5f}")
    print(f"  MXFP4's two widest cells (O4): {cells}")

    out = {"intervals": iv, "widest_cells": cells, "models": {}}
    for tag, src in SRC.items():
        try:
            m = AutoModelForCausalLM.from_pretrained(src, dtype=torch.float32)
            m.eval()
            ws = []
            for name, mod in m.named_modules():
                if "lm_head" in name:
                    continue
                if isinstance(mod, Conv1D):
                    ws.append(mod.weight.data.t().contiguous())
                elif isinstance(mod, torch.nn.Linear):
                    ws.append(mod.weight.data)
            if not ws:
                print(f"  {tag:<9} NO TARGETS -- skipped, not counted as zero")
                continue
            y = norm_mags(ws)
            rec = {"n": int(y.numel())}
            for n, (lo, hi) in iv.items():
                rec[n] = float(((y >= lo) & (y < hi)).float().mean())
            rec["widest2"] = float(sum(
                ((y >= lo) & (y < hi)).float().mean() for lo, hi in cells))
            out["models"][tag] = rec
            print(f"  {tag:<9} NEAR0 {rec['MX-asym-NEAR0']:.5f}   "
                  f"MID {rec['MX-asym-MID']:.5f}   widest2 {rec['widest2']:.5f}",
                  flush=True)
            del m, y, ws
        except Exception as e:                                    # noqa: BLE001
            print(f"  {tag:<9} FAILED {type(e).__name__}: {str(e)[:60]}")
    out["provenance"] = PV.harness_fingerprint()
    json.dump(out, open(os.path.join(HERE, "occupancy_all.json"), "w"), indent=1)
    print("  wrote occupancy_all.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
