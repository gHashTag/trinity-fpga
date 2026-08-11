#!/usr/bin/env python3
"""Five invariants across every TNF rung, asserted rather than printed.

The suite that shipped before this campaign checked add/mul commutativity, which
is structurally blind to a sign inversion: an inverted sign survives on both sides
of a + b == b + a. A sign-placement defect lived in the oracle for exactly that
reason. Round-trip catches that class; the other four catch its neighbours.

Run: python3 conformance/tnf_ladder_invariants_test.py
"""
import random
import sys
from fractions import Fraction as F

sys.path.insert(0, __file__.rsplit("/", 1)[0])
import tnf_ref as G

# UNIT: POSITIONS. This ladder is the position budget -- one sign position, E_t
# ternary positions and M binary positions, so N = 1 + E_t + M and
# M = N - 1 - E_t. It is NOT the stored-bit ladder.
#
# conformance/tnf_spec_ref.py declares a DIFFERENT ladder under the SAME names,
# in UNIT: STORED BITS, where the width is 1 + ceil(E_t log2 3) + M. The two
# disagree on tnf16 (M = 11 here, 9 there) and tnf64 (56 here, 52 there), and
# both passed their own tests for the whole campaign because neither said which
# unit it was counting. The RTL implements the stored-bit ladder; this file's
# rungs are not the ones in silicon.
#
# tools/check_ladder_units.py now requires both files to declare their unit and
# forbids a name meaning two different things.
UNIT = "positions"
LADDER = [(4, 2, 1), (8, 3, 4), (16, 4, 11), (32, 6, 25), (64, 7, 56),
          (128, 8, 119), (256, 9, 246), (512, 10, 501), (1024, 11, 1012)]


def probes(Et, M, n, rng):
    """Values inside the rung's range and finer than its mantissa."""
    eo = (3 ** Et - 1) // 2
    lim = min(eo - 2, 900)
    out = []
    for _ in range(n):
        e = rng.randint(-lim, lim)
        m = F(rng.getrandbits(M + 8), 1 << (M + 8))
        v = (1 + m) * (F(2) ** e)
        out.append(v if rng.random() < 0.5 else -v)
    return out


def check_rung(N, Et, M, rng):
    fmt = G.TNFFormat(Et, M)
    eo = (3 ** Et - 1) // 2
    vals = probes(Et, M, 600, rng)

    # 1. Round trip preserves sign exactly. Commutativity cannot see this.
    for v in vals:
        d = G.decode(fmt, G.encode(fmt, v))
        assert isinstance(d, F) and d != 0, f"TNF{N}: {v} decoded to {d!r}"
        assert (d < 0) == (v < 0), f"TNF{N}: sign flipped on {v}"

    # 2. Encoding is monotone in magnitude.
    pos = sorted(set(abs(v) for v in vals))[:300]
    raws = [int(G.encode(fmt, v)) for v in pos]
    for a, b in zip(raws, raws[1:]):
        assert b >= a, f"TNF{N}: encoding not monotone ({a} then {b})"

    # 3. The two signs quantise to the same magnitude.
    for v in pos[:200]:
        assert abs(G.decode(fmt, G.encode(fmt, v))) == abs(G.decode(fmt, G.encode(fmt, -v))), \
            f"TNF{N}: +/- asymmetry at {v}"

    # 4. Both ends of the finite range decode to something positive and finite.
    for e in (-eo + 1, eo - 1):
        d = G.decode(fmt, G.encode(fmt, F(2) ** e))
        assert isinstance(d, F) and d > 0, f"TNF{N}: boundary 2^{e} decoded to {d!r}"

    # 5. Zero round-trips to zero.
    assert float(G.decode(fmt, G.encode(fmt, 0.0))) == 0.0, f"TNF{N}: zero lost"

    # 6. The width rule the ladder is built on.
    assert 1 + Et + M == N, f"TNF{N}: 1 + {Et} + {M} != {N}"


def _selftest():
    rng = random.Random(20260809)
    for N, Et, M in LADDER:
        check_rung(N, Et, M, rng)
    print(f"SELF-TEST: PASS ({len(LADDER)} rungs x round-trip/monotonicity/"
          f"symmetry/boundaries/zero/width-rule)")


if __name__ == "__main__":
    _selftest()
