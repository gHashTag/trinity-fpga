#!/usr/bin/env python3
"""phi_is_phi.py — does the golden ratio in GFTernary behave like the golden ratio?

Asked natively: not "is 1.618 close to phi" but "does the thing the format
calls phi satisfy the property that defines phi, in the arithmetic the format
actually uses". Three arithmetics carry a phi here and they do not agree.

  1. the oracle          exact in Z[phi], phi^2 = phi + 1 by construction
  2. the closed 2-bit    phi is inert: any positive constant gives the
     format               same 16 add and 16 mul results
  3. the RTL             phi is fp32 0x3FCF1BBD, and phi*phi != phi + 1

Run it: python3 conformance/phi_is_phi.py
Exit 0 if every claim below still holds; non-zero, loudly, if one moves.

No network, no yosys, no board. Everything here is arithmetic.
"""

import struct
import sys
from decimal import Decimal, getcontext

getcontext().prec = 60
PHI = (1 + Decimal(5).sqrt()) / 2

# The constant the decode RTL puts on the wire, read straight out of
# fpga/openxc7-synth/gfternary_decode.v rather than retyped from a paper.
RTL_PHI_BITS = 0x3FCF1BBD

# Code -> balanced-ternary shadow. 0b11 is reserved and the RTL folds it to
# +phi, so it folds to +1 here; a format with two codes for one value is worth
# knowing about but is not what this file measures.
SHADOW = {0: 0, 1: 1, 2: -1, 3: 1}

failures = []


