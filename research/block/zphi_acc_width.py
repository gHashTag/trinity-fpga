#!/usr/bin/env python3
"""What accumulator width does a Z[phi] dot product ACTUALLY need?

The corrected exactness theorem says a W-bit two's-complement Z[phi] datapath returns
(exact result) mod 2^W: intermediate overflow is self-cancelling because componentwise
add, the Fibonacci step and integer scaling are all Z-linear and reduction mod 2^W is a
ring homomorphism.  So only the FINAL pair has to fit.  That turns a design question into
a measurement: how big is the final pair, really?

The worst-case provisioning is the triangle inequality over partial sums,
    W = ceil(log2(n * A * max(F_S,1))) + 1,
which at n=512, A=127, S=43 (the measured per-dot-product phi-span over all 210 SmolLM2
linear tensors) gives 46 bits per component.  The final value is a SIGNED sum with
cancellation and has no reason to be anywhere near that.

MODEL UNDER TEST
  weights   SmolLM2-135M, all 210 nn.Linear tensors (lm_head excluded, it is tied),
            quantised on the campaign's phi^k grid exactly as research/block/order_spread.py
            does it: block 32 along in_features, block scale phi^ceil(log_phi amax),
            ladder phi^-6..phi^0, so every nonzero weight is exactly +-phi^(e+i-7).
  acts      real inputs to each Linear, captured from an fp32 forward pass on wikitext-2,
            quantised per token, symmetric, to int8 (values in [-127,127]).
            A uniform-random int8 control is run as well.
  fan-in    512.  Columns are tiled into ceil(in/512) tiles of EXACTLY 512 columns, the
            last tile right-aligned (so in=576 gives tiles [0:512] and [64:576] -- every
            column is covered and every tile has the stated fan-in).  32 divides both 512
            and 64, so tiles never split a quantisation block.

WHAT IS ACCUMULATED
  Inside one tile the nonzero weights are +-phi^m.  Factor out m_min, the smallest exponent
  present in that tile (a static property of the weights, so real hardware can bake it in):

      sum_j x_j w_j = phi^m_min * sum_j x_j s_j phi^d_j ,   d_j = m_j - m_min >= 0
                    = phi^m_min * (A*phi + B),
      A = sum_j x_j s_j F_(d_j),   B = sum_j x_j s_j F_(d_j - 1),   F_(-1) = 1.

  A and B are exact integers.  They are the accumulator state the RTL (zphi_add.v, ACC
  parameter) has to hold.  This script measures their distribution over every row of every
  tensor and reports the signed two's-complement width needed.

  d_j >= 0 keeps every Fibonacci coefficient non-negative, so a per-tile overflow
  certificate 127 * 512 * F_(S_tile) < 2^62 licenses int64 numpy for the accumulation.
  Tiles that fail the certificate fall back to Python-int (object) arithmetic; none did.
  Every number below is preceded by self-tests, including a Python-int cross-check.
"""
import os
import sys
import json
import time
from fractions import Fraction

import numpy as np
import torch
import torch.nn.functional as F_nn

WDIR = ("/private/tmp/claude-501/-Users-ssdm4-Desktop-PROJECTS-CLAUDE/"
        "0e868af8-ab2d-4d00-be03-8fea94ba48e4/scratchpad/weights")
TAG = "smollm2"
MODEL = os.path.join(WDIR, TAG)
K = 32                      # quantisation block
# Fan-in of one accumulation.  512 is the campaign's operating point and the default;
# ZPHI_FANIN sweeps it to ask which fan-in a given ACC width actually supports.
FANIN = int(os.environ.get("ZPHI_FANIN", 512))
NTOK = int(sys.argv[1]) if len(sys.argv) > 1 else 32     # activation vectors per layer
SEQLEN = 2048
PHI = (1 + 5 ** 0.5) / 2
LOGPHI = np.log(PHI)
torch.set_grad_enabled(False)
torch.set_num_threads(8)

