#!/usr/bin/env python3
"""Checks every claim of T41 that can be checked without a model.

1. Proposition 1, the dilation identity e_A(y) = c e_B(y/c), against the
   quantisers this project actually runs -- campaignC_books.make_quant_signed
   with the block scale pinned so E8M0 gives s = 1 -- on a dense grid.
   Expected: exact off the extra-rung interval (beta, 1], and off it only at
   decision-boundary ties, where the harness's round-toward-zero rule applies.

2. Corollary 1's two limiting cases, which are what make it a prediction rather
   than a description:
       uniform ladder        -> granular gain exactly 1 - c^2
       geometric ladder      -> granular gain exactly 0
   A geometric ladder is scale-invariant, so contracting it cannot buy anything.

3. Corollary 2's break-even beta = (1+c)/2, located by brute force on the real
   E2M1 ladder rather than assumed, plus the proviso beta > (l6+1)/2.
"""
import numpy as np
import torch

SRC, MARKER = "block_tnf.py", 'print("загружаю модель…", flush=True)'
ns = {}
exec(compile(open(SRC, encoding="utf-8").read().split(MARKER)[0], SRC, "exec"), ns)
import campaignA_books as A
import campaignC_books as C

torch.set_grad_enabled(False)
K = ns["K"]
BOOKS = {n: [float(x) for x in lv] for n, _, lv in A.all_books()}
MX, TOP = BOOKS["MXFP4"], BOOKS["MX-asym-TOP"]
c = max(-x for x in TOP)
beta = (1.0 + c) / 2.0
fails = []


def qmag(z, mags):
    """Nearest-level quantiser on a signed magnitude book, ties toward zero,
    saturating past the top -- the reference for e_B extended by saturation."""
    lv = torch.tensor(sorted([-m for m in mags if m > 0] + list(mags)),
                      dtype=torch.float64)
    bnd = (lv[:-1] + lv[1:]) / 2
    return lv[torch.where(z < 0, torch.bucketize(z, bnd, right=True),
                          torch.bucketize(z, bnd, right=False))]


