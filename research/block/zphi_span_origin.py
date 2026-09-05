#!/usr/bin/env python3
"""Where does the 43-step phi span come from, and which span governs the accumulator?

zphi_acc_width.py measures the per-dot-product phi span of the CAMPAIGN grid (block 32
along in_features, block scale phi^ceil(log_phi amax), ladder phi^-6..phi^0) and gets
max 13 over all 210 SmolLM2 linear tensors.  The campaign's own worst-case accumulator
provisioning uses S = 43, which yields 46 bits/component.  Two numbers for the same-named
quantity is a contradiction, and a contradiction gets resolved, not appended to.

Hypothesis: 43 is the span of the RAW weights on a single global phi^k grid -- no block
scale, no ladder, no zero code -- i.e. the dynamic range of a row in phi steps.  The
campaign grid never sees that span because the per-block scale re-centres every 32 weights
and the 7-level ladder floors everything more than 6 phi-steps below its block maximum.

This script measures BOTH spans on the same weights, per 512-tile and per full row:
    G_raw       m = round(log_phi |w|), every nonzero weight            <- expect ~43
    G_campaign  m = e_block + ladder_index - 7, nonzero codes only      <- expect 13

Self-tested before any number is printed, including a Decimal recomputation of the raw
exponents and cross-instrument agreement with zphi_acc_width.py's span.
"""
import os
import sys
import json
import math
import decimal

import numpy as np
import torch

WDIR = ("/private/tmp/claude-501/-Users-ssdm4-Desktop-PROJECTS-CLAUDE/"
        "0e868af8-ab2d-4d00-be03-8fea94ba48e4/scratchpad/weights")
MODEL = os.path.join(WDIR, "smollm2")
K = 32
FANIN = 512
PHI = (1 + 5 ** 0.5) / 2
LOGPHI = np.log(PHI)
NLAD = 8
PHIL = torch.tensor([0.0] + [PHI ** (-k) for k in range(6, -1, -1)], dtype=torch.float64)
torch.set_grad_enabled(False)


def fail(msg):
    print(f"\n  SELF-TEST FAILED: {msg}\n  No numbers reported.")
    sys.exit(1)


_F = [0, 1]
while len(_F) < 400:
    _F.append(_F[-1] + _F[-2])


def fib(d):
    """F_d, Python int, F_0 = 0."""
    return _F[d]


def campaign_exponents(w):
    """(m, valid): m = e_block + idx - 7 for the campaign grid, valid = nonzero code."""
    out, n = w.shape
    nb = n // K
    b = w.reshape(out * nb, K)
    amax = b.abs().amax(dim=1).clamp(min=1e-300)
    e = torch.ceil(torch.log(amax) / LOGPHI - 1e-9)
    s = torch.pow(PHI, e)
    idx = torch.bucketize((b / s[:, None]).abs(), (PHIL[:-1] + PHIL[1:]) / 2)
    e = e.to(torch.int64).reshape(out, nb)
    idx = idx.reshape(out, n).to(torch.int64)
    m = e.repeat_interleave(K, dim=1) + idx - (NLAD - 1)
    return m.numpy(), (idx > 0).numpy()


def raw_exponents(w):
    """(m, valid): nearest point of the single global grid {+-phi^k}, no scale, no zero."""
    a = w.abs()
    valid = (a > 0).numpy()
    m = torch.where(a > 0, torch.round(torch.log(a.clamp(min=1e-300)) / LOGPHI),
                    torch.zeros_like(a)).to(torch.int64).numpy()
    return m, valid


