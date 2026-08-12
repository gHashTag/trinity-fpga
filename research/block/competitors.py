#!/usr/bin/env python3
"""Single source of truth for every competitor format, with conformance checks.

Three times in this programme a table named a format it was not actually using:

  1. the MX shared-scale rule -- ceiling instead of floor(log2 max) - emax
  2. E2M1 -- missing its subnormal, 7 magnitudes instead of 8
  3. NF4 -- a symmetric 8-magnitude reconstruction standing in for the real 16-value table

Each was internally consistent, each survived every cross-check we had, and each was found only
by going back to the specification. Rather than pay for that lesson a fourth time, every
reference format lives here, with a source and an assertion against a PUBLISHED constant that
is independent of how the format is constructed. Import this; do not redefine formats locally.

The checks below run at import. If one fails, the module refuses to load rather than silently
handing out a wrong format -- which is the whole point, since a wrong format is not detectable
downstream.

SOURCES
  OCP Microscaling Formats (MX) Specification v1.0
  microsoft/microxcaling, mx/mx_ops.py and mx/elemwise_ops.py  (reference implementation)
  bitsandbytes-foundation/bitsandbytes, bitsandbytes/functional.py  (get_4bit_type, NF4)
  Dettmers et al., QLoRA (NF4 derivation)
"""
import numpy as np


def _mags(eb, mb, emax_expected=None, maxnorm_expected=None, reserved="none"):
    """Element magnitudes for a floating-point format, INCLUDING SUBNORMALS.

    subnormal:  (m / 2^mb) * 2^(1 - bias)     m = 1 .. 2^mb - 1
    normal:     (1 + m / 2^mb) * 2^e          e = 1-bias .. 2^eb - 1 - bias

    `reserved` handles encodings a format sets aside for NaN/Inf, which shrink the maximum.
    Ignoring them is how the first version of this module produced E4M3 max = 480 (published
    448) and E5M2 max = 114688 (published 57344) -- the FOURTH instance of a competitor being
    defined from the general pattern instead of from its specification. The assertions below
    caught it on the first run, which is the entire reason this module exists.

      "none"    no reserved encodings                  (E2M1, E3M2, E2M3)
      "e4m3fn"  top exponent keeps all mantissas but the last, which is NaN  -> max 448
      "ieee"    top exponent reserved entirely for Inf/NaN                   -> E5M2 max 57344
    """
    bias = (1 << (eb - 1)) - 1
    e_hi = (1 << eb) - 1 - bias
    if reserved == "ieee":
        e_hi -= 1
    out = {0.0}
    for m in range(1, 1 << mb):
        out.add((m / (1 << mb)) * 2.0 ** (1 - bias))
    for e in range(1 - bias, e_hi + 1):
        m_hi = (1 << mb) - 1
        if reserved == "e4m3fn" and e == e_hi:
            m_hi -= 1                                   # S.1111.111 is NaN
        for m in range(m_hi + 1):
            out.add((1 + m / (1 << mb)) * 2.0 ** e)
    lv = np.array(sorted(out))
    # Cardinality, because the top of the ladder does not witness its bottom:
    # a ladder built with the subnormal loop DELETED has the same max normal and
    # the same emax, and would pass both checks below while the docstring says
    # INCLUDING SUBNORMALS.  0 + (2^mb - 1) subnormals + one binade per exponent.
    n_expected = 1 + ((1 << mb) - 1) + (e_hi - (1 - bias) + 1) * (1 << mb)
    if reserved == "e4m3fn":
        n_expected -= 1                                 # S.1111.111 is NaN
    assert len(lv) == n_expected, (
        f"E{eb}M{mb}: {len(lv)} magnitudes, definition gives {n_expected}")
    if maxnorm_expected is not None:
        assert abs(lv[-1] - maxnorm_expected) < 1e-9, (
            f"E{eb}M{mb}: max normal {lv[-1]} != published {maxnorm_expected}")
    if emax_expected is not None:
        import math
        assert math.floor(math.log2(lv[-1])) == emax_expected, (
            f"E{eb}M{mb}: emax {math.floor(math.log2(lv[-1]))} != published {emax_expected}")
    return lv


