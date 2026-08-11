"""E3M4 minifloat reference: 1 sign + 3 exponent + 4 mantissa, bias 3.

Written from the parameters `minifloat_decode.v` declares in its header. This is
NOT the E4M3 of OCP fp8 -- the two differ in where the split falls, and
comparing one against the other is the variant error this catalogue records
twice already.
"""
NAN = float("nan"); INF = float("inf")

def value(code):
    s = -1.0 if (code >> 7) & 1 else 1.0
    e = (code >> 4) & 0x7
    m = code & 0xF
    if e == 0x7:
        return s * INF if m == 0 else NAN
    if e == 0:
        return 0.0 * s if m == 0 else s * (m / 16.0) * 2.0 ** (1 - 3)
    return s * (1.0 + m / 16.0) * 2.0 ** (e - 3)

FORMATS = {"minifloat": "e3m4"}
def decode(fmt, code): return value(code)
