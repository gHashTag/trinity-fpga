#!/usr/bin/env python3
"""Does the scale-rounding result survive on the leader's own axis?

scale_theory.py found two things about the SCALE, both contrary to what the derivation
predicted:

  (1) The asymmetry runs the OTHER WAY. I argued clipping (r<1) is a cliff and coarsening
      (r>1) a ramp, so rounding up should be right. Measured, growing the scale is WORSE:
      at +/-25%, shrink costs 1.42x and grow costs 1.57x. The reason is accounting -- when
      r<1 only the single maximal element clips (weight 1/K), while all K elements get a
      finer step. One clipped element is cheaper than coarsening thirty-two.

  (2) Therefore the MX spec's CEILING rounding of the E8M0 scale is badly suboptimal, and
      the exact block-max scale is not optimal either: the best scale is about 4.5% SMALLER
      than the block maximum requires (r* = 0.955 for E2M1, 3.26% distortion gain).

Both are rounding-rule changes. No new format, no bit-width change, no hardware change --
they apply to deployed MXFP4 exactly as standardised. That makes them worth testing properly,
because a cheap improvement to the incumbent is a stronger result than a new format nobody
will adopt.

This measures wikitext-2 perplexity for each rounding rule. If the theory is right, ceiling
should be the worst of them.
"""
import os
import sys

import numpy as np
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

W = ("/private/tmp/claude-501/-Users-ssdm4-Desktop-PROJECTS-CLAUDE/"
     "0e868af8-ab2d-4d00-be03-8fea94ba48e4/scratchpad/weights")
MODEL = os.path.join(W, "smollm2")
K, SEQLEN = 32, 2048
NW = int(os.environ.get("NW", "24"))
torch.set_grad_enabled(False)


def fp_levels(eb, mb):
    bias = (1 << (eb - 1)) - 1
    out = {0.0}
    for e in range(1 - bias, (1 << eb) - bias):
        for m in range(1 << mb):
            out.add((1 + m / (1 << mb)) * 2.0 ** e)
    lv = np.array(sorted(out))
    return lv / lv.max()


E2M1 = torch.tensor(fp_levels(2, 1), dtype=torch.float64)
DP_OPT = torch.tensor([0.0, 0.1095, 0.2219, 0.3400, 0.4680, 0.6121, 0.7825, 1.0],
                      dtype=torch.float64)


def scale_e8m0(s, offset):
    """Power-of-two scale, rounded with a log-domain offset.
    offset = 0.5 -> ceiling (the MX spec).  offset = 0.0 -> round-to-nearest."""
    return torch.pow(2.0, torch.round(torch.log2(s.clamp(min=1e-30)) + offset - 0.0))


def scale_ue4m3(s, offset):
    """UE4M3 with the same log-domain offset applied before the mantissa is rounded."""
    s = s.clamp(min=1e-30)
    e = torch.floor(torch.log2(s)).clamp(-6, 8)
    m = torch.round((s / torch.pow(2.0, e) - 1.0) * 8 + offset * 8).clamp(0, 8)
    e = e + (m == 8).to(e.dtype)
    m = torch.where(m == 8, torch.zeros_like(m), m)
    return (1 + m / 8) * torch.pow(2.0, e)