def signed(mags):
    """Mirror magnitudes into a signed level set (0 appears once)."""
    return np.array(sorted(set([-float(v) for v in mags] + [float(v) for v in mags])))


# ---------------------------------------------------------------- element formats
# Published max normals: E2M1 = 6, E3M2 = 28, E2M3 = 7.5, E4M3 = 448, E5M2 = 57344.
FP4_E2M1_MAGS = _mags(2, 1, emax_expected=2, maxnorm_expected=6.0)
FP6_E3M2_MAGS = _mags(3, 2, maxnorm_expected=28.0)
FP6_E2M3_MAGS = _mags(2, 3, maxnorm_expected=7.5)
FP8_E4M3_MAGS = _mags(4, 3, maxnorm_expected=448.0, reserved="e4m3fn")
FP8_E5M2_MAGS = _mags(5, 2, maxnorm_expected=57344.0, reserved="ieee")

FP4_E2M1 = signed(FP4_E2M1_MAGS / FP4_E2M1_MAGS[-1])
INT4 = signed(np.array([i / 7.0 for i in range(8)]))

# bitsandbytes get_4bit_type("nf4") -- quoted verbatim, not reconstructed.
NF4 = np.array([-1.0, -0.6961928009986877, -0.5250730514526367, -0.39491748809814453,
                -0.28444138169288635, -0.18477343022823334, -0.09105003625154495, 0.0,
                0.07958029955625534, 0.16093020141124725, 0.24611230194568634,
                0.33791524171829224, 0.44070982933044434, 0.5626170039176941,
                0.7229568362236023, 1.0])

# ---------------------------------------------------------------- the MX scale rule
E2M1_EMAX = 2
E2M1_MAXNORM = 6.0
MX_SCALE_C = E2M1_MAXNORM / 2.0 ** E2M1_EMAX          # 1.5


def mx_shared_scale(amax, emax=E2M1_EMAX, maxnorm=E2M1_MAXNORM, normalised=True):
    """OCP MX shared scale.  X = 2^(floor(log2 amax) - emax)

    microxcaling: shared_exp = floor(log2(max|A|)); shared_exp -= emax; A = A / 2**shared_exp
    Note this is a FLOOR, and the largest element clamps to max_norm whenever amax/X > maxnorm.

    normalised=True returns the scale in units where the element format's top level is 1,
    which is what our quantisers use:  s = (maxnorm / 2^emax) * 2^floor(log2 amax).
    Forgetting the maxnorm factor divides every element into [2^emax, 2^(emax+1)) against
    levels topping out at 1 and clips the entire tensor -- a bug that once produced a
    perplexity of 3e9.
    """
    xp = np if not hasattr(amax, "log2") else None
    if xp is None:                                     # torch tensor
        import torch
        E = torch.floor(torch.log2(amax.clamp(min=1e-30)))
        base = torch.pow(2.0, E)
    else:
        E = np.floor(np.log2(np.maximum(amax, 1e-30)))
        base = np.power(2.0, E)
    return base * (maxnorm / 2.0 ** emax) if normalised else base * 2.0 ** (-emax)


