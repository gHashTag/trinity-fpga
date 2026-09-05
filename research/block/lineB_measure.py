#!/usr/bin/env python3
"""LINE B: measure fp32 / MXFP4 / MX-asym-TOP on a checkpoint with NO published ruler.

lineD_ruler.py can only run the four discovery checkpoints: it looks the model up
in a RULERS table of published fp32/MXFP4 values and cross-checks every window
against campaignB's stored NLL.  A NEW checkpoint has neither, so it needs a
driver whose gate is different -- but it must be the SAME INSTRUMENT, or the new
margins are not comparable to the four the predictor was found on.

Nothing on the measurement path is reimplemented.  quant / perplexity /
target_modules / q_e8m0_t come out of block_tnf.py's source up to its driver
marker, exactly as lineD_ruler.py and campaignA_run.py execute them; the
asymmetric quantiser is campaignC_books.make_quant_signed; the two level lists
are campaignA_books.

That the driver is the same instrument is not asserted, it is CHECKED: run it on
a discovery model with VERIFY=1 and it reproduces lineD_ruler_<m>.json window by
window.  See the SILENT-NULL GATES below for what replaces the published ruler.

    W=<weights dir> MDIR=gptneo125m python3 lineB_measure.py
    W=<weights dir> MDIR=opt VERIFY=1 python3 lineB_measure.py
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
quant, perplexity, target_modules = (
    ns[k] for k in ("quant", "perplexity", "target_modules"))
K, SEQLEN = ns["K"], ns["SEQLEN"]

import campaignA_books as A
import campaignC_books as C

torch.set_grad_enabled(False)
MDIR = os.environ["MDIR"]
WDIR = os.environ.get("W") or os.path.dirname(ns["MODEL"])
VERIFY = os.environ.get("VERIFY") == "1"
NWIN = int(os.environ.get("NWIN", "40"))     # pre-registered before any measurement
ARM = "MX-asym-TOP"

# --- SILENT-NULL GATES ------------------------------------------------------
# A published ruler catches a broken harness by disagreeing with a known number.
# With no published number the same failures have to be caught structurally.
# GPT-2 is why this section exists: its blocks are transformers Conv1D, not
# nn.Linear, so target_modules() returns ZERO tensors, quant() is never called,
# and every arm silently reports the fp32 perplexity as its own.
MIN_TENSORS = 8          # a transformer with fewer is not being quantised
MIN_SHARE = 0.30         # share of non-embedding parameters that must be covered
MIN_MXFP4_DEGRADE = 0.02  # MXFP4 at 4 bits must move perplexity by >= 2 %


def main():
    from transformers import AutoModelForCausalLM, AutoTokenizer
    BOOKS = {n: (k, [float(x) for x in lv]) for n, k, lv in A.all_books()}
    list(A.check(A.all_books()))
    quant_signed = C.make_quant_signed(K, ns["q_e8m0_t"])

    path = os.path.join(WDIR, MDIR)
    tok = AutoTokenizer.from_pretrained(path)
    model = AutoModelForCausalLM.from_pretrained(path, dtype=torch.float32)
    model.eval()
    txt = "\n\n".join(
        __import__("pyarrow.parquet", fromlist=["parquet"])
        .read_table(os.path.join(WDIR, "wikitext2-test.parquet"))
        .column("text").to_pylist())
    ids = tok(txt, return_tensors="pt").input_ids
    flat = ids.reshape(-1)
    ntot = flat.numel() // SEQLEN
    win = flat[:ntot * SEQLEN].view(-1, SEQLEN)
    nwin = min(NWIN, ntot)

    lins = target_modules(model)
    n_par = sum(p.numel() for p in model.parameters())
    n_emb = sum(m.weight.numel() for m in model.modules()
                if isinstance(m, torch.nn.Embedding))
    n_q = sum(m.weight[:, :(m.weight.shape[1] // K) * K].numel() for _, m in lins)
    share = n_q / max(n_par - n_emb, 1)
    print(f"{MDIR}: {len(lins)} nn.Linear tensors (lm_head excluded), "
          f"{n_q:,} of {n_par - n_emb:,} non-embedding params quantised "
          f"({share:.1%}), {ntot} windows available, using {nwin}", flush=True)
    if len(lins) < MIN_TENSORS or share < MIN_SHARE:
        print("GATE FAILED: the harness is not quantising this architecture "
              "(nn.Linear coverage too low). Refusing to produce numbers.")
        return 4

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
        return np.array([float(np.log(perplexity(model, win[i], 1)))
                         for i in range(nwin)], dtype=np.float64)

    # instrument self-test, in THIS process, on THIS checkpoint's tensors
    worst = 0.0
    for _, m in lins:
        w = m.weight.detach()
        worst = max(worst, (quant(w, BOOKS["MXFP4"][1])
                            - quant_signed(w, C.signed_from_magnitudes(
                                BOOKS["MXFP4"][1]))).abs().max().item())
    print(f"INSTRUMENT max|quant - quant_signed| = {worst:.3e}", flush=True)
    if worst != 0.0:
        return 3

    nll = {}
    for name, entry in (("fp32", None), ("MXFP4", BOOKS["MXFP4"]),
                        (ARM, BOOKS[ARM])):
        t0 = time.time()
        apply(entry)
        nll[name] = per_window()
        print(f"{name:<14}{float(np.exp(nll[name].mean())):>10.4f}"
              f"   ({time.time()-t0:.0f}s)", flush=True)
    apply(None)

    ppl = {k: float(np.exp(v.mean())) for k, v in nll.items()}
    degrade = ppl["MXFP4"] / ppl["fp32"] - 1.0
    print(f"GATE MXFP4 vs fp32 = {degrade:+.2%} "
          f"(must be >= {MIN_MXFP4_DEGRADE:.0%})", flush=True)
    if degrade < MIN_MXFP4_DEGRADE:
        print("GATE FAILED: 4-bit quantisation barely moved perplexity -- "
              "the arms are probably not being applied. Refusing.")
        return 5

    out = {"model": MDIR, "nwin": nwin, "n_tensors": len(lins),
           "quantised_share_nonembed": share, "ppl": ppl,
           "per_window_nll": {k: list(map(float, v)) for k, v in nll.items()},
           "mxfp4_vs_fp32_pct": 100.0 * degrade,
           "top_vs_mxfp4_pct": 100.0 * (ppl[ARM] / ppl["MXFP4"] - 1.0),
           "instrument_selftest": worst, "gates_pass": True}

    if VERIFY:
        ref = json.load(open(os.path.join(HERE, f"lineD_ruler_{MDIR}.json")))
        d = max(float(np.abs(np.array(out["per_window_nll"][k])
                             - np.array(ref["per_window_nll"][k][:nwin])).max())
                for k in ("fp32", "MXFP4", ARM))
        print(f"VERIFY vs lineD_ruler_{MDIR}.json: max|dNLL| = {d:.2e}   "
              f"{'SAME INSTRUMENT' if d == 0.0 else 'DIFFERENT INSTRUMENT'}")
        out["verify_max_dnll_vs_lineD_ruler"] = d
        if d != 0.0:
            return 6

    dst = os.path.join(HERE, f"lineB_ruler_{MDIR}.json")
    json.dump(out, open(dst, "w"), indent=1)
    print(f"{ARM} vs MXFP4 = {out['top_vs_mxfp4_pct']:+.2f} %\nwrote {dst}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
