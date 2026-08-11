#!/usr/bin/env python3
"""Campaign C: how steep is the perplexity surface in codebook space?

The KL codebook is a SMALL perturbation of normalised Lloyd-Max (levels 4 and 5
agree to five decimals) yet the two differ by 11.6% in perplexity. If perplexity
is that sensitive to small codebook perturbations, every codebook margin in this
repository is being read off a very steep surface and the SIZE of a margin says
less than it appears to.

Three measurements on SmolLM2-135M, 40 windows:
  1. INTERPOLATE  a straight line normalised-Lloyd-Max -> KL, 11 points.
  2. PERTURB      each interior MXFP4 level by +-1%, +-2%, +-5%, one at a time.
  3. RANDOM       15 codebooks at exactly 2% RMS relative distance from MXFP4.

Measurement path is NOT reimplemented: quant, perplexity, target_modules and
load_wikitext come from block_tnf.py by executing its source up to the driver
marker.

T38 (SCALE_PHASE_THEOREM): the E8M0 scale rounds up to a power of two, so a
codebook whose top is not a power of two sits at a different headroom phase.
EVERY codebook here is renormalised to top exactly 1.0 and that is ASSERTED.

Rulers must reproduce before any new number is quoted; the script exits non-zero
and does no further work if they miss.
"""
import json
import math
import os
import sys
import time

import numpy as np
import torch

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "block_tnf.py")
MARKER = 'print("загружаю модель…", flush=True)'
_s = open(SRC, encoding="utf-8").read()
if MARKER not in _s:
    raise SystemExit("driver marker not found in block_tnf.py")
ns = {}
exec(compile(_s.split(MARKER)[0], SRC, "exec"), ns)

fp_levels = ns["fp_levels"]
quant, perplexity, target_modules, load_wikitext = (
    ns[k] for k in ("quant", "perplexity", "target_modules", "load_wikitext"))
K, SEQLEN = ns["K"], ns["SEQLEN"]
W = os.path.dirname(ns["MODEL"])

torch.set_grad_enabled(False)

NWIN = int(os.environ.get("NWIN", "40"))
MDIR = os.environ.get("MDIR", "smollm2")
OUT = os.path.join(HERE, f"campaignC_sensitivity_{MDIR}.json")

# ---------------------------------------------------------------- codebooks --
def normalise(lv):
    """T38: top level exactly 1.0 so every codebook sits at headroom phase 0."""
    v = sorted(float(x) for x in lv)
    v = [x / v[-1] for x in v]
    v[-1] = 1.0
    return v


def check(name, lv):
    assert len(lv) == 8, (name, len(lv))
    assert lv[0] == 0.0, name
    assert all(lv[i] < lv[i + 1] for i in range(7)), (name, lv)
    assert abs(lv[-1] - 1.0) < 1e-12, f"{name}: top={lv[-1]} -- phase phi != 0"
    assert abs(math.log2(lv[-1]) % 1.0) < 1e-12, name
    return lv


MXFP4 = check("MXFP4", normalise(fp_levels(2, 1)))
LLOYD = check("Lloyd-Max", normalise(
    [0.0, 0.10334, 0.21079, 0.32491, 0.44963, 0.59031, 0.75635, 0.96567]))
KL = check("KL-opt", normalise(
    [0.0, 0.07701, 0.18828, 0.31396, 0.46561, 0.6113, 0.79074, 1.0]))
NSSE = check("nSSE-equal", normalise(
    [0.0, 0.09083, 0.18167, 0.28750, 0.40833, 0.55250, 0.73417, 1.0]))

RULERS = {"smollm2": {"nwin": 40, "fp32": 14.4874, "MXFP4": 21.9397,
                      "Lloyd-Max": 22.9166}}
# KL ruler from KL_CODEBOOK_WITHDRAWN_2026-08-11.md, same model/windows.
KL_RULER = 20.2586