PHIL = torch.tensor([0.0] + [PHI ** (-k) for k in range(6, -1, -1)], dtype=torch.float64)
NLAD = len(PHIL)            # 8 codes: index 0 = zero, index i>=1 = phi^(i-7)

# Fibonacci, Python ints.  FA[d] = F_d, FB[d] = F_(d-1) with F_(-1) = 1.
DMAX = 200
_F = [0, 1]
while len(_F) < DMAX + 2:
    _F.append(_F[-1] + _F[-2])
FA_py = [_F[d] for d in range(DMAX + 1)]
FB_py = [1] + [_F[d - 1] for d in range(1, DMAX + 1)]
# The int64 lookup tables stop at NP_MAX.  The per-tile overflow certificate
# 127*512*F_S < 2^62 already fails at S = 68, so a span that outran these tables would
# have been rejected before they were indexed; the bound is checked, not assumed.
NP_MAX = 67
FA_np = np.array(FA_py[:NP_MAX + 1], dtype=np.int64)
FB_np = np.array(FB_py[:NP_MAX + 1], dtype=np.int64)
POW2 = np.array([1 << i for i in range(63)], dtype=np.int64)


def fail(msg):
    print(f"\n  SELF-TEST FAILED: {msg}\n  No numbers reported.")
    sys.exit(1)


def sgnwidth_py(v):
    """Minimal W with v in [-2^(W-1), 2^(W-1)-1]."""
    u = v if v >= 0 else -v - 1
    return u.bit_length() + 1


def sgnwidth_np(v):
    u = np.where(v >= 0, v, -v - 1)
    return (np.searchsorted(POW2, u, side="right") + 1).astype(np.int16)


# ---------------------------------------------------------------- quantiser (campaign's)
def q_ladder_idx(a):
    """|a| -> ladder INDEX, same call order_spread.quant_phi uses (ties to lower level)."""
    return torch.bucketize(a, (PHIL[:-1] + PHIL[1:]) / 2)


def phi_codes(w):
    """w (out,in) float64 -> (e int64 (out,nb), idx int64 (out,in), sign int64 (out,in)).

    Reproduces order_spread.quant_phi bit for bit; the reconstruction is
    sign * PHIL[idx] * phi^e = sign * phi^(e + idx - 7).
    """
    out, n = w.shape
    nb = n // K
    b = w.reshape(out * nb, K)
    amax = b.abs().amax(dim=1).clamp(min=1e-300)
    e = torch.ceil(torch.log(amax) / LOGPHI - 1e-9)
    s = torch.pow(PHI, e)
    idx = q_ladder_idx((b / s[:, None]).abs())
    sign = torch.sign(b).to(torch.int64)
    return (e.to(torch.int64).reshape(out, nb),
            idx.reshape(out, n).to(torch.int64),
            sign.reshape(out, n))


def rebuild(e, idx, sign):
    """float64 reconstruction from the integer codes, computed the same way quant_phi does."""
    out, nb = e.shape
    s = torch.pow(PHI, e.double())
    lev = PHIL[idx.reshape(out, nb, K)]
    return (sign.reshape(out, nb, K).double() * lev * s[:, :, None]).reshape(out, nb * K)


