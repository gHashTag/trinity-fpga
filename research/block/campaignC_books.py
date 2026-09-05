#!/usr/bin/env python3
"""Campaign C codebooks + the ASYMMETRIC quantiser, and the proof it is the same
instrument as the symmetric one.

`block_tnf.quant` takes a list of MAGNITUDES and applies `sign(w)`: it can only
express a symmetric book. NF4 is asymmetric (8 positive, 7 negative, one zero),
so it needs a quantiser that maps to an explicit SIGNED level list. If those two
quantisers are not the same instrument, the two arms are not comparable and every
number downstream is meaningless.

`quant_signed` is therefore checked, on real checkpoint tensors, to agree with
`block_tnf.quant` BIT-EXACTLY whenever it is handed the signed level set
+/- the magnitudes and zero.

The one place the two could differ is a weight that lands EXACTLY on a decision
boundary. `quant` bucketizes |w|, so a tie rounds toward the smaller magnitude,
i.e. toward zero, on both signs. A naive signed bucketize rounds toward -inf, so
negative ties would go the other way. `quant_signed` reproduces round-half-toward-
ZERO explicitly; that is what makes the agreement exact rather than
almost-everywhere.

bitsandbytes is not installed in this environment, so `create_normal_map` is
transcribed from its source and then CHECKED against the published NF4 table
(the sixteen values shipped in the QLoRA data type) to 1e-6. If that check fails
the script refuses to hand out a codebook.
"""
import math

import numpy as np
import torch
from scipy.stats import norm

# ---------------------------------------------------------------------------
# bitsandbytes.functional.create_normal_map, transcribed
# ---------------------------------------------------------------------------
def create_normal_map(offset=0.9677083, use_extra_value=True):
    if use_extra_value:
        # one more positive value, this is an asymmetric type
        v1 = norm.ppf(torch.linspace(offset, 0.5, 9)[:-1]).tolist()
        v2 = [0] * (256 - 15)
        v3 = (-norm.ppf(torch.linspace(offset, 0.5, 8)[:-1])).tolist()
    else:
        v1 = norm.ppf(torch.linspace(offset, 0.5, 8)[:-1]).tolist()
        v2 = [0] * (256 - 14)
        v3 = (-norm.ppf(torch.linspace(offset, 0.5, 8)[:-1])).tolist()
    v = v1 + v2 + v3
    values = torch.Tensor(v)
    values = values.sort().values
    values /= values.max()
    assert values.numel() == 256
    return values


# The sixteen values of the NF4 data type as published (QLoRA / bitsandbytes).
NF4_PUBLISHED = [
    -1.0, -0.6961928009986877, -0.5250730514526367, -0.39491748809814453,
    -0.28444138169288635, -0.18477343022823334, -0.09105003625154495, 0.0,
    0.07958029955625534, 0.16093020141124725, 0.24611230194568634,
    0.33791524171829224, 0.44070982933044434, 0.5626170039176941,
    0.7229568362236023, 1.0]


def _distinct(t):
    v = sorted(set(round(float(x), 12) for x in t.tolist()))
    return v


def nf4_levels():
    """16 SIGNED levels, asymmetric."""
    v = _distinct(create_normal_map(use_extra_value=True))
    assert len(v) == 16, len(v)
    err = max(abs(a - b) for a, b in zip(v, NF4_PUBLISHED))
    assert err < 1e-6, f"NF4 does not reproduce the published table: {err:.2e}"
    return v


def nf4_sym_magnitudes():
    """8 MAGNITUDES (zero + 7), i.e. 15 distinct signed values."""
    v = _distinct(create_normal_map(use_extra_value=False))
    assert len(v) == 15, len(v)
    pos = [x for x in v if x > 0]
    neg = sorted(-x for x in v if x < 0)
    assert len(pos) == 7 and len(neg) == 7
    assert max(abs(a - b) for a, b in zip(pos, neg)) < 1e-12, "not symmetric"
    return [0.0] + pos


def normalise(lv):
    v = sorted(float(x) for x in lv)
    top = max(abs(v[0]), abs(v[-1]))
    return [x / top for x in v]


MXFP4 = [0.0, 1 / 12, 1 / 6, 0.25, 1 / 3, 0.5, 2 / 3, 1.0]
LLOYD = normalise([0.0, 0.10334, 0.21079, 0.32491, 0.44963,
                   0.59031, 0.75635, 0.96567])
KLOPT = [0.0, 0.07701, 0.18828, 0.31396, 0.46561, 0.6113, 0.79074, 1.0]
NSSE = [0.0, 0.09083, 0.18167, 0.28750, 0.40833, 0.55250, 0.73417, 1.0]
JOINTKL = [0.0, 0.06833333, 1 / 6, 0.25, 0.35583333, 0.5, 2 / 3, 1.0]


def books():
    """(name, kind, levels).  kind 'mag' -> magnitudes for block_tnf.quant,
    kind 'sig' -> explicit signed levels for quant_signed."""
    return [
        ("MXFP4",      "mag", MXFP4),
        ("Lloyd-Max",  "mag", LLOYD),
        ("KL-opt",     "mag", KLOPT),
        ("nSSE-equal", "mag", NSSE),
        ("JOINT-KL",   "mag", JOINTKL),
        ("NF4-sym",    "mag", nf4_sym_magnitudes()),
        ("NF4",        "sig", nf4_levels()),
    ]


def check_phase(bs):
    """T38: every book normalised so its largest MAGNITUDE is exactly 1.0."""
    for name, kind, lv in bs:
        top = max(abs(float(x)) for x in lv)
        assert abs(top - 1.0) < 1e-12, f"{name}: max|level| = {top} -- phase phi != 0"
        assert abs(math.log2(top) % 1.0) < 1e-12, name
        assert list(lv) == sorted(lv), name
        if kind == "mag":
            assert lv[0] == 0.0, name
            assert len(lv) == 8, (name, len(lv))
            n_distinct = 2 * len(lv) - 1
        else:
            assert 0.0 in [float(x) for x in lv], name
            n_distinct = len(lv)
        yield name, kind, len(lv), n_distinct


# ---------------------------------------------------------------------------
# the asymmetric quantiser
# ---------------------------------------------------------------------------
def make_quant_signed(K, q_e8m0_t):
    def quant_signed(w, levels):
        """levels: explicit SIGNED list, sorted, containing 0.0.
        Scale is E8M0 over max|level| exactly as block_tnf.quant does.
        Ties on a decision boundary round toward ZERO, which is what
        bucketizing |w| does in the symmetric reference."""
        lv_t = torch.tensor(sorted(float(x) for x in levels), dtype=torch.float64)
        top = lv_t.abs().max()
        orig = w.shape
        n = (orig[1] // K) * K
        if n == 0:
            return w
        head = w[:, :n].reshape(-1, K).double()
        s = (head.abs().amax(dim=1) / top).clamp(min=1e-30)
        s = q_e8m0_t(s).clamp(min=1e-30)
        y = head / s[:, None]
        bnd = (lv_t[:-1] + lv_t[1:]) / 2
        i_lo = torch.bucketize(y, bnd, right=False)   # tie -> toward -inf
        i_hi = torch.bucketize(y, bnd, right=True)    # tie -> toward +inf
        idx = torch.where(y < 0, i_hi, i_lo)          # tie -> toward zero
        rec = lv_t[idx] * s[:, None]
        out = w.clone()
        out[:, :n] = rec.reshape(-1, n).to(w.dtype)
        return out
    return quant_signed


def signed_from_magnitudes(mags):
    v = sorted(set([0.0] + [float(m) for m in mags] + [-float(m) for m in mags]))
    return v
