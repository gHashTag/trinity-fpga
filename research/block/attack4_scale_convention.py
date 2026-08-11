#!/usr/bin/env python3
"""ATTACK 4 — is the KL-optimised codebook's win an artefact of the alignment rule?

`MXFP4_SCALE_CONVENTION_2026-08-11.md` shows the shared-scale alignment rule
decides which eight-level codebook wins:

    s = 2^ceil(log2(a_max / top))   -> Lloyd-Max beats MXFP4 by 0.90 %
    s = 2^ceil(log2(a_max)) / top   -> MXFP4 beats Lloyd-Max by 4.45 %

`kl_optimal_codebook.py` found its codebook under the SECOND rule, because it
normalised every codebook to a top of exactly 1.0 before quantising. The
algebraic identity that makes this a trap:

    rule 2 on raw levels L (top T)  ==  rule 1 on the SAME levels scaled to top 1

so "normalise everything to 1.0" is not neutral: it moves every codebook onto
the SAME power-of-two lattice offset (offset 0). MXFP4's raw top is 6.0, whose
offset is log2(6) mod 1 = 0.585 binades — a different lattice. The KL search ran
entirely at offset 0.

Design: 3 codebooks x lattice offset {top=1.0, top=6.0} under rule 1, plus each
codebook's raw top, plus the OCP MX spec rule. Only the expression for `s`
changes; the rest of the path is block_tnf.quant transcribed unchanged, and that
transcription is checked tensor-for-tensor against the original.
"""
import os
import sys
import json
import time

import numpy as np
import torch

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "block_tnf.py")
MARKER = 'print("загружаю модель…", flush=True)'
_src = open(SRC, encoding="utf-8").read()
if MARKER not in _src:
    raise SystemExit("attack4: driver marker not found in block_tnf.py")
_ns = {}
exec(compile(_src.split(MARKER)[0], SRC, "exec"), _ns)

quant_orig = _ns["quant"]
perplexity = _ns["perplexity"]
target_modules = _ns["target_modules"]
load_wikitext = _ns["load_wikitext"]
MODEL, K, SEQLEN = _ns["MODEL"], _ns["K"], _ns["SEQLEN"]

torch.set_grad_enabled(False)
NWIN = int(os.environ.get("NWIN", "40"))

MXFP4_RAW = [0.0, 0.5, 1.0, 1.5, 2.0, 3.0, 4.0, 6.0]           # E2M1, top 6.0
LLOYD_RAW = [0.0, 0.10334, 0.21079, 0.32491, 0.44963,
             0.59031, 0.75635, 0.96567]                         # top 0.96567
KL_RAW = [0.0, 0.07701, 0.18828, 0.31396, 0.46561,
          0.6113, 0.79074, 1.0]                                 # top 1.0

PUB = {"fp32": 14.4874,
       "MXFP4 @1.0 rule1": 21.9397,      # == published "rule 2" MXFP4
       "Lloyd @1.0 rule1": 22.9166,      # == published "rule 2" Lloyd-Max
       "KL    @1.0 rule1": 20.2587,      # the result under attack
       "MXFP4 @6.0 rule1": 22.4998,      # == published "rule 1" MXFP4 (raw)
       "Lloyd @0.96567 rule1": 22.2976,  # == published "rule 1" Lloyd-Max (raw)
       "MXFP4 @6.0 ocp": 23.5380}        # OCP spec rule on raw E2M1


def scaled(lv, top):
    v = sorted(float(x) for x in lv)
    return [x * top / v[-1] for x in v]