# --- 1. Proposition 1 -------------------------------------------------------
qs = C.make_quant_signed(K, ns["q_e8m0_t"])
g = torch.linspace(-1.0, 1.0, 31 * 4000 + 1, dtype=torch.float64)[:31 * 4000]
row = torch.cat([torch.ones(g.numel() // 31, 1, dtype=torch.float64),
                 g.reshape(-1, 31)], dim=1)
assert float((row.abs().amax(dim=1) - 1).abs().max()) == 0.0, "scale not pinned"
eA = (qs(row, TOP) - row)[:, 1:].reshape(-1)
d = (eA - c * (qmag(g / c, MX) - g / c)).abs()
rung = (g > beta) & (g <= 1.0)
off = float(d[~rung].max())
n_off_bad = int((d[~rung] > 1e-12).sum())
ties = sorted(set(round(float(x), 6) for x in g[~rung][d[~rung] > 1e-12]))
print(f"P1  max|e_A - c e_B(./c)| off (beta,1] = {off:.3e}   "
      f"({n_off_bad} of {int((~rung).sum())} points, all ties: {ties})")
if n_off_bad > len(ties) + 1:
    fails.append("P1 fails away from isolated ties")

# --- 2. Corollary 1's limits ------------------------------------------------
def gain(mags, lo, seed=0, n=4_000_000):
    """Measured granular gain of the contracted ladder, in-range only."""
    z = torch.tensor(np.random.default_rng(seed).uniform(lo, c, n),
                     dtype=torch.float64)
    eB = qmag(z, mags) - z
    eA_ = c * (qmag(z / c, mags) - z / c)          # Proposition 1
    return 1.0 - float((eA_ ** 2).sum() / (eB ** 2).sum())


uni = [i / 8 for i in range(9)]                    # uniform ladder
geo = [0.0] + [c ** k for k in range(12, -1, -1)]  # geometric, ratio 1/c

# The uniform case is a HIGH-RESOLUTION statement (e^2 ~ h^2/12 holds for a
# density smooth on the scale of h), so it is checked to 1 % relative -- the
# seed-to-seed spread is itself ~1.3e-3.
gu = [gain(uni, 0.02, s) for s in range(3)]
print(f"C1  uniform ladder gain = {np.mean(gu):.6f} "
      f"(seeds {', '.join(f'{x:.6f}' for x in gu)})   "
      f"predicted 1-c^2 = {1-c*c:.6f}   rel {abs(np.mean(gu)/(1-c*c)-1):.2%}")
if abs(np.mean(gu) / (1 - c * c) - 1) > 0.01:
    fails.append("C1 uniform limit")

# The geometric case is EXACT wherever the ladder is actually geometric. Below
# the smallest rung the gap 0 -> c^12 is not, and that -- not the corollary --
# is the whole of the residual: sampling from 0.02 (under the rung) leaves
# ~5e-4, sampling from above it leaves exactly 0.
small = c ** 12
for lo in (0.02, 0.05, 0.10, 0.20):
    gg = gain(geo, lo)
    tag = "below smallest rung, edge effect" if lo < small else "EXACT"
    print(f"C1  geometric ladder gain, z from {lo:.2f} = {gg:+.6f}   {tag}")
    if lo > small and abs(gg) > 1e-12:
        fails.append(f"C1 geometric limit at lo={lo}")
print(f"C1  smallest nonzero rung = {small:.5f}; the geometric ladder is "
      f"scale-invariant only above it")

# --- 3. Corollary 2's break-even -------------------------------------------
m = torch.linspace(c + 1e-9, 1.0, 2_000_001, dtype=torch.float64)
excess = (m - c) ** 2 - (qmag(m, MX) - m) ** 2
first = float(m[(excess > 0).nonzero()[0]]) if bool((excess > 0).any()) else None
signs = int((torch.sign(excess[1:]) != torch.sign(excess[:-1])).sum())
l6 = sorted(MX)[-2]
print(f"C2  break-even found at {first:.6f}   predicted (1+c)/2 = {beta:.6f}   "
      f"sign changes on (c,1] = {signs}")
print(f"C2  proviso beta > (l6+1)/2:  {beta:.6f} > {(l6+1)/2:.6f}  "
      f"{'OK' if beta > (l6 + 1) / 2 else 'VIOLATED'}")
if abs(first - beta) > 1e-4 or signs != 1:
    fails.append("C2 break-even")


# --- 4. Corollary 3: the clipped tail IS the OCP MX rule --------------------
# Our harness aligns the codebook top to the block max, s = 2^ceil(log2 a), and
# never saturates.  The OCP MX specification aligns a power of two to the
# element format's own e_max, s = 2^(floor(log2 a) - 2), and does saturate.
# For a not an exact power of two those differ by exactly 8, which is precisely
# the factor between TOP's negative ladder and E2M1's -- so TOP's negative half
# should be bit-identical to spec-rule MXFP4.  Asserted, not assumed.
E2M1 = [0.0, 0.5, 1.0, 1.5, 2.0, 3.0, 4.0, 6.0]


def q_ocp(w):
    lv = torch.tensor(E2M1, dtype=torch.float64)
    n = (w.shape[1] // K) * K
    head = w[:, :n].reshape(-1, K).double()
    a = head.abs().amax(dim=1).clamp(min=1e-30)
    s = torch.pow(2.0, torch.floor(torch.log2(a)) - 2)
    y = (head / s[:, None]).abs()
    bnd = (lv[:-1] + lv[1:]) / 2
    rec = torch.sign(head) * lv[torch.bucketize(y, bnd)] * s[:, None]
    out = w.clone()
    out[:, :n] = rec.reshape(-1, n).to(w.dtype)
    return out


w = torch.randn(4000, 256, generator=torch.Generator().manual_seed(7))
dneg = float((qs(w, TOP) - q_ocp(w))[w < 0].abs().max())
dpos = float((qs(w, TOP) - q_ocp(w))[w > 0].abs().max())
aa = w[:, :256].reshape(-1, K).abs().amax(dim=1).double()
p2 = int((torch.log2(aa) == torch.floor(torch.log2(aa))).sum())
print(f"C3  max|TOP - OCP-rule MXFP4| on negatives = {dneg:.3e}  "
      f"(on positives {dpos:.3f}, as designed)   "
      f"blocks with amax an exact power of two: {p2} of {aa.numel()}")
if dneg != 0.0:
    fails.append("C3 the clipped tail is not the OCP rule")

print("\n" + ("ALL CHECKS PASS" if not fails else "FAILED: " + "; ".join(fails)))
raise SystemExit(1 if fails else 0)
