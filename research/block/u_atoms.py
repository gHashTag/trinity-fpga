"""Is the u axis continuous?  The block-maximum distribution's ATOMS, measured.

WHY THIS FILE EXISTS
--------------------
u_surface.py's model gate G11 failed on SmolLM2: the OCP cell measured 24.1633 where the
campaign's established value is 23.5224.  The two runs differ by ~1e-11 in u.  Before any u*
is reported, that has to be explained or the whole surface is mush.

Mechanism proposed (stated before measuring, so it can fail):

  Write a block maximum as amax = 2^e * t with t in [1,2), and the alignment as c = 2^p * v
  with v in [1,2).  s = 2^floor(log2(amax/c)) gives

      t >= v :  s = 2^(e-p)      r = amax/s = 2^p * t
      t <  v :  s = 2^(e-p-1)    r = amax/s = 2^(p+1) * t

  so for E2M1 (max_norm 6) the clamp set is a function of t and c ALONE:

      c in [3,4) : p=1, v=c/2 in [1.5,2)  ->  clamp iff 1.5 < t < c/2
      c in [4,6) : p=2, v=c/4 in [1,1.5)  ->  clamp iff t > 1.5 or t < c/4

  At c = 4 exactly the second branch's "t < c/4" set is EMPTY.  One ulp above 4 it becomes
  {t = 1}: every block whose maximum is an exact power of two.  If the weights live on a coarse
  binary grid (a bf16 checkpoint has 8 mantissa bits), t = 1 is an ATOM with mass of order
  1/256, not a measure-zero event -- and those blocks jump from r = 4 (their maximum EXACTLY
  representable) to r = 8 (clamped to 6: a 25% error on the largest weight in the block).

  Prediction, to be falsified: the clamp fraction is a STAIRCASE in u whose steps are the atoms
  of the distribution of t, and one step sits exactly at c = 4, i.e. exactly at OCP's alignment.

Instruments here are independent of u_surface.py: the scale is computed with frexp (no
logarithm anywhere) and the clamp set is computed a second time from the t/v algebra above,
which never divides amax by anything.  The two must agree bitwise at every u.  No model forward
pass is run; this is weights only.

Usage:  u_atoms.py smollm2|qwen|pythia|opt|gpt2 [--K 16,32,64,128]
"""
import argparse
import json
import math
import os
import sys

import numpy as np
import torch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

W = ("/private/tmp/claude-501/-Users-ssdm4-Desktop-PROJECTS-CLAUDE/"
     "0e868af8-ab2d-4d00-be03-8fea94ba48e4/scratchpad/weights")
torch.set_grad_enabled(False)

MAXNORM = {"E2M1": 6.0, "E3M0": 16.0, "INT4": 7.0}
FAILED = []


def check(cond, label, detail=""):
    print(f"    [{'ok ' if cond else 'FAIL'}] {label}" + (f"   {detail}" if detail else ""),
          flush=True)
    if not cond:
        FAILED.append(label)


def linears(m):
    for nm, mod in m.named_modules():
        if isinstance(mod, torch.nn.Linear) and not any(h in nm for h in ("lm_head", "embed_out")):
            yield nm, mod


def blockmax(w, K):
    out_f, in_f = w.shape
    pad = (-in_f) % K
    b = w.double()
    if pad:
        b = torch.cat([b, torch.zeros(out_f, pad, dtype=torch.float64)], dim=1)
    return b.reshape(-1, K).abs().amax(dim=1)


def clamp_frexp(amax, c, max_norm):
    """Instrument A: scale from frexp, clamp counted on amax/s directly."""
    _, e = torch.frexp(amax / c)
    s = torch.pow(torch.tensor(2.0, dtype=torch.float64), (e - 1).double())
    return amax / s > max_norm