def check(cond, claim, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {claim}")
    if detail:
        print(f"        {detail}")
    if not cond:
        failures.append(claim)


def f32(bits):
    return struct.unpack(">f", struct.pack(">I", bits))[0]


def bits_of(x):
    return struct.unpack(">I", struct.pack(">f", x))[0]


# ---------------------------------------------------------------- 1. exact ring

class PhiVal:
    """a + b*phi with integer a, b. phi is never a number here — the identity
    phi^2 = phi + 1 is the whole implementation of multiplication."""

    __slots__ = ("a", "b")

    def __init__(self, a, b):
        self.a, self.b = a, b

    def __add__(self, o):
        return PhiVal(self.a + o.a, self.b + o.b)

    def __mul__(self, o):
        # (a+b.phi)(c+d.phi) = ac + bd.phi^2 + (ad+bc).phi, and phi^2 = phi+1
        return PhiVal(self.a * o.a + self.b * o.b,
                      self.a * o.b + self.b * o.a + self.b * o.b)

    def __eq__(self, o):
        return self.a == o.a and self.b == o.b

    def __repr__(self):
        return f"{self.a} + {self.b}.phi"


def ring_claims():
    print("\n1. The oracle's phi, in Z[phi]")
    phi, one = PhiVal(0, 1), PhiVal(1, 0)
    check(phi * phi == phi + one,
          "phi^2 = phi + 1 holds exactly and symbolically",
          f"phi*phi = {phi*phi}, phi+1 = {phi + one}")
    # x^2 = x+1 has two roots; only the positive one is phi. Exactness here
    # matters: 1 < phi < 2 is checked in the ring, not against a float.
    check(sign(PhiVal(-1, 1)) > 0 and sign(PhiVal(2, -1)) > 0,
          "it is the positive root: 1 < phi < 2, decided in Z[sqrt 5]")


def sign(v):
    """Sign of a + b*phi = (2a + b + b*sqrt 5)/2, decided in integers.

    Squaring is legitimate only on non-negative sides, hence the branches. The
    equality case is unreachable for b != 0 (it would make sqrt 5 rational) and
    is kept so a future caller with rational coefficients cannot fall through.
    """
    a, b = v.a, v.b
    if a == 0 and b == 0:
        return 0
    s = 2 * a + b
    if b == 0:
        return (s > 0) - (s < 0)
    if b > 0:
        if s >= 0:
            return +1
        return +1 if 5 * b * b > s * s else (-1 if 5 * b * b < s * s else 0)
    if s <= 0:
        return -1
    return +1 if s * s > 5 * b * b else (-1 if s * s < 5 * b * b else 0)


def sign_is_exact():
    print("\n2. The sign decision, against 60-digit arithmetic")
    bad = 0
    n = 0
    for a in range(-60, 61):
        for b in range(-60, 61):
            want = Decimal(a) + Decimal(b) * PHI
            n += 1
            if sign(PhiVal(a, b)) != (want > 0) - (want < 0):
                bad += 1
    check(bad == 0,
          f"all {n} sign decisions agree with 60-digit phi",
          f"{n - bad}/{n} agree; the comparison never touches a float")


# ------------------------------------------------------- 3. is phi observable?

def phi_is_inert_in_the_closed_format():
    print("\n3. Is phi observable in the closed 2-bit format?")
    # Decode, operate, quantise back to a code by sign. That round trip is the
    # whole arithmetic of the 2-bit format.
    def tables(c):
        val = {0: Decimal(0), 1: c, 2: -c, 3: c}
        q = lambda v: 1 if v > 0 else (2 if v < 0 else 0)
        return [(q(val[x] + val[y]), q(val[x] * val[y]))
                for x in range(4) for y in range(4)]

    ref = tables(PHI)
    # `tables` is compared only against other `tables` results, so nothing here
    # pins the quantiser: a degenerate q (say, one that always returns 1) would
    # make every substitution agree and the inertness claim would pass
    # VACUOUSLY. `tri mutate` found exactly that -- mutating the code values on
    # this line left every claim green. So the phi table is tied to the shadow
    # map, which is itself tied to the decode RTL above.
    code = {1: 1, -1: 2, 0: 0}
    expected = [(code[(SHADOW[x] + SHADOW[y] > 0) - (SHADOW[x] + SHADOW[y] < 0)],
                 code[(SHADOW[x] * SHADOW[y] > 0) - (SHADOW[x] * SHADOW[y] < 0)])
                for x in range(4) for y in range(4)]
    check(ref == expected,
          "the phi table is the sign rule over the RTL's own shadow map",
          "without this the substitution test compares tables only to each "
          "other, and a degenerate quantiser passes it vacuously")
    check(len({c for pair in ref for c in pair}) == 3,
          "the table is non-degenerate: all three codes occur")

    others = {"1 (balanced ternary)": Decimal(1),
              "2": Decimal(2),
              "pi": Decimal("3.14159265358979323846"),
              "1/1000": Decimal("0.001"),
              "10^12": Decimal("1e12")}
    same = {k: tables(v) == ref for k, v in others.items()}
    check(all(same.values()),
          "phi is INERT here: every positive constant gives the same tables",
          "so the closed 2-bit format is observationally balanced ternary — "
          "substituted " + ", ".join(others))


def phi_is_a_scale_not_information():
    print("\n4. In a MAC, is phi information or a scale factor?")
    print("        Theorem. For GFTernary vectors x, y with balanced shadows")
    print("        x~, y~ (the same codes), <x,y> = phi^2 * <x~,y~> exactly,")
    print("        because each term is (phi.t)(phi.u) = phi^2.tu.")
    print("        In Z[phi] that means the accumulator is always (k, k).")
    import random
    rng = random.Random(20260818)
    bad = 0
    n = 0
    for _ in range(20000):
        N = rng.randrange(1, 200)
        xs = [rng.randrange(4) for _ in range(N)]
        ys = [rng.randrange(4) for _ in range(N)]
        acc = PhiVal(0, 0)
        for x, y in zip(xs, ys):
            acc = acc + PhiVal(0, SHADOW[x]) * PhiVal(0, SHADOW[y])
        bal = sum(SHADOW[x] * SHADOW[y] for x, y in zip(xs, ys))
        n += 1
        # phi^2 * bal = bal*(1+phi) -> coefficients (bal, bal). Integer equality:
        # measuring this through a decimal phi gave 1e-47 and nearly got called
        # exact — the ruler was the error, not the result.
        if acc != PhiVal(bal, bal):
            bad += 1
    check(bad == 0,
          f"exact on {n} random dot products, as integers",
          "so phi multiplies the whole result and never interacts with the "
          "data — a per-tensor scale of phi^2 = 2.618034 carries it entirely")


# ---------------------------------------------------------------- 5. the silicon

def the_shadow_map_matches_the_rtl():
    """SHADOW is the bridge between the format and balanced ternary, and until
    this check existed nothing pinned it: mutating 0b11 from +1 to -1 left every
    other claim passing, because the same map sits on both sides of the theorem
    and cancels. An unchecked constant in a checker is the vacuous-assertion
    failure again, so the map is read back against the decode RTL's own table."""
    print("\n5. The shadow map, against the decode RTL's own table")
    # fpga/openxc7-synth/gfternary_decode.v, verbatim.
    RTL_DECODE = {0: 0x00000000, 1: 0x3FCF1BBD, 2: 0xBFCF1BBD, 3: 0x3FCF1BBD}
    phi32 = f32(RTL_PHI_BITS)
    bad = []
    for code, bits in RTL_DECODE.items():
        want = SHADOW[code] * phi32
        if f32(bits) != want:
            bad.append(f"code {code:02b}: RTL {f32(bits)}, shadow says {want}")
    check(not bad,
          "every code's shadow reproduces the RTL decode value",
          "; ".join(bad) if bad else
          "0b11 is a second code for +phi — a duplicate encoding, checked here "
          "rather than assumed")


def the_silicon_constant():
    print("\n6. The constant the RTL actually puts on the wire")
    v = f32(RTL_PHI_BITS)
    nearest = bits_of(float(PHI))
    check(nearest == RTL_PHI_BITS,
          f"0x{RTL_PHI_BITS:08X} is the correctly-rounded fp32 phi",
          f"decodes to {Decimal(v):.17f}, true phi {PHI:.17f}, "
          f"{abs(Decimal(v) - PHI) / (Decimal(f32(RTL_PHI_BITS + 1)) - Decimal(v)):.3f} ulp")

    # The identity that defines phi, evaluated where the hardware evaluates it.
    def mul32(x, y):
        return f32(bits_of(x * y))

    sq = mul32(v, v)
    inc = f32(bits_of(v + 1.0))
    d = abs(bits_of(sq) - bits_of(inc))
    check(sq != inc,
          f"phi^2 != phi + 1 in fp32 — they differ by {d} ulp",
          f"phi*phi = 0x{bits_of(sq):08X}, phi+1 = 0x{bits_of(inc):08X}. "
          "This is asserted as a FACT about the current RTL, not as a wish: "
          "if a future decode makes them agree, this line fires and should be "
          "rewritten, not silenced.")


def main():
    print(__doc__.split("\n\n")[0])
    ring_claims()
    sign_is_exact()
    phi_is_inert_in_the_closed_format()
    phi_is_a_scale_not_information()
    the_shadow_map_matches_the_rtl()
    the_silicon_constant()
    print()
    if failures:
        print(f"{len(failures)} claim(s) moved:")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("Every claim holds. What this does NOT establish: nothing here says")
    print("phi is the wrong choice for GF-T, where phi is the exponent BASE and")
    print("sets the grid spacing — that property cannot be rescaled away. It")
    print("says phi in the 2-bit DIGIT SET is a scale factor, and that the fp32")
    print("constant implementing it costs rounding the exact ring does not.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
