#!/usr/bin/env python3
"""What relative perturbation does MXFP4 actually apply?

TWO_REGIMES_2026-08-12.md compares OPT and GPT-Neo on an eps ladder and finds
different functional forms -- OPT quadratic at 1.998, GPT-Neo steeper at 2.440.
The reading that would explain a 21x cost difference is that MXFP4's fixed-size
perturbation lands inside one checkpoint's quadratic basin and past the other's.

That reading is unfalsifiable until MXFP4's perturbation is on the same axis as
the ladder. So: measure it.

    eps_eff = RMS(quantised - original) / RMS(original)

per tensor and pooled, over exactly the tensors the campaign quantises, with the
same E8M0 block scale. Same definition the noise ladder uses -- seed_control
perturbs by `eps * RMS(w)` per tensor, so eps_eff is directly comparable and no
conversion is involved.

TWO THINGS THIS DOES NOT ASSUME, both of which would be easy to slip:

  * that the quantisation error is isotropic. It is NOT -- it is a deterministic
    function of the weights, correlated with them, and concentrated where the
    codebook is coarse. eps_eff says how BIG it is, not that random noise of the
    same size costs the same. The ladder measures the isotropic response; the gap
    between the two is a real effect and is reported, never assumed away.
  * that RMS is the right summary. A perturbation with the same RMS and a heavier
    tail is a different perturbation, so the ratio of 4th to 2nd moments of the
    error is reported alongside.

    MDIR=<tag> python3 effective_eps.py
"""
import json
import os
import sys

import numpy as np
import torch

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import sensitivity as S                                          # noqa: E402
import provenance as PV                                          # noqa: E402

MXFP4 = [0.0, 1 / 12, 2 / 12, 3 / 12, 4 / 12, 6 / 12, 8 / 12, 1.0]


def main():
    from transformers import AutoModelForCausalLM
    from transformers.pytorch_utils import Conv1D

    tag = os.environ["MDIR"]
    src = S.SRC[tag]
    mdl = AutoModelForCausalLM.from_pretrained(src, dtype=torch.float32)
    mdl.eval()
    mods, conv = [], 0
    for name, m in mdl.named_modules():
        if "lm_head" in name:
            continue
        if isinstance(m, Conv1D):
            mods.append(m.weight.data.t().contiguous()); conv += 1
        elif isinstance(m, torch.nn.Linear):
            mods.append(m.weight.data)
    if not mods:
        print(f"ABORT: no target tensors on {tag}")
        return 3

    quant = S.ns["quant"]
    num = den = 0.0
    e4 = e2 = 0.0
    n = 0
    per = []
    for w in mods:
        q = quant(w, MXFP4)
        d = (q - w).flatten().double()
        num += float((d ** 2).sum()); den += float((w.flatten().double() ** 2).sum())
        e4 += float((d ** 4).sum()); e2 += float((d ** 2).sum()); n += d.numel()
        per.append(float(d.pow(2).mean().sqrt() / w.flatten().double().pow(2).mean().sqrt()))
    eps = (num / den) ** 0.5
    kurt = (e4 / n) / ((e2 / n) ** 2)
    out = {"model": tag, "src": src, "n_tensors": len(mods), "n_conv1d": conv,
           "n_elements": n, "eps_eff": eps,
           "eps_eff_per_tensor": {"min": min(per), "median": float(np.median(per)),
                                  "max": max(per)},
           "error_kurtosis": kurt,
           "provenance": PV.describe(src=src)}
    print(f"  {tag:<9} eps_eff = {eps:.5f}   per-tensor [{min(per):.5f}, {max(per):.5f}] "
          f"median {np.median(per):.5f}   error kurtosis {kurt:.3f}", flush=True)
    json.dump(out, open(os.path.join(HERE, f"epseff_{tag}.json"), "w"), indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
