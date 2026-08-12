#!/usr/bin/env python3
"""Judge the four one-model KL fits on every model, including the three each
one never saw.

Reads onefit_kl_<m>.json for m in the four models, takes the fitted book out of
each, and measures per-window NLL for all four books on THIS model.  The ruler
is reproduced first and the per-window vectors are cross-checked against
campaign B's, so campaign B's already-measured MXFP4 / JOINT-KL / NF4 / NF4-sym /
MX-asym-NEAR0 columns can be joined to these without a second measurement.

    W=<weights> MDIR=pythia python3 onefit_measure.py
"""
import json
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

import campaignC_books as C

torch.set_grad_enabled(False)
if os.environ.get("THREADS"):
    torch.set_num_threads(int(os.environ["THREADS"]))

MDIR = os.environ["MDIR"]
WDIR = os.environ.get("W") or os.path.dirname(ns["MODEL"])
ns["load_wikitext"] = load_wikitext = (
    lambda: __import__("pyarrow.parquet", fromlist=["parquet"])
    .read_table(os.path.join(WDIR, "wikitext2-test.parquet"))
    .column("text").to_pylist())

MODELS = ["smollm2", "qwen", "pythia", "opt"]
RULERS = {
    "smollm2": {"nwin": 40, "fp32": 14.4874, "MXFP4": 21.9397},
    "qwen":    {"nwin": 20, "fp32": 12.6999, "MXFP4": 15.4374},
    "pythia":  {"nwin": 40, "fp32": 25.9561, "MXFP4": 47.6504},
    "opt":     {"nwin": 40, "fp32": 27.5678, "MXFP4": 30.7871},
}
NWIN = int(os.environ.get("NWIN", RULERS[MDIR]["nwin"]))
# See onefit_kl.py: 5e-4 nats clears pythia's non-reproducible forward (7.9e-05
# between campaigns B and C) while staying thirty times below the smallest
# margin quoted.  The observed value is recorded in the output either way.
WTOL = float(os.environ.get("WTOL", "5e-4"))


def t38(lv):
    v = [float(x) for x in lv]
    assert v == sorted(v) and len(set(v)) == len(v)
    assert v[0] == 0.0
    pos = max(v)
    neg = max(-x for x in v) if min(v) < 0 else pos
    assert abs(pos - 1.0) < 1e-12 and abs(neg - 1.0) < 1e-12, (pos, neg)
    return v


def main():
    from transformers import AutoModelForCausalLM, AutoTokenizer

    BOOKS = {}
    for f in MODELS:
        p = os.path.join(HERE, f"onefit_kl_{f}.json")
        j = json.load(open(p))
        assert j["ruler_reproduces"], f
        BOOKS[f"FIT-{f}"] = t38(j["fitted"])
    t38(C.MXFP4)
    print("books under test (T38 asserted on both tails):")
    for n, lv in BOOKS.items():
        print(f"  {n:<14} {[round(x, 6) for x in lv]}")

    path = os.path.join(WDIR, MDIR)
    print(f"\nmodel dir = {path}  NWIN={NWIN}", flush=True)
    tok = AutoTokenizer.from_pretrained(path)
    model = AutoModelForCausalLM.from_pretrained(path, dtype=torch.float32)
    model.eval()
    ids = tok("\n\n".join(load_wikitext()), return_tensors="pt").input_ids
    flat = ids.reshape(-1)
    win = flat[:(flat.numel() // SEQLEN) * SEQLEN].view(-1, SEQLEN)
    lins = target_modules(model)
    orig = {n: m.weight.detach().clone() for n, m in lins}
    print(f"{len(lins)} linear tensors quantised (lm_head excluded)", flush=True)

    def apply(lv):
        if lv is None:
            for n, m in lins:
                m.weight.copy_(orig[n])
            return
        for n, m in lins:
            m.weight.copy_(quant(orig[n], lv))

    def per_window():
        return np.array([float(np.log(perplexity(model, win[i], 1)))
                         for i in range(NWIN)], dtype=np.float64)

    bref = json.load(open(os.path.join(HERE, f"campaignB_{MDIR}.json")))
    assert bref["rulers_reproduce"], MDIR
    r = RULERS[MDIR]
    ok = (NWIN == r["nwin"])
    nll = {}
    drift = {}
    for name, lv in (("fp32", None), ("MXFP4", C.MXFP4)):
        t0 = time.time()
        apply(lv)
        nll[name] = per_window()
        p = float(np.exp(nll[name].mean()))
        d = abs(p - r[name]) / r[name]
        dw = float(np.abs(nll[name] - np.array(bref["per_window_nll"][name][:NWIN])).max())
        drift[name] = dw
        good = d < 5e-4 and dw < WTOL
        ok &= good
        print(f"RULER {name:<6} {p:>10.4f}  published {r[name]:>9.4f}  rel {d:.2e}"
              f"   max|per-window - campaignB| = {dw:.2e}  "
              f"{'OK' if good else 'MISMATCH'}   ({time.time()-t0:.0f}s)", flush=True)
    if not ok:
        print("RULER BROKEN -- refusing to produce numbers.", flush=True)
        return 2

    for name, lv in BOOKS.items():
        t0 = time.time()
        apply(lv)
        v = per_window()
        nll[name] = v
        tag = "  <- in-sample" if name == f"FIT-{MDIR}" else ""
        print(f"  {name:<14}{float(np.exp(v.mean())):>10.4f}"
              f"   ({time.time()-t0:.0f}s){tag}", flush=True)
    apply(None)

    out = {"model": MDIR, "nwin": NWIN, "rulers_reproduce": True,
           "ruler_window_drift": drift, "wtol": WTOL,
           "ppl": {k: float(np.exp(v.mean())) for k, v in nll.items()},
           "per_window_nll": {k: list(map(float, v)) for k, v in nll.items()},
           "books": {n: lv for n, lv in BOOKS.items()} | {"MXFP4": list(C.MXFP4)}}
    dst = os.path.join(HERE, f"onefit_ppl_{MDIR}.json")
    json.dump(out, open(dst, "w"), indent=1)
    print(f"wrote {dst}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
