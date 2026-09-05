#!/usr/bin/env python3
"""Campaign D, step 3: predictor P3 -- each bin's share of KL(fp32 || MXFP4).

A bin's KL contribution is measured the only way that does not require a model
of the error: ZERO the quantisation error inside that bin alone -- weights that
land there keep their fp32 value, every other weight is quantised by MXFP4
exactly as before -- and re-measure the output-distribution divergence.

    contribution(b) = KL(fp32 || MXFP4) - KL(fp32 || MXFP4 repaired on bin b)

The reconstruction comes from `block_tnf.quant` itself; only the restore mask is
new, so the baseline arm here is bit-identical to the MXFP4 arm of campaign B.
Both the reference and the mutated model are held in memory and evaluated on the
same window, so every arm sees identical text and the comparison is paired.

KL is a per-token average over the vocabulary and has far lower variance than
perplexity; NWIN_KL windows are used and the count is reported, not hidden.

    MDIR=smollm2 WROOT=... NWIN_KL=8 python3 campaignD_kl.py
"""
import json
import math
import os

import numpy as np
import torch
import torch.nn.functional as Fn

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "block_tnf.py")
MARKER = 'print("загружаю модель…", flush=True)'
_s = open(SRC, encoding="utf-8").read()
ns = {}
exec(compile(_s.split(MARKER)[0], SRC, "exec"), ns)
quant, target_modules, load_wikitext = (
    ns[k] for k in ("quant", "target_modules", "load_wikitext"))
q_e8m0_t, K, SEQLEN = ns["q_e8m0_t"], ns["K"], ns["SEQLEN"]
W = os.environ.get("WROOT", os.path.dirname(ns["MODEL"]))
ns["W"] = W
torch.set_grad_enabled(False)

import campaignC_books as C
import campaignD_pred as P

MDIR = os.environ.get("MDIR", "smollm2")
NWIN = int(os.environ.get("NWIN_KL", "8"))
CHUNK = 128


def repaired(w, target_bin):
    """MXFP4 everywhere, except elements whose SIGNED bin is `target_bin`,
    which keep their exact fp32 value."""
    wq = quant(w, C.MXFP4)
    n = (w.shape[1] // K) * K
    if n == 0:
        return wq
    head = w[:, :n].reshape(-1, K).double()
    s = q_e8m0_t((head.abs().amax(dim=1) / 1.0).clamp(min=1e-30)).clamp(min=1e-30)
    y = head / s[:, None]
    m = (P.signed_bins(y) == target_bin).reshape(-1, n)
    out = wq.clone()
    out[:, :n] = torch.where(m, w[:, :n], wq[:, :n])
    return out


def kl_window(ref, mut, c):
    """mean per-token KL(p_ref || p_mut) over one window."""
    a = ref(c).logits[0].float()
    b = mut(c).logits[0].float()
    tot = 0.0
    for i in range(0, a.shape[0], CHUNK):
        lp = Fn.log_softmax(a[i:i + CHUNK], dim=-1)
        lq = Fn.log_softmax(b[i:i + CHUNK], dim=-1)
        tot += float((lp.exp() * (lp - lq)).sum(-1).sum())
    return tot / a.shape[0]


def main():
    from transformers import AutoModelForCausalLM, AutoTokenizer
    path = os.path.join(W, MDIR)
    tok = AutoTokenizer.from_pretrained(path)
    ref = AutoModelForCausalLM.from_pretrained(path, dtype=torch.float32).eval()
    mut = AutoModelForCausalLM.from_pretrained(path, dtype=torch.float32).eval()
    ids = tok(load_wikitext(), return_tensors="pt").input_ids
    flat = ids.reshape(-1)
    ntot = flat.numel() // SEQLEN
    win = flat[:ntot * SEQLEN].view(-1, SEQLEN)[:NWIN]
    print(f"{MDIR}: {win.shape[0]} windows x {SEQLEN} tokens", flush=True)

    orig = {n: m.weight.detach().clone() for n, m in target_modules(mut)}
    # ALL=1 repairs every one of the 15 signed bins.  That is the control for
    # the mirror pairs: bins +k and -k carry near-identical mass and SSE, so any
    # systematic KL asymmetry between them is either a real sign effect or a bug
    # in the mask, and one run distinguishes the two.
    if os.environ.get("BINS"):
        bins = sorted(int(x) for x in os.environ["BINS"].split(","))
    elif os.environ.get("ALL"):
        bins = list(range(-7, 8))
    else:
        bins = sorted({P.SPLIT[k] for k in P.SPLIT})
    print(f"split bins to repair: {bins}", flush=True)

    def run(setter, tag):
        for n, m in target_modules(mut):
            m.weight.copy_(setter(orig[n]))
        v = [kl_window(ref, mut, win[i:i + 1]) for i in range(win.shape[0])]
        print(f"  {tag:<14} KL = {np.mean(v):.6f}", flush=True)
        return v

    zero = run(lambda w: w, "fp32-selftest")
    assert max(abs(x) for x in zero) < 1e-6, f"self-test KL not zero: {zero}"

    base = run(lambda w: quant(w, C.MXFP4), "MXFP4")
    rep = {b: run(lambda w, b=b: repaired(w, b), f"repair bin {b:+d}") for b in bins}

    bm, out = float(np.mean(base)), {}
    print(f"\n{'bin':>5}{'KL repaired':>14}{'contribution':>14}{'share %':>10}")
    for b in bins:
        c = bm - float(np.mean(rep[b]))
        out[str(b)] = {"kl_repaired": float(np.mean(rep[b])), "contribution": c,
                       "share": c / bm}
        print(f"{b:>+5d}{np.mean(rep[b]):>14.6f}{c:>14.6f}{100*c/bm:>10.4f}")

    print(f"\n{'placement':<8}{'split bin':>10}{'P3 KL share %':>16}")
    pl = {}
    for name in ["NEAR0", "MIDN", "MID", "MID2", "TOP"]:
        b = P.SPLIT[name]
        pl[name] = out[str(b)]["share"]
        print(f"{name:<8}{b:>10}{100*pl[name]:>16.4f}")

    # per-window KL for EVERY arm: the repairs are evaluated on identical text,
    # so the contribution of a bin is a PAIRED quantity and gets a CI.
    json.dump({"model": MDIR, "nwin": int(win.shape[0]), "kl_mxfp4": bm,
               "per_window_kl_mxfp4": base, "bins": out, "placements": pl,
               "per_window_kl_repair": {str(b): rep[b] for b in bins}},
              open(os.path.join(HERE, f"campaignD_kl_{MDIR}.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
