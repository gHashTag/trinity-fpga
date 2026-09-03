#!/usr/bin/env python3
"""T42, measurement side: per-window NLL for fp32, MXFP4 and MX-asym-NEAR0 on
every checkpoint the session can reach.

The cross-model replicate unit is the MODEL. This campaign has been stuck at
n = 4 and eleven verdicts died of that. So the point of this file is not another
window count -- it is more checkpoints.

Gates, all of which stop the run rather than warn:
  * the four published rulers must reproduce in THIS process (0.5 % band);
  * `quant_signed` must still be bit-identical to `block_tnf.quant` on the
    symmetric book, on this checkpoint's own tensors;
  * quantisation must actually CHANGE weights -- the nn.Linear-only selector
    silently no-ops on Conv1D checkpoints and would report a 0.00 % margin.

    MDIR=gpt2 NWIN=40 python3 campaignE_ppl.py
"""
import json
import os
import sys
import time

import numpy as np
import torch

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.chdir(HERE)

_s = open("block_tnf.py", encoding="utf-8").read()
MARKER = 'print("загружаю модель…", flush=True)'
if MARKER not in _s:
    raise SystemExit("driver marker not found in block_tnf.py")
ns = {}
exec(compile(_s.split(MARKER)[0], "block_tnf.py", "exec"), ns)
quant, perplexity, target_modules, load_wikitext = (
    ns[k] for k in ("quant", "perplexity", "target_modules", "load_wikitext"))
K, SEQLEN = ns["K"], ns["SEQLEN"]

import campaignA_books as A
import campaignC_books as C
import campaignE_occupancy as E

torch.set_grad_enabled(False)
if os.environ.get("THREADS"):
    torch.set_num_threads(int(os.environ["THREADS"]))

RULERS = {
    "smollm2": {"nwin": 40, "fp32": 14.4874, "MXFP4": 21.9397},
    "qwen":    {"nwin": 20, "fp32": 12.6999, "MXFP4": 15.4374},
    "pythia":  {"nwin": 40, "fp32": 25.9561, "MXFP4": 47.6504},
    "opt":     {"nwin": 40, "fp32": 27.5678, "MXFP4": 30.7871},
}
MODELS = json.load(open(os.path.join(HERE, "campaignE_models.json")))


def main():
    from transformers import AutoModelForCausalLM, AutoTokenizer
    mdir = os.environ["MDIR"]
    path = MODELS[mdir]
    nwin = int(os.environ.get("NWIN", RULERS.get(mdir, {}).get("nwin", 40)))
    quant_signed = C.make_quant_signed(K, ns["q_e8m0_t"])

    BOOKS = {n: (k, [float(x) for x in lv]) for n, k, lv in A.all_books()}
    list(A.check(A.all_books()))
    arms = [("fp32", None), ("MXFP4", BOOKS["MXFP4"]),
            ("MX-asym-NEAR0", BOOKS["MX-asym-NEAR0"])]

    tok = AutoTokenizer.from_pretrained(path)
    model = AutoModelForCausalLM.from_pretrained(path, dtype=torch.float32)
    model.eval()
    E.assert_same_as_ruler(model)
    lins = E.quantisable(model)
    n_conv = sum(1 for _, _, t in lins if t)
    if not lins:
        raise SystemExit("no quantisable tensors -- the arm would be a no-op")

    ids = tok(load_wikitext(), return_tensors="pt").input_ids
    flat = ids.reshape(-1)
    ntot = flat.numel() // SEQLEN
    win = flat[:ntot * SEQLEN].view(-1, SEQLEN)
    print(f"{mdir}: {len(lins)} tensors ({n_conv} Conv1D), tokens={flat.numel()},"
          f" windows={ntot}, using {nwin}", flush=True)
    if ntot < nwin:
        raise SystemExit(f"only {ntot} windows, need {nwin}")

    orig = {n: E.get_w(m, t).clone() for n, m, t in lins}

    def apply(entry):
        if entry is None:
            for n, m, t in lins:
                E.set_w(m, t, orig[n])
            return
        kind, lv = entry
        f = quant if kind == "mag" else quant_signed
        for n, m, t in lins:
            E.set_w(m, t, f(orig[n], lv))

    # ---- instrument check, on this checkpoint's own tensors -----------------
    worst = 0.0
    mags = BOOKS["MXFP4"][1]
    sig = C.signed_from_magnitudes(mags)
    assert len(sig) == 15
    for n, m, t in lins:
        w = orig[n]
        worst = max(worst, (quant(w, mags) - quant_signed(w, sig)).abs().max().item())
    print(f"INSTRUMENT max|quant - quant_signed| = {worst:.3e}", flush=True)
    if worst != 0.0:
        return 3

    # ---- the arm must actually change weights ------------------------------
    apply(BOOKS["MXFP4"])
    changed = max(float((E.get_w(m, t) - orig[n]).abs().max())
                  for n, m, t in lins)
    apply(None)
    print(f"NO-OP GATE  max|w_MXFP4 - w| = {changed:.3e}", flush=True)
    if changed == 0.0:
        raise SystemExit("quantisation changed nothing -- silent no-op")

    def per_window():
        return np.array([float(np.log(perplexity(model, win[i], 1)))
                         for i in range(nwin)], dtype=np.float64)

    out = {"model": mdir, "nwin": nwin, "n_tensors": len(lins),
           "n_conv1d": n_conv, "instrument_max_abs_diff": worst,
           "noop_gate_max_abs_change": changed, "per_window_nll": {}, "ppl": {}}
    for name, entry in arms:
        t0 = time.time()
        apply(entry)
        d = per_window()
        out["per_window_nll"][name] = d.tolist()
        p = float(np.exp(d.mean()))
        out["ppl"][name] = p
        msg = f"{name:<16} ppl {p:10.4f}   {time.time()-t0:6.1f}s"
        if mdir in RULERS and name in RULERS[mdir] and nwin == RULERS[mdir]["nwin"]:
            ref = RULERS[mdir][name]
            rel = abs(p - ref) / ref
            out.setdefault("ruler", {})[name] = {"published": ref, "here": p,
                                                 "rel": rel}
            msg += f"   ruler {ref:.4f}  rel {rel:.2e}"
            if rel > 5e-3:
                print(msg + "   RULER MISS -- STOP", flush=True)
                return 2
        print(msg, flush=True)
    apply(None)
    out["rulers_reproduce"] = (mdir not in RULERS
                               or all(v["rel"] <= 5e-3
                                      for v in out.get("ruler", {}).values()))
    json.dump(out, open(os.path.join(HERE, f"campaignE_ppl_{mdir}.json"), "w"))
    m = np.array(out["per_window_nll"]["MX-asym-NEAR0"])
    b = np.array(out["per_window_nll"]["MXFP4"])
    print(f"NEAR0 vs MXFP4: {100*(np.exp((m-b).mean())-1):+.3f} %   "
          f"windows won {int((m<b).sum())}/{nwin}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