def clamp_algebra(t, c, max_norm):
    """Instrument B: the t/v algebra, which never divides amax by anything."""
    p = math.floor(math.log2(c))
    v = c / 2.0 ** p
    hi = torch.where(t >= v, (2.0 ** p) * t, (2.0 ** (p + 1)) * t)
    return hi > max_norm


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("tag")
    ap.add_argument("--K", default="16,32,64,128")
    a = ap.parse_args()
    Ks = [int(v) for v in a.K.split(",")]

    from transformers import AutoModelForCausalLM
    path = os.path.join(W, a.tag)
    m = AutoModelForCausalLM.from_pretrained(path, dtype=torch.float32)
    m.eval()
    ws = {nm: mod.weight.data.clone() for nm, mod in linears(m)}
    nparam = sum(int(v.numel()) for v in ws.values())
    print(f"\n  {a.tag}: {len(ws)} nn.Linear tensors, {nparam:,} weights", flush=True)

    # ---- how coarse is the weight grid?  (a bf16 checkpoint loaded as fp32 is still bf16)
    n = nparam
    n_bf16 = 0
    n_pow2 = 0
    for v in ws.values():
        bits = v.reshape(-1).view(torch.int32)
        n_bf16 += int((bits & 0xFFFF == 0).sum())
        n_pow2 += int(((bits & 0x007FFFFF) == 0).sum()) - int((v == 0).sum())
    print(f"      weights exactly representable in bf16 (low 16 bits zero): "
          f"{n_bf16:,} / {n:,} = {100.0 * n_bf16 / n:.4f}%", flush=True)
    print(f"      weights that are an exact power of two: {n_pow2:,} / {n:,} = "
          f"{100.0 * n_pow2 / n:.6f}%", flush=True)
    print(f"      => weight grid is {'bf16, 8 mantissa bits' if n_bf16 == n else 'finer than bf16'}",
          flush=True)

    out = dict(model=a.tag, nparam=nparam, ntensor=len(ws), pct_bf16=100.0 * n_bf16 / n, K={})

    for K in Ks:
        amax = torch.cat([blockmax(v, K) for v in ws.values()])
        nblk = amax.numel()
        mm, ee = torch.frexp(amax)
        t = (mm * 2.0).double()                      # t in [1,2)
        check(bool(((t >= 1.0) & (t < 2.0)).all()), f"K={K} t in [1,2) for every block")

        n_t1 = int((t == 1.0).sum())
        print(f"\n  K={K}: {nblk:,} blocks", flush=True)
        print(f"      blocks whose maximum is an exact power of two (t == 1): "
              f"{n_t1:,} / {nblk:,} = {100.0 * n_t1 / nblk:.4f}%", flush=True)

        vals, cnts = torch.unique(t, return_counts=True)
        order = torch.argsort(cnts, descending=True)[:10]
        print(f"      ten largest atoms of t   (denominator {nblk:,} blocks)", flush=True)
        for i in order.tolist():
            tv, cv = float(vals[i]), int(cnts[i])
            us = []
            for cc in (2.0 * tv, 4.0 * tv):
                if 3.0 <= cc < 6.0:
                    us.append(1.0 + math.log2(cc / 6.0))
            print(f"        t={tv:.8f}  {cv:>9,}  {100.0 * cv / nblk:6.3f}%   "
                  f"E2M1 clamp-set boundary at u = "
                  f"{', '.join(f'{x:.5f}' for x in us) if us else '-'}", flush=True)
        print(f"      distinct t values: {vals.numel():,} (a bf16 grid allows 256)", flush=True)

        rows, jumps, prev = [], [], None
        us = sorted(set([i / 2000.0 for i in range(0, 1201)]
                        + [1.0 - math.log2(1.5)]))
        max_norm = MAXNORM["E2M1"]
        agree = True
        for u in us:
            c = max_norm / 2.0 ** (1.0 - u)
            A = clamp_frexp(amax, c, max_norm)
            B = clamp_algebra(t, c, max_norm)
            if not torch.equal(A, B):
                agree = False
                check(False, f"K={K} u={u}: frexp instrument == algebra instrument")
                break
            fr = float(A.double().mean())
            rows.append((u, c, fr))
            if prev is not None and abs(fr - prev[2]) > 0.002:
                jumps.append((prev[0], u, prev[2], fr, c))
            prev = (u, c, fr)
        if agree:
            check(True, f"K={K} frexp == algebra, bitwise, on all {len(us)} u values")

        print(f"      clamp-fraction jumps > 0.2 pp between adjacent u (grid 0.0005 on [0,0.6])",
              flush=True)
        for u0, u1, f0, f1, c in jumps[:12]:
            print(f"        u {u0:.7f} -> {u1:.7f}   clamp {100 * f0:6.3f}% -> {100 * f1:6.3f}%"
                  f"   (+{100 * (f1 - f0):.3f} pp)   c={c:.9f}", flush=True)
        print(f"        total such jumps: {len(jumps)}", flush=True)

        u_ocp = 1.0 - math.log2(1.5)
        f_at = float(clamp_frexp(amax, 4.0, max_norm).double().mean())
        f_above = float(clamp_frexp(amax, float(np.nextafter(4.0, 5.0)), max_norm)
                        .double().mean())
        f_below = float(clamp_frexp(amax, float(np.nextafter(4.0, 3.0)), max_norm)
                        .double().mean())
        print(f"      OCP alignment c = 4 isolated  (u_spec = {u_ocp:.12f})", flush=True)
        print(f"        c = 4 - 1ulp : clamp {100 * f_below:.4f}%", flush=True)
        print(f"        c = 4        : clamp {100 * f_at:.4f}%", flush=True)
        print(f"        c = 4 + 1ulp : clamp {100 * f_above:.4f}%   "
              f"(+{100 * (f_above - f_at):.4f} pp)", flush=True)
        check(abs((f_above - f_at) - n_t1 / nblk) < 1e-12,
              f"K={K} the c=4+1ulp step is EXACTLY the t==1 atom",
              f"step {100 * (f_above - f_at):.4f} pp vs atom {100.0 * n_t1 / nblk:.4f}%")

        out["K"][K] = dict(nblk=nblk, n_t1=n_t1, pct_t1=100.0 * n_t1 / nblk,
                           ndistinct_t=int(vals.numel()),
                           clamp_c4=f_at, clamp_c4_plus=f_above, clamp_c4_minus=f_below,
                           top_atoms=[[float(vals[i]), int(cnts[i])] for i in order.tolist()],
                           jumps=[dict(u0=j[0], u1=j[1], f0=j[2], f1=j[3]) for j in jumps],
                           stair=[dict(u=r[0], c=r[1], clamp=r[2]) for r in rows])

    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           f"u_atoms_{a.tag}.json"), "w") as fh:
        json.dump(out, fh, indent=1)
    print(f"\n  {'ALL CHECKS PASSED' if not FAILED else 'FAILURES: ' + str(FAILED)}", flush=True)


if __name__ == "__main__":
    main()
