#!/usr/bin/env python3
"""Closed form for the ESCAPE lever, replacing the empirical composition tables.

The composition work measured escape (store the block's largest element separately, scale the
rest by the SECOND largest) on a grid of block sizes and reported a table. The finite-N
formula makes that a theorem instead, because escape is exactly a change of ORDER STATISTIC.

DERIVATION.

Plain block scaling conditions on the first order statistic a_1 = max|x|:

    f_1(a) = K f(a) F(a)^(K-1)                            [K iid samples of |x|]

Escape removes the largest element from the block, so the scale is set by the second order
statistic, and the survivors are truncated to [-a_2, a_2]:

    f_2(a) = K(K-1) f(a) F(a)^(K-2) (1 - F(a))

    D_esc = INTEGRAL f_2(a) * (K-2)/K * E[ (s Q(x/s) - x)^2 | |x| <= a ] da  +  D_payload/K

where s = a/t_max as before and D_payload is the error on the escaped element itself. The
(K-2)/K prefactor is the accounting: one element is escaped, one is the new maximum and is
reproduced exactly, K-2 are ordinary.

WHY THIS SHOULD HELP: f_2 is stochastically smaller than f_1, so the scale is smaller, so
every surviving element gets a finer effective step. The whole benefit of escape is the gap
between the first and second order statistics -- which is large for heavy tails and small for
light ones. The theory therefore predicts escape pays MOST on heavy-tailed data, and that
prediction is testable.

BIT-FAIR CRITERION. Escape is not free: it costs log2(K) index bits plus b_esc payload bits,
amortised over K elements. The honest comparison is against simply SPENDING THOSE BITS ON
PRECISION. So we ask:

    does 4-bit + escape beat 4-bit plain by MORE than the same bit budget buys as
    extra mantissa?

measured against a 5-bit derived codebook, which costs a full 1.0 bit/element. Escape is
worth it only where its cost/benefit ratio beats that line. That is the criterion the
empirical tables never stated.
"""
import math
import random

from design_space import DISTS, lloyd, p_eff, q, sample

random.seed(20260811)


def d_theory(dist, K, levels, order=1):
    """Block-scaled distortion conditioning on the 1st or 2nd order statistic."""
    pdf, cdf_abs, a_hi = dist
    top = max(levels)
    na, nx = 700, 500
    da = a_hi / na
    total = 0.0
    for ia in range(1, na + 1):
        a = ia * da
        Fa = cdf_abs(a)
        if Fa <= 1e-14:
            continue
        f_abs = 2 * pdf(a)
        if order == 1:
            f_a = K * f_abs * (Fa ** (K - 1))
            share = (K - 1) / K
        else:
            f_a = K * (K - 1) * f_abs * (Fa ** (K - 2)) * (1 - Fa)
            share = (K - 2) / K
        if f_a <= 0:
            continue
        s = a / top
        acc = 0.0
        dx = 2 * a / nx
        for ix in range(nx):
            x = -a + (ix + 0.5) * dx
            acc += (s * q(x / s, levels) - x) ** 2 * pdf(x) * dx
        total += share * (acc / Fa) * f_a * da
    return total


def measured(data, K, levels, escape):
    top = max(levels)
    tot, nb = 0.0, 0
    for i in range(0, len(data) - K, K):
        blk = list(data[i:i + K])
        err = 0.0
        if escape:
            j = max(range(K), key=lambda t: abs(blk[t]))
            esc = blk.pop(j)
            err += 0.0                       # escaped element stored at high precision
        amax = max((abs(v) for v in blk), default=0.0)
        if amax == 0:
            nb += 1
            continue
        s = amax / top
        err += sum((s * q(v / s, lv0) - v) ** 2 for v, lv0 in ((v, levels) for v in blk))
        tot += err / K
        nb += 1
    return tot / nb


DATA = {d: sample(d, 300000) for d in DISTS}

print("Escape as a theorem: order statistics, and whether the bits are better spent elsewhere\n")
print("  D4      4-bit derived codebook, plain block scaling")
print("  D4+esc  same codebook, scale set by the 2nd order statistic, top element escaped")
print("  D5      5-bit derived codebook, plain -- the 'just add a bit' alternative\n")

for K in (16, 32, 64, 128):
    print(f"  K = {K}")
    ovh = (math.log2(K) + 16) / K          # index bits + a 16-bit escaped payload, amortised
    for dname, dist in DISTS.items():
        lv4 = lloyd(*p_eff(dist, K), nlev=8)
        lv5 = lloyd(*p_eff(dist, K), nlev=16)
        t4 = d_theory(dist, K, lv4, order=1)
        te = d_theory(dist, K, lv4, order=2)
        m4 = measured(DATA[dname], K, lv4, escape=False)
        me = measured(DATA[dname], K, lv4, escape=True)
        m5 = measured(DATA[dname], K, lv5, escape=False)
        # gain per bit spent, for each way of spending bits
        g_esc = (1 - me / m4) / ovh
        g_bit = (1 - m5 / m4) / 1.0
        verdict = "ESCAPE WINS" if g_esc > g_bit else "spend on precision"
        print(f"    {dname:<12} theory 1st/2nd {t4:.5f}/{te:.5f}   "
              f"measured esc {me/m4:.3f}, 5-bit {m5/m4:.3f}  "
              f"| per bit: esc {g_esc:.3f} vs prec {g_bit:.3f}  -> {verdict}")
    print(f"    escape overhead at K={K}: {ovh:.4f} bits/element\n")

print("  Prediction under test: escape pays most on heavy tails (t3 > laplace > gaussian),")
print("  because its whole benefit is the gap between the 1st and 2nd order statistics.")
