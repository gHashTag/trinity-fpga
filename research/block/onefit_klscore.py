#!/usr/bin/env python3
"""Score every book under the SAME KL objective the fits were made against.

Two things this settles that the perplexity table cannot.

1.  KL-opt and FIT-smollm2 are the same search on the same model against the
    same objective with the same budget; they differ only in the SEED
    (Lloyd-Max against MXFP4).  Their held-out behaviour is opposite.  Scoring
    both under the objective says whether the objective PREFERRED the seed that
    fails out of sample -- i.e. whether the original protocol's best-of-two-seeds
    rule selected its own failure.

2.  Summing the score over models gives the joint objective JOINT-KL was fitted
    against, so a three-model joint SELECTION over the fitted books can be run
    without a new joint fit.

Objective, window count, reduction and quantiser are campaignA_run.py's, which
reproduces joint_kl_codebook.py's.

    W=<weights> MDIR=opt python3 onefit_klscore.py
"""
import json
import os
import sys
import time

import numpy as np
import torch
import torch.nn.functional as F

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "block_tnf.py")
MARKER = 'print("загружаю модель…", flush=True)'
_s = open(SRC, encoding="utf-8").read()
ns = {}
exec(compile(_s.split(MARKER)[0], SRC, "exec"), ns)
quant, perplexity, target_modules, load_wikitext = (
    ns[k] for k in ("quant", "perplexity", "target_modules", "load_wikitext"))
K, SEQLEN = ns["K"], ns["SEQLEN"]

import campaignA_books as A
import campaignC_books as C

torch.set_grad_enabled(False)
if os.environ.get("THREADS"):
    torch.set_num_threads(int(os.environ["THREADS"]))

MDIR = os.environ["MDIR"]
KLWIN = int(os.environ.get("KLWIN", "2"))
CHUNK = int(os.environ.get("CHUNK", "128"))
SCRATCH = os.environ.get("SCRATCH", os.path.join(os.sep, "tmp"))
WDIR = os.environ.get("W") or os.path.dirname(ns["MODEL"])
WTOL = float(os.environ.get("WTOL", "5e-4"))
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


def t38(lv):
    """Every book normalised so max|level| == 1.0, checked on BOTH tails.

    max(pos, neg) is satisfied by EITHER tail, so it admits a book at
    +1.000 / -0.750 -- a clipping arm, not a placement.  Identical to
    onefit_kl.t38 / onefit_measure.t38; a magnitude ladder has min(v) == 0 and
    mirrors.  See CLIPPING_ARM_CORRECTION_2026-08-12.md.
    """
    v = [float(x) for x in lv]
    assert v == sorted(v) and len(set(v)) == len(v)
    pos = max(v)
    neg = max(-x for x in v) if min(v) < 0 else pos     # symmetric book: mirror
    assert abs(pos - 1.0) < 1e-12, f"positive tail {pos}"
    assert abs(neg - 1.0) < 1e-12, f"negative tail {neg}"
    return v


