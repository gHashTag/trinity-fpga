#!/usr/bin/env python3
"""LINE D: reproduce the rulers in THIS process and re-measure the clipping arm.

Nothing on the measurement path is reimplemented -- quant / perplexity /
target_modules / load_wikitext / q_e8m0_t are executed out of block_tnf.py's
source up to its driver marker, exactly as campaignA_run.py does, and the
asymmetric quantiser is campaignC_books.make_quant_signed.

Writes lineD_ruler_<mdir>.json.  Refuses to emit anything if a ruler misses.

    W=<weights dir> MDIR=pythia python3 lineD_ruler.py
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

import campaignA_books as A
import campaignC_books as C

torch.set_grad_enabled(False)
MDIR = os.environ["MDIR"]
WDIR = os.environ.get("W") or os.path.dirname(ns["MODEL"])
ns["W"] = WDIR
load_wikitext = (lambda: __import__("pyarrow.parquet", fromlist=["parquet"])
                 .read_table(os.path.join(WDIR, "wikitext2-test.parquet"))
                 .column("text").to_pylist())

RULERS = {
    "smollm2": {"nwin": 40, "fp32": 14.4874, "MXFP4": 21.9397},
    "qwen":    {"nwin": 20, "fp32": 12.6999, "MXFP4": 15.4374},
    "pythia":  {"nwin": 40, "fp32": 25.9561, "MXFP4": 47.6504},
    "opt":     {"nwin": 40, "fp32": 27.5678, "MXFP4": 30.7871},
}
NWIN = RULERS[MDIR]["nwin"]
ARM = "MX-asym-TOP"


def main():
    from transformers import AutoModelForCausalLM, AutoTokenizer
    BOOKS = {n: (k, [float(x) for x in lv]) for n, k, lv in A.all_books()}
    list(A.check(A.all_books()))
    quant_signed = C.make_quant_signed(K, ns["q_e8m0_t"])

    path = os.path.join(WDIR, MDIR)
    tok = AutoTokenizer.from_pretrained(path)
    model = AutoModelForCausalLM.from_pretrained(path, dtype=torch.float32)
    model.eval()
    ids = tok("\n\n".join(load_wikitext()), return_tensors="pt").input_ids
    flat = ids.reshape(-1)
    ntot = flat.numel() // SEQLEN
    win = flat[:ntot * SEQLEN].view(-1, SEQLEN)
    lins = target_modules(model)
    orig = {n: m.weight.detach().clone() for n, m in lins}
    print(f"{MDIR}: {len(lins)} tensors, {ntot} windows, using {NWIN}", flush=True)

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
        return np.array([float(np.log(perplexity(model, win[i], 1)))
                         for i in range(NWIN)], dtype=np.float64)

    # instrument self-test, in THIS process
    worst = 0.0
    for _, m in lins:
        w = m.weight.detach()
        worst = max(worst, (quant(w, BOOKS["MXFP4"][1])
                            - quant_signed(w, C.signed_from_magnitudes(
                                BOOKS["MXFP4"][1]))).abs().max().item())
    print(f"INSTRUMENT max|quant - quant_signed| = {worst:.3e}", flush=True)
    if worst != 0.0:
        return 3

    bref = json.load(open(os.path.join(HERE, f"campaignB_{MDIR}.json")))
    r, nll, ok = RULERS[MDIR], {}, True
    for name, entry in (("fp32", None), ("MXFP4", BOOKS["MXFP4"]),
                        (ARM, BOOKS[ARM])):
        t0 = time.time()
        apply(entry)
        nll[name] = per_window()
        p = float(np.exp(nll[name].mean()))
        prev = np.array(bref["per_window_nll"][name][:NWIN])
        dw = float(np.abs(nll[name] - prev).max())
        line = f"{name:<14}{p:>10.4f}"
        if name in r:
            d = abs(p - r[name]) / r[name]
            ok &= d < 5e-4
            line += f"  published {r[name]:>9.4f}  rel {d:.2e}  " \
                    f"{'OK' if d < 5e-4 else 'MISMATCH'}"
        else:
            line += f"  campaignB {float(np.exp(prev.mean())):>9.4f}"
        print(f"{line}   max|dNLL vs campaignB| = {dw:.2e}   "
              f"({time.time()-t0:.0f}s)", flush=True)
    if not ok:
        print("RULER BROKEN -- refusing to produce numbers.", flush=True)
        return 2

    ppl = {k: float(np.exp(v.mean())) for k, v in nll.items()}
    out = {"model": MDIR, "nwin": NWIN, "ppl": ppl,
           "per_window_nll": {k: list(map(float, v)) for k, v in nll.items()},
           "top_vs_mxfp4_pct": 100.0 * (ppl[ARM] / ppl["MXFP4"] - 1.0),
           "ruler_reproduces": True}
    dst = os.path.join(HERE, f"lineD_ruler_{MDIR}.json")
    json.dump(out, open(dst, "w"), indent=1)
    print(f"{ARM} vs MXFP4 = {out['top_vs_mxfp4_pct']:+.2f} %\nwrote {dst}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
