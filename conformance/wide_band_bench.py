#!/usr/bin/env python3
"""wide_band_bench.py — the one unmeasured cell of the tekum-vs-TNF line.

research/TEKUM_VS_TNF_LINE_2026-08-19.md §6: the accuracy tie was measured on
one ±3-decade band. TNF(4,8) spans e ∈ [-39, +39] binades (~11.9 decades of
magnitude) and then hard-clips; tekum's tapered exponent keeps going. No
benchmark in this line has exercised the band past TNF's span. This one does.

Harness = conformance/tekum_true_bench.py, unchanged in structure: 64-term
accumulation, seed 11, the running sum re-quantised through the format after
every add, identical samples for all formats per trial. Bands: log-uniform
magnitudes over ±3, ±6, ±9, ±11, ±13, ±16, ±20, ±30 decades, 60 trials each.
The ±3 band is first re-run through the parent bench's own accumulation
functions verbatim and must reproduce its recorded means exactly before any
wider band is measured.

ONE deliberate deviation, stated up front: the parent bench converts each
float sample with Fraction(x).limit_denominator(10**12). That call maps every
magnitude below ~1e-12 to exactly zero — at ±3 decades it is harmless float
hygiene, past ±12 decades it erases the low half of the band, i.e. the
instrument lies inside the failure domain it is supposed to measure. The wide
bands therefore use Fraction(x) directly (a binary float IS an exact
rational). The ±3 band is run through BOTH pipelines below; they agree to all
printed digits, which is the license to widen.

TNF(4,8) overflow semantics, explicit: encode() of any value whose exponent
offset reaches offset_max = 3^4 - 1 = 80 returns
(sign << 15) | (80 << 8) — the reserved SPECIAL ROW with zero mantissa —
and decode() maps that word to ±math.inf (a float, not a Fraction).
Detection here: tnf_ref.is_special() on the freshly encoded word at every
step. Underflow: encode() has no subnormals; |v| <= 2^-40 returns the bare
sign bit (the zero code) — detected as a FLUSH when the pre-quantisation
value was nonzero.

Accounting (repo discipline: never fold failures into a mean). Per band and
format:
  (a) mean rel err over trials the format finished finite and in range;
  (b) failed trials, split by cause: special (overflow row / NaR / inf),
      flush (running sum quantised to zero while the true sum is nonzero),
      sat (pre-quantisation magnitude above the format's largest finite —
      catches silent saturation in the formats that clamp instead of
      overflowing: takum16's encode clamps to its top code, tekum's
      bisection can only return finite codes);
  (c) element clip rate: fraction of INPUT samples strictly outside the
      format's representable magnitude range [min_pos, max_finite], ranges
      taken from exhaustive/monotone code-space scans, not from formulas.

Run: python3 conformance/wide_band_bench.py
"""

import math
import random
import sys
from fractions import Fraction

sys.path.insert(0, "conformance")
sys.path.insert(0, ".")
import takum_ref            # noqa: E402
import tekum_true_ref as TK  # noqa: E402
import tnf_ref               # noqa: E402
import tekum_true_bench as TB  # noqa: E402  (reused: acc, acc_tekum, TRIALS/TERMS/BAND)

TERMS = TB.TERMS      # 64
TRIALS = TB.TRIALS    # 60 (>= 40 per band)
SEED = 11
BANDS = (3.0, 6.0, 9.0, 11.0, 13.0, 16.0, 20.0, 30.0)

TNF48 = tnf_ref.TNFFormat(4, 8)
TK16 = takum_ref.FORMATS["takum16"]
FMT_NAMES = ("TNF(4,8)", "takum16", "tekum10")

# Recorded 16-bit-class means of tekum_true_bench.py (research/
# TEKUM_VS_TNF_LINE_2026-08-19.md §2). The ±3 anchor must reproduce these.
ANCHOR = {"tekum10": "8.561e-03", "takum16": "5.697e-03", "TNF(4,8)": "5.323e-03"}


# ---------------------------------------------------------------- ranges ---

def measured_ranges():
    """[min_pos, max_finite] per format, from the code space itself."""
    # TNF: offset runs 1..offset_max-1, mantissa 0..2^8-1, both monotone.
    mn = tnf_ref.decode(TNF48, 1 << TNF48.exp_shift)
    mx = tnf_ref.decode(TNF48, ((TNF48.offset_max - 1) << TNF48.exp_shift)
                        | (TNF48.mant - 1))
    ranges = {"TNF(4,8)": (mn, mx)}
    # takum16: raw code order is not magnitude order — scan all 65,536 codes.
    lo = hi = None
    for raw in range(1 << TK16.n):
        v = takum_ref.decode(TK16, raw)
        if isinstance(v, takum_ref.Special) or v == 0:
            continue
        a = -v if v < 0 else v
        if lo is None or a < lo:
            lo = a
        if hi is None or a > hi:
            hi = a
    ranges["takum16"] = (lo, hi)
    # tekum10: strict monotonicity in the integer code is proven in
    # tekum_true_ref's selftest, so the extreme finite codes are the extremes.
    ranges["tekum10"] = (TK.decode(10, 1), TK.decode(10, TK.vmax(10) - 1))
    return ranges


RANGES = measured_ranges()


# ------------------------------------------------------- one format step ---

