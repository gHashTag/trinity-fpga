#!/usr/bin/env python3
"""Does rotation move quantisation error onto the channels that matter?

`WHY_ROTATION_HURTS_2026-08-11.md` established the puzzle and killed the easy
answer: a block-wise Hadamard **reduces** total weight quantisation error by
3.31 % while making perplexity **8.24 % worse**. No weight-magnitude statistic
explains it, because every one of them says rotation helped. The surviving
hypothesis, written there as a hypothesis:

> Unrotated, quantisation error concentrates on the large weights in a block and
> leaves the small ones nearly exact; a Hadamard mix spreads it evenly across all
> 32 coordinates. If a model's sensitivity is concentrated on particular input
> channels, then spreading error onto sensitive channels costs more than the
> 3.31 % MSE reduction buys.

That predicts something specific and falsifiable. Weight the per-input-channel
quantisation error by how much each channel actually matters, and:

  - plain error must fall (it does, −3.31 %, and this script re-derives it as a
    consistency check rather than trusting the earlier number), while
  - **importance-weighted error must rise.**

If the weighted error falls too, this hypothesis dies exactly like the last one.

Importance is the per-input-channel mean activation magnitude collected by
forward hooks on calibration text — AWQ's own definition, and the same hook the
repository already uses in `importance_diagnostic.py`. Note the repository's
standing caveat: that script found E[h|y] essentially flat, i.e. importance is
nearly independent of *weight magnitude*. That does not make importance itself
flat, and it is the spread across channels, not its coupling to weight size,
that this test needs.

Controls, because a weighted sum can be made to say anything:

  C1  SHUFFLED IMPORTANCE. Permute the importance vector within each layer. The
      weighted change must collapse back towards the unweighted −3.31 %; if a
      random weighting reproduces the effect, the effect is arithmetic, not
      mechanism.
  C2  UNIFORM IMPORTANCE. Must reproduce the unweighted number exactly. This
      catches a bug in the weighting code itself rather than in the idea.

    python3 where_error_lands.py
"""
import os
import sys

import numpy as np
import torch

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "block_tnf.py")

MARKER = 'print("загружаю модель…", flush=True)'
_src = open(SRC, encoding="utf-8").read()
if MARKER not in _src:
    raise SystemExit("where_error_lands: driver marker not found in block_tnf.py")
_ns = {}
exec(compile(_src.split(MARKER)[0], SRC, "exec"), _ns)

fp_levels = _ns["fp_levels"]
q_e8m0_t = _ns["q_e8m0_t"]
target_modules = _ns["target_modules"]
load_wikitext = _ns["load_wikitext"]
MODEL, K, SEQLEN = _ns["MODEL"], _ns["K"], _ns["SEQLEN"]

torch.set_grad_enabled(False)
LV = torch.tensor(sorted(fp_levels(2, 1)), dtype=torch.float64)   # MXFP4 E2M1


def hadamard(n):
    h = np.array([[1.0]])
    while h.shape[0] < n:
        h = np.block([[h, h], [h, -h]])
    return torch.tensor(h, dtype=torch.float64)


HN = hadamard(K) / np.sqrt(K)


def quantise(bl):
    s = (bl.abs().amax(dim=1) / LV[-1]).clamp(min=1e-30)
    s = q_e8m0_t(s).clamp(min=1e-30)
    y = (bl / s[:, None]).abs()
    bnd = (LV[:-1] + LV[1:]) / 2
    return torch.sign(bl) * LV[torch.bucketize(y, bnd)] * s[:, None]