# ---- block_tnf.quant transcribed; ONLY `srule` differs between conventions ---
def quant_rule(w, lv, srule):
    lv_t = torch.tensor(sorted(lv), dtype=torch.float64)
    n = (w.shape[1] // K) * K
    if n == 0:
        return w
    head = w[:, :n].reshape(-1, K).double()
    amax = head.abs().amax(dim=1)
    s = srule(amax, float(lv_t[-1])).clamp(min=1e-30)
    y = (head / s[:, None]).abs()
    bnd = (lv_t[:-1] + lv_t[1:]) / 2
    rec = torch.sign(head) * lv_t[torch.bucketize(y, bnd)] * s[:, None]
    out = w.clone()
    out[:, :n] = rec.reshape(-1, n).to(w.dtype)
    return out


def s_rule1(amax, top):          # s = 2^ceil(log2(a_max / top))
    return torch.pow(2.0, torch.ceil(torch.log2((amax / top).clamp(min=1e-30))))


def s_rule2(amax, top):          # s = 2^ceil(log2(a_max)) / top
    return torch.pow(2.0, torch.ceil(torch.log2(amax.clamp(min=1e-30)))) / top


def s_ocp(amax, top):            # s = 2^(floor(log2 a_max) - floor(log2 top))
    emax = float(np.floor(np.log2(top)))
    return torch.pow(2.0, torch.floor(torch.log2(amax.clamp(min=1e-30))) - emax)


def main():
    print("loading model…", flush=True)
    from transformers import AutoModelForCausalLM, AutoTokenizer
    tok = AutoTokenizer.from_pretrained(MODEL)
    model = AutoModelForCausalLM.from_pretrained(MODEL, dtype=torch.float32)
    model.eval()
    ids = tok(load_wikitext(), return_tensors="pt").input_ids
    lins = target_modules(model)
    orig = {n: m.weight.detach().clone() for n, m in lins}
    print(f"{len(lins)} linear layers, NWIN={NWIN}", flush=True)

    # ---- instrument check on the transcribed quantiser, before any run -------
    probe = orig[lins[0][0]]
    for lv in (MXFP4_RAW, LLOYD_RAW, KL_RAW):
        a = quant_rule(probe, lv, s_rule1)
        b = quant_orig(probe, lv)
        if not torch.equal(a, b):
            print("TRANSCRIPTION MISMATCH: quant_rule(s_rule1) != block_tnf.quant")
            return 1
    # identity: rule2 on raw levels == rule1 on the same levels scaled to top 1
    for lv in (MXFP4_RAW, LLOYD_RAW):
        a = quant_rule(probe, lv, s_rule2)
        b = quant_rule(probe, scaled(lv, 1.0), s_rule1)
        d = (a - b).abs().max().item()
        print(f"  identity check  rule2(raw top {max(lv)}) vs rule1(@1.0): "
              f"max|Δ| = {d:.3e}")
    print("  transcription == block_tnf.quant on all three codebooks: ok", flush=True)

    results = {}

    def restore():
        for n, m in lins:
            m.weight.copy_(orig[n])

    def measure(tag, lv, srule):
        t0 = time.time()
        for n, m in lins:
            m.weight.copy_(quant_rule(orig[n], lv, srule))
        p = perplexity(model, ids, NWIN)
        results[tag] = p
        exp = PUB.get(tag)
        note = ""
        if exp is not None:
            note = f"   published {exp}  {'OK' if abs(p-exp) < 0.02 else 'MISMATCH'}"
        print(f"  {tag:<26} {p:9.4f}{note}   [{time.time()-t0:.0f}s]", flush=True)
        return p

    restore()
    t0 = time.time()
    base = perplexity(model, ids, NWIN)
    results["fp32"] = base
    print(f"\nRULER  fp32 = {base:.4f} (published {PUB['fp32']}) [{time.time()-t0:.0f}s]",
          flush=True)
    if abs(base - PUB["fp32"]) > 0.02:
        print("RULER BROKEN. Stop.")
        return 1

    print("\n1) rule 1  s = 2^ceil(log2(a_max/top)),  lattice offset 0  (top = 1.0)")
    print("   this is exactly the convention kl_optimal_codebook.py used")
    measure("MXFP4 @1.0 rule1", scaled(MXFP4_RAW, 1.0), s_rule1)
    measure("Lloyd @1.0 rule1", scaled(LLOYD_RAW, 1.0), s_rule1)
    measure("KL    @1.0 rule1", scaled(KL_RAW, 1.0), s_rule1)

    print("\n2) rule 1, lattice offset log2(6) mod 1 = 0.585  (top = 6.0, MXFP4's own)")
    measure("MXFP4 @6.0 rule1", MXFP4_RAW, s_rule1)
    measure("Lloyd @6.0 rule1", scaled(LLOYD_RAW, 6.0), s_rule1)
    measure("KL    @6.0 rule1", scaled(KL_RAW, 6.0), s_rule1)

    print("\n3) rule 1 at each codebook's RAW top, as the published tables use it")
    measure("Lloyd @0.96567 rule1", LLOYD_RAW, s_rule1)

    print("\n4) OCP MX spec rule  s = 2^(floor(log2 a_max) - floor(log2 top))")
    measure("MXFP4 @6.0 ocp", MXFP4_RAW, s_ocp)
    measure("Lloyd @6.0 ocp", scaled(LLOYD_RAW, 6.0), s_ocp)
    measure("KL    @6.0 ocp", scaled(KL_RAW, 6.0), s_ocp)
    measure("Lloyd @1.0 ocp", scaled(LLOYD_RAW, 1.0), s_ocp)
    measure("KL    @1.0 ocp", scaled(KL_RAW, 1.0), s_ocp)

    restore()
    out = os.path.join(HERE, "attack4_scale_convention.json")
    json.dump(results, open(out, "w"), indent=1)
    print(f"\nwrote {out}")

    def rel(a, b):
        return 100 * (results[a] / results[b] - 1)

    print("\n═══ KL-opt vs MXFP4 and vs Lloyd-Max, per convention ═══")
    for tag, k, m, l in (
            ("rule1 @1.0 (KL's own)", "KL    @1.0 rule1", "MXFP4 @1.0 rule1", "Lloyd @1.0 rule1"),
            ("rule1 @6.0 (MXFP4's)", "KL    @6.0 rule1", "MXFP4 @6.0 rule1", "Lloyd @6.0 rule1"),
            ("OCP spec @6.0", "KL    @6.0 ocp", "MXFP4 @6.0 ocp", "Lloyd @6.0 ocp")):
        print(f"  {tag:<22} KL {results[k]:8.4f}  MXFP4 {results[m]:8.4f} "
              f"({rel(k, m):+.2f}%)  Lloyd {results[l]:8.4f} ({rel(k, l):+.2f}%)")
    print("\n═══ raw-top comparison, the mixture the published tables actually use ═══")
    print(f"  MXFP4 raw(6.0) {results['MXFP4 @6.0 rule1']:.4f} | "
          f"Lloyd raw(0.96567) {results['Lloyd @0.96567 rule1']:.4f} | "
          f"KL raw(1.0) {results['KL    @1.0 rule1']:.4f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
