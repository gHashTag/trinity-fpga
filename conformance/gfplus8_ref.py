"""Reference for GF+A, the adaptive 8-bit container (`gfplus8_a_decode`).

Written from the format parameters the RTL declares in its own header, not
transcribed from its logic: each pocket is implemented here from its stated
(sign, exponent, mantissa, bias) and compared against what the module computes.

  pocket 00  phi_e3m4   1S + 3E + 4M, bias 3
  pocket 01  e2m5       1S + 2E + 5M, bias 1
  pocket 10  int8       symmetric fixed point
  pocket 11  lns8       declared logarithmic

The payload is 8 bits and the pocket selector is 2 more, so the decoder sees a
10-bit input. The container amortises the selector over a group of K rows, which
is why the storage column says 8 bits; the decode cost is a 10-bit cost.
"""

def _ieee(sign, exp_field, mant_field, ebits, mbits, bias):
    """Value of a (1, ebits, mbits) float with the given bias, IEEE-style."""
    s = -1.0 if sign else 1.0
    if exp_field == 0:
        if mant_field == 0: return 0.0 * s
        return s * (mant_field / (1 << mbits)) * 2.0 ** (1 - bias)   # subnormal
    return s * (1.0 + mant_field / (1 << mbits)) * 2.0 ** (exp_field - bias)

def phi_e3m4(word):
    return _ieee(word >> 7, (word >> 4) & 0x7, word & 0xF, 3, 4, 3)

def e2m5(word):
    return _ieee(word >> 7, (word >> 5) & 0x3, word & 0x1F, 2, 5, 1)

def int8(word):
    """Symmetric fixed point: the 7-bit magnitude scaled by 1/64."""
    mag = word & 0x7F
    return (-1.0 if word >> 7 else 1.0) * (mag / 64.0)

def lns8(word):
    """What the module computes: a power-of-two ladder, mantissa always zero.

    The RTL forms shift = floor(inv/16) + floor(inv/32) with inv = 127 - mag,
    and emits 2^(-shift). Its own comment beside that line says the intent was
    inv*8/127; floor(inv/16)+floor(inv/32) approximates inv*3/32. The two
    disagree by half again, and the result is a ladder of eleven magnitudes,
    not a logarithmic format.
    """
    mag = word & 0x7F
    if mag == 0: return 0.0 * (-1.0 if word >> 7 else 1.0)
    inv = 127 - mag
    shift = (inv >> 4) + (inv >> 5)
    return (-1.0 if word >> 7 else 1.0) * 2.0 ** (-shift)

POCKETS = {0: phi_e3m4, 1: e2m5, 2: int8, 3: lns8}

def decode(pocket, word):
    return POCKETS[pocket & 3](word & 0xFF)
