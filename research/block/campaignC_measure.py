#!/usr/bin/env python3
"""Campaign C: the full table against NF4-sym, at equal alphabet.

Seven arms, four models, per-window NLL so every comparison can be paired.
Measurement path reused from block_tnf.py by source split -- never reimplemented.
The one thing that IS new is quant_signed (campaignC_books), the quantiser for an
asymmetric level list, which campaignC_agree.py proves is bit-exactly the same
instrument as block_tnf.quant on any symmetric book.

    MDIR=qwen NWIN=20 python3 campaignC_measure.py
"""
import json
import math
import os
import sys
import time

import numpy as np
import torch

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "block_tnf.py")
MARKER = 'print("загружаю модель…", flush=True)'
_s = open(SRC, encoding="utf-8").read()
if MARKER not in _s:
    raise SystemExit("driver marker not found in block_tnf.py")
ns = {}
exec(compile(_s.split(MARKER)[0], SRC, "exec"), ns)

quant, perplexity, target_modules, load_wikitext = (
    ns[k] for k in ("quant", "perplexity", "target_modules", "load_wikitext"))
K, SEQLEN = ns["K"], ns["SEQLEN"]
W = os.path.dirname(ns["MODEL"])

import campaignC_books as C

torch.set_grad_enabled(False)
if os.environ.get("THREADS"):
    torch.set_num_threads(int(os.environ["THREADS"]))

MDIR = os.environ.get("MDIR", "smollm2")
NWIN = int(os.environ.get("NWIN", "40"))

RULERS = {
    "smollm2": {"nwin": 40, "fp32": 14.4874, "MXFP4": 21.9397, "Lloyd-Max": 22.9166},
    "qwen":    {"nwin": 20, "fp32": 12.6999, "MXFP4": 15.4374, "Lloyd-Max": 16.0703},
    "pythia":  {"nwin": 40, "fp32": 25.9561, "MXFP4": 47.6504, "Lloyd-Max": 52.9992},
    "opt":     {"nwin": 40, "fp32": 27.5678, "MXFP4": 30.7871, "Lloyd-Max": 31.8288},
}


def main():
    from transformers import AutoModelForCausalLM, AutoTokenizer
    BOOKS = C.books()
    print("=== codebooks (T38: max|level| == 1.0 asserted) ===")
    for name, kind, n, nd in C.check_phase(BOOKS):
        print(f"  {name:<11} {kind}  entries={n:2d}  distinct signed values={nd:2d}")
    quant_signed = C.make_quant_signed(K, ns["q_e8m0_t"])

    path = os.path.join(W, MDIR)
    print(f"\nmodel dir = {path}   NWIN={NWIN}", flush=True)
    tok = AutoTokenizer.from_pretrained(path)
    model = AutoModelForCausalLM.from_pretrained(path, dtype=torch.float32)
    model.eval()
    ids = tok(load_wikitext(), return_tensors="pt").input_ids
    flat = ids.reshape(-1)
    ntot = flat.numel() // SEQLEN
    win = flat[:ntot * SEQLEN].view(-1, SEQLEN)
    if ntot < NWIN:
        raise SystemExit(f"only {ntot} windows available, need {NWIN}")
    lins = target_modules(model)
    print(f"{len(lins)} linear tensors quantised (lm_head excluded)", flush=True)
    orig = {n: m.weight.detach().clone() for n, m in lins}

    def apply(entry):
        if entry is None:
            for n, m in lins:
                m.weight.copy_(orig[n])
            return
        kind, lv = entry
        f = quant if kind == "mag" else quant_signed
        for n, m in lins:
            m.weight.copy_(f(orig[n], lv))

    def per_window():
        return np.array([math.log(perplexity(model, win[i], 1))
                         for i in range(NWIN)], dtype=np.float64)

    nlls, ppl = {}, {}
    t0 = time.time()
    apply(None)
    nlls["fp32"] = per_window()
    ppl["fp32"] = float(np.exp(nlls["fp32"].mean()))
    whole = perplexity(model, win[:NWIN].reshape(1, -1), NWIN)
    rel = abs(whole - ppl["fp32"]) / ppl["fp32"]
    print(f"\nfp32 = {ppl['fp32']:.4f}  ({time.time()-t0:.0f}s)")
    print(f"  identity: whole-slice perplexity() {whole:.6f} vs "
          f"exp(mean per-window nll) {ppl['fp32']:.6f}  rel {rel:.2e}", flush=True)
    assert rel < 1e-9, "per-window decomposition is wrong"

    for name, kind, lv in BOOKS:
        t0 = time.time()
        apply((kind, lv))
        v = per_window()
        nlls[name] = v
        ppl[name] = float(np.exp(v.mean()))
        print(f"  {name:<11} {ppl[name]:>10.4f}   ({time.time()-t0:.0f}s)", flush=True)
    apply(None)

    r = RULERS[MDIR]
    ok = r["nwin"] == NWIN
    print("\n=== RULER CHECK ===")
    for key in ("fp32", "MXFP4", "Lloyd-Max"):
        got, exp_ = ppl[key], r[key]
        d = abs(got - exp_) / exp_
        good = d < 5e-4
        ok &= good
        print(f"  {key:<11} got {got:>9.4f}  published {exp_:>9.4f}  rel {d:.2e}  "
              f"{'OK' if good else 'MISMATCH'}")
    print(f"  RULERS {'REPRODUCE' if ok else 'DO NOT REPRODUCE'}", flush=True)

    ref = nlls["NF4-sym"]
    print(f"\n  {'arm':<11}{'ppl':>10}{'vs NF4-sym':>12}")
    for name, _, _ in BOOKS:
        print(f"  {name:<11}{ppl[name]:>10.4f}"
              f"{100*(ppl[name]/ppl['NF4-sym']-1):>+11.2f}%")

    out = {"model": MDIR, "nwin": NWIN, "rulers_reproduce": bool(ok),
           "ppl": ppl,
           "per_window_nll": {k: list(map(float, v)) for k, v in nlls.items()},
           "books": {n: [float(x) for x in lv] for n, k, lv in BOOKS},
           "book_kind": {n: k for n, k, lv in BOOKS}}
    dst = os.path.join(HERE, f"campaignC_{MDIR}.json")
    json.dump(out, open(dst, "w"), indent=1)
    print(f"\nwrote {dst}")
    return 0 if ok else 2


if __name__ == "__main__":
    sys.exit(main())
