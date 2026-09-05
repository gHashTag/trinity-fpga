#!/usr/bin/env python3
"""Campaign D, step 0: reproduce the published rulers on THIS session's copy of
the checkpoints before any new number is quoted from them.

    MDIR=smollm2 WROOT=/path/to/weights python3 campaignD_ruler.py
"""
import json
import os

import torch

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "block_tnf.py")
MARKER = 'print("загружаю модель…", flush=True)'
_s = open(SRC, encoding="utf-8").read()
ns = {}
exec(compile(_s.split(MARKER)[0], SRC, "exec"), ns)
quant, perplexity, target_modules, load_wikitext = (
    ns[k] for k in ("quant", "perplexity", "target_modules", "load_wikitext"))
K = ns["K"]
W = os.environ.get("WROOT", os.path.dirname(ns["MODEL"]))
ns["W"] = W                                   # load_wikitext reads W from ns
torch.set_grad_enabled(False)

import campaignC_books as C

RULERS = {"smollm2": (40, 14.4874, 21.9397), "qwen": (20, 12.6999, 15.4374),
          "pythia": (40, 25.9561, 47.6504), "opt": (40, 27.5678, 30.7871)}
TOL = 5e-3


def main():
    from transformers import AutoModelForCausalLM, AutoTokenizer
    mdir = os.environ["MDIR"]
    nwin, fp_ref, mx_ref = RULERS[mdir]
    path = os.path.join(W, mdir)
    tok = AutoTokenizer.from_pretrained(path)
    model = AutoModelForCausalLM.from_pretrained(path, dtype=torch.float32)
    model.eval()
    ids = tok(load_wikitext(), return_tensors="pt").input_ids

    fp = perplexity(model, ids, nwin)
    orig = {n: m.weight.detach().clone() for n, m in target_modules(model)}
    for n, m in target_modules(model):
        m.weight.copy_(quant(orig[n], C.MXFP4))
    mx = perplexity(model, ids, nwin)
    for n, m in target_modules(model):
        m.weight.copy_(orig[n])

    ok = abs(fp - fp_ref) < TOL and abs(mx - mx_ref) < TOL
    print(f"{mdir}: fp32 {fp:.4f} (ref {fp_ref})   MXFP4 {mx:.4f} (ref {mx_ref})"
          f"   {'RULER OK' if ok else 'RULER BROKEN'}", flush=True)
    p = os.path.join(HERE, "campaignD_ruler.json")
    d = json.load(open(p)) if os.path.exists(p) else {}
    d[mdir] = {"nwin": nwin, "fp32": fp, "MXFP4": mx, "ok": bool(ok)}
    json.dump(d, open(p, "w"), indent=1)
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