def quantise(name, v):
    """v (exact Fraction) -> (event or None, decoded Fraction or None)."""
    if name == "TNF(4,8)":
        raw = tnf_ref.encode(TNF48, v)
        if tnf_ref.is_special(TNF48, raw):
            return "special", None
        return None, tnf_ref.decode(TNF48, raw)
    if name == "takum16":
        d = takum_ref.decode(TK16, takum_ref.encode(TK16, v))
        if isinstance(d, takum_ref.Special):
            return "special", None
        return None, d
    d = TK.decode(10, TK.encode(10, v))
    if not isinstance(d, Fraction):
        return "special", None
    return None, d


def run_trial(name, xf):
    """Accumulate one trial; returns (final Fraction, None) or (None, event)."""
    mn, mx = RANGES[name]
    s = Fraction(0)
    for x in xf:
        v = s + x
        ev, d = quantise(name, v)
        if ev is None:
            av = -v if v < 0 else v
            if v != 0 and av > mx:
                ev = "sat"           # silent clamp: out of range, no special
            elif d == 0 and v != 0:
                ev = "flush"
        if ev is not None:
            return None, ev
        s = d
    return s, None


# ----------------------------------------------------------- anchor gate ---

def verify_anchor():
    """Re-run the parent bench's 16-bit class through its own functions;
    abort unless the recorded means reproduce exactly."""
    random.seed(SEED)
    tot = {k: 0.0 for k in FMT_NAMES}
    cnt = 0
    for _ in range(TRIALS):
        xs = [random.uniform(-1, 1) * 10 ** random.uniform(-TB.BAND, TB.BAND)
              for _ in range(TERMS)]
        exact = sum(Fraction(x).limit_denominator(10 ** 12) for x in xs)
        if exact == 0:
            continue
        a = TB.acc_tekum(10, xs)
        b = TB.acc(takum_ref, TK16, xs)
        c = TB.acc(tnf_ref, TNF48, xs)
        if a is None or b is None or c is None:
            continue
        tot["tekum10"] += abs(float((a - exact) / exact))
        tot["takum16"] += abs(float((b - exact) / exact))
        tot["TNF(4,8)"] += abs(float((c - exact) / exact))
        cnt += 1
    print(f"  anchor (±3, parent pipeline, {cnt} trials):")
    ok = True
    for k in ("tekum10", "takum16", "TNF(4,8)"):
        got = f"{tot[k] / cnt:.3e}"
        match = got == ANCHOR[k]
        ok = ok and match
        print(f"    {k:<10} {got}  recorded {ANCHOR[k]}  "
              f"{'ok' if match else 'MISMATCH'}")
    if not ok:
        print("  ANCHOR FAILED — refusing to widen a band the harness "
              "cannot reproduce.")
        sys.exit(1)
    print()


# -------------------------------------------------------------- the bench ---

def run_band(band):
    random.seed(SEED)
    st = {k: {"err": 0.0, "ok": 0, "special": 0, "flush": 0, "sat": 0,
              "clip": 0} for k in FMT_NAMES}
    n_samples = 0
    for _ in range(TRIALS):
        xs = [random.uniform(-1, 1) * 10 ** random.uniform(-band, band)
              for _ in range(TERMS)]
        xf = [Fraction(x) for x in xs]   # exact: a float IS a rational
        exact = sum(xf)
        if exact == 0:
            continue
        n_samples += TERMS
        for name in FMT_NAMES:
            mn, mx = RANGES[name]
            st[name]["clip"] += sum(
                1 for a in xf if a != 0 and not (mn <= abs(a) <= mx))
            s, ev = run_trial(name, xf)
            if ev is not None:
                st[name][ev] += 1
            else:
                st[name]["err"] += abs(float((s - exact) / exact))
                st[name]["ok"] += 1
    return st, n_samples


def main():
    print(__doc__.split("\n\n")[0])
    print()
    print("  representable magnitude ranges (code-space scans):")
    for k in FMT_NAMES:
        mn, mx = RANGES[k]
        print(f"    {k:<10} [{float(mn):.3e}, {float(mx):.3e}]  "
              f"log10 [{math.log10(mn):+.2f}, {math.log10(mx):+.2f}]")
    print()
    verify_anchor()
    print(f"  {TERMS}-term accumulation, seed {SEED}, {TRIALS} trials/band, "
          f"exact-Fraction inputs:\n")
    hdr = (f"  {'band':>5}  " + "".join(
        f"{k + '  err / fail(s+f+sat) / clip%':>42}" for k in FMT_NAMES))
    print(hdr)
    for band in BANDS:
        st, n = run_band(band)
        row = f"  ±{band:>4.0f}  "
        for k in FMT_NAMES:
            d = st[k]
            fails = d["special"] + d["flush"] + d["sat"]
            err = f"{d['err'] / d['ok']:.3e}" if d["ok"] else "   --    "
            row += (f"{err:>12} {fails:>3}"
                    f"({d['special']:>2}+{d['flush']:>2}+{d['sat']:>2})"
                    f" {100.0 * d['clip'] / n:>6.2f}%   ")
        print(row)
    print()
    print("Read honestly. The fail split is special+flush+sat; a trial is")
    print("excluded from the mean on its first event, so surviving means at")
    print("high failure rates describe a survivor subset, not the format.")
    print("takum16's own range ends at ±76.7 decades and tekum10's at ±87.4")
    print("(both from code-space scans); the clip columns above say whether")
    print("any band reached them.")


if __name__ == "__main__":
    sys.exit(main())
