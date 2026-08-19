#!/usr/bin/env python3
"""Generator for regret_sweep_2026-08-20.json — the eight-bit exponent-width
sweep behind the paper's regret sentence ("E=1 giving 4.5 million and E=2
giving 288 while E=4 costs 0.3% and E=5 costs 6%") and the falsified
width-rule predictions (BNF8 E=4 predicted / E=3 measured, TNF8 Et=3
predicted / Et=2 measured).

The generating experiment is research/block/four_families.py (its record:
research/block/FOUR_FAMILIES_2026-08-10.md).  That script points MODEL at a
session-scratchpad path which is a symlink into the local HF cache; this
rerun addresses the cache snapshot directly (same bytes, sha256-verified at
the time of the rerun) and reproduces the arms the paper quotes:

  fp32 baseline, BNF8 E=1..5, TNF8 Et=1..3
  (GF8 E=3 and GF-T8 Et=3 are bit-identical to BNF8 E=3 / TNF8 Et=3 by the
  levels() construction, so the distinct value sets are covered.)

quant/levels/target_modules/perplexity are copied verbatim from
research/block/four_families.py; the span estimator (median over layers of
log2(amax / q0.001 of nonzero magnitudes)) likewise.

Deterministic: quantisation and the first-40-windows evaluation contain no
randomness.
Model: HuggingFaceTB/SmolLM2-135M snapshot 93efa2f097d58c2a74874c7e644dbc9b0cee75a2
Data:  Salesforce/wikitext wikitext-2-raw-v1 test parquet, dataset snapshot
       b08601e04326c79dfdd32d625aee71d232d685c3
Run:   python3 gen_regret_sweep.py   (~20 min on CPU: 9 x 40-window evals)
"""
import json
import math
import os

import numpy as np
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

torch.set_grad_enabled(False)

MODEL = os.path.expanduser(
    "~/.cache/huggingface/hub/models--HuggingFaceTB--SmolLM2-135M/"
    "snapshots/93efa2f097d58c2a74874c7e644dbc9b0cee75a2")
WIKI = os.path.expanduser(
    "~/.cache/huggingface/hub/datasets--Salesforce--wikitext/"
    "snapshots/b08601e04326c79dfdd32d625aee71d232d685c3/"
    "wikitext-2-raw-v1/test-00000-of-00001.parquet")
SEQLEN, NWIN = 2048, 40
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   "regret_sweep_2026-08-20.json")

PAPER = {  # research/block/FOUR_FAMILIES_2026-08-10.md, quoted in the paper
    "baseline": 14.4874,
    "BNF8 E=1": 4574409.0, "BNF8 E=2": 288.5224, "BNF8 E=3": 14.6130,
    "BNF8 E=4": 14.6592, "BNF8 E=5": 15.5147,
    "TNF8 Et=1": 270015.0, "TNF8 Et=2": 14.7012, "TNF8 Et=3": 15.5147,
}


# ---- copied verbatim from research/block/four_families.py -------------------
def levels(N, E, radix):
    if E < 0:
        return None
    nexp = (3 ** E if radix == 3 else 2 ** E)
    cap = 1 << (N - 1)
    if nexp > cap or nexp > 4096:
        return None
    M = 0
    while nexp * (1 << (M + 1)) <= cap:
        M += 1
    if M < 1:
        return None
    half = nexp // 2
    out = {0.0}
    for e in range(-half, nexp - half):
        for m in range(1 << M):
            out.add((1 + m / (1 << M)) * (2.0 ** e))
    v = sorted(out)
    return np.array(v) / v[-1]


def quant(w, lv):
    lv_t = torch.tensor(lv, dtype=torch.float64)
    x = w.double()
    s = x.abs().amax().clamp(min=1e-30) / lv_t[-1]
    y = (x / s).abs()
    bnd = (lv_t[:-1] + lv_t[1:]) / 2
    return (torch.sign(x) * lv_t[torch.bucketize(y, bnd)] * s).to(w.dtype)


def target_modules(model):
    return [(n, m) for n, m in model.named_modules()
            if isinstance(m, torch.nn.Linear) and "lm_head" not in n]


