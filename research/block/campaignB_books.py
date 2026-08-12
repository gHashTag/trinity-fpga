#!/usr/bin/env python3
"""Campaign B codebooks: spend the sixteenth codeword on OUR OWN books.

T40 (THE_SIXTEENTH_CODEWORD_2026-08-12.md) established that a symmetric
magnitude table with a sign bit represents +0 and -0 with two codewords and
therefore has 15 distinct values where the 4-bit index affords 16, and that the
forfeit is worth 4.43 % of perplexity.  Nothing in this repository spends it.

Here MXFP4 and JOINT-KL are made ASYMMETRIC -- 8 positive levels, 7 negative,
one zero, exactly NF4's structure -- and the placement of the freed codeword is
enumerated rather than guessed:

  TOP    an extra positive magnitude beyond the current top.  E2M1's ladder in
         units of 1/12 is 1,2,3,4,6,8,12; its natural continuation is 16.  The
         book is then renormalised to max|level| = 1 (T38), which drops the
         NEGATIVE extreme to -12/16 = -0.75: the extra reach on one side is paid
         for by clipping on the other.  That trade is the measurement.
  MID    an extra positive magnitude at the midpoint of the COARSEST interior
         gap (8->12 in E2M1 units).  Endpoints stay at +-1, so this is NF4's own
         structure: the asymmetry lives in the interior.
  MID2   the same at the second-coarsest gap (4->6), to check MID is not a fluke
         of one particular hole.
  NEAR0  an extra positive magnitude at half the smallest one, where a Gaussian
         puts most of its mass.
  MIDN   the mirror of MID -- extra level on the NEGATIVE side.  Weights are
         near-symmetric, so if the codeword is what matters and not its sign,
         MIDN must land on top of MID.  A control, not a candidate.

Everything is normalised so max|level| == 1.0 exactly, so every arm sits at
headroom phase phi = 0 (T38).  Asserted, not assumed.

The quantiser for a signed level list is NOT reimplemented here: it is
campaignC_books.make_quant_signed, proven bit-exactly equal to block_tnf.quant
on any symmetric book by campaignB_agree.py.
"""
from fractions import Fraction as F

import campaignC_books as C

# --- E2M1's exact magnitudes, in units of 1/12 -----------------------------
MX_UNITS = [1, 2, 3, 4, 6, 8, 12]          # 0 handled separately

# Exact binary rationals of the published floats, so an asym variant carries
# BIT-IDENTICAL level values to its symmetric parent wherever a level survives.
JK_POS = [F(x) for x in C.JOINTKL[1:]]
assert [float(x) for x in JK_POS] == list(C.JOINTKL[1:])
assert [float(F(u, 12)) for u in MX_UNITS] == list(C.MXFP4[1:])


def asym(pos, neg):
    """Build a signed level list from positive and negative MAGNITUDES.
    Normalised so max|level| == 1.0 (T38)."""
    pos = sorted(F(x) for x in pos)
    neg = sorted(F(x) for x in neg)
    top = max(pos[-1], neg[-1])
    lv = sorted([float(-x / top) for x in neg] + [0.0] + [float(x / top) for x in pos])
    assert abs(max(abs(v) for v in lv) - 1.0) < 1e-15
    return lv


def mid(seq, i):
    """Midpoint of gap i -> i+1 of a magnitude ladder."""
    return (F(seq[i]) + F(seq[i + 1])) / 2


def mx_family():
    u = [F(x) for x in MX_UNITS]
    gaps = [u[i + 1] - u[i] for i in range(len(u) - 1)]
    assert gaps == [F(1), F(1), F(1), F(2), F(2), F(4)]
    i_coarse = 5                                   # 8 -> 12, gap 4
    i_second = 3                                   # 4 -> 6,  gap 2
    return {
        "MX-asym-TOP":   asym(u + [F(16)], u),
        "MX-asym-MID":   asym(sorted(u + [mid(u, i_coarse)]), u),      # +10
        "MX-asym-MID2":  asym(sorted(u + [mid(u, i_second)]), u),      # +5
        "MX-asym-NEAR0": asym(sorted(u + [u[0] / 2]), u),              # +0.5
        "MX-asym-MIDN":  asym(u, sorted(u + [mid(u, i_coarse)])),      # mirror
    }


def jk_family():
    p = list(JK_POS)
    gaps = [p[i + 1] - p[i] for i in range(len(p) - 1)]
    i_coarse = max(range(len(gaps)), key=lambda i: gaps[i])
    assert i_coarse == 5, i_coarse                 # 2/3 -> 1
    rest = [i for i in range(len(gaps)) if i != i_coarse]
    i_second = max(rest, key=lambda i: gaps[i])
    assert i_second == 4, i_second                 # 1/2 -> 2/3
    # TOP: JOINT-KL keeps E2M1's upper ladder verbatim (6/12, 8/12, 12/12), so
    # its natural continuation is the same 16/12 = 4/3.
    return {
        "JK-asym-TOP":   asym(p + [F(4, 3)], p),
        "JK-asym-MID":   asym(sorted(p + [mid(p, i_coarse)]), p),
        "JK-asym-MID2":  asym(sorted(p + [mid(p, i_second)]), p),
        "JK-asym-NEAR0": asym(sorted(p + [p[0] / 2]), p),
    }


def books():
    """(name, kind, levels).  'mag' -> block_tnf.quant, 'sig' -> quant_signed."""
    out = [
        ("MXFP4",      "mag", C.MXFP4),
        ("Lloyd-Max",  "mag", C.LLOYD),
        ("JOINT-KL",   "mag", C.JOINTKL),
        ("NF4-sym",    "mag", C.nf4_sym_magnitudes()),
        ("NF4",        "sig", C.nf4_levels()),
    ]
    for d in (mx_family(), jk_family()):
        for k, v in d.items():
            out.append((k, "sig", v))
    return out


def check(bs):
    """T38 phase assert + alphabet accounting."""
    for name, kind, lv in bs:
        lv = [float(x) for x in lv]
        top = max(abs(x) for x in lv)
        assert abs(top - 1.0) < 1e-12, f"{name}: max|level| = {top}, phase phi != 0"
        assert lv == sorted(lv), name
        if kind == "mag":
            assert lv[0] == 0.0 and len(lv) == 8, (name, len(lv))
            nd, npos, nneg = 15, 7, 7
        else:
            assert 0.0 in lv, name
            npos = sum(1 for x in lv if x > 0)
            nneg = sum(1 for x in lv if x < 0)
            nd = len(set(lv))
            assert nd == len(lv) == 16, (name, nd)
            assert npos + nneg + 1 == 16, (name, npos, nneg)
        yield name, kind, nd, npos, nneg


if __name__ == "__main__":
    bs = books()
    print(f"{'book':<15}{'kind':>5}{'distinct':>10}{'pos':>5}{'neg':>5}   levels")
    for (name, kind, nd, npos, nneg), (_, _, lv) in zip(check(bs), bs):
        s = ", ".join(f"{float(x):+.5f}" for x in lv)
        print(f"{name:<15}{kind:>5}{nd:>10}{npos:>5}{nneg:>5}   [{s}]")
