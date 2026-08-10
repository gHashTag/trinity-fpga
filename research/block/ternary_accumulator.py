#!/usr/bin/env python3
"""The accumulator law for ternary networks, measured rather than assumed.

In a ternary layer the weight is {-1,0,+1} and carries no format at all: there is
no multiply, only add/subtract/skip. The only thing a number format describes is
what flows through the datapath -- the activation and the accumulator. Every
published ternary method (BitNet, TWN, TernaryBERT, PTQTP) quantises the WEIGHT,
so none of them is a competitor here; they answer a different question.

Predicted, before measuring:
  range   visited by the accumulator   B(K) = log2(pK) + c        (log in fan-in)
  error   after pK roundings           ~ sqrt(pK) * 2^-(M+1)      (sqrt in fan-in)
so demand for mantissa grows as 0.5*log2(K) while demand for exponent grows only
as log_3 log2(K). The prediction is a CROSSOVER: a fixed accumulator width stops
sufficing past some fan-in, and formats that spend positions on exponent hit it
sooner.

Falsifiable: if the measured error grows as K rather than sqrt(K), the law is
wrong. If wide-exponent formats do NOT degrade faster with fan-in, the corollary
is wrong. Both are reported as they come.
"""
import os, sys, math
import numpy as np, torch
torch.set_grad_enabled(False)
W = ("/private/tmp/claude-501/-Users-ssdm4-Desktop-PROJECTS-CLAUDE/"
     "0e868af8-ab2d-4d00-be03-8fea94ba48e4/scratchpad/weights")
rng = np.random.default_rng(20260809)

def levels_packed(N, Et, radix=3):
    """Positions say 1+Et+M=N; BINARY FABRIC says 3^Et * 2^M <= 2^(N-1).
    The gap between the two is the packing loss -- exactly the no-free-range
    theorem -- and ignoring it is what produced a 100x perplexity artefact
    earlier in this work."""
    cap = 1 << (N - 1)
    M = 0
    while (radix ** Et) * (1 << (M + 1)) <= cap:
        M += 1
    out = {0.0}
    for e in range(radix ** Et):
        for m in range(1 << M):
            out.add((1 + m / (1 << M)) * (2.0 ** -e))
    v = np.array(sorted(out))
    return v / v[-1], Et, M

def qfmt(v, M, nbin):
    """A real accumulator: FIXED fields, fixed scale. Round the significand to M
    bits inside its own binade, and clamp to the +/- nbin/2 binades the exponent
    field can address.

    The earlier version normalised each value by its own magnitude, which put
    every sample exactly on a grid point and returned error identically zero at
    every fan-in. Error that is exactly zero everywhere is not a result, it is a
    broken instrument -- a format that never rounds is not a format."""
    if v == 0.0: return 0.0
    e = math.floor(math.log2(abs(v)))
    hi = nbin // 2
    if e > hi: return math.copysign(2.0 ** hi * (2 - 2.0 ** -M), v)   # saturate
    if e < -hi: return 0.0                                            # underflow
    sig = abs(v) / 2.0 ** e
    sig = round(sig * (1 << M)) / (1 << M)
    return math.copysign(sig * 2.0 ** e, v)

# ---- real activations and real ternary weights -----------------------------
from safetensors import safe_open
f = safe_open(os.path.join(W, "smollm2", "model.safetensors"), framework="pt")
key = [k for k in f.keys() if k.endswith("mlp.down_proj.weight")][0]
Wm = f.get_tensor(key).double().numpy()
thr = 0.7 * np.abs(Wm).mean()
tern = np.sign(Wm) * (np.abs(Wm) > thr)          # BitNet-style ternarisation
p = float((tern != 0).mean())
print(f"вес: {key}  форма {Wm.shape}  доля ненулевых p = {p:.3f}\n", flush=True)

print("═══ 1. КАК РАСТЁТ ОШИБКА АККУМУЛЯТОРА ПО ВЕЕРУ ═══")
print("предсказано: ~ sqrt(K).  показатель 0.5 подтверждает, 1.0 опровергает.\n")
print(f"{'K':>7s} {'бинад':>7s} " + " ".join(f"{n:>11s}" for n in ("TNF16 Et=2","TNF16 Et=3","TNF16 Et=4")))
Ks = [64, 256, 1024, 4096, 16384]
fmts = [levels_packed(16, e) for e in (2, 3, 4)]
curves = {i: [] for i in range(len(fmts))}
for K in Ks:
    errs, bins = [[] for _ in fmts], []
    for _ in range(40):
        r = rng.integers(0, tern.shape[0])
        s = np.resize(tern[r], K)          # tile the row when K exceeds its width
        x = rng.standard_normal(K) * 0.3
        part = np.cumsum(s * x)                      # the running accumulator
        exact = part[-1]
        if abs(exact) < 1e-12: continue
        nz = np.abs(part[np.abs(part) > 0])
        bins.append(math.log2(nz.max() / nz.min()) if len(nz) > 1 else 0.0)
        for i, (lv, Et, M) in enumerate(fmts):
            acc = 0.0
            nbin = 3 ** Et
            for j in range(K):                        # round at every step
                acc = qfmt(acc + s[j] * x[j], M, nbin)
            errs[i].append(abs(acc - exact) / abs(exact))
    curves_row = [np.median(e) for e in errs]
    for i, v in enumerate(curves_row): curves[i].append(v)
    print(f"{K:7d} {np.median(bins):7.1f} " + " ".join(f"{v:11.3e}" for v in curves_row), flush=True)

print()
for i, (lv, Et, M) in enumerate(fmts):
    sl = np.polyfit(np.log2(Ks), np.log2(np.maximum(curves[i], 1e-30)), 1)[0]
    print(f"TNF16 Et={Et} M={M} ({len(lv)} уровней): показатель по K = {sl:+.3f}  "
          f"-> {'sqrt(K) ПОДТВЕРЖДЁН' if 0.35 < sl < 0.65 else 'закон ОПРОВЕРГНУТ'}")

print("\n═══ 2. СЛЕДСТВИЕ: ШИРОКАЯ ЭКСПОНЕНТА ДЕГРАДИРУЕТ БЫСТРЕЕ ═══")
print("предсказано: чем шире экспонента, тем меньше мантиссы и тем раньше порог.\n")
best_at = {}
for k_i, K in enumerate(Ks):
    vals = [(curves[i][k_i], fmts[i][1], fmts[i][2]) for i in range(len(fmts))]
    b = min(vals)
    best_at[K] = b
    print(f"  K={K:6d}: лучший Et={b[1]} M={b[2]}   " +
          "  ".join(f"Et={fmts[i][1]}:{curves[i][k_i]:.2e}" for i in range(len(fmts))))
et_seq = [best_at[K][1] for K in Ks]
print(f"\n  последовательность оптимальных Et по вееру: {et_seq}")
print("  " + ("НЕ УБЫВАЕТ -> следствие подтверждено (шире веер -> не больше экспоненты)"
      if all(a >= b for a, b in zip(et_seq, et_seq[1:])) or len(set(et_seq)) == 1
      else "РАСТЁТ -> следствие ОПРОВЕРГНУТО, экспоненте нужно больше при большем веере"))