def perplexity(model, ids, limit_windows=None):
    flat = ids.reshape(-1)
    n = (flat.numel() // SEQLEN) * SEQLEN
    x = flat[:n].view(-1, SEQLEN)
    if limit_windows:
        x = x[:limit_windows]
    nll = cnt = 0.0
    for i in range(x.shape[0]):
        c = x[i:i + 1]
        nll += model(c, labels=c).loss.double().item() * (SEQLEN - 1)
        cnt += SEQLEN - 1
    return float(np.exp(nll / cnt))
# -----------------------------------------------------------------------------


def main():
    import pyarrow.parquet as pq
    tok = AutoTokenizer.from_pretrained(MODEL)
    model = AutoModelForCausalLM.from_pretrained(
        MODEL, dtype=torch.float32).eval()
    text = "\n\n".join(pq.read_table(WIKI).column("text").to_pylist())
    ids = tok(text, return_tensors="pt").input_ids

    base = perplexity(model, ids, NWIN)
    print(f"fp32 baseline: {base:.4f} (paper {PAPER['baseline']})", flush=True)
    if not (10.0 < base < 60.0):
        raise SystemExit("baseline out of band; ruler broken, stopping")

    # span estimator, verbatim convention (0.1st pct of nonzero -> max)
    spans = []
    for _, m in target_modules(model):
        x = m.weight.detach().double().abs()
        x = x[x > 0]
        spans.append(float(torch.log2(x.amax() / torch.quantile(x, 0.001))))
    span = float(np.median(spans))
    need_bin = math.ceil(math.log2(max(span, 2)))
    need_tri = math.ceil(math.log(max(span, 2), 3))
    print(f"span estimator: {span:.2f} binades -> predicts BNF8 E={need_bin},"
          f" TNF8 Et={need_tri}", flush=True)

    arms = [(f"BNF8 E={E}", levels(8, E, 2)) for E in range(1, 6)]
    arms += [(f"TNF8 Et={t}", levels(8, t, 3)) for t in range(1, 4)]

    orig = {n: m.weight.detach().clone() for n, m in target_modules(model)}
    rows = {"baseline": {"ppl": round(base, 4), "paper": PAPER["baseline"]}}
    for name, lv in arms:
        for n, m in target_modules(model):
            m.weight.copy_(quant(orig[n], lv))
        p = perplexity(model, ids, NWIN)
        for n, m in target_modules(model):
            m.weight.copy_(orig[n])
        rows[name] = {"ppl": round(p, 4), "magnitudes": len(lv),
                      "paper": PAPER[name]}
        print(f"{name}: {p:.4f} (paper {PAPER[name]})", flush=True)

    e3, e4, e5 = (rows[f"BNF8 E={k}"]["ppl"] for k in (3, 4, 5))
    rec = {
        "record": "8-bit exponent-width regret sweep (paper's E=1..E=5 "
                  "asymmetry sentence and the falsified width-rule "
                  "predictions)",
        "date": "2026-08-20",
        "generator": "research/arxiv_tnf/measurements/gen_regret_sweep.py",
        "generating_experiment": "research/block/four_families.py "
                                 "(record: research/block/"
                                 "FOUR_FAMILIES_2026-08-10.md)",
        "model": "HuggingFaceTB/SmolLM2-135M",
        "snapshot": "93efa2f097d58c2a74874c7e644dbc9b0cee75a2",
        "data": "Salesforce/wikitext wikitext-2-raw-v1 test, snapshot "
                "b08601e04326c79dfdd32d625aee71d232d685c3",
        "windows": NWIN, "seqlen": SEQLEN, "scale": "per-tensor",
        "span_estimator": {
            "definition": "median over layers of log2(amax / q0.001 of "
                          "nonzero magnitudes)",
            "binades": round(span, 4),
            "predicts": {"BNF8_E": need_bin, "TNF8_Et": need_tri},
        },
        "arms": rows,
        "derived": {
            "E4_over_E3_pct": round(100 * (e4 / e3 - 1), 2),
            "E5_over_E3_pct": round(100 * (e5 / e3 - 1), 2),
            "paper_says": "E=4 costs 0.3%, E=5 costs 6%",
        },
    }
    with open(OUT, "w") as f:
        json.dump(rec, f, indent=2)
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