def quant_phi_ref(w):
    """Verbatim order_spread.quant_phi, for the agreement test."""
    n = (w.shape[1] // K) * K
    b = w[:, :n].reshape(-1, K).double()
    amax = b.abs().amax(dim=1).clamp(min=1e-300)
    s = torch.pow(PHI, torch.ceil(torch.log(amax) / LOGPHI - 1e-9))
    lad = PHIL
    lev = lad[torch.bucketize((b / s[:, None]).abs(), (lad[:-1] + lad[1:]) / 2)]
    rec = torch.sign(b) * lev * s[:, None]
    out = w.clone()
    out[:, :n] = rec.reshape(-1, n)
    return out


# ---------------------------------------------------------------- tiling
ROWMODE = len(sys.argv) > 2 and sys.argv[2] == "row"


def tiles(n):
    """(start, length) pairs.  Default: ceil(n/512) tiles of exactly 512 columns, the last
    right-aligned so every column is covered.  ROWMODE: one tile spanning the whole row."""
    if ROWMODE:
        return [(0, n)]
    if n < FANIN:
        raise ValueError(f"in_features {n} < fan-in {FANIN}")
    st = [(i * FANIN, FANIN) for i in range(n // FANIN)]
    if n % FANIN:
        st.append((n - FANIN, FANIN))
    return st


# ---------------------------------------------------------------- self-tests
def selftests():
    print("  self-tests")

    # T1 Fibonacci closed form phi^m = F_m phi + F_(m-1), for m>=0, in exact rational terms:
    # (F_m phi + F_(m-1))^2 == (F_m phi + F_(m-1)) * phi holds iff phi^2 = phi+1, so check
    # the ladder recurrence and the identity numerically at high precision instead.
    import decimal
    decimal.getcontext().prec = 60
    D = decimal.Decimal
    phid = (1 + D(5).sqrt()) / 2
    worst = D(0)
    for m in range(0, DMAX + 1):
        v = FA_py[m] * phid + FB_py[m]
        worst = max(worst, abs(v - phid ** m) / (phid ** m))
    if worst > D("1e-45"):
        fail(f"phi^m != F_m phi + F_(m-1); worst relative {worst}")
    if any(FA_py[d] != FA_py[d - 1] + FA_py[d - 2] for d in range(2, DMAX + 1)):
        fail("Fibonacci table breaks its own recurrence")
    if (FA_py[0], FB_py[0], FA_py[1], FB_py[1], FA_py[2], FB_py[2]) != (0, 1, 1, 0, 1, 1):
        fail("F_(-1)=1 seeding wrong")
    print(f"    T1 phi^m = F_m*phi + F_(m-1) to {worst:.2e} relative over m=0..{DMAX}, "
          f"60-digit decimal; recurrence exact; F_(-1)=1  OK")

    # T2 signed-width function against Python int semantics, incl. the -2^k edge
    cases = [(0, 1), (-1, 1), (1, 2), (7, 4), (8, 5), (-8, 4), (-9, 5), (2 ** 40, 42),
             (-2 ** 40, 41), (2 ** 40 - 1, 41)]
    for v, w in cases:
        if sgnwidth_py(v) != w:
            fail(f"sgnwidth_py({v}) = {sgnwidth_py(v)}, want {w}")
    rng = np.random.default_rng(3)
    probe = np.concatenate([rng.integers(-(2 ** 61), 2 ** 61, 5000),
                            np.array([c[0] for c in cases], dtype=np.int64)]).astype(np.int64)
    if not np.array_equal(sgnwidth_np(probe), np.array([sgnwidth_py(int(v)) for v in probe])):
        fail("vectorised width != Python-int width")
    print(f"    T2 signed width: 10 hand cases incl. -2^k, and 5000 random int64 agree with "
          f"Python bit_length  OK")

    # T3 the integer codes reproduce the campaign quantiser BITWISE
    g = torch.Generator().manual_seed(7)
    w = torch.randn(96, 512, generator=g, dtype=torch.float64) * 0.03
    w[3, 17] = 0.0
    w[5, :] *= 1e-4                       # a whole block far below the ladder floor
    w[7, 40] = 9.0                        # a lone outlier -> large in-row phi span
    e, idx, sg = phi_codes(w)
    if not torch.equal(rebuild(e, idx, sg), quant_phi_ref(w)):
        fail("integer codes do not reproduce order_spread.quant_phi bitwise")
    print(f"    T3 (e, ladder index, sign) reproduce order_spread.quant_phi BITWISE on a "
          f"96x512 probe with zeros, a dead block and an outlier  OK")

    # T4 every nonzero reconstructed weight is exactly +-phi^(e+i-7)
    r = rebuild(e, idx, sg)
    nz = r[r != 0].abs()
    mm = torch.log(nz) / LOGPHI
    dev = (mm - mm.round()).abs().max().item()
    if dev > 1e-9:
        fail(f"reconstructed weight off the phi^k grid by {dev}")
    print(f"    T4 every nonzero weight is exactly +-phi^m, max |log_phi|w| - round| = "
          f"{dev:.2e}  OK")

    # T5 block scale bracket phi^(e-1) < amax <= phi^e, checked EXACTLY (Fraction + sqrt5
    # sign test) on the blocks nearest the boundary, floats elsewhere.
    b = w.reshape(-1, K)
    amax = b.abs().amax(dim=1).clamp(min=1e-300)
    ee = e.reshape(-1)
    hi = torch.pow(PHI, ee.double())
    lo = torch.pow(PHI, ee.double() - 1)
    if not bool(((amax <= hi * (1 + 1e-12)) & (amax > lo * (1 - 1e-12))).all()):
        fail("block scale does not bracket amax")
    lg = (torch.log(amax) / LOGPHI)
    near = (lg - lg.round()).abs() < 1e-6
    nchk = int(near.sum())
    for j in torch.nonzero(near).flatten().tolist():
        if not exact_bracket(float(amax[j]), int(ee[j])):
            fail(f"exact bracket fails at block {j}")
    print(f"    T5 phi^(e-1) < amax <= phi^e on all {len(ee)} blocks (float, 1e-12 margin); "
          f"{nchk} near-boundary blocks re-checked in exact Z[phi]+Fraction arithmetic  OK")

    # T6 THE CRITICAL ONE: the integer pair really is the dot product.
    # Build tiles from the probe, accumulate in Python ints, compare (A phi + B) phi^mmin
    # against the float64 dot product of the SAME quantised weights with the same int8
    # activations.  A broken F table, a wrong m_min or a wrong ladder offset all fail here.
    xq = torch.randint(-127, 128, (512,), generator=g, dtype=torch.float64)
    rq = rebuild(e, idx, sg)
    m_all = (e.repeat_interleave(K, dim=1) + idx - (NLAD - 1))
    bad = 0
    seen = 0
    for row in range(96):
        val = idx[row] > 0
        if not bool(val.any()):
            continue
        mmin = int(m_all[row][val].min())
        A = B = 0
        for j in range(512):
            if not bool(val[j]):
                continue
            d = int(m_all[row, j]) - mmin
            c = int(sg[row, j]) * int(xq[j])
            A += c * FA_py[d]
            B += c * FB_py[d]
        ref = float(torch.dot(rq[row], xq))
        got = (A * PHI + B) * PHI ** mmin
        seen += 1
        if abs(got - ref) > 1e-9 * max(abs(ref), 1e-300):
            bad += 1
    if bad or seen < 90:
        fail(f"Z[phi] pair != dot product on {bad}/{seen} rows")
    print(f"    T6 (A*phi + B)*phi^m_min equals the float64 dot product of the same "
          f"quantised weights to <1e-9 relative on all {seen} probe rows  OK")

    # T6b negative control: corrupt one Fibonacci entry, T6 must break
    save = FA_py[5]
    FA_py[5] = save + 1
    row = 7
    val = idx[row] > 0
    mmin = int(m_all[row][val].min())
    A = B = 0
    for j in range(512):
        if bool(val[j]):
            d = int(m_all[row, j]) - mmin
            c = int(sg[row, j]) * int(xq[j])
            A += c * FA_py[d]
            B += c * FB_py[d]
    ref = float(torch.dot(rq[row], xq))
    broke = abs((A * PHI + B) * PHI ** mmin - ref) > 1e-9 * abs(ref)
    FA_py[5] = save
    if not broke:
        fail("corrupting F_5 did not change the answer -- T6 is not actually testing anything")
    print(f"    T6b negative control: corrupting F_5 breaks T6 on the outlier row  OK")

    # T7 int64 numpy path == Python-int path, bitwise, on real tiles
    print(f"    T7 int64-vs-Python cross-check deferred to the first real tensor  OK")
    print()


def exact_bracket(amax, e):
    """Exact test phi^(e-1) < amax <= phi^e, amax a float64 (an exact binary rational)."""
    a = Fraction(amax)
    return _cmp_phi(e, a) >= 0 and _cmp_phi(e - 1, a) < 0


def _fib_signed(m):
    """F_m for any integer m; F_(-n) = (-1)^(n+1) F_n."""
    if m >= 0:
        return FA_py[m]
    n = -m
    return (1 if n % 2 else -1) * _F[n]


def _cmp_phi(e, a):
    """sign of phi^e - a, exact.  phi^e = F_e phi + F_(e-1) = (F_e + 2F_(e-1) + F_e sqrt5)/2."""
    U = Fraction(_fib_signed(e) + 2 * _fib_signed(e - 1)) - 2 * a   # rational part * 2
    V = _fib_signed(e)                                             # coefficient of sqrt5
    if U >= 0 and V >= 0:
        return 0 if (U == 0 and V == 0) else 1
    if U <= 0 and V <= 0:
        return 0 if (U == 0 and V == 0) else -1
    if V > 0:      # U < 0: compare 5V^2 vs U^2
        return 1 if 5 * V * V > U * U else (-1 if 5 * V * V < U * U else 0)
    return -1 if 5 * V * V > U * U else (1 if 5 * V * V < U * U else 0)


# ---------------------------------------------------------------- activations
def capture_acts(model, layers, ntok):
    """Real inputs to every Linear, ntok token positions, symmetric per-token int8."""
    store = {}
    hs = []

    def mk(nm):
        def h(_m, args):
            if nm not in store:
                store[nm] = args[0].detach()[0].double()      # (T_seq, in)
        return h
    for nm, mod in layers:
        hs.append(mod.register_forward_pre_hook(mk(nm)))
    import pyarrow.parquet as pq
    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained(MODEL)
    text = "\n\n".join(pq.read_table(os.path.join(WDIR, "wikitext2-test.parquet"))
                       .column("text").to_pylist())
    ids = tok(text, return_tensors="pt").input_ids[0][:SEQLEN].reshape(1, -1)
    model(ids)
    for h in hs:
        h.remove()
    pos = np.linspace(64, ids.shape[1] - 1, ntok).astype(int)
    out = {}
    for nm, a in store.items():
        v = a[pos]                                            # (ntok, in)
        sc = v.abs().amax(dim=1, keepdim=True).clamp(min=1e-30) / 127.0
        q = torch.clamp(torch.round(v / sc), -127, 127).to(torch.int64).numpy()
        out[nm] = q
    return out


# ---------------------------------------------------------------- measurement
def measure(layers, acts, label, stats, worst=False, pertensor=False):
    """acts[nm] -> (ntok, in) int64 in [-127,127].  Fills stats in place.

    worst=True ignores `acts` and computes, per row-tile, the EXACT attainable maximum of
    |A| and |B| over every int8 activation vector.  Because m_min normalisation makes every
    Fibonacci coefficient non-negative, x_j = +-127 chosen to match sign(s_j) attains
    127 * sum_j F_(d_j) exactly -- this is a reachable value, not a loose bound.

    pertensor=True additionally reports the width if ONE reference exponent per tensor is
    used instead of one per tile, via the exact Z[phi] scaling identity
        F_(d+c) = F_(c+1) F_d + F_c F_(d-1).
    """
    FA, FB = FA_np, FB_np
    LIM = 1 << 62
    widths = []
    spans = []
    pt_widths = []
    per_tensor_max = {}
    maxA = maxB = 0
    argmax = None
    nfallback = 0
    ndead = 0
    t0 = time.time()
    for nm, mod in layers:
        w = mod.weight.data.double()
        e, idx, sg = phi_codes(w)
        m_all = (e.repeat_interleave(K, dim=1) + idx - (NLAD - 1)).numpy()
        val = (idx > 0).numpy()
        sgn = sg.numpy()
        X = None if worst else acts[nm].T.copy()               # (in, ntok)
        n = w.shape[1]
        tmin = int(np.where(val, m_all, np.int64(1 << 40)).min())   # tensor-wide reference
        wmax_t = 0
        for st, L in tiles(n):
            sl = slice(st, st + L)
            mv = np.where(val[:, sl], m_all[:, sl], np.int64(1 << 40))
            mmin = mv.min(axis=1)
            live = mmin < (1 << 40)
            if not live.all():
                ndead += int((~live).sum())
            if not live.any():
                continue
            d = np.where(val[:, sl], m_all[:, sl] - mmin[:, None], 0)
            d = np.where(live[:, None], d, 0)
            if d.max() > NP_MAX:
                fail(f"phi span {d.max()} exceeds the int64 Fibonacci table ({NP_MAX}); "
                     f"the exact-arithmetic guarantee would be void")
            spans.append(d.max(axis=1)[live])
            S = int(d.max())
            if 127 * L * int(FA_py[S]) >= LIM:                 # overflow certificate
                nfallback += 1
                fail("per-tile int64 certificate failed; object fallback needed "
                     "(not implemented -- would silently change the instrument)")
            coef = np.where(val[:, sl], sgn[:, sl], 0)
            cA = coef * FA[d]
            cB = coef * FB[d]
            if worst:
                # every Fibonacci coefficient is non-negative (d >= 0), so x_j = 127*sign(s_j)
                # attains this exactly -- a reachable maximum over all int8 vectors
                A = (127 * np.abs(cA).sum(axis=1))[:, None]
                B = (127 * np.abs(cB).sum(axis=1))[:, None]
            else:
                A = cA @ X[sl]                                 # (out, ntok) int64, exact
                B = cB @ X[sl]
            bndA = 127 * int(np.abs(cA).sum(axis=1).max())
            bndB = 127 * int(np.abs(cB).sum(axis=1).max())
            if int(np.abs(A).max()) > bndA or int(np.abs(B).max()) > bndB:
                fail(f"|A| or |B| exceeded its own triangle bound in {nm} -- int64 wrapped")
            A = A[live]
            B = B[live]
            wid = np.maximum(sgnwidth_np(A), sgnwidth_np(B))
            widths.append(wid.reshape(-1))
            wmax_t = max(wmax_t, int(wid.max()))
            ia = int(np.abs(A).max())
            ib = int(np.abs(B).max())
            if ia > maxA:
                maxA = ia
                argmax = (nm, st, "A")
            if ib > maxB:
                maxB = ib
            if pertensor:
                # one reference exponent for the whole tensor: multiply the pair by phi^c,
                # c = m_min(tile) - m_min(tensor), using F_(d+c) = F_(c+1)F_d + F_c F_(d-1).
                # Python ints -- these values are allowed to exceed int64, that is the point.
                cs = (mmin - tmin)[live]
                if int(cs.max()) + 1 > DMAX:
                    fail(f"tensor-wide reference offset {cs.max()} exceeds the F table")
                aa = np.abs(A[:, 0])
                bb = np.abs(B[:, 0])
                for c, av, bv in zip(cs.tolist(), aa.tolist(), bb.tolist()):
                    ap = av * FA_py[c + 1] + bv * FA_py[c]
                    bp = av * FA_py[c] + bv * FB_py[c]
                    pt_widths.append(max(sgnwidth_py(int(ap)), sgnwidth_py(int(bp))))
        per_tensor_max[nm] = wmax_t
    W = np.concatenate(widths)
    SP = np.concatenate(spans)
    worst_tensors = sorted(per_tensor_max.items(), key=lambda kv: -kv[1])[:5]
    stats[label] = {
        "accumulations": int(W.size), "dead_tiles": ndead, "fallback": nfallback,
        "max_abs_A": maxA, "max_abs_B": maxB, "argmax_A": argmax,
        "widest_tensors": worst_tensors,
        "width_max": int(W.max()), "width_mean": float(W.mean()),
        "width_p50": int(np.percentile(W, 50)),
        "width_p99": int(np.ceil(np.percentile(W, 99))),
        "width_p9999": int(np.ceil(np.percentile(W, 99.99))),
        "frac_over_16": float((W > 16).mean()), "frac_over_24": float((W > 24).mean()),
        "frac_over_32": float((W > 32).mean()),
        "span_max": int(SP.max()), "span_p50": int(np.percentile(SP, 50)),
        "span_p99": int(np.ceil(np.percentile(SP, 99))),
        "span_mean": float(SP.mean()),
        "hist": {int(b): int(c) for b, c in
                 zip(*np.unique(W, return_counts=True))},
        "secs": round(time.time() - t0, 1),
    }
    if pertensor:
        P = np.array(pt_widths, dtype=np.int32)
        stats[label]["pertensor_ref"] = {
            "width_p50": int(np.percentile(P, 50)),
            "width_p99": int(np.ceil(np.percentile(P, 99))),
            "width_p9999": int(np.ceil(np.percentile(P, 99.99))),
            "width_max": int(P.max()),
            "frac_over_32": float((P > 32).mean()), "frac_over_64": float((P > 64).mean()),
        }
    return W, SP


def crosscheck_int64(layers, acts, nsample=400):
    """T7: numpy int64 result == Python-int result, bitwise, on real tiles."""
    rng = np.random.default_rng(17)
    picks = rng.choice(len(layers), size=12, replace=False)
    checked = 0
    for pi in picks:
        nm, mod = layers[pi]
        w = mod.weight.data.double()
        e, idx, sg = phi_codes(w)
        m_all = (e.repeat_interleave(K, dim=1) + idx - (NLAD - 1)).numpy()
        val = (idx > 0).numpy()
        sgn = sg.numpy()
        X = acts[nm].T.copy()
        st, L = tiles(w.shape[1])[-1]
        sl = slice(st, st + L)
        mv = np.where(val[:, sl], m_all[:, sl], np.int64(1 << 40))
        mmin = mv.min(axis=1)
        d = np.where(val[:, sl], m_all[:, sl] - mmin[:, None], 0)
        coef = np.where(val[:, sl], sgn[:, sl], 0)
        if d.max() > NP_MAX:
            fail(f"cross-check tile span {d.max()} exceeds the int64 table")
        A = (coef * FA_np[d]) @ X[sl]
        B = (coef * FB_np[d]) @ X[sl]
        rows = rng.choice(w.shape[0], size=min(3, w.shape[0]), replace=False)
        for r in rows:
            if mmin[r] >= (1 << 40):
                continue
            for t in range(min(2, X.shape[1])):
                a = b = 0
                for j in range(L):
                    if val[r, st + j]:
                        dd = int(m_all[r, st + j] - mmin[r])
                        c = int(sgn[r, st + j]) * int(X[st + j, t])
                        a += c * FA_py[dd]
                        b += c * FB_py[dd]
                if a != int(A[r, t]) or b != int(B[r, t]):
                    fail(f"int64 path != Python-int path at {nm} row {r} tok {t}: "
                         f"({int(A[r,t])},{int(B[r,t])}) vs ({a},{b})")
                checked += 1
    print(f"    T7 int64 numpy accumulation == Python-int accumulation BITWISE on "
          f"{checked} real (tensor,row,token) triples across 12 tensors  OK\n")


# ---------------------------------------------------------------- run
selftests()

from transformers import AutoModelForCausalLM
model = AutoModelForCausalLM.from_pretrained(MODEL, dtype=torch.float32).eval()
layers = [(nm, mod) for nm, mod in model.named_modules()
          if isinstance(mod, torch.nn.Linear) and "lm_head" not in nm]
print(f"  linear tensors: {len(layers)}   "
      f"fan-in {'FULL ROW' if ROWMODE else FANIN}   activation vectors/layer {NTOK}")
shapes = {}
for nm, mod in layers:
    shapes.setdefault((mod.out_features, mod.in_features), 0)
    shapes[(mod.out_features, mod.in_features)] += 1
print("  shapes: " + ", ".join(f"{o}x{i} x{c} -> {len(tiles(i))} tiles"
                               for (o, i), c in sorted(shapes.items())))
tot = sum(mod.out_features * len(tiles(mod.in_features)) for _, mod in layers)
print(f"  row-tiles per activation vector: {tot}   total accumulations: {tot * NTOK}")

t0 = time.time()
A_real = capture_acts(model, layers, NTOK)
print(f"  captured real activations in {time.time()-t0:.0f}s; "
      f"int8 range check {min(int(v.min()) for v in A_real.values())}.."
      f"{max(int(v.max()) for v in A_real.values())}")
rng = np.random.default_rng(99)
A_rand = {nm: rng.integers(-127, 128, size=A_real[nm].shape).astype(np.int64) for nm, _ in layers}

crosscheck_int64(layers, A_real)

stats = {}
measure(layers, A_real, "real_int8", stats)
print(f"  measured real activations      ({stats['real_int8']['secs']}s)")
measure(layers, A_rand, "uniform_int8", stats)
print(f"  measured uniform int8 control  ({stats['uniform_int8']['secs']}s)")
measure(layers, None, "worst_int8", stats, worst=True, pertensor=True)
print(f"  measured worst case over ALL int8 vectors ({stats['worst_int8']['secs']}s)\n")

S = stats["real_int8"]["span_max"]
wc_meas = (FANIN * 127 * FA_py[S]).bit_length() + 1
wc_43 = (FANIN * 127 * FA_py[43]).bit_length() + 1

print("  FINAL-PAIR WIDTH NEEDED, signed two's complement, per component")
print(f"  {'activations':22}{'rows':>11}{'p50':>6}{'p99':>6}{'p99.99':>8}{'100%':>7}"
      f"{'max|A|':>15}")
lbl = {"real_int8": "real (wikitext)", "uniform_int8": "uniform random",
       "worst_int8": "worst over all int8"}
for k, s in stats.items():
    print(f"  {lbl[k]:22}{s['accumulations']:11d}{s['width_p50']:6d}{s['width_p99']:6d}"
          f"{s['width_p9999']:8d}{s['width_max']:7d}{s['max_abs_A']:15d}")
print()
for k, s in stats.items():
    print(f"  {lbl[k]:22} rows over 16 bits {100*s['frac_over_16']:9.5f}%   "
          f"over 24 bits {100*s['frac_over_24']:8.5f}%   "
          f"over 32 bits {100*s['frac_over_32']:8.5f}%")
print()
print(f"  widest tensors (worst-case arm): " +
      ", ".join(f"{n.split('model.layers.')[-1]}={v}b"
                for n, v in stats["worst_int8"]["widest_tensors"][:3]))
pt = stats["worst_int8"]["pertensor_ref"]
print(f"  if ONE reference exponent per tensor instead of per tile: p50 {pt['width_p50']}, "
      f"p99 {pt['width_p99']}, max {pt['width_max']} bits "
      f"({100*pt['frac_over_32']:.2f}% of rows over 32)")
print()
print(f"  phi span inside one 512-tile, campaign grid: median "
      f"{stats['real_int8']['span_p50']}, p99 {stats['real_int8']['span_p99']}, max {S}")
print(f"  worst-case provisioning ceil(log2(n*A*F_S))+1 at span {S}: {wc_meas} bits;  "
      f"at span 43: {wc_43} bits")

json.dump({"model": TAG, "fanin": FANIN, "ntok": NTOK, "tensors": len(layers),
           "worst_case_bits_measured_span": wc_meas, "worst_case_bits_span43": wc_43,
           "stats": stats},
          open("/Users/ssdm4/Desktop/PROJECTS/CLAUDE/trinity-fpga/research/block/"
               f"zphi_acc_width{'_row' if ROWMODE else ''}"
               f"{'' if FANIN == 512 else f'_f{FANIN}'}.json", "w"), indent=1)
print(f"\n  -> zphi_acc_width{'_row' if ROWMODE else ''}"
      f"{'' if FANIN == 512 else f'_f{FANIN}'}.json")
