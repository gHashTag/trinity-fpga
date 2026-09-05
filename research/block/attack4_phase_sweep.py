#!/usr/bin/env python3
"""ATTACK 4b — the alignment rule is one continuous knob, not two named rules.

Under s = 2^ceil(log2(a_max / top)) the reconstruction set is {2^k * L_i}, and
scaling a codebook by 2 leaves it unchanged (s halves, levels double). So the
ONLY thing the top level contributes is

    phase  φ = log2(top) mod 1

  φ = 0.000   every codebook normalised to top 1.0   ("rule 2")
  φ = 0.585   raw E2M1, top 6.0                      ("rule 1", MXFP4)
  φ = 0.950   raw Lloyd-Max, top 0.96567             ("rule 1", Lloyd-Max)

The named conventions are three samples of a circle. If MXFP4 at its BEST phase
beats the KL codebook at its best phase, the KL win is an artefact of the phase
the search happened to run at.

Signal: KL(fp32 || quantised) on KLWIN windows — the same objective
kl_optimal_codebook.py searched against, and ~20x cheaper than 40-window
perplexity. Decisive phases are then re-measured on 40-window perplexity by
attack4_phase_confirm.

    NPHASE=12 KLWIN=2 python3 attack4_phase_sweep.py
"""
import os
import sys
import json
import time

import numpy as np
import torch
import torch.nn.functional as F

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "block_tnf.py")
MARKER = 'print("загружаю модель…", flush=True)'
_src = open(SRC, encoding="utf-8").read()
_ns = {}
exec(compile(_src.split(MARKER)[0], SRC, "exec"), _ns)
perplexity = _ns["perplexity"]
target_modules = _ns["target_modules"]
load_wikitext = _ns["load_wikitext"]
MODEL, K, SEQLEN = _ns["MODEL"], _ns["K"], _ns["SEQLEN"]
torch.set_grad_enabled(False)

NPHASE = int(os.environ.get("NPHASE", "12"))
KLWIN = int(os.environ.get("KLWIN", "2"))

MXFP4_RAW = [0.0, 0.5, 1.0, 1.5, 2.0, 3.0, 4.0, 6.0]
LLOYD_RAW = [0.0, 0.10334, 0.21079, 0.32491, 0.44963, 0.59031, 0.75635, 0.96567]
KL_RAW = [0.0, 0.07701, 0.18828, 0.31396, 0.46561, 0.6113, 0.79074, 1.0]


def at_phase(lv, phi):
    """same codebook shape, top level moved to 2^phi (only phi mod 1 matters)"""
    v = sorted(float(x) for x in lv)
    return [x * (2.0 ** phi) / v[-1] for x in v]


def quant_rule1(w, lv):
    lv_t = torch.tensor(sorted(lv), dtype=torch.float64)
    n = (w.shape[1] // K) * K
    if n == 0:
        return w
    head = w[:, :n].reshape(-1, K).double()
    amax = head.abs().amax(dim=1)
    s = torch.pow(2.0, torch.ceil(torch.log2(
        (amax / float(lv_t[-1])).clamp(min=1e-30)))).clamp(min=1e-30)
    y = (head / s[:, None]).abs()
    bnd = (lv_t[:-1] + lv_t[1:]) / 2
    rec = torch.sign(head) * lv_t[torch.bucketize(y, bnd)] * s[:, None]
    out = w.clone()
    out[:, :n] = rec.reshape(-1, n).to(w.dtype)
    return out


def main():
    print("loading model…", flush=True)
    from transformers import AutoModelForCausalLM, AutoTokenizer
    tok = AutoTokenizer.from_pretrained(MODEL)
    model = AutoModelForCausalLM.from_pretrained(MODEL, dtype=torch.float32)
    model.eval()
    ids = tok(load_wikitext(), return_tensors="pt").input_ids
    lins = target_modules(model)
    orig = {n: m.weight.detach().clone() for n, m in lins}
    flat = ids.reshape(-1)
    win = flat[:(flat.numel() // SEQLEN) * SEQLEN].view(-1, SEQLEN)

    # ---- mechanism: how is log2(a_max) distributed mod 1 across blocks? -----
    fr = []
    for _, m in lins:
        w = m.weight.detach().double()
        n = (w.shape[1] // K) * K
        if n == 0:
            continue
        a = w[:, :n].reshape(-1, K).abs().amax(dim=1)
        a = a[a > 0]
        fr.append((torch.log2(a) % 1.0).numpy())
    fr = np.concatenate(fr)
    hist, _ = np.histogram(fr, bins=10, range=(0, 1))
    print(f"\nblocks = {fr.size};  frac(log2 a_max) histogram over [0,1) in 10 bins:")
    print("  " + " ".join(f"{100*h/fr.size:5.1f}%" for h in hist))
    print(f"  uniform would be 10.0% each; max bin {100*hist.max()/fr.size:.1f}%",
          flush=True)

    def apply(lv):
        if lv is None:
            for n, m in lins:
                m.weight.copy_(orig[n])
            return
        for n, m in lins:
            m.weight.copy_(quant_rule1(orig[n], lv))

    apply(None)
    ref = torch.cat([model(win[i:i + 1]).logits.double() for i in range(KLWIN)])
    logp_ref = F.log_softmax(ref, dim=-1)
    p_ref = logp_ref.exp()

    def kl_of(lv):
        apply(lv)
        L = torch.cat([model(win[i:i + 1]).logits.double() for i in range(KLWIN)])
        return float((p_ref * (logp_ref - F.log_softmax(L, dim=-1))).sum(-1).mean())

    phases = [i / NPHASE for i in range(NPHASE)]
    books = (("MXFP4", MXFP4_RAW), ("Lloyd-Max", LLOYD_RAW), ("KL-opt", KL_RAW))
    out = {"phases": phases, "hist": hist.tolist(), "nblocks": int(fr.size)}
    print(f"\nKL(fp32 || quantised), {KLWIN} windows, vs lattice phase")
    print("  phase   " + "".join(f"{n:>12}" for n, _ in books))
    grid = {n: [] for n, _ in books}
    for phi in phases:
        row = []
        for name, lv in books:
            t0 = time.time()
            v = kl_of(at_phase(lv, phi))
            grid[name].append(v)
            row.append(v)
        print(f"  {phi:5.3f}   " + "".join(f"{v:12.6f}" for v in row), flush=True)
    # the three named conventions
    named = {"MXFP4 raw top 6.0": np.log2(6.0) % 1,
             "Lloyd raw top 0.96567": np.log2(0.96567) % 1,
             "all normalised to 1.0": 0.0}
    print("\n  named conventions sit at phase: " +
          ", ".join(f"{k} = {v:.3f}" for k, v in named.items()))
    print("\n  best phase per codebook (by KL):")
    for name, _ in books:
        arr = np.array(grid[name])
        i, j = int(arr.argmin()), int(arr.argmax())
        out[name] = grid[name]
        print(f"    {name:<10} best φ={phases[i]:.3f} KL={arr[i]:.6f} | "
              f"worst φ={phases[j]:.3f} KL={arr[j]:.6f} | "
              f"spread {100*(arr[j]/arr[i]-1):.1f}%")
    print("\n  KL-opt best vs MXFP4 best: "
          f"{100*(min(grid['KL-opt'])/min(grid['MXFP4'])-1):+.2f}% "
          "(negative = KL codebook still wins at each one's own best phase)")
    apply(None)
    p = os.path.join(HERE, "attack4_phase_sweep.json")
    json.dump(out, open(p, "w"), indent=1)
    print(f"\nwrote {p}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
