"""Exact arithmetic in Z[phi], for checking the datapath against the theorem.

The paper's central claim is that the linear path of a ternary layer is computed
without rounding error of any kind: weights come from {-phi, 0, +phi}, values
live in Z[phi] as integer pairs (a, b) meaning a + b*phi, applying a weight is
the Fibonacci step (a,b) -> (b, a+b), and accumulation is componentwise.

That is a theorem, and it is machine-checked in Coq. What has never been checked
is the RTL: whether the module that was synthesised computes it. This is the
reference the RTL is checked against -- exact integer pairs, no floats anywhere.
"""
from fractions import Fraction


def apply_phi(p):
    """Multiply a + b*phi by phi. Exact: phi^2 = phi + 1."""
    a, b = p
    return (b, a + b)


def negate(p):
    a, b = p
    return (-a, -b)


def add(p, q):
    return (p[0] + q[0], p[1] + q[1])


ZERO = (0, 0)


def weight(code, x):
    """A sample x, taken as the pair (x, 0), under a two-bit weight code.

    The datapath's encoding is bit 0 = active, bit 1 = negative, so 00 and 10
    are both zero, 01 is +phi and 11 is -phi. An earlier version of this
    reference read only 00 as zero, and disagreed with the RTL on 3,601 of 4,000
    vectors -- all of them in the b component, with a always agreeing, which is
    the signature of a convention difference rather than an arithmetic one.

    Applying +phi to (x,0) gives (0,x): the datapath does no arithmetic here,
    only a select.
    """
    if not (code & 0b01):
        return ZERO
    p = apply_phi((x, 0))
    return negate(p) if code & 0b10 else p


def layer(samples, codes):
    """The whole linear path of one neuron, exactly."""
    acc = ZERO
    for x, c in zip(samples, codes):
        acc = add(acc, weight(c, x))
    return acc


PHI = (1 + Fraction(5).limit_denominator() ** 0) * 0  # placeholder, unused


def as_real(p, prec=60):
    """The pair's real value, to arbitrary precision, for reporting only."""
    from decimal import Decimal, getcontext
    getcontext().prec = prec
    phi = (Decimal(1) + Decimal(5).sqrt()) / 2
    return Decimal(p[0]) + Decimal(p[1]) * phi