def quantise(w, lv, scale_fn, offset, shrink=1.0):
    n = (w.shape[1] // K) * K
    if n == 0:
        return w
    b = w[:, :n].reshape(-1, K).double()
    a = b.abs().amax(dim=1)
    s = scale_fn(shrink * a / lv[-1], offset).clamp(min=1e-30)
    mag = (b / s[:, None]).abs()
    idx = torch.bucketize(mag, (lv[:-1] + lv[1:]) / 2)
    rec = torch.sign(b) * lv[idx] * s[:, None]
    out = w.clone()
    out[:, :n] = rec.reshape(-1, n).to(w.dtype)
    return out


tok = AutoTokenizer.from_pretrained(MODEL)
model = AutoModelForCausalLM.from_pretrained(MODEL, dtype=torch.float32).eval()
import pyarrow.parquet as pq
text = "\n\n".join(pq.read_table(os.path.join(W, "wikitext2-test.parquet"))
                   .column("text").to_pylist())
ids = tok(text, return_tensors="pt").input_ids[0]
lins = [(n, m) for n, m in model.named_modules()
        if isinstance(m, torch.nn.Linear) and "lm_head" not in n]
base = {n: m.weight.detach().clone() for n, m in lins}


def ppl():
    n = (ids.numel() // SEQLEN) * SEQLEN
    x = ids[:n].view(-1, SEQLEN)[:NW]
    nll = 0.0
    for i in range(x.shape[0]):
        c = x[i:i + 1]
        nll += model(c, labels=c).loss.double().item()
    return float(np.exp(nll / x.shape[0]))


p0 = ppl()
print(f"RULER CHECK -- fp32 baseline perplexity {p0:.3f} ({NW} windows)")
if not (5.0 < p0 < 60.0):
    sys.exit("baseline implausible; refusing to compare.")
print()

CASES = [
    ("E2M1 + E8M0  ceiling  (MX spec)", E2M1, scale_e8m0, 0.5, 1.0),
    ("E2M1 + E8M0  nearest", E2M1, scale_e8m0, 0.0, 1.0),
    ("E2M1 + E8M0  t=0.10", E2M1, scale_e8m0, 0.10, 1.0),
    ("E2M1 + E8M0  nearest + shrink .955", E2M1, scale_e8m0, 0.0, 0.955),
    ("E2M1 + UE4M3 nearest", E2M1, scale_ue4m3, 0.0, 1.0),
    ("E2M1 + UE4M3 nearest + shrink .955", E2M1, scale_ue4m3, 0.0, 0.955),
    ("DP-opt + UE4M3 nearest", DP_OPT, scale_ue4m3, 0.0, 1.0),
    ("DP-opt + UE4M3 nearest + shrink .965", DP_OPT, scale_ue4m3, 0.0, 0.965),
]

print(f"  {'configuration':<38}{'perplexity':>12}{'vs fp32':>10}")
ref = None
for name, lv, fn, off, sh in CASES:
    for n, m in lins:
        m.weight.copy_(quantise(base[n].double(), lv, fn, off, sh).to(m.weight.dtype))
    p = ppl()
    if ref is None:
        ref = p
    print(f"  {name:<38}{p:>12.3f}{p - p0:>+10.3f}")
for n, m in lins:
    m.weight.copy_(base[n])

print("\n  Prediction under test: the MX spec's ceiling rule should be the WORST of the")
print("  E8M0 rows, and shrinking the scale below the block maximum should help.")


# ---------------------------------------------------------------------------
# CORRECTION: what the OCP MX spec actually prescribes.
#
# The rows above label a CEILING-rounded E8M0 as "MX spec". Checking the OCP Microscaling
# Formats specification, that is not what it says. The shared scale is
#
#     X = 2 ^ ( floor(log2(max_i |V_i|)) - emax_elem )
#
# with emax_elem the largest exponent of the element format (2 for E2M1, whose maximum is
# 6 = 1.5 x 2^2). So the spec uses a FLOOR on the block maximum's exponent, not a ceiling.
# Writing amax = m * 2^E with m in [1,2), the spec's scale corresponds to a ratio
#
#     r = 1.5 / m ,   m in [1,2)  =>  r in (0.75, 1.5]
#
# i.e. it SHRINKS whenever m > 1.5 and grows otherwise, and it deliberately tolerates
# clipping of the maximal element by up to 25%. My ceiling implementation gives r in [1,2) --
# always growing, which scale_theory.py identifies as the worst region. So the earlier
# "true MXFP4" perplexity was measured against a rule HARSHER than the standard, and that
# label was wrong.
#
# This block measures the spec rule alongside the others so the comparison is honest.
# (Stated as my reading of the spec; the formula is what is implemented and can be checked.)

def scale_ocp_mx(s, offset):
    """OCP MX shared scale. `s` arrives as amax/top, so recover amax = s*top."""
    amax = s * float(E2M1[-1])
    E = torch.floor(torch.log2(amax.clamp(min=1e-30)))
    return torch.pow(2.0, E - 2.0)


print("\n\nCORRECTION -- the OCP MX spec uses a FLOOR rule, not the ceiling used above\n")
EXTRA = [
    ("E2M1 + OCP MX spec rule (floor)", E2M1, scale_ocp_mx, 0.0, 1.0),
    ("E2M1 + E8M0 ceiling (what I called MX)", E2M1, scale_e8m0, 0.5, 1.0),
    ("E2M1 + E8M0 nearest", E2M1, scale_e8m0, 0.0, 1.0),
]
print(f"  {'configuration':<42}{'perplexity':>12}{'vs fp32':>10}")
for name, lv, fn, off, sh in EXTRA:
    for n, m in lins:
        m.weight.copy_(quantise(base[n].double(), lv, fn, off, sh).to(m.weight.dtype))
    p = ppl()
    print(f"  {name:<42}{p:>12.3f}{p - p0:>+10.3f}")
for n, m in lins:
    m.weight.copy_(base[n])
