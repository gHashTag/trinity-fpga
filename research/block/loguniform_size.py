#!/usr/bin/env python3
"""CAMPAIGN C, phase 4 -- how big is the violation, and where does it come from?

S1  error bars on T39-ATTAINED, so a deviation can be called real or a tie
S2  the two DEPLOYED widths: E8M0 (m=0, MXFP4/OCP MX) and E4M3 (m=3, NVFP4)
S3  where the (integral sqrt p)^2 correction stops meaning anything (the lattice)
S4  mechanism: is the non-uniformity a property of max-of-32, or of these files?
"""
import os, sys, math, json
import numpy as np, torch
from scipy import stats

HERE = os.path.dirname(os.path.abspath(__file__))
W = ("/private/tmp/claude-501/-Users-ssdm4-Desktop-PROJECTS-CLAUDE/"
     "0e868af8-ab2d-4d00-be03-8fea94ba48e4/scratchpad/weights")
_s = open(os.path.join(HERE, "block_tnf.py"), encoding="utf-8").read()
ns = {}
exec(compile(_s.split('print("загружаю модель…", flush=True)')[0],
             "block_tnf.py", "exec"), ns)
target_modules, K = ns["target_modules"], ns["K"]
sys.path.insert(0, HERE)
from loguniform_verdict import (grid_geometric, grid_float, waste_vec, W as Wm,
                                paired_t, MODELS)

torch.set_grad_enabled(False)


def ci(v):
    m = v.mean()
    se = v.std(ddof=1) / math.sqrt(len(v))
    return float(m), float(se), (float(m - 1.96 * se), float(m + 1.96 * se))


