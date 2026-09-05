#!/usr/bin/env python3
"""Campaign B measurement: asymmetric variants of OUR books vs MXFP4 and NF4.

Per-window NLL so every comparison downstream can be paired.  The measurement
path is reused from block_tnf.py by source split -- never reimplemented -- and
the asymmetric quantiser is campaignC_books.make_quant_signed, proven bit-exact
against block_tnf.quant by campaignB_agree.py.

Rulers (fp32, MXFP4, Lloyd-Max) are re-measured every run and checked against
the published values before anything new is quoted.

    MDIR=smollm2 NWIN=40 python3 campaignB_measure.py
Results append to campaignB_<model>.json, so a run can be resumed.
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

import campaignB_books as B
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
DST = os.path.join(HERE, f"campaignB_{MDIR}.json")


def main():
    from transformers import AutoModelForCausalLM, AutoTokenizer
    BOOKS = B.books()
    print("=== codebooks (T38: max|level| == 1.0 asserted) ===")
    for name, kind, nd, npos, nneg in B.check(BOOKS):
        print(f"  {name:<15} {kind}  distinct={nd:2d}  pos={npos}  neg={nneg}")
    quant_signed = C.make_quant_signed(K, ns["q_e8m0_t"])

    done = {}
    if os.path.exists(DST):
        prev = json.load(open(DST))
        if prev.get("nwin") == NWIN:
            done = prev.get("per_window_nll", {})
            print(f"\nresuming: {len(done)} arms already measured", flush=True)

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

    nlls = {k: np.array(v, dtype=np.float64) for k, v in done.items()}

    def save():
        json.dump({"model": MDIR, "nwin": NWIN,
                   "ppl": {k: float(np.exp(v.mean())) for k, v in nlls.items()},
                   "per_window_nll": {k: list(map(float, v))
                                      for k, v in nlls.items()},
                   "books": {n: [float(x) for x in lv] for n, k, lv in BOOKS},
                   "book_kind": {n: k for n, k, lv in BOOKS}},
                  open(DST, "w"), indent=1)

    if "fp32" not in nlls:
        t0 = time.time()
        apply(None)
        nlls["fp32"] = per_window()
        whole = perplexity(model, win[:NWIN].reshape(1, -1), NWIN)
        got = float(np.exp(nlls["fp32"].mean()))
        rel = abs(whole - got) / got
        print(f"\nfp32 = {got:.4f}  ({time.time()-t0:.0f}s)")
        print(f"  identity: whole-slice perplexity() {whole:.6f} vs "
              f"exp(mean per-window nll) {got:.6f}  rel {rel:.2e}", flush=True)
        assert rel < 1e-9, "per-window decomposition is wrong"
        save()

    for name, kind, lv in BOOKS:
        if name in nlls:
            continue
        t0 = time.time()
        apply((kind, lv))
        nlls[name] = per_window()
        save()
        print(f"  {name:<15} {float(np.exp(nlls[name].mean())):>10.4f}   "
              f"({time.time()-t0:.0f}s)", flush=True)
    apply(None)

    ppl = {k: float(np.exp(v.mean())) for k, v in nlls.items()}
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

    out = json.load(open(DST))
    out["rulers_reproduce"] = bool(ok)
    json.dump(out, open(DST, "w"), indent=1)

    print(f"\n  {'arm':<15}{'ppl':>10}{'vs MXFP4':>11}{'vs NF4':>10}")
    for name in ["fp32"] + [n for n, _, _ in BOOKS]:
        print(f"  {name:<15}{ppl[name]:>10.4f}"
              f"{100*(ppl[name]/ppl['MXFP4']-1):>+10.2f}%"
              f"{100*(ppl[name]/ppl['NF4']-1):>+9.2f}%")
    print(f"\nwrote {DST}")
    return 0 if ok else 2


if __name__ == "__main__":
    sys.exit(main())
