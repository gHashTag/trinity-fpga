#!/usr/bin/env python3
"""Second part: does the sixteenth-codeword gain track the alphabet ratio?

T40 measured one number: at a 4-bit index, spending the wasted +0/-0 codeword is
worth 4.43 %. The conjecture on offer is that the gain is a function of how much
the ALPHABET grows -- from 2n-1 to 2n values, a factor 2n/(2n-1).

A single point cannot test a functional form, so this sweeps the index width.
`create_normal_map` generalises exactly: for a b-bit index the asymmetric book
takes 2^(b-1) positive quantiles and 2^(b-1)-1 negative ones (2^b values), the
symmetric book takes 2^(b-1)-1 of each (2^b - 1 values). Same construction, same
offset within a width, only the extra codeword differs -- so the sym/asym pair at
each width isolates the same effect T40 isolated at b = 4.

    b = 3   n = 4    7 -> 8  values   ratio 8/7  = +14.29 %
    b = 4   n = 8   15 -> 16 values   ratio 16/15 = +6.67 %
    b = 5   n = 16  31 -> 32 values   ratio 32/31 = +3.23 %

QLoRA's offset is 1 - (1/(2(2^b-1)) + 1/(2*2^b))/2, which at b = 4 is bitsandbytes'
0.9677083; it is applied at its own width, asserted against that value at b = 4.

b = 4 is measured here too rather than reused, so all three widths come from one
process under one convention.

    MDIR=qwen NWIN=20 python3 campaignC_width.py
"""
import json
import math
import os
import sys
import time

import numpy as np
import torch
from scipy.stats import norm

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "block_tnf.py")
MARKER = 'print("загружаю модель…", flush=True)'
_s = open(SRC, encoding="utf-8").read()
ns = {}
exec(compile(_s.split(MARKER)[0], SRC, "exec"), ns)
quant, perplexity, target_modules, load_wikitext = (
    ns[k] for k in ("quant", "perplexity", "target_modules", "load_wikitext"))
K, SEQLEN = ns["K"], ns["SEQLEN"]
W = os.path.dirname(ns["MODEL"])

import campaignC_books as C

torch.set_grad_enabled(False)
if os.environ.get("THREADS"):
    torch.set_num_threads(int(os.environ["THREADS"]))
MDIR = os.environ.get("MDIR", "smollm2")
NWIN = int(os.environ.get("NWIN", "40"))
BITS = [3, 4, 5]


def qlora_offset(bits):
    n = 1 << bits
    return 1 - (1 / (2 * (n - 1)) + 1 / (2 * n)) / 2


assert abs(qlora_offset(4) - 0.9677083) < 1e-7, qlora_offset(4)


def normal_map(bits, extra):
    """Signed level list. extra=True -> 2^bits values, False -> 2^bits - 1."""
    off = qlora_offset(bits)
    npos = (1 << (bits - 1)) if extra else (1 << (bits - 1)) - 1
    nneg = (1 << (bits - 1)) - 1
    v1 = norm.ppf(torch.linspace(off, 0.5, npos + 1)[:-1]).tolist()
    v3 = (-norm.ppf(torch.linspace(off, 0.5, nneg + 1)[:-1])).tolist()
    v = sorted(set(round(float(x), 12) for x in v1 + [0.0] + v3))
    top = max(abs(x) for x in v)
    v = [x / top for x in v]
    assert len(v) == (1 << bits) - (0 if extra else 1), (bits, extra, len(v))
    assert abs(max(abs(x) for x in v) - 1.0) < 1e-12
    return v


def main():
    from transformers import AutoModelForCausalLM, AutoTokenizer
    quant_signed = C.make_quant_signed(K, ns["q_e8m0_t"])

    # the b = 4 pair must be the very books Campaign C measured
    ref16 = C.nf4_levels()
    got16 = normal_map(4, True)
    e16 = max(abs(a - b) for a, b in zip(got16, ref16))
    ref15 = C.signed_from_magnitudes(C.nf4_sym_magnitudes())
    got15 = normal_map(4, False)
    e15 = max(abs(a - b) for a, b in zip(got15, ref15))
    print(f"b=4 reproduces NF4      : max dev {e16:.2e}")
    print(f"b=4 reproduces NF4-sym  : max dev {e15:.2e}")
    assert e16 < 1e-12 and e15 < 1e-12, "generalisation does not match bnb at b=4"

    BOOKS = []
    for b in BITS:
        for extra in (False, True):
            lv = normal_map(b, extra)
            BOOKS.append((f"b{b}-{'asym' if extra else 'sym'}", lv))
    print("\nbooks:")
    for nm, lv in BOOKS:
        print(f"  {nm:<10} {len(lv):>3} values   bits/elem = "
              f"{[b for b in BITS if f'b{b}-' in nm][0] + 8 / K:.3f}")

    path = os.path.join(W, MDIR)
    print(f"\nmodel dir = {path}   NWIN={NWIN}", flush=True)
    tok = AutoTokenizer.from_pretrained(path)
    model = AutoModelForCausalLM.from_pretrained(path, dtype=torch.float32)
    model.eval()
    ids = tok(load_wikitext(), return_tensors="pt").input_ids
    flat = ids.reshape(-1)
    win = flat[:(flat.numel() // SEQLEN) * SEQLEN].view(-1, SEQLEN)
    lins = target_modules(model)
    orig = {n: m.weight.detach().clone() for n, m in lins}

    def per_window():
        return np.array([math.log(perplexity(model, win[i], 1))
                         for i in range(NWIN)], dtype=np.float64)

    nlls, ppl = {}, {}
    for n, m in lins:
        m.weight.copy_(orig[n])
    nlls["fp32"] = per_window()
    ppl["fp32"] = float(np.exp(nlls["fp32"].mean()))
    print(f"\nfp32 = {ppl['fp32']:.4f}", flush=True)

    for nm, lv in BOOKS:
        t0 = time.time()
        for n, m in lins:
            m.weight.copy_(quant_signed(orig[n], lv))
        v = per_window()
        nlls[nm] = v
        ppl[nm] = float(np.exp(v.mean()))
        print(f"  {nm:<10} {ppl[nm]:>10.4f}   ({time.time()-t0:.0f}s)", flush=True)
    for n, m in lins:
        m.weight.copy_(orig[n])

    print(f"\n  {'width':<8}{'n mags':>8}{'alphabet':>12}{'ratio':>9}"
          f"{'asym vs sym':>14}")
    rows = {}
    for b in BITS:
        n = 1 << (b - 1)
        d = nlls[f"b{b}-asym"] - nlls[f"b{b}-sym"]
        gain = 100 * (math.exp(d.mean()) - 1)
        rows[b] = {"n": n, "alphabet": [2 * n - 1, 2 * n],
                   "ratio_pct": 100 * (1 / (2 * n - 1)),
                   "gain_pct": gain,
                   "ppl_sym": ppl[f"b{b}-sym"], "ppl_asym": ppl[f"b{b}-asym"],
                   "d": list(map(float, d))}
        print(f"  b={b:<6}{n:>8}{f'{2*n-1}->{2*n}':>12}"
              f"{100/(2*n-1):>+8.2f}%{gain:>+13.2f}%")

    out = {"model": MDIR, "nwin": NWIN, "ppl": ppl, "rows": rows,
           "per_window_nll": {k: list(map(float, v)) for k, v in nlls.items()}}
    dst = os.path.join(HERE, f"campaignC_width_{MDIR}.json")
    json.dump(out, open(dst, "w"), indent=1)
    print(f"\nwrote {dst}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