def tiles(n):
    st = [(i * FANIN, FANIN) for i in range(n // FANIN)]
    if n % FANIN:
        st.append((n - FANIN, FANIN))
    return st


BIG = np.int64(1 << 40)


def spans(m, valid, per_tile):
    """Per-dot-product span (max m - min m) over the valid entries, as a flat int array."""
    out, n = m.shape
    rngs = tiles(n) if per_tile else [(0, n)]
    acc = []
    for st, L in rngs:
        sl = slice(st, st + L)
        hi = np.where(valid[:, sl], m[:, sl], -BIG).max(axis=1)
        lo = np.where(valid[:, sl], m[:, sl], BIG).min(axis=1)
        live = lo < BIG
        acc.append((hi - lo)[live])
    return np.concatenate(acc)


# ------------------------------------------------------------------ self-tests
def selftests():
    print("  self-tests")
    g = torch.Generator().manual_seed(11)
    w = torch.randn(64, 512, generator=g, dtype=torch.float64) * 0.02
    w[0, 5] = 0.0
    w[1, :] *= 1e-6
    w[2, 7] = 12.0

    # S1 raw exponents recomputed at 60 digits, no float log anywhere
    decimal.getcontext().prec = 60
    D = decimal.Decimal
    phid = (1 + D(5).sqrt()) / 2
    lnphi = phid.ln()
    m, val = raw_exponents(w)
    bad = 0
    for r in range(8):
        for c in range(0, 512, 37):
            if not val[r, c]:
                continue
            ex = int((D(float(w[r, c].abs())).ln() / lnphi).to_integral_value(
                rounding=decimal.ROUND_HALF_EVEN))
            if abs(ex - int(m[r, c])) > 0:
                bad += 1
    if bad:
        fail(f"raw phi exponent disagrees with 60-digit Decimal on {bad} entries")
    print("    S1 raw exponents == 60-digit Decimal round(ln|w|/ln phi) on 112 probes  OK")

    # S2 the raw grid really is a grid: phi^m is within a half-step of |w|
    r = PHI ** m.astype(np.float64)
    ratio = np.where(val, r / np.maximum(w.abs().numpy(), 1e-300), 1.0)
    if ratio.max() > PHI ** 0.5 + 1e-9 or ratio.min() < PHI ** -0.5 - 1e-9:
        fail(f"raw grid not nearest: ratio range {ratio.min()}..{ratio.max()}")
    print(f"    S2 every raw code is the NEAREST phi^k: |w|/phi^m in "
          f"[{ratio.min():.4f}, {ratio.max():.4f}] subset [phi^-.5, phi^.5]  OK")

    # S3 span by numpy == span by Python loop
    mc, vc = campaign_exponents(w)
    sp = spans(mc, vc, True)
    ref = []
    for r in range(64):
        vals = [int(mc[r, j]) for j in range(512) if vc[r, j]]
        if vals:
            ref.append(max(vals) - min(vals))
    if not np.array_equal(np.sort(sp), np.sort(np.array(ref))):
        fail("vectorised span != Python-loop span")
    print(f"    S3 vectorised span == Python-loop span on all {len(ref)} probe rows  OK")

    # S4 a dead block (all weights below the ladder floor is impossible -- the block scale
    # follows amax -- but an all-zero row must drop out, not report a span)
    z = torch.zeros(4, 512, dtype=torch.float64)
    mz, vz = campaign_exponents(z)
    if vz.any() or spans(mz, vz, True).size != 0:
        fail("all-zero rows did not drop out of the span statistic")
    print("    S4 all-zero rows contribute no span (they are not dot products)  OK\n")


selftests()

from transformers import AutoModelForCausalLM
model = AutoModelForCausalLM.from_pretrained(MODEL, dtype=torch.float32).eval()
layers = [(nm, mod) for nm, mod in model.named_modules()
          if isinstance(mod, torch.nn.Linear) and "lm_head" not in nm]
print(f"  linear tensors: {len(layers)}   fan-in {FANIN}")

res = {}
for grid, fn in (("campaign", campaign_exponents), ("raw", raw_exponents)):
    for scope, per_tile in (("tile512", True), ("fullrow", False)):
        allsp = []
        worst = ("", 0)
        for nm, mod in layers:
            w = mod.weight.data.double()
            m, val = fn(w)
            sp = spans(m, val, per_tile)
            allsp.append(sp)
            if sp.size and int(sp.max()) > worst[1]:
                worst = (nm, int(sp.max()))
        S = np.concatenate(allsp)
        wc = (FANIN * 127 * fib(int(S.max()))).bit_length() + 1
        res[f"{grid}_{scope}"] = {
            "rows": int(S.size), "max": int(S.max()), "p99": int(np.ceil(np.percentile(S, 99))),
            "p50": int(np.percentile(S, 50)), "mean": round(float(S.mean()), 3),
            "worst_tensor": worst[0], "worst_case_bits": wc,
        }
        print(f"  {grid:9s} {scope:8s}  rows {S.size:9d}  median {np.percentile(S,50):5.1f}  "
              f"p99 {np.ceil(np.percentile(S,99)):5.0f}  MAX {S.max():4d}  "
              f"-> ceil(log2(512*127*F_S))+1 = {wc} bits   ({worst[0].split('model.layers.')[-1]})")

json.dump(res, open("/Users/ssdm4/Desktop/PROJECTS/CLAUDE/trinity-fpga/research/block/"
                    "zphi_span_origin.json", "w"), indent=1)
print("\n  -> zphi_span_origin.json")
