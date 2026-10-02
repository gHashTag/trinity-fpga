#!/usr/bin/env python3
"""Testable fix for GPTQ's max-exactness destruction, proposed but not run in
THEOREM_2026-08-09.md (line 2326): "quantise each group's maximal column first, before
compensation can perturb it ... [this] restores the property; whether that restores GPTQ's
advantage is the experiment."

MECHANISM (established in THEOREM_2026-08-09.md, lines 2294-2313): block-max scaling sets
s = a/t_max, a = block maximum, so the maximal element always maps exactly onto the top codebook
level. GPTQ's sequential error propagation perturbs later columns with the residual from earlier
ones; if the column holding a row's group-maximum is not first in processing order, it absorbs
compensation before its own turn and no longer sits exactly on the scale that was fixed from its
(now stale) original value. Measured: 95.0% of blocks lose max-exactness under GPTQ, 0.0% under
RTN.

IMPLEMENTATION NOTE: "process the maximal column first" cannot be a single column reordering,
because GPTQ processes one column index at a time for the WHOLE weight matrix (all d_out rows
share a column index and a single global Hinv ordering), while each ROW has its own per-group
argmax column -- these differ row to row. A literal per-row reorder would need a separate
Cholesky factorisation (and Hinv permutation) per output row, at O(d_out) times the cost.

This script instead implements the mathematically EQUIVALENT and much cheaper operation: since a
column that is quantised exactly contributes ZERO error to the columns after it
(err = (col - q)/Hinv[i,i], and col == q exactly at the max), "process the max column first" and
"protect the max column's original value from incoming compensation until its own turn" produce
IDENTICAL results. So: for every (row, group), precompute the group-local argmax column from the
UNPERTURBED entering weights (same value that defines the group's scale s), and zero out any
compensation update that would land on that (row, column) pair for as long as its own turn has
not yet come within the group. When its turn arrives, the value is untouched since group start,
therefore col/s = +-1 exactly, therefore it quantises to the pinned +-1.0 codebook level exactly,
therefore its own propagated error is exactly zero -- consistent by construction.

Runs, in order:
  1. sanity re-run of RTN 4-bit and GPTQ-original 4-bit, to confirm this environment reproduces
     THEOREM_2026-08-09.md's numbers (17.3662 / 17.7846) before trusting any new number from it.
  2. max-exactness diagnostic (blocks whose row-max is not exact) for GPTQ-original AND
     GPTQ-fixed, to confirm the mechanism is actually restored, not just that perplexity moved.
  3. GPTQ-fixed 4-bit perplexity vs the RTN 4-bit gate (17.3662): does the fix clear the bar GPTQ
     itself failed to clear?
"""
import os
import re
import sys

import numpy as np
import torch

W = "/home/user/workspace/weights"
MODEL = os.path.join(W, "smollm2")
K, SEQLEN, NBIN = 32, 2048, 800
NCAL = 4
torch.set_grad_enabled(False)


def layer_index(nm):
    m = re.search(r"layers?\.(\d+)\.", nm)
    return int(m.group(1)) if m else -1


