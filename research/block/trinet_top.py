#!/usr/bin/env python3
"""The top that matters for TRI-NET: which accumulator format holds the link.

TRI-NET's own README states the premise: ONE multiplier-free primitive -- the
sign-select MAC -- builds both the radio matched filter and the transformer.
Radio and AI are the same datapath. So there is exactly one number-format
question in the whole system, and it is not about weights or activations:

    the weight is a code in {-1,0,+1} and needs no format at all;
    the sample is ADC-native int16 and needs no format at all;
    ONLY THE ACCUMULATOR HAS A FORMAT.

The RTL currently sizes it by a heuristic:
    parameter integer ACC = 20    // W + ceil(log2(8)) headroom
We have a law for it, so the law is tested against the heuristic on real air.

METRIC. Perplexity is meaningless here. What a radio must preserve is
SEPARATION: matched RMS over mismatched RMS (code reject) and over the
TX-off floor (noise reject). Published measured values on this capture:
    matched 237.9 | mismatched 47.2 (~5x) | TX-off 14.0 (~17x)
A format keeps the link if it keeps those ratios. That is the ranking.

RULER CHECK: the exact (float64) run must reproduce the published ratios, or
the harness is not measuring the same thing the hardware measured.
"""
import math, sys, os
import numpy as np

OTA = "/Users/ssdm4/Desktop/PROJECTS/CLAUDE/tri-net/fpga/ternary/ota"

def load(name):
    v = [int(l.strip(), 16) for l in open(os.path.join(OTA, name)) if l.strip()]
    return np.array([x - 65536 if x >= 32768 else x for x in v], dtype=np.float64)

MATCHED    = [ 1,  1, 0, -1, -1, -1, 0,  1]     # sign(cos(2 pi k / 8))
MISMATCHED = [ 1, -1, 0,  1, -1,  1, 0, -1]     # sign(cos(2 pi 3k / 8))

def correlate(x, code, qfn):
    """Sliding 8-tap ternary correlator, rounding the accumulator at every tap
    exactly as the hardware register would."""
    out = []
    for i in range(len(x) - len(code) + 1):
        acc = 0.0
        for k, c in enumerate(code):
            if c:
                acc = qfn(acc + (x[i + k] if c > 0 else -x[i + k]))
        out.append(acc)
    return np.array(out)

def exact(v): return v

def mk_float(Et, M, radix=3):
    """Fixed fields: significand rounded to M bits inside its binade, exponent
    field spanning radix^Et binades, with saturation and underflow."""
    nbin = radix ** Et
    hi = nbin // 2
    def q(v):
        if v == 0.0: return 0.0
        e = math.floor(math.log2(abs(v)))
        if e > hi:  return math.copysign(2.0 ** hi * (2 - 2.0 ** -M), v)
        if e < -hi: return 0.0
        s = abs(v) / 2.0 ** e
        return math.copysign(round(s * (1 << M)) / (1 << M) * 2.0 ** e, v)
    return q

def mk_fixed(bits):
    """The RTL's own choice: a plain signed integer accumulator."""
    lim = (1 << (bits - 1)) - 1
    def q(v): return float(max(-lim, min(lim, round(v))))
    return q

on, off = load("rx_on_raw.hex"), load("rx_off_raw.hex")

def ratios(qfn):
    m  = correlate(on,  MATCHED,    qfn)
    mm = correlate(on,  MISMATCHED, qfn)
    o  = correlate(off, MATCHED,    qfn)
    rms = lambda a: float(np.sqrt(np.mean(a ** 2)))
    return rms(m), rms(mm), rms(o)

rm, rmm, ro = ratios(exact)
print(f"ЛИНЕЙКА (точная арифметика): matched {rm:.1f}  mismatched {rmm:.1f}  TX-off {ro:.1f}")
print(f"   опубликовано железом:     matched 237.9  mismatched 47.2  TX-off 14.0")
ok = abs(rm - 237.9) / 237.9 < 0.15 and abs(rmm - 47.2) / 47.2 < 0.25
print(f"   -> {'совпало, прибор мерит то же' if ok else 'НЕ СОВПАЛО — прибор мерит не то'}\n")
if not ok: sys.exit(1)
REJ_CODE, REJ_NOISE = rm / rmm, rm / ro
print(f"эталон разделения: код-реджект {REJ_CODE:.2f}x, шум-реджект {REJ_NOISE:.2f}x\n")

print("═══ ТОП ДЛЯ ТЕРНАРНОГО ИНТЕРНЕТА: кто держит линк и на скольких битах ═══")
print("критерий: оба разделения удержаны в пределах 5% от точной арифметики\n")
print(f"{'формат аккумулятора':30s} {'бит':>4s} {'код-реджект':>12s} {'шум-реджект':>12s}  вердикт")

CANDS = []
for b in (12, 14, 16, 20, 24):
    CANDS.append((f"int{b} (эвристика RTL)" if b == 20 else f"int{b}", b, mk_fixed(b)))
for N in (12, 14, 16):
    for Et in (2, 3):
        M = 0
        while (3 ** Et) * (1 << (M + 1)) <= (1 << (N - 1)): M += 1
        CANDS.append((f"TNF{N} Eₜ={Et} M={M}", N, mk_float(Et, M)))
for N, e, m, nm in ((16, 5, 10, "binary16"), (16, 8, 7, "bfloat16"), (16, 6, 9, "GF-T16 (φ)")):
    r = 3 if "GF-T" in nm else 2
    CANDS.append((nm, N, mk_float(e, m, r)))

rows = []
for name, bits, q in CANDS:
    a, b_, c = ratios(q)
    rc, rn = (a / b_ if b_ else 0), (a / c if c else 0)
    keep = abs(rc - REJ_CODE) / REJ_CODE < 0.05 and abs(rn - REJ_NOISE) / REJ_NOISE < 0.05
    rows.append((name, bits, rc, rn, keep))
    print(f"{name:30s} {bits:4d} {rc:11.2f}x {rn:11.2f}x  "
          f"{'✓ ЛИНК ДЕРЖИТ' if keep else '✗ линк потерян'}")

good = [r for r in rows if r[4]]
if good:
    win = min(good, key=lambda r: r[1])
    print(f"\nПОБЕДИТЕЛЬ: «{win[0]}» — держит линк на {win[1]} битах.")
    heur = [r for r in rows if "эвристика" in r[0]]
    if heur:
        h = heur[0]
        d = h[1] - win[1]
        print(f"Эвристика RTL — int20 — {'держит' if h[4] else 'НЕ держит'}; "
              f"{'экономия ' + str(d) + ' бит аккумулятора' if d > 0 else 'закон подтверждает эвристику'}.")
else:
    print("\nНИ ОДИН кандидат не удержал оба разделения — критерий слишком строг или тракт хрупок.")