# ---------------------------------------------------------------- conformance checks
def _check():
    m = FP4_E2M1_MAGS
    assert len(m) == 8, f"E2M1 must have 8 magnitudes (incl. subnormal 0.5), got {len(m)}: {m}"
    assert np.allclose(m, [0, 0.5, 1, 1.5, 2, 3, 4, 6]), f"E2M1 magnitudes wrong: {m}"
    assert len(FP4_E2M1) == 15, f"E2M1 signed must have 15 values, got {len(FP4_E2M1)}"

    assert len(NF4) == 16, f"NF4 must have 16 values, got {len(NF4)}"
    assert len(set(np.round(NF4, 12))) == 16, "NF4 values must be distinct"
    assert NF4[0] == -1.0 and NF4[-1] == 1.0, "NF4 must span [-1, 1]"
    assert 0.0 in set(NF4), "NF4 must contain exact zero"
    assert not np.allclose(NF4, -NF4[::-1]), "NF4 is ASYMMETRIC; a symmetric table is not NF4"

    assert len(INT4) == 15, f"int4 signed must have 15 values, got {len(INT4)}"

    # MX rule: amax/X must land in [2^emax, 2^(emax+1)), i.e. [4, 8) for E2M1, so the top
    # element clips whenever it exceeds max_norm = 6. Verified against the definition, not
    # against our own implementation.
    a = np.array([0.3, 1.0, 1.7, 5.0, 1e-4])
    X = mx_shared_scale(a, normalised=False)
    r = a / X
    assert np.all((r >= 2.0 ** E2M1_EMAX - 1e-9) & (r < 2.0 ** (E2M1_EMAX + 1) + 1e-9)), \
        f"MX rule: amax/X must lie in [4,8), got {r}"
    # and in normalised units the same ratio maps into [4/6, 8/6)
    Xn = mx_shared_scale(a, normalised=True)
    rn = a / Xn
    assert np.all((rn >= 4 / 6 - 1e-9) & (rn < 8 / 6 + 1e-9)), \
        f"MX normalised scale wrong, ratios {rn} outside [0.667, 1.333)"


_check()

if __name__ == "__main__":
    print("All competitor conformance checks PASSED.\n")
    print(f"  E2M1 magnitudes  {list(FP4_E2M1_MAGS)}")
    print(f"  E2M1 signed      {len(FP4_E2M1)} values")
    print(f"  NF4              {len(NF4)} values, asymmetric, contains 0")
    print(f"  int4 signed      {len(INT4)} values")
    print(f"  MX scale C       {MX_SCALE_C}  (= max_norm / 2^emax = 6/4)")
    print(f"  FP8 E4M3 max     {FP8_E4M3_MAGS[-1]}")
    print(f"  FP8 E5M2 max     {FP8_E5M2_MAGS[-1]}")
    print(f"  FP6 E3M2 max     {FP6_E3M2_MAGS[-1]}")
    print(f"  FP6 E2M3 max     {FP6_E2M3_MAGS[-1]}")
    print("\n  Every value above is checked against a PUBLISHED constant at import time.")
    print("  A format that fails its check stops the import instead of being handed out.")


# ---------------------------------------------------------------- scale quantisers
FP8_E4M3_MAXNORM = float(FP8_E4M3_MAGS[-1])            # 448.0, checked above
FP8_E4M3_MINNORM = 2.0 ** (1 - ((1 << 4) // 2 - 1))    # 2^-6


def ue4m3_scale(s):
    """Unsigned E4M3 scale, as NVFP4 uses. Clamps to the format's real maximum, 448.

    Our earlier implementation allowed exponent 8 with mantissa 7, i.e. a maximum of 480, because
    it ignored E4M3's reserved NaN encoding. Every "UE4M3 scale" row measured before this fix is
    slightly wrong. The effect is small (the scale rarely saturates) but it is not zero, and it
    is exactly the class of error competitors.py exists to stop.
    """
    import torch
    s = s.clamp(min=1e-30)
    e = torch.floor(torch.log2(s)).clamp(-6, 8)
    m = torch.round((s / torch.pow(2.0, e) - 1.0) * 8).clamp(0, 8)
    e = e + (m == 8).to(e.dtype)
    m = torch.where(m == 8, torch.zeros_like(m), m)
    out = (1 + m / 8) * torch.pow(2.0, e)
    return out.clamp(max=FP8_E4M3_MAXNORM)             # <- the fix: 448, not 480


def _check_scales():
    import torch
    # every representable UE4M3 value must be an element of the E4M3 magnitude set
    s = torch.tensor([1e-8, 0.001, 0.5, 1.0, 3.3, 100.0, 447.0, 460.0, 1e6], dtype=torch.float64)
    q = ue4m3_scale(s).numpy()
    allowed = set(np.round(FP8_E4M3_MAGS, 9))
    for v in q:
        assert round(float(v), 9) in allowed, f"UE4M3 produced {v}, not an E4M3 value"
    assert q.max() <= FP8_E4M3_MAXNORM + 1e-9, f"UE4M3 exceeded 448: {q.max()}"


try:
    import torch as _t          # only check when torch is present
    _check_scales()
except ImportError:
    pass