def dp_pinned(dens, nlev):
    """Copied verbatim from bitwidth_scaling.py -- inlined so importing this script does not
    trigger bitwidth_scaling.py's own module-level model load (which hardcodes a different,
    now-nonexistent weights path and would crash on import)."""
    pins = {0: -1.0, nlev - 1: 1.0, nlev // 2 - 1: 0.0}
    y = np.linspace(-1, 1, NBIN, endpoint=False) + 1.0 / NBIN
    w = dens * (2.0 / NBIN)
    S0 = np.concatenate([[0.0], np.cumsum(w)])
    S1 = np.concatenate([[0.0], np.cumsum(w * y)])
    S2 = np.concatenate([[0.0], np.cumsum(w * y * y)])

    def cost(a, b, k):
        s0, s1, s2 = S0[b] - S0[a], S1[b] - S1[a], S2[b] - S2[a]
        if k in pins:
            r = pins[k]
            return s2 - 2 * r * s1 + r * r * s0
        return np.where(s0 > 0, s2 - s1 * s1 / np.maximum(s0, 1e-300), 0.0)

    M = NBIN
    f = np.full((nlev, M + 1), np.inf)
    bk = np.zeros((nlev, M + 1), dtype=int)
    f[0] = cost(0, np.arange(M + 1), 0)
    for k in range(1, nlev):
        prev = f[k - 1]
        for i in range(1, M + 1):
            j = np.arange(0, i)
            c = prev[j] + cost(j, i, k)
            t = int(np.argmin(c))
            f[k][i], bk[k][i] = c[t], t
    bounds, cur = [M], M
    for k in range(nlev - 1, 0, -1):
        cur = bk[k][cur]
        bounds.append(cur)
    bounds = sorted(set(bounds + [0]))
    while len(bounds) < nlev + 1:
        bounds.append(M)
    bounds = sorted(bounds)
    lv = []
    for k in range(nlev):
        a, b = bounds[k], bounds[k + 1]
        if k in pins:
            lv.append(pins[k])
        else:
            s0 = S0[b] - S0[a]
            lv.append((S1[b] - S1[a]) / s0 if s0 > 0 else 0.0)
    return np.array(lv)


def rtn_layer(w, lv):
    n = (w.shape[1] // K) * K
    if n == 0:
        return w
    out = w.clone()
    g = w[:, :n].reshape(-1, K)
    s = g.abs().amax(1).clamp(min=1e-30)
    idx = torch.bucketize(g / s[:, None], (lv[:-1] + lv[1:]) / 2).clamp(0, len(lv) - 1)
    out[:, :n] = (lv[idx] * s[:, None]).reshape(w.shape[0], n)
    return out


def gptq_layer_original(w, H, lv, damp_frac=0.01):
    """Unmodified GPTQ, copied verbatim from gptq_baseline.py, for side-by-side comparison."""
    w = w.double().clone()
    d_in = w.shape[1]
    H = H.double().clone()
    dead = torch.diag(H) == 0
    H[dead, dead] = 1.0
    w[:, dead] = 0.0
    damp = damp_frac * torch.mean(torch.diag(H))
    H += torch.eye(d_in, dtype=H.dtype) * damp
    try:
        L = torch.linalg.cholesky(H)
        Hi = torch.cholesky_inverse(L)
        Hinv = torch.linalg.cholesky(Hi, upper=True)
    except Exception:
        return rtn_layer(w, lv)
    Q = torch.zeros_like(w)
    for g0 in range(0, d_in - d_in % K, K):
        g1 = g0 + K
        s = w[:, g0:g1].abs().amax(dim=1).clamp(min=1e-30)
        for i in range(g0, g1):
            col = w[:, i]
            idx = torch.bucketize(col / s, (lv[:-1] + lv[1:]) / 2).clamp(0, len(lv) - 1)
            q = lv[idx] * s
            Q[:, i] = q
            d = Hinv[i, i]
            err = (col - q) / d
            if i + 1 < d_in:
                w[:, i + 1:] -= err[:, None] * Hinv[i, i + 1:][None, :]
    tail = d_in - d_in % K
    if tail < d_in:
        Q[:, tail:] = w[:, tail:]
    return Q


def gptq_layer_maxexact(w, H, lv, damp_frac=0.01):
    """GPTQ with the group's per-row maximal element protected from compensation until its own
    turn. See module docstring for why this is equivalent to processing it first."""
    w = w.double().clone()
    w0 = w.clone()                                    # entering values, defines s AND cstar
    d_in = w.shape[1]
    d_out = w.shape[0]
    H = H.double().clone()
    dead = torch.diag(H) == 0
    H[dead, dead] = 1.0
    w[:, dead] = 0.0
    w0[:, dead] = 0.0
    damp = damp_frac * torch.mean(torch.diag(H))
    H += torch.eye(d_in, dtype=H.dtype) * damp
    try:
        L = torch.linalg.cholesky(H)
        Hi = torch.cholesky_inverse(L)
        Hinv = torch.linalg.cholesky(Hi, upper=True)
    except Exception:
        return rtn_layer(w, lv)
    Q = torch.zeros_like(w)
    for g0 in range(0, d_in - d_in % K, K):
        g1 = g0 + K
        group0 = w0[:, g0:g1]
        s = group0.abs().amax(dim=1).clamp(min=1e-30)
        cstar = g0 + group0.abs().argmax(dim=1)        # [d_out] protected column, this group
        for i in range(g0, g1):
            col = w[:, i]
            idx = torch.bucketize(col / s, (lv[:-1] + lv[1:]) / 2).clamp(0, len(lv) - 1)
            q = lv[idx] * s
            Q[:, i] = q
            d = Hinv[i, i]
            err = (col - q) / d
            if i + 1 < d_in:
                delta = err[:, None] * Hinv[i, i + 1:][None, :]
                future = torch.arange(i + 1, d_in)
                in_group = future < g1
                hit = (future[None, :] == cstar[:, None]) & in_group[None, :]
                delta = delta.masked_fill(hit, 0.0)     # protect the not-yet-quantised max
                w[:, i + 1:] -= delta
    tail = d_in - d_in % K
    if tail < d_in:
        Q[:, tail:] = w[:, tail:]
    return Q


def max_exactness(w_orig, w_quant, k=K):
    """Fraction of (row, group) blocks whose maximum-magnitude element is not exactly
    reproduced, and the summed squared error on those maxima. Same methodology as
    THEOREM_2026-08-09.md lines 2305-2310."""
    n = (w_orig.shape[1] // k) * k
    if n == 0:
        return 0, 0, 0.0
    a = w_orig[:, :n].reshape(-1, k)
    b = w_quant[:, :n].reshape(-1, k)
    idx = a.abs().argmax(dim=1)
    rows = torch.arange(a.shape[0])
    amax_orig = a[rows, idx]
    amax_quant = b[rows, idx]
    not_exact = (amax_orig != amax_quant)
    sq_err = ((amax_orig - amax_quant) ** 2).sum().item()
    return int(not_exact.sum().item()), a.shape[0], sq_err


from transformers import AutoModelForCausalLM, AutoTokenizer
import pyarrow.parquet as pq

tok = AutoTokenizer.from_pretrained(MODEL)
model = AutoModelForCausalLM.from_pretrained(MODEL, dtype=torch.float32).eval()
text = "\n\n".join(pq.read_table(os.path.join(W, "wikitext2-test.parquet"))
                    .column("text").to_pylist())
ids = tok(text, return_tensors="pt").input_ids[0]
n_tok = (ids.numel() // SEQLEN) * SEQLEN
WINS = ids[:n_tok].view(-1, SEQLEN)
CAL = WINS[18:18 + NCAL]
LO, HI = 6, 18

lins = [(n, m) for n, m in model.named_modules()
        if isinstance(m, torch.nn.Linear) and "lm_head" not in n]
BASE = {n: m.weight.detach().clone() for n, m in lins}
NL = max(layer_index(n) for n, _ in lins) + 1

hist = np.zeros(NBIN)
for n, m in lins:
    w = BASE[n].double()
    nn_ = (w.shape[1] // K) * K
    if nn_ == 0:
        continue
    b = w[:, :nn_].reshape(-1, K)
    a = b.abs().amax(1)
    ok = a > 0
    hist += np.histogram((b[ok] / a[ok][:, None]).reshape(-1).numpy(),
                          bins=NBIN, range=(-1, 1))[0]
dens = hist / (hist.sum() * (2.0 / NBIN))
CB = {b: torch.tensor(dp_pinned(dens, 1 << b), dtype=torch.float64) for b in (4,)}


def ppl():
    x = WINS[LO:HI]
    return float(np.exp(sum(model(x[i:i + 1], labels=x[i:i + 1]).loss.double().item()
                             for i in range(x.shape[0])) / x.shape[0]))


def restore():
    for n, m in lins:
        m.weight.copy_(BASE[n])


def apply_rtn(bits):
    for n, m in lins:
        m.weight.copy_(rtn_layer(BASE[n].double(), CB[bits[layer_index(n)]]).to(m.weight.dtype))


def apply_gptq(bits, layer_fn):
    restore()
    for bi in range(NL):
        names = [n for n, _ in lins if layer_index(n) == bi]
        Hs, cnt, hooks = {}, {}, []

        def mk(nm):
            def h(mod, inp, out):
                x = inp[0].detach().double().reshape(-1, inp[0].shape[-1])
                Hs[nm] = Hs.get(nm, 0) + 2.0 * (x.T @ x)
                cnt[nm] = cnt.get(nm, 0) + x.shape[0]
            return h

        for n, m in lins:
            if n in names:
                hooks.append(m.register_forward_hook(mk(n)))
        for i in range(CAL.shape[0]):
            model(CAL[i:i + 1])
        for h in hooks:
            h.remove()
        for n, m in lins:
            if n in names and n in Hs:
                q = layer_fn(BASE[n], Hs[n] / max(cnt[n], 1), CB[bits[bi]])
                m.weight.copy_(q.to(m.weight.dtype))


p0 = ppl()
U4 = np.full(NL, 4)

print(f"RULER CHECK -- fp32 baseline {p0:.4f} (windows {LO}-{HI - 1}, calib 18-{18 + NCAL - 1})")
if not (5.0 < p0 < 60.0):
    sys.exit("baseline implausible")

# --- Step 1: reproduce THEOREM_2026-08-09.md's known numbers before trusting anything new ---
apply_rtn(U4)
rtn4 = ppl()
rtn4_weights = {n: m.weight.detach().clone().double() for n, m in lins}
restore()

apply_gptq(U4, gptq_layer_original)
gptq_orig4 = ppl()
gptq_orig_weights = {n: m.weight.detach().clone().double() for n, m in lins}
restore()

print(f"\n  RTN  uniform 4-bit          {rtn4:>10.4f}  {rtn4 - p0:>+8.4f}   "
      f"(THEOREM_2026-08-09.md: 17.3662 / +2.6386)")
print(f"  GPTQ uniform 4-bit (orig)   {gptq_orig4:>10.4f}  {gptq_orig4 - p0:>+8.4f}   "
      f"(THEOREM_2026-08-09.md: 17.7846 / +3.0570)")
repro_ok = abs(rtn4 - 17.3662) < 0.02 and abs(gptq_orig4 - 17.7846) < 0.02
print(f"  reproduction of both known numbers within 0.02: {'PASS' if repro_ok else 'FAIL'}")

# --- Step 2: max-exactness diagnostic, GPTQ-original vs GPTQ-fixed ---
not_exact_total, blocks_total, sq_err_total = 0, 0, 0.0
for n, m in lins:
    ne, nb, se = max_exactness(BASE[n].double(), gptq_orig_weights[n])
    not_exact_total += ne
    blocks_total += nb
    sq_err_total += se
print(f"\n  GPTQ-original max-exactness: {not_exact_total}/{blocks_total} blocks NOT exact "
      f"({100 * not_exact_total / blocks_total:.1f}%), summed sq. error on maxima "
      f"{sq_err_total:.3e}   (THEOREM_2026-08-09.md: 157632/165888 = 95.0%)")

apply_gptq(U4, gptq_layer_maxexact)
gptq_fix4 = ppl()
gptq_fix_weights = {n: m.weight.detach().clone().double() for n, m in lins}
restore()

not_exact_fix, blocks_fix, sq_err_fix = 0, 0, 0.0
for n, m in lins:
    ne, nb, se = max_exactness(BASE[n].double(), gptq_fix_weights[n])
    not_exact_fix += ne
    blocks_fix += nb
    sq_err_fix += se
print(f"  GPTQ-fixed    max-exactness: {not_exact_fix}/{blocks_fix} blocks NOT exact "
      f"({100 * not_exact_fix / blocks_fix:.1f}%), summed sq. error on maxima "
      f"{sq_err_fix:.3e}")

# --- Step 3: does the fix clear the RTN 4-bit gate? ---
print(f"\n  GPTQ-fixed uniform 4-bit    {gptq_fix4:>10.4f}  {gptq_fix4 - p0:>+8.4f}")
print(f"  vs RTN 4-bit ({rtn4:.4f}):  {gptq_fix4 - rtn4:>+8.4f}   "
      f"gate: {'PASS (beats RTN)' if gptq_fix4 < rtn4 else 'FAIL (still worse than RTN)'}")
print(f"  vs GPTQ-original ({gptq_orig4:.4f}): {gptq_fix4 - gptq_orig4:>+8.4f}   "
      f"{'improved' if gptq_fix4 < gptq_orig4 else 'did not improve'}")
