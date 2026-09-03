import numpy as np

def quantise_np(x, e_bits, m_bits):
    """Round-to-nearest-even into an (e_bits, m_bits) binary float, vectorised.

    bias = 2^(e-1)-1, no Inf and no NaN row (the all-ones exponent is a finite
    normal), saturating at the top, subnormals at the bottom -- the same shape
    the exact oracle in conformance/gf_ref.py implements. Verified against it
    rather than assumed: an approximate quantiser would silently change the
    ranking this benchmark exists to produce.
    """
    x = np.asarray(x, dtype=np.float64)
    sign = np.sign(x)
    a = np.abs(x)
    bias = (1 << (e_bits - 1)) - 1
    exp_max = (1 << e_bits) - 1

    out = np.zeros_like(a)
    nz = a > 0
    if not np.any(nz):
        return (sign * out).astype(x.dtype)

    e = np.zeros_like(a)
    e[nz] = np.floor(np.log2(a[nz]))
    e = np.clip(e, 1 - bias, exp_max - bias)          # normal exponent range

    # subnormal region: exponent pinned at the minimum, implicit bit is 0
    min_e = 1 - bias
    scale = np.exp2(e - m_bits)
    q = np.rint(a / scale)                            # round-to-nearest-even
    # a mantissa that rounds up past the implicit bit carries into the exponent
    carry = q >= (1 << (m_bits + 1))
    e = np.where(carry & (e < exp_max - bias), e + 1, e)
    scale = np.exp2(e - m_bits)
    q = np.rint(a / scale)

    top = (float((1 << (m_bits + 1)) - 1)) * np.exp2(float(exp_max - bias - m_bits))
    out = q * scale
    out = np.minimum(out, top)                        # saturate
    out = np.where(a < np.exp2(float(min_e - m_bits)) / 2, 0.0, out)
    return (sign * out).astype(np.float64)