def main():
    from transformers import AutoModelForCausalLM, AutoTokenizer
    quant_signed = C.make_quant_signed(K, ns["q_e8m0_t"])

    BOOKS = [("MXFP4", "mag", list(C.MXFP4)),
             ("JOINT-KL", "mag", list(C.JOINTKL)),
             ("KL-opt", "mag", list(C.KLOPT))]
    for f in MODELS:
        j = json.load(open(os.path.join(HERE, f"onefit_kl_{f}.json")))
        BOOKS.append((f"FIT-{f}", "mag", [float(x) for x in j["fitted"]]))
    BOOKS.append(("NF4-sym", "mag", C.nf4_sym_magnitudes()))
    BOOKS.append(("NF4", "sig", C.nf4_levels()))
    cand = dict((n, lv) for n, k, lv in A.candidates())
    BOOKS.append(("MX-asym-NEAR0", "sig", [float(x) for x in cand["MX-asym-NEAR0"]]))
    for n, k, lv in BOOKS:
        t38(lv)

    path = os.path.join(WDIR, MDIR)
    print(f"model dir = {path}  NWIN={NWIN}  KLWIN={KLWIN}", flush=True)
    tok = AutoTokenizer.from_pretrained(path)
    model = AutoModelForCausalLM.from_pretrained(path, dtype=torch.float32)
    model.eval()
    ids = tok("\n\n".join(load_wikitext()), return_tensors="pt").input_ids
    flat = ids.reshape(-1)
    win = flat[:(flat.numel() // SEQLEN) * SEQLEN].view(-1, SEQLEN)
    lins = target_modules(model)
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

    # ---- instrument: quant_signed is still block_tnf.quant, in THIS process --
    worst = 0.0
    for _, m in lins:
        w = m.weight.detach()
        worst = max(worst, (quant(w, C.MXFP4)
                            - quant_signed(w, C.signed_from_magnitudes(C.MXFP4))
                            ).abs().max().item())
    print(f"INSTRUMENT max|quant - quant_signed| = {worst:.3e}  "
          f"{'BIT-EXACT' if worst == 0.0 else 'MISMATCH'}", flush=True)
    if worst != 0.0:
        return 3

    bref = json.load(open(os.path.join(HERE, f"campaignB_{MDIR}.json")))
    r = RULERS[MDIR]
    ok = (NWIN == r["nwin"])
    for name, entry in (("fp32", None), ("MXFP4", ("mag", list(C.MXFP4)))):
        apply(entry)
        v = np.array([float(np.log(perplexity(model, win[i], 1)))
                      for i in range(NWIN)])
        p = float(np.exp(v.mean()))
        d = abs(p - r[name]) / r[name]
        dw = float(np.abs(v - np.array(bref["per_window_nll"][name][:NWIN])).max())
        good = d < 5e-4 and dw < WTOL
        ok &= good
        print(f"RULER {name:<6} {p:>10.4f}  published {r[name]:>9.4f}  rel {d:.2e}"
              f"   drift {dw:.2e}  {'OK' if good else 'MISMATCH'}", flush=True)
    if not ok:
        print("RULER BROKEN -- refusing to produce numbers.", flush=True)
        return 2

    apply(None)
    V = int(model(win[0:1]).logits.shape[-1])
    ref_path = os.path.join(SCRATCH, f"onefitsc_ref_{MDIR}.f32")
    ref = np.memmap(ref_path, dtype=np.float32, mode="w+",
                    shape=(KLWIN * SEQLEN, V))
    for i in range(KLWIN):
        lg = model(win[i:i + 1]).logits[0]
        for a in range(0, SEQLEN, CHUNK):
            b = min(a + CHUNK, SEQLEN)
            ref[i * SEQLEN + a: i * SEQLEN + b] = \
                F.log_softmax(lg[a:b].double(), dim=-1).float().numpy()
        del lg
    ref.flush()

    def kl():
        tot, cnt = 0.0, 0
        for i in range(KLWIN):
            lg = model(win[i:i + 1]).logits[0]
            for a in range(0, SEQLEN, CHUNK):
                b = min(a + CHUNK, SEQLEN)
                lpr = torch.from_numpy(
                    np.asarray(ref[i * SEQLEN + a: i * SEQLEN + b])).double()
                lpq = F.log_softmax(lg[a:b].double(), dim=-1)
                tot += float((lpr.exp() * (lpr - lpq)).sum())
                cnt += b - a
                del lpr, lpq
            del lg
        return tot / cnt

    # The reference log-probs are STORED as float32 and compared against a fresh
    # float64 log_softmax, so self-KL is not zero by construction: it is the
    # float32 storage floor, and it moves with thread count (3.2e-10 at 8
    # threads, 1.0e-09 at 3 on smollm2).  The gate is 1e-7 -- four orders below
    # the smallest KL difference this campaign discusses (0.209090 against
    # 0.161978) -- and the observed value is recorded, not just gated.
    apply(None)
    ks = kl()
    print(f"self-KL = {ks:.3e}  {'OK' if abs(ks) < 1e-7 else 'BROKEN'}", flush=True)
    if abs(ks) >= 1e-7:
        return 4

    scores = {}
    for name, kind, lv in BOOKS:
        t0 = time.time()
        apply((kind, lv))
        scores[name] = kl()
        print(f"  KL {name:<16}{scores[name]:>12.6f}   ({time.time()-t0:.0f}s)",
              flush=True)
    apply(None)
    del ref
    os.unlink(ref_path)

    dst = os.path.join(HERE, f"onefit_klscore_{MDIR}.json")
    json.dump({"model": MDIR, "klwin": KLWIN, "self_kl": ks,
               "ruler_reproduces": True, "kl": scores,
               "books": {n: [float(x) for x in lv] for n, k, lv in BOOKS}},
              open(dst, "w"), indent=1)
    print(f"wrote {dst}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