def main():
    from transformers import AutoModelForCausalLM, AutoTokenizer
    path = os.path.join(W, MDIR)
    print(f"model={path}  NWIN={NWIN}  K={K}  SEQLEN={SEQLEN}", flush=True)
    tok = AutoTokenizer.from_pretrained(path)
    model = AutoModelForCausalLM.from_pretrained(path, dtype=torch.float32)
    model.eval()
    ids = tok(load_wikitext(), return_tensors="pt").input_ids
    flat = ids.reshape(-1)
    ntot = flat.numel() // SEQLEN
    win = flat[:ntot * SEQLEN].view(-1, SEQLEN)
    if ntot < NWIN:
        raise SystemExit(f"only {ntot} windows, need {NWIN}")
    lins = target_modules(model)
    print(f"{len(lins)} linear tensors quantised (lm_head excluded)", flush=True)
    if len(lins) == 0:
        raise SystemExit("zero target modules -- nothing would be quantised")
    orig = {n: m.weight.detach().clone() for n, m in lins}

    log = {"model": MDIR, "nwin": NWIN, "k": K, "seqlen": SEQLEN,
           "n_linear": len(lins), "codebooks": {}, "runs": []}

    def save():
        json.dump(log, open(OUT, "w"), indent=1)

    cache = {}

    def measure(tag, lv):
        """Perplexity of the model with every target Linear quantised to lv."""
        key = None if lv is None else tuple(round(x, 12) for x in lv)
        if key in cache:
            return cache[key]
        t0 = time.time()
        for n, m in lins:
            m.weight.copy_(orig[n] if lv is None else quant(orig[n], lv))
        p = perplexity(model, win[:NWIN].reshape(1, -1), NWIN)
        for n, m in lins:
            m.weight.copy_(orig[n])
        dt = time.time() - t0
        cache[key] = p
        log["runs"].append({"tag": tag, "ppl": p,
                            "levels": None if lv is None else list(lv),
                            "sec": dt})
        save()
        print(f"  {tag:<44}{p:>10.4f}   ({dt:.0f}s)", flush=True)
        return p

    # ===================== STAGE 0: RULERS ==================================
    print("\n=== STAGE 0: RULER CHECK ===", flush=True)
    base = measure("fp32", None)
    p_mx = measure("MXFP4 (E2M1)", MXFP4)
    p_ll = measure("Lloyd-Max normalised", LLOYD)
    p_kl = measure("KL-opt", KL)
    r = RULERS[MDIR]
    ok = True
    for key, got, exp_ in (("fp32", base, r["fp32"]),
                           ("MXFP4", p_mx, r["MXFP4"]),
                           ("Lloyd-Max", p_ll, r["Lloyd-Max"]),
                           ("KL-opt", p_kl, KL_RULER)):
        d = abs(got - exp_) / exp_
        good = d < 5e-4
        ok &= good
        print(f"  {key:<22} got {got:>9.4f}  expected {exp_:>9.4f}  "
              f"rel {d:.2e}  {'OK' if good else 'MISMATCH'}", flush=True)
    log["rulers_reproduce"] = bool(ok)
    log["baseline"] = {"fp32": base, "MXFP4": p_mx, "Lloyd": p_ll, "KL": p_kl}
    log["lloyd_vs_kl_pct"] = 100 * (p_ll / p_kl - 1)
    save()
    print(f"  RULERS {'REPRODUCE' if ok else 'DO NOT REPRODUCE'}", flush=True)
    if not ok:
        print("STOP: instrument does not reproduce; nothing new is measurable.")
        return 2
    print(f"  Lloyd-Max vs KL gap = {log['lloyd_vs_kl_pct']:+.2f}%", flush=True)

    # ===================== STAGE 1: INTERPOLATION ===========================
    print("\n=== STAGE 1: straight line Lloyd-Max -> KL, 11 points ===",
          flush=True)
    interp = []
    for i in range(11):
        t = i / 10.0
        lv = check(f"t={t}", normalise(
            [(1 - t) * a + t * b for a, b in zip(LLOYD, KL)]))
        p = measure(f"interp t={t:.1f}", lv)
        interp.append({"t": t, "ppl": p, "levels": lv})
    log["interp"] = interp
    save()

    # ===================== STAGE 2: ONE-LEVEL PERTURBATION ==================
    print("\n=== STAGE 2: one interior MXFP4 level at a time ===", flush=True)
    # interior = indices 1..6; index 0 is the exact zero, index 7 is the top
    # which renormalisation pins to 1.0 (T38), so neither is a free coordinate.
    DELTAS = (-0.05, -0.02, -0.01, 0.01, 0.02, 0.05)
    perturb = []
    for j in range(1, 7):
        for d in DELTAS:
            lv = list(MXFP4)
            lv[j] = MXFP4[j] * (1 + d)
            lv = check(f"lvl{j}{d:+}", normalise(lv))
            # renormalisation must be a no-op: interior levels never exceed top
            assert abs(lv[7] - 1.0) < 1e-12
            assert all(abs(lv[q] - MXFP4[q]) < 1e-12
                       for q in range(8) if q != j), "more than one level moved"
            p = measure(f"MXFP4 level[{j}]={MXFP4[j]:.5f} {d:+.0%}", lv)
            perturb.append({"level": j, "base": MXFP4[j], "delta": d,
                            "value": lv[j], "ppl": p})
    log["perturb"] = perturb
    save()

    # ===================== STAGE 3: RANDOM PERTURBATION =====================
    print("\n=== STAGE 3: 15 random codebooks at 2% RMS from MXFP4 ===",
          flush=True)
    RMS = 0.02
    rng = np.random.default_rng(20260811)
    rand = []
    for s in range(15):
        while True:
            e = rng.standard_normal(6)
            e = e / math.sqrt(float((e ** 2).mean())) * RMS   # exact 2% RMS
            lv = list(MXFP4)
            for j in range(1, 7):
                lv[j] = MXFP4[j] * (1 + float(e[j - 1]))
            if all(lv[i] < lv[i + 1] for i in range(7)):
                break
        lv = check(f"rand{s}", normalise(lv))
        assert abs(lv[7] - 1.0) < 1e-12
        got_rms = math.sqrt(float(np.mean(
            [(lv[j] / MXFP4[j] - 1) ** 2 for j in range(1, 7)])))
        assert abs(got_rms - RMS) < 1e-12, got_rms
        p = measure(f"random #{s:02d} (2% RMS)", lv)
        rand.append({"seed_idx": s, "rms": got_rms, "levels": lv, "ppl": p,
                     "eps": [float(x) for x in e]})
    log["random"] = rand
    save()

    # ===================== REPORT ==========================================
    print("\n" + "=" * 72)
    print(f"fp32 {base:.4f} | MXFP4 {p_mx:.4f} | Lloyd {p_ll:.4f} | "
          f"KL {p_kl:.4f}")

    print("\n--- 1. INTERPOLATION Lloyd-Max -> KL ---")
    print(f"{'t':>5}{'ppl':>11}{'vs MXFP4':>11}{'d ppl':>10}")
    prev = None
    for row in interp:
        dd = "" if prev is None else f"{row['ppl'] - prev:+10.4f}"
        print(f"{row['t']:>5.1f}{row['ppl']:>11.4f}"
              f"{100*(row['ppl']/p_mx-1):>+10.2f}%{dd:>10}")
        prev = row["ppl"]
    dif = np.diff([r["ppl"] for r in interp])
    mono = bool(np.all(dif <= 1e-9) or np.all(dif >= -1e-9))
    log["interp_monotone"] = mono
    log["interp_steps"] = [float(x) for x in dif]
    print(f"monotone along the path: {mono}")
    print(f"largest single-step drop: {float(dif.min()):+.4f} "
          f"({100*float(dif.min())/p_ll:+.2f}% of the Lloyd end)")

    print("\n--- 2. ONE-LEVEL GRADIENT (central difference on +-1%) ---")
    print(f"{'lvl':>4}{'value':>10}{'ppl-1%':>10}{'ppl+1%':>10}"
          f"{'dppl/dlevel':>13}{'dppl/dlnL':>11}{'%ppl per 1%':>13}")
    grads = []
    by = {(p["level"], p["delta"]): p["ppl"] for p in perturb}
    for j in range(1, 7):
        lo, hi = by[(j, -0.01)], by[(j, 0.01)]
        dppl_dl = (hi - lo) / (2 * 0.01 * MXFP4[j])
        dppl_dln = (hi - lo) / (2 * 0.01)
        pct = 100 * (hi - lo) / (2 * p_mx)
        grads.append({"level": j, "value": MXFP4[j], "ppl_minus1": lo,
                      "ppl_plus1": hi, "dppl_dlevel": dppl_dl,
                      "dppl_dlnlevel": dppl_dln, "pct_ppl_per_1pct": pct})
        print(f"{j:>4}{MXFP4[j]:>10.5f}{lo:>10.4f}{hi:>10.4f}"
              f"{dppl_dl:>+13.3f}{dppl_dln:>+11.4f}{pct:>+12.3f}%")
    log["gradients"] = grads
    print(f"\n{'lvl':>4}" + "".join(f"{d:>+10.0%}" for d in DELTAS)
          + "   (ppl, MXFP4 = %.4f)" % p_mx)
    for j in range(1, 7):
        print(f"{j:>4}" + "".join(f"{by[(j, d)]:>10.4f}" for d in DELTAS))
    print(f"\n{'lvl':>4}" + "".join(f"{d:>+10.0%}" for d in DELTAS)
          + "   (% vs MXFP4)")
    for j in range(1, 7):
        print(f"{j:>4}" + "".join(
            f"{100*(by[(j, d)]/p_mx-1):>+9.2f}%" for d in DELTAS))

    print("\n--- 3. RANDOM 2% RMS PERTURBATIONS ---")
    rp = np.array([r["ppl"] for r in rand])
    rel = 100 * (rp / p_mx - 1)
    print(f"{'#':>3}{'ppl':>11}{'vs MXFP4':>11}")
    for r_, x in zip(rand, rel):
        print(f"{r_['seed_idx']:>3}{r_['ppl']:>11.4f}{x:>+10.2f}%")
    stats = {"n": len(rp), "mean_ppl": float(rp.mean()),
             "sd_ppl": float(rp.std(ddof=1)),
             "min_ppl": float(rp.min()), "max_ppl": float(rp.max()),
             "mean_pct": float(rel.mean()), "sd_pct": float(rel.std(ddof=1)),
             "min_pct": float(rel.min()), "max_pct": float(rel.max()),
             "n_better": int((rp < p_mx).sum()),
             "n_worse": int((rp > p_mx).sum()),
             "range_pct": float(rel.max() - rel.min())}
    log["random_stats"] = stats
    print(f"\nmean {stats['mean_pct']:+.2f}%  sd {stats['sd_pct']:.2f}pp  "
          f"min {stats['min_pct']:+.2f}%  max {stats['max_pct']:+.2f}%  "
          f"span {stats['range_pct']:.2f}pp")
    print(f"better than MXFP4: {stats['n_better']}/{stats['n']}   "
          f"worse: {stats['n_worse']}/{stats['n']}")

    print("\n--- MARGINS THIS SPREAD HAS TO BE COMPARED AGAINST ---")
    p_nsse = measure("nSSE-equal (published -5.24%)", NSSE)
    log["nsse_ppl"] = p_nsse
    for nm, p in (("Lloyd-Max", p_ll), ("KL-opt", p_kl),
                  ("nSSE-equal", p_nsse)):
        print(f"  {nm:<14}{p:>10.4f}{100*(p/p_mx-1):>+10.2f}% vs MXFP4")
    save()
    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