def per_channel_err(w):
    """Squared quantisation error summed per INPUT channel, unrotated and rotated.

    The rotated arm is folded back to the original basis exactly as a deployment
    would see it -- W_hat = Q(W H) Hᵀ -- so both arms are expressed in the same
    coordinates and their per-channel errors are comparable at all.
    """
    n = (w.shape[1] // K) * K
    if n == 0:
        return None
    raw = w[:, :n].double().reshape(-1, K)
    e_raw = ((quantise(raw) - raw) ** 2).reshape(-1, n)

    rot = raw @ HN
    back = (quantise(rot) @ HN.T).reshape(-1, n)
    e_rot = ((back - w[:, :n].double()) ** 2)

    return e_raw.sum(dim=0), e_rot.sum(dim=0), n


def main():
    print("loading model…", flush=True)
    from transformers import AutoModelForCausalLM, AutoTokenizer
    tok = AutoTokenizer.from_pretrained(MODEL)
    model = AutoModelForCausalLM.from_pretrained(MODEL, dtype=torch.float32)
    model.eval()
    ids = tok(load_wikitext(), return_tensors="pt").input_ids
    flat = ids.reshape(-1)
    nfull = (flat.numel() // SEQLEN) * SEQLEN
    windows = flat[:nfull].view(-1, SEQLEN)

    # --- importance: mean |activation| per input channel, AWQ's definition ----
    acts = {}
    lins = target_modules(model)

    def mk(name):
        def h(_mod, inp, _out):
            a = inp[0].detach().abs().double().reshape(-1, inp[0].shape[-1]).mean(0)
            acts[name] = acts.get(name, 0.0) + a
        return h

    handles = [m.register_forward_hook(mk(n)) for n, m in lins]
    NCAL = 8
    for i in range(NCAL):
        model(windows[i:i + 1])
    for h in handles:
        h.remove()
    print(f"  importance from {NCAL} calibration windows, {len(acts)} layers")

    sp = []
    for v in acts.values():
        v = v / v.mean().clamp(min=1e-30)
        sp.append(float(v.max() / v.median().clamp(min=1e-30)))
    print(f"  channel importance spread (max/median), median over layers: {np.median(sp):.2f}×")

    # --- accumulate plain, weighted, shuffled-weighted and uniform ------------
    g = torch.Generator().manual_seed(11)
    tot = {k: [0.0, 0.0] for k in ("plain", "weighted", "shuffled", "uniform")}
    for name, mod in lins:
        r = per_channel_err(mod.weight.detach())
        if r is None:
            continue
        e_raw, e_rot, n = r
        h = acts[name][:n].clone()
        h = h / h.mean().clamp(min=1e-30)          # scale-free, so layers compare
        hs = h[torch.randperm(n, generator=g)]     # C1
        u = torch.ones_like(h)                     # C2

        for key, wv in (("plain", u), ("weighted", h), ("shuffled", hs), ("uniform", u)):
            tot[key][0] += float((e_raw * wv).sum())
            tot[key][1] += float((e_rot * wv).sum())

    print(f"\n  {'weighting':<26} {'unrotated':>14} {'rotated':>14} {'change':>10}")
    out = {}
    for key in ("plain", "uniform", "shuffled", "weighted"):
        a, b = tot[key]
        pct = 100.0 * (b - a) / a
        out[key] = pct
        print(f"  {key:<26} {a:>14.4e} {b:>14.4e} {pct:>+9.2f}%")

    # --- the controls have to hold before the result is read -----------------
    print()
    if abs(out["uniform"] - out["plain"]) > 1e-9:
        print("INSTRUMENT BROKEN — uniform weighting did not reproduce the plain "
              "number. The weighting code is wrong, not the idea.")
        return 1
    print(f"C2 uniform reproduces plain exactly ({out['uniform']:+.2f}%)  ok")
    if abs(out["shuffled"] - out["plain"]) > 1.0:
        print(f"C1 FAILED — a random weighting moved the number to "
              f"{out['shuffled']:+.2f}%, so the weighted result below is "
              f"arithmetic rather than mechanism.")
        return 1
    print(f"C1 shuffled importance stays near plain "
          f"({out['shuffled']:+.2f}% vs {out['plain']:+.2f}%)  ok")

    print()
    if out["weighted"] > 0 and out["plain"] < 0:
        print(f"RESULT: rotation REDUCES plain weight error by {abs(out['plain']):.2f}% "
              f"and RAISES importance-weighted error by {out['weighted']:.2f}%.")
        print("        The hypothesis is supported: the error moves onto the "
              "channels that matter.")
    elif out["weighted"] < out["plain"]:
        print(f"RESULT: weighted error falls FURTHER than plain "
              f"({out['weighted']:+.2f}% vs {out['plain']:+.2f}%). The hypothesis "
              "is refuted — rotation moves error AWAY from important channels.")
    else:
        print(f"RESULT: weighted {out['weighted']:+.2f}% against plain "
              f"{out['plain']:+.2f}%. Same sign, so this does not explain a "
              "perplexity change of the opposite sign. Not supported.")
    print("\nSCOPE: weights and activation magnitudes only, one model, one "
          "codebook. Importance here is AWQ's proxy, not a measured perplexity "
          "derivative; a proxy that failed once in this line already.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