def main():
    X = {k: np.load(os.path.join(HERE, f"loguniform_x_{k}.npy"))
         for k, _, _ in MODELS}
    out = {}

    print("=" * 84)
    print("S1.  T39-ATTAINED with error bars.  Is E[waste] = 2^-(m+1) a TIE or a MISS?")
    print("     ratio to 2^-(m+1), 95% CI. A CI containing 1.000 is a TIE.")
    print("=" * 84)
    print(f"{'m':>2}" + "".join(f"{lb:>21}" for _, lb, _ in MODELS))
    tabS1 = {}
    for m in range(0, 9):
        pred = 2.0 ** (-(m + 1))
        cells, row = [], []
        for k, _, _ in MODELS:
            v = waste_vec(X[k], grid_geometric(m))
            mu, se, (lo, hi) = ci(v)
            tie = lo / pred <= 1.0 <= hi / pred
            row.append(dict(ratio=mu / pred, lo=lo / pred, hi=hi / pred, tie=tie))
            cells.append(f"{mu/pred:>10.4f}[{lo/pred:.3f},{hi/pred:.3f}]"[:21].rjust(21))
        tabS1[m] = row
        print(f"{m:>2}" + "".join(cells))
    nties = sum(c["tie"] for m in tabS1 for c in tabS1[m])
    print(f"\n     ties (CI contains 1.000): {nties} of {9*4} cells."
          f"  Every other cell is a real miss.")
    out["S1"] = {str(m): tabS1[m] for m in tabS1}

    print()
    print("=" * 84)
    print("S2.  THE TWO DEPLOYED WIDTHS")
    print("=" * 84)
    print("     (a) m = 0  --  E8M0, what MXFP4 and every OCP MX format actually ships.")
    print("         T38/T39 corollary: E[waste] = 1/2 bit. No grid choice exists here.")
    print(f"     {'model':<15}{'E[waste] bits':>15}{'95% CI':>22}{'error vs 1/2':>14}")
    tabS2 = {}
    for k, lb, _ in MODELS:
        mu, se, (lo, hi) = ci(waste_vec(X[k], grid_geometric(0)))
        tabS2[k] = dict(m0=mu, ci=[lo, hi], err=mu - 0.5)
        print(f"     {lb:<15}{mu:>15.6f}   [{lo:.6f},{hi:.6f}]{mu-0.5:>+14.4f}")
    e = [abs(tabS2[k]["err"]) for k, _, _ in MODELS]
    print(f"         worst |error| = {max(e):.4f} bits = {max(e)/0.5*100:.1f}% of the"
          " predicted half-bit")

    print()
    print("     (b) m = 3  --  E4M3 scales, what NVFP4 ships. This is where")
    print("         T39-FLOAT's 1/(2 ln^2 2) = 1.0406845 is actually cashed.")
    print(f"     {'model':<15}{'geometric':>11}{'float':>11}{'ratio':>9}"
          f"{'95% CI on ratio':>22}{'predicted':>11}")
    for k, lb, _ in MODELS:
        a = waste_vec(X[k], grid_geometric(3))
        b = waste_vec(X[k], grid_float(3))
        r = b.mean() / a.mean()
        d = b - a
        se = d.std(ddof=1) / math.sqrt(len(d))
        lo, hi = (d.mean() - 1.96 * se) / a.mean() + 1, (d.mean() + 1.96 * se) / a.mean() + 1
        tabS2[k]["m3_ratio"] = float(r)
        tabS2[k]["m3_ci"] = [float(lo), float(hi)]
        print(f"     {lb:<15}{a.mean():>11.6f}{b.mean():>11.6f}{r:>9.4f}"
              f"   [{lo:.4f},{hi:.4f}]{1.0406845:>11.4f}")
    rs = [tabS2[k]["m3_ratio"] for k, _, _ in MODELS]
    print(f"         measured float penalty spans {(min(rs)-1)*100:.2f}% .."
          f" {(max(rs)-1)*100:.2f}%, against a predicted 4.07%")
    out["S2"] = tabS2

    print()
    print("=" * 84)
    print("S3.  WHERE THE DENSITY CORRECTION STOPS BEING A DENSITY CORRECTION")
    print("     (integral sqrt p)^2 estimated at increasing resolution. It is a")
    print("     valid asymptotic ratio only while the grid is much coarser than")
    print("     the checkpoint's mantissa lattice (bf16 128/oct, fp16 1024/oct).")
    print("=" * 84)
    print(f"     {'bins':>6}" + "".join(f"{lb:>16}" for _, lb, _ in MODELS))
    tabS3 = {}
    for B in (4, 8, 16, 32, 64, 128, 256, 1024):
        row = []
        for k, _, _ in MODELS:
            h, _ = np.histogram(X[k], bins=B, range=(0, 1))
            p = h / h.sum() * B
            row.append(float(np.sqrt(p).mean() ** 2))
        tabS3[B] = row
        print(f"     {B:>6}" + "".join(f"{v:>16.6f}" for v in row))
    out["S3"] = {str(b): tabS3[b] for b in tabS3}
    print("     (a fair reading: use 16 bins. Beyond ~2^t the estimate is measuring")
    print("      the storage lattice, where the true optimum is not a density at all)")

    print()
    print("=" * 84)
    print("S4.  MECHANISM.  Is this max-of-32 statistics, or these four files?")
    print("     control: replace each block by 32 iid Gaussians with the SAME rms,")
    print("     in float64 (no storage lattice), and remeasure.")
    print("=" * 84)
    from transformers import AutoModelForCausalLM
    print(f"     {'model':<15}{'real KS D':>11}{'ctrl KS D':>11}"
          f"{'real E[w]':>11}{'ctrl E[w]':>11}{'shuffled':>11}")
    tabS4 = {}
    rng = np.random.default_rng(7)
    for k, lb, _ in MODELS:
        mdl = AutoModelForCausalLM.from_pretrained(os.path.join(W, k),
                                                   dtype=torch.float32).eval()
        cs, sh = [], []
        for _, mod in target_modules(mdl):
            w = mod.weight.detach().double()
            n = (w.shape[1] // K) * K
            if n == 0:
                continue
            b = w[:, :n].reshape(-1, K).numpy()
            rms = np.sqrt((b ** 2).mean(1))
            g = rng.standard_normal(b.shape) * rms[:, None]
            cs.append(np.abs(g).max(1))
            # second control: same rms, but scale re-drawn log-uniform over an
            # octave -- this is exactly T39's assumption, and must come out flat
            sh.append(np.abs(g).max(1) * np.exp2(rng.random(len(rms))))
        del mdl
        xc = np.mod(np.log2(np.concatenate(cs)), 1.0)
        xs = np.mod(np.log2(np.concatenate(sh)), 1.0)
        dr = float(stats.kstest(X[k], "uniform").statistic)
        dc = float(stats.kstest(xc[:200000], "uniform").statistic)
        wr = Wm(X[k], grid_geometric(0))
        wc = Wm(xc, grid_geometric(0))
        ws = Wm(xs, grid_geometric(0))
        tabS4[k] = dict(real_D=dr, ctrl_D=dc, real_w=wr, ctrl_w=wc, shuf_w=ws)
        print(f"     {lb:<15}{dr:>11.4f}{dc:>11.4f}{wr:>11.6f}{wc:>11.6f}{ws:>11.6f}")
    out["S4"] = tabS4
    print("     'shuffled' = the same blocks with a log-uniform scale re-drawn over")
    print("      one octave: T39's assumption imposed by construction. It lands on")
    print("      0.5, which is the check that the measurement itself is not biased.")

    with open(os.path.join(HERE, "loguniform_size.json"), "w") as f:
        json.dump(out, f, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
