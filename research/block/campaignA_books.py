#!/usr/bin/env python3
"""Campaign A candidate set: EVERY single-codeword placement, not three of seven.

Campaign B enumerated five placements of the sixteenth codeword on E2M1's ladder
and chose among them on ONE model. The leave-one-out rotation in
SIXTEENTH_CODEWORD_SPENT_2026-08-12.md showed the choice is inside the noise:
SmolLM2 picks NEAR0, Pythia picks TOP, and TOP loses to both references.

Two things are wrong with that selection and this file fixes the first.

1. The enumeration was INCOMPLETE. E2M1's magnitude ladder in units of 1/12 is
   1,2,3,4,6,8,12, so a positive level inserted at the midpoint of a gap has
   SEVEN places to go (counting the gap between zero and the smallest level),
   and campaign B tried three of them: 0->1 (NEAR0), 4->6 (MID2), 8->12 (MID).
   A placement chosen from an incomplete enumeration is a weaker claim than one
   chosen from a complete one, so the four missing gaps are added here:
   1->2, 2->3, 3->4, 6->8.

2. The selection used one model.  That is campaignA_run.py / campaignA_stats.py.

Also carried over from campaign B: TOP (extend the ladder to 16/12, which
renormalisation pays for by clipping the negative extreme to -0.75) and MIDN
(the 8->12 insertion on the NEGATIVE side).  NEAR0N is added as the matching
negative mirror of NEAR0, so the best positive arm and the best negative arm are
each tested against their own reflection rather than only one of them being.

Level construction is campaignB_books.asym -- exact Fractions, then normalised so
max|level| == 1.0 on BOTH tails (T38).  Nothing is reimplemented: the symmetric
references and the signed quantiser come from campaignC_books.
"""
from fractions import Fraction as F

import campaignB_books as B
import campaignC_books as C

# E2M1's exact magnitudes in units of 1/12; 0 handled separately by asym().
U = [F(x) for x in B.MX_UNITS]
assert [float(F(u, 12)) for u in B.MX_UNITS] == list(C.MXFP4[1:])

# midpoint of every gap of the ladder, including the gap zero -> smallest level
GAPS = {
    "NEAR0": U[0] / 2,                 # 0  -> 1     = 1/2   (campaign B)
    "G12":   (U[0] + U[1]) / 2,        # 1  -> 2     = 3/2   NEW
    "G23":   (U[1] + U[2]) / 2,        # 2  -> 3     = 5/2   NEW
    "G34":   (U[2] + U[3]) / 2,        # 3  -> 4     = 7/2   NEW
    "MID2":  (U[3] + U[4]) / 2,        # 4  -> 6     = 5     (campaign B)
    "G68":   (U[4] + U[5]) / 2,        # 6  -> 8     = 7     NEW
    "MID":   (U[5] + U[6]) / 2,        # 8  -> 12    = 10    (campaign B)
}
assert len(GAPS) == len(U)             # seven gaps for seven ladder rungs


def candidates():
    """(name, kind, levels) for every placement of the sixteenth codeword."""
    out = []
    for tag, x in GAPS.items():
        out.append((f"MX-asym-{tag}", "sig", B.asym(sorted(U + [x]), U)))
    out.append(("MX-asym-TOP",   "sig", B.asym(U + [F(16)], U)))
    out.append(("MX-asym-MIDN",  "sig", B.asym(U, sorted(U + [GAPS["MID"]]))))
    out.append(("MX-asym-NEAR0N", "sig", B.asym(U, sorted(U + [GAPS["NEAR0"]]))))
    return out


def references():
    return [("MXFP4",   "mag", C.MXFP4),
            ("NF4-sym", "mag", C.nf4_sym_magnitudes()),
            ("NF4",     "sig", C.nf4_levels())]


def all_books():
    return candidates() + references()


def check(bs):
    """T38 on BOTH tails + the 16-codeword accounting, asserted not assumed."""
    seen = {}
    for name, kind, lv in bs:
        lv = [float(x) for x in lv]
        assert lv == sorted(lv), name
        assert len(set(lv)) == len(lv), name
        pos = max(x for x in lv)
        neg = -min(x for x in lv)
        assert abs(max(pos, neg) - 1.0) < 1e-12, f"{name}: max|level|={max(pos,neg)}"
        assert pos <= 1.0 + 1e-12 and neg <= 1.0 + 1e-12, name
        if kind == "mag":
            assert lv[0] == 0.0 and len(lv) == 8, (name, len(lv))
            nd, npos, nneg = 15, 7, 7
        else:
            assert 0.0 in lv and len(lv) == 16, (name, len(lv))
            npos = sum(1 for x in lv if x > 0)
            nneg = sum(1 for x in lv if x < 0)
            nd = 16
            assert npos + nneg + 1 == 16, (name, npos, nneg)
        key = tuple(round(x, 12) for x in lv)
        assert key not in seen, f"{name} duplicates {seen.get(key)}"
        seen[key] = name
        yield name, kind, nd, npos, nneg, pos, neg


if __name__ == "__main__":
    bs = all_books()
    print(f"{'book':<16}{'kind':>5}{'dist':>6}{'pos':>5}{'neg':>5}"
          f"{'+top':>8}{'-top':>8}   levels")
    for (n, k, nd, np_, nn, pos, neg), (_, _, lv) in zip(check(bs), bs):
        s = ", ".join(f"{float(x):+.5f}" for x in lv)
        print(f"{n:<16}{k:>5}{nd:>6}{np_:>5}{nn:>5}{pos:>8.4f}{neg:>8.4f}   [{s}]")
    print(f"\n{len(candidates())} placements, {len(references())} references")
