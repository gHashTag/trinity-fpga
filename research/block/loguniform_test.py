#!/usr/bin/env python3
"""CAMPAIGN C, phase 1 -- is T39's log-uniformity assumption true?

T39 (GRID_OPTIMALITY_THEOREM_2026-08-11.md) proves that expected headroom waste
is (1/2) sum g_i^2, minimised uniquely by equal log-spacing, at 2^-(m+1) bits.
Every line of that proof assumes BLOCK MAXIMA ARE LOG-UNIFORM inside an octave,
i.e. that x = frac(log2 a_max) is uniform on [0,1). The document states the
assumption and does not test it. This tests it.

For each of the four models: every K=32 block of every quantised linear layer
(exactly the blocks block_tnf.quant would make), x = frac(log2 a_max).
Reported: histogram, Kolmogorov-Smirnov against U[0,1), and the measured mean of
the E8M0 waste 1 - x against T38/T39's predicted 1/2.

Writes the raw x samples to loguniform_x_<model>.npy for phase 2.
"""
import os, sys, math, json
import numpy as np, torch

HERE = os.path.dirname(os.path.abspath(__file__))
W = ("/private/tmp/claude-501/-Users-ssdm4-Desktop-PROJECTS-CLAUDE/"
     "0e868af8-ab2d-4d00-be03-8fea94ba48e4/scratchpad/weights")

# ---- reuse the measurement harness, never reimplement it --------------------
_s = open(os.path.join(HERE, "block_tnf.py"), encoding="utf-8").read()
ns = {}
exec(compile(_s.split('print("загружаю модель…", flush=True)')[0],
             "block_tnf.py", "exec"), ns)
quant, perplexity, target_modules, load_wikitext = (ns[k] for k in
    ("quant", "perplexity", "target_modules", "load_wikitext"))
K, SEQLEN = ns["K"], ns["SEQLEN"]
fp_levels, q_e8m0_t = ns["fp_levels"], ns["q_e8m0_t"]

# ---- T38 hygiene: every codebook normalised to top exactly 1.0, phase phi=0 --
for nm, lv in (("MXFP4 E2M1", fp_levels(2, 1)), ("MXFP6 E2M3", fp_levels(2, 3)),
               ("int4", ns["uniform_levels"](4))):
    top = sorted(lv)[-1]
    assert top == 1.0, f"{nm} top is {top!r}, not 1.0 -- phase phi != 0"
    assert math.log2(top) % 1.0 == 0.0, f"{nm} phase phi != 0"
print("T38 hygiene: all codebooks top == 1.0 exactly, phi = 0.  ok", flush=True)
# With T = 1 the scale rule s = 2^ceil(log2(a_max / T)) is s = 2^ceil(log2 a_max),
# so the headroom waste of a block is exactly 1 - frac(log2 a_max).

MODELS = [("smollm2", "SmolLM2-135M"), ("qwen", "Qwen2.5-0.5B"),
          ("pythia", "Pythia-160M"), ("opt", "OPT-125M")]

torch.set_grad_enabled(False)


def block_maxima(model):
    """Exactly the blocks block_tnf.quant forms: w[:, :n].reshape(-1, K).amax."""
    out = []
    nz = 0
    for _, m in target_modules(model):
        w = m.weight.detach().double()
        n = (w.shape[1] // K) * K
        if n == 0:
            continue
        a = w[:, :n].reshape(-1, K).abs().amax(dim=1)
        nz += int((a <= 0).sum())
        out.append(a[a > 0].numpy())
    return np.concatenate(out), nz


def ks_uniform(x):
    """Two-sided KS statistic of x against U[0,1), plus the asymptotic p."""
    from scipy import stats
    r = stats.kstest(x, "uniform")
    return float(r.statistic), float(r.pvalue)


def main():
    from transformers import AutoModelForCausalLM
    rows = []
    for key, label in MODELS:
        print(f"\n=== {label} ===", flush=True)
        mdl = AutoModelForCausalLM.from_pretrained(os.path.join(W, key),
                                                   dtype=torch.float32)
        mdl.eval()
        a, nz = block_maxima(mdl)
        del mdl
        la = np.log2(a)
        x = np.mod(la, 1.0)                      # frac(log2 a_max), in [0,1)
        np.save(os.path.join(HERE, f"loguniform_x_{key}.npy"), x)

        d, p = ks_uniform(x)
        # E8M0 headroom waste. T38 Prop 2: it is 1 - frac(log2 a), AND 0 when the
        # fractional part is 0. Writing plain 1 - x gets the second clause wrong,
        # and 0.11-0.90 % of real blocks are in it (a_max an exact power of two,
        # which happens because checkpoints store bf16/fp16 mantissas).
        waste = np.where(x == 0.0, 0.0, 1.0 - x)
        # circular first harmonic -- this is what makes the phase matter at m=0
        c1 = np.mean(np.cos(2 * np.pi * x))
        s1 = np.mean(np.sin(2 * np.pi * x))
        r1 = math.hypot(c1, s1)
        se = 1.0 / math.sqrt(len(x)) * np.std(waste, ddof=1) * math.sqrt(len(x)) / math.sqrt(len(x))
        se = float(np.std(waste, ddof=1) / math.sqrt(len(x)))

        hist, _ = np.histogram(x, bins=20, range=(0, 1))
        dens = hist / hist.sum() * 20            # density, 1.0 == uniform

        print(f"  blocks {len(x):,}  (zero-max blocks excluded: {nz:,})")
        print(f"  binades spanned by log2 a_max: "
              f"{la.min():.3f} .. {la.max():.3f}  ({la.max()-la.min():.2f} octaves)")
        print(f"  mean x        = {x.mean():.6f}   (uniform: 0.5)")
        print(f"  E[waste]      = {waste.mean():.6f} +- {se:.6f} bits"
              f"   (T38/T39 predict 0.5)")
        print(f"  KS vs U[0,1)  D = {d:.6f}   p = {p:.3e}")
        print(f"  first harmonic |r1| = {r1:.6f}  (0 for uniform)")
        print("  density by 20 bins (1.000 == uniform):")
        for i in range(0, 20, 5):
            print("    " + " ".join(f"{v:5.3f}" for v in dens[i:i + 5]))
        rows.append(dict(model=label, key=key, blocks=int(len(x)),
                         zero_blocks=int(nz),
                         octaves=float(la.max() - la.min()),
                         mean_x=float(x.mean()), E_waste=float(waste.mean()),
                         se_waste=se, ks_D=d, ks_p=p, r1=r1,
                         density20=[float(v) for v in dens]))

    with open(os.path.join(HERE, "loguniform_test.json"), "w") as f:
        json.dump(rows, f, indent=1)
    print("\n=== SUMMARY ===")
    print(f"{'model':<16}{'blocks':>12}{'E[waste]':>11}{'pred':>7}{'KS D':>9}{'|r1|':>9}")
    for r in rows:
        print(f"{r['model']:<16}{r['blocks']:>12,}{r['E_waste']:>11.4f}"
              f"{0.5:>7.3f}{r['ks_D']:>9.4f}{r['r1']:>9.4f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
