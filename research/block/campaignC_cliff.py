#!/usr/bin/env python3
"""Does MXFP4's level 1 sit exactly on a step of the perplexity surface?

The zoom found the response flat-ish from -0.02% to -0.35% (22.0627 -> 22.0485)
but 21.9397 at exactly 0 -- a 0.123 ppl gap opening within the first 0.02%,
which is 17x smaller than the interval over which the rest of the curve barely
moves. Either there is a step at delta -> 0-, or the curve turns over somewhere
inside the first 0.02%.

This brackets delta = 0 as tightly as float64 usefully allows, symmetrically, so
the two sides can be compared. If ppl at -0.001% is already ~22.06 then MXFP4's
own level 1 sits ON a discontinuity of the surface, which is a stronger and more
uncomfortable statement than "the surface is steep".

Also reports how many weights change bin at each step, so a bin-reassignment
mechanism can be confirmed or ruled out with the same run.
"""
import json
import os
import sys
import time

if os.environ.get("CAMPC_DETACH") == "1" and os.fork() > 0:
    os._exit(0)
if os.environ.get("CAMPC_DETACH") == "1":
    os.setsid()
    sys.stdout.flush()

import torch

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "block_tnf.py")
MARKER = 'print("загружаю модель…", flush=True)'
ns = {}
exec(compile(open(SRC, encoding="utf-8").read().split(MARKER)[0], SRC, "exec"),
     ns)
fp_levels, q_e8m0_t = ns["fp_levels"], ns["q_e8m0_t"]
quant, perplexity, target_modules, load_wikitext = (
    ns[k] for k in ("quant", "perplexity", "target_modules", "load_wikitext"))
K, SEQLEN = ns["K"], ns["SEQLEN"]
W = os.path.dirname(ns["MODEL"])
torch.set_grad_enabled(False)
NWIN, MDIR = 40, "smollm2"
OUT = os.path.join(HERE, f"campaignC_cliff_{MDIR}.json")

v = sorted(fp_levels(2, 1))
MXFP4 = [x / v[-1] for x in v]
MXFP4[-1] = 1.0

DELTAS = [-0.0002, -0.00005, -0.00001, 0.0, 0.00001, 0.00005, 0.0002]


def main():
    from transformers import AutoModelForCausalLM, AutoTokenizer
    path = os.path.join(W, MDIR)
    tok = AutoTokenizer.from_pretrained(path)
    model = AutoModelForCausalLM.from_pretrained(path, dtype=torch.float32)
    model.eval()
    ids = tok(load_wikitext(), return_tensors="pt").input_ids
    flat = ids.reshape(-1)
    win = flat[:(flat.numel() // SEQLEN) * SEQLEN].view(-1, SEQLEN)
    lins = target_modules(model)
    orig = {n: m.weight.detach().clone() for n, m in lins}

    res = {}

    def bins(lv):
        """Bin index of every weight, so reassignment can be counted."""
        t = torch.tensor(sorted(lv), dtype=torch.float64)
        bnd = (t[:-1] + t[1:]) / 2
        out = []
        for _, m in lins:
            w = m.weight.detach().double()
            n = (w.shape[1] // K) * K
            if n == 0:
                continue
            head = w[:, :n].reshape(-1, K)
            s = q_e8m0_t((head.abs().amax(dim=1) / t[-1]).clamp(min=1e-30))
            out.append(torch.bucketize((head / s[:, None]).abs(),
                                       bnd).reshape(-1).to(torch.int8))
        return torch.cat(out)

    base_idx = bins(MXFP4)          # reference assignment, before the loop
    for d in DELTAS:
        lv = list(MXFP4)
        lv[1] = MXFP4[1] * (1 + d)
        assert lv[0] < lv[1] < lv[2] and abs(lv[-1] - 1.0) < 1e-12
        moved = int((bins(lv) != base_idx).sum())
        t0 = time.time()
        for n, m in lins:
            m.weight.copy_(quant(orig[n], lv))
        p = perplexity(model, win[:NWIN].reshape(1, -1), NWIN)
        for n, m in lins:
            m.weight.copy_(orig[n])
        res[d] = {"ppl": p, "level": lv[1], "moved_bins": moved}
        json.dump({str(k): v for k, v in res.items()}, open(OUT, "w"), indent=1)
        print(f"  {d:>+11.5%}  L1={lv[1]:.17f}  ppl {p:>9.4f}  "
              f"bins moved {moved:>9}   ({time.time()-t0:.0f}s)", flush=True)

    p0 = res[0.0]["ppl"]
    print(f"\n{'delta':>12}{'ppl':>11}{'vs MXFP4':>11}{'bins moved':>13}")
    for d in DELTAS:
        print(f"{d:>+12.5%}{res[d]['ppl']:>11.4f}"
              f"{100*(res[d]['ppl']/p0-1):>+10.3f}%{res[d]['moved_bins']:>13,}")
    lo, hi = res[-0.00001]["ppl"], res[0.00001]["ppl"]
    print(f"\nacross the smallest bracket (+-0.001% of the level, "
          f"+-{MXFP4[1]*1e-5:.2e} absolute):")
    print(f"   left  {lo:.4f}   centre {p0:.4f}   right {hi:.4f}")
    print(f"   left-centre {lo-p0:+.4f} ppl   right-centre {hi-p0:+.4f} ppl")
    step = abs(lo - p0) > 0.05
    print(f"\n{'STEP AT ZERO: MXFP4 sits on a discontinuity' if step else
           'no step: the curve turns over smoothly inside 0.02%'}")
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
