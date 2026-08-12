#!/usr/bin/env python3
"""Campaign A, per-model pass: the ruler, the instrument, the KL scores.

MODE=kl   reproduce the published ruler for this model, prove the signed
          quantiser is still the same instrument as block_tnf.quant in THIS
          process, then score every candidate placement by
          KL(fp32 || quantised) on KLWIN calibration windows -- the same
          objective, window count and reduction joint_kl_codebook.py used to
          fit JOINT-KL.  Writes campaignA_kl_<mdir>.json.

MODE=ppl  measure per-window NLL for the books named in BOOKS on this model,
          for arms campaign B never measured.  Writes campaignA_ppl_<mdir>.json
          (merging into it if it exists).

Nothing on the measurement path is reimplemented: quant / perplexity /
target_modules / load_wikitext / q_e8m0_t are executed out of block_tnf.py's
source up to its driver marker, and quant_signed is campaignC_books'.

    W=<weights dir> MDIR=qwen MODE=kl python3 campaignA_run.py
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
if os.environ.get("THREADS"):
    torch.set_num_threads(int(os.environ["THREADS"]))

MDIR = os.environ["MDIR"]
MODE = os.environ.get("MODE", "kl")
KLWIN = int(os.environ.get("KLWIN", "2"))
CHUNK = int(os.environ.get("CHUNK", "128"))
SCRATCH = os.environ.get("SCRATCH", os.path.join(os.sep, "tmp"))

# block_tnf.py's own W points at another session's dir; this campaign carries
# its own copy of the same four checkpoints and the same parquet.
WDIR = os.environ.get("W") or os.path.dirname(ns["MODEL"])
ns["W"] = WDIR
ns["load_wikitext"] = load_wikitext = (
    lambda: __import__("pyarrow.parquet", fromlist=["parquet"])
    .read_table(os.path.join(WDIR, "wikitext2-test.parquet"))
    .column("text").to_pylist())

RULERS = {
    "smollm2": {"nwin": 40, "fp32": 14.4874, "MXFP4": 21.9397},
    "qwen":    {"nwin": 20, "fp32": 12.6999, "MXFP4": 15.4374},
    "pythia":  {"nwin": 40, "fp32": 25.9561, "MXFP4": 47.6504},
    "opt":     {"nwin": 40, "fp32": 27.5678, "MXFP4": 30.7871},
}
NWIN = int(os.environ.get("NWIN", RULERS[MDIR]["nwin"]))


def wikitext():
    return "\n\n".join(load_wikitext())


def main():
    from transformers import AutoModelForCausalLM, AutoTokenizer
    quant_signed = C.make_quant_signed(K, ns["q_e8m0_t"])
    BOOKS = {n: (k, [float(x) for x in lv]) for n, k, lv in A.all_books()}
    list(A.check(A.all_books()))          # T38 on both tails, 16-codeword count

    path = os.path.join(WDIR, MDIR)
    print(f"model dir = {path}  MODE={MODE}  NWIN={NWIN}  KLWIN={KLWIN}", flush=True)
    tok = AutoTokenizer.from_pretrained(path)
    model = AutoModelForCausalLM.from_pretrained(path, dtype=torch.float32)
    model.eval()
    ids = tok(wikitext(), return_tensors="pt").input_ids
    flat = ids.reshape(-1)
    ntot = flat.numel() // SEQLEN
    win = flat[:ntot * SEQLEN].view(-1, SEQLEN)
    print(f"tokens={flat.numel()}  windows={ntot}", flush=True)
    if ntot < NWIN:
        raise SystemExit(f"only {ntot} windows, need {NWIN}")

    lins = target_modules(model)
    orig = {n: m.weight.detach().clone() for n, m in lins}
    print(f"{len(lins)} linear tensors quantised (lm_head excluded)", flush=True)

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

    # ---- instrument: quant_signed is still block_tnf.quant, in THIS process --
    worst = 0.0
    for name in ("MXFP4", "NF4-sym"):
        mags = BOOKS[name][1]
        sig = C.signed_from_magnitudes(mags)
        assert len(sig) == 15, (name, len(sig))
        for _, m in lins:
            w = m.weight.detach()
            worst = max(worst, (quant(w, mags) - quant_signed(w, sig)).abs().max().item())
    print(f"INSTRUMENT max|quant - quant_signed| = {worst:.3e}  "
          f"{'BIT-EXACT' if worst == 0.0 else 'MISMATCH'}", flush=True)
    if worst != 0.0:
        return 3

    # ---- ruler: reproduce the published fp32 and MXFP4 perplexity -----------
    bref = json.load(open(os.path.join(HERE, f"campaignB_{MDIR}.json")))
    r = RULERS[MDIR]
    ruler_ok = (NWIN == r["nwin"])
    nll = {}
    for name, entry in (("fp32", None), ("MXFP4", BOOKS["MXFP4"])):
        t0 = time.time()
        apply(entry)
        nll[name] = per_window()
        p = float(np.exp(nll[name].mean()))
        d = abs(p - r[name]) / r[name]
        prev = np.array(bref["per_window_nll"][name][:NWIN])
        dw = float(np.abs(nll[name] - prev).max())
        good = d < 5e-4
        ruler_ok &= good
        print(f"RULER {name:<6} {p:>10.4f}  published {r[name]:>9.4f}  rel {d:.2e}  "
              f"{'OK' if good else 'MISMATCH'}   max|per-window - campaignB| = "
              f"{dw:.2e}   ({time.time()-t0:.0f}s)", flush=True)
    if not ruler_ok:
        print("RULER BROKEN -- refusing to produce numbers.", flush=True)
        return 2

    if MODE == "ppl":
        want = [b for b in os.environ["BOOKS"].split(",") if b]
        dst = os.path.join(HERE, f"campaignA_ppl_{MDIR}.json")
        out = json.load(open(dst)) if os.path.exists(dst) else {}
        out.setdefault("model", MDIR)
        out.setdefault("nwin", NWIN)
        out.setdefault("per_window_nll", {})
        out["per_window_nll"]["fp32"] = list(map(float, nll["fp32"]))
        out["per_window_nll"]["MXFP4"] = list(map(float, nll["MXFP4"]))
        for b in want:
            t0 = time.time()
            apply(BOOKS[b])
            v = per_window()
            out["per_window_nll"][b] = list(map(float, v))
            print(f"  {b:<16}{float(np.exp(v.mean())):>10.4f}"
                  f"   ({time.time()-t0:.0f}s)", flush=True)
        out["books"] = {n: BOOKS[n][1] for n in out["per_window_nll"] if n in BOOKS}
        json.dump(out, open(dst, "w"), indent=1)
        print(f"wrote {dst}")
        return 0

    # ---- KL(fp32 || quantised), joint_kl_codebook.py's objective -----------
    apply(None)
    V = int(model(win[0:1]).logits.shape[-1])
    ref_path = os.path.join(SCRATCH, f"campA_ref_{MDIR}.f32")
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
    print(f"reference log-probs: vocab {V}, {ref.nbytes/1e9:.2f} GB", flush=True)

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

    apply(None)
    kl_self = kl()
    print(f"self-KL (fp32 vs fp32) = {kl_self:.3e}  "
          f"{'OK' if abs(kl_self) < 1e-9 else 'INSTRUMENT BROKEN'}", flush=True)
    if abs(kl_self) >= 1e-9:
        return 4

    scores = {}
    for name in BOOKS:
        t0 = time.time()
        apply(BOOKS[name])
        scores[name] = kl()
        print(f"  KL {name:<16}{scores[name]:>12.6f}   ({time.time()-t0:.0f}s)",
              flush=True)
    apply(None)
    del ref
    os.unlink(ref_path)

    out = {"model": MDIR, "nwin": NWIN, "klwin": KLWIN, "vocab": V,
           "ruler_reproduces": True, "self_kl": kl_self, "kl": scores,
           "ppl": {"fp32": float(np.exp(nll["fp32"].mean())),
                   "MXFP4": float(np.exp(nll["MXFP4"].mean()))},
           "per_window_nll": {k: list(map(float, v)) for k, v in nll.items()},
           "books": {n: BOOKS[n][1] for n in BOOKS}}
    dst = os.path.join(HERE, f"campaignA_kl_{MDIR}.json")
    json.dump(out, open(dst, "w"), indent=1)
    print(f"wrote {dst}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
