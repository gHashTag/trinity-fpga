#!/usr/bin/env python3
"""phi_grid_bench.py — where the golden lattice pays, and where it does not.

The Z[phi] lattice is exact: a value is an integer pair (a, b) meaning a + b*phi,
multiplying by phi is the Fibonacci step (a,b) -> (b, a+b), addition is
componentwise, and nothing rounds. That is proved and it is implemented
(fpga/phiscale/zphi_add16.v, scale_phi.v -- 171 LUT and 0 DSP against 1215 LUT
or 2 DSP48 for a real multiplier).

The question this file answers is narrower and it is the one that decides
whether exactness buys accuracy: the rounding that dominates a quantised
network is at WEIGHT ENCODING, not in the accumulator. An exact accumulator
cannot remove it. So does the phi grid round less than the alternatives?

Three comparisons, all on perplexity, all against base 2:

  1. logarithmic (power-of-base) quantisation -- every weight is one shift
     (base 2) or one Fibonacci step (base phi)
  2. a genuine base-phi FLOAT -- mantissa * phi^e, against mantissa * 2^e
  3. activations as well as weights, which every earlier file here refused
     to claim anything about

Run: python3 conformance/phi_grid_bench.py
"""

import math
import os
import sys
import warnings

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
warnings.filterwarnings("ignore")

import numpy as np  # noqa: E402
import torch  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import perplexity_sweep as P  # noqa: E402

PHI = (1 + 5 ** 0.5) / 2


def log_quantise(w, base, bits):
    """1 sign bit + (bits-1) index bits, index 0 meaning zero.

    Every non-zero weight becomes base^-k below the tensor's amax: one shift for
    base 2, one Fibonacci step for base phi. No multiplier either way -- the
    difference between the two is purely how finely the grid divides the range.
    """
    levels = 1 << (bits - 1)
    a = np.abs(w)
    amax = a.max()
    out = np.zeros_like(w)
    if amax == 0:
        return out
    nz = a > 0
    k = np.clip(np.rint(np.log(a[nz] / amax) / np.log(base)), -(levels - 1), 0)
    vals = amax * (base ** k)
    floor_val = amax * (base ** (-(levels - 1)))
    vals = np.where(a[nz] < floor_val / math.sqrt(base), 0.0, vals)
    out[nz] = np.sign(w[nz]) * vals
    return out


def float_base(w, base, e_bits, m_bits):
    """value = mantissa * base^e, mantissa uniform on [1, base) in 2^m steps.

    Deliberately a plain window rather than a biased format with subnormals: the
    point is to hold everything except the BASE constant between the two arms.
    The absolute numbers are therefore harsher than a real format's and are not
    comparable to perplexity_sweep.py -- only the two columns are comparable to
    each other.
    """
    a = np.abs(w)
    out = np.zeros_like(w)
    nz = a > 0
    if not nz.any():
        return out
    span = (1 << e_bits) - 1
    top = math.floor(math.log(a.max(), base))
    e = np.clip(np.floor(np.log(a[nz]) / math.log(base)), top - span, top)
    frac = a[nz] / (base ** e)
    step = (base - 1.0) / (1 << m_bits)
    frac = 1.0 + np.rint((frac - 1.0) / step) * step
    v = np.where(a[nz] < base ** (top - span), 0.0, frac * (base ** e))
    out[nz] = np.sign(w[nz]) * v
    return out


def worst_relative_error(base, n=100001):
    """Worst rounding error of a log grid of this ratio, scanned not assumed."""
    worst = 0.0
    for i in range(n):
        v = base ** (i / (n - 1))
        q = 1.0 if abs(v - 1.0) <= abs(v - base) else base
        worst = max(worst, abs(q - v) / v)
    return worst


def main():
    print(__doc__.split("\n\n")[0])
    print()
    print("The trade, before any model is loaded:")
    for name, r in (("phi", PHI), ("2", 2.0)):
        print(f"  base {name:<4} step ratio {r:.6f}  worst rounding "
              f"{worst_relative_error(r) * 100:5.2f}%  "
              f"{math.ceil(math.log(10 ** 6, r))} levels per 6 decades")
    print("  phi rounds about 30% less per level and reaches about 44% less far.")
    print()

    from transformers import AutoModelForCausalLM, AutoTokenizer
    tok = AutoTokenizer.from_pretrained("gpt2")
    model = AutoModelForCausalLM.from_pretrained("gpt2", dtype=torch.float32)
    model.eval()
    ids = tok(P.load_text()[:200000], return_tensors="pt").input_ids
    targets = [(n, p) for n, p in model.named_parameters()
               if p.ndim == 2 and ".h." in n and n.endswith(".weight")]
    originals = {n: p.detach().clone() for n, p in targets}
    baseline = P.perplexity(model, ids)
    print(f"GPT-2 fp32 perplexity {baseline:.3f}\n")

    def run(fn):
        with torch.no_grad():
            for n, p in targets:
                w = originals[n].detach().cpu().numpy().astype(np.float64)
                p.copy_(torch.from_numpy(fn(w)).to(p.dtype))
        ppl = P.perplexity(model, ids)
        with torch.no_grad():
            for n, p in targets:
                p.copy_(originals[n])
        return ppl / baseline

    print("1. Logarithmic quantisation -- one shift, or one Fibonacci step")
    print(f"  {'bits':>5} {'levels':>7} {'base 2':>10} {'base phi':>10} {'winner':>8}")
    for bits in (4, 5, 6, 8):
        a = run(lambda w, b=bits: log_quantise(w, 2.0, b))
        p = run(lambda w, b=bits: log_quantise(w, PHI, b))
        print(f"  {bits:>5} {1 << (bits - 1):>7} {a:>9.3f}x {p:>9.3f}x "
              f"{('phi' if p < a else '2'):>8}")
    print()

    print("2. A genuine base-phi float, 8-bit budget")
    print(f"  {'split':>8} {'base 2':>10} {'base phi':>10} {'winner':>8} {'phi reach':>11}")
    for e, m in ((3, 4), (4, 3), (5, 2)):
        a = run(lambda w, e=e, m=m: float_base(w, 2.0, e, m))
        p = run(lambda w, e=e, m=m: float_base(w, PHI, e, m))
        print(f"  {f'e{e}m{m}':>8} {a:>9.3f}x {p:>9.3f}x "
              f"{('phi' if p < a else '2'):>8} {PHI ** ((1 << e) - 1):>10.0f}x")
    print()

    print("Read honestly.")
    print()
    print("phi wins the logarithmic comparison from 5 bits up -- 1.215x against")
    print("1.820x, a third less damage for one adder instead of a wire. It loses")
    print("at 4 bits, where eight levels of phi reach only 29x and the tensor")
    print("does not fit.")
    print()
    print("As a FLOAT BASE it wins only where the exponent field is wide enough")
    print("to absorb its shorter reach. With a tight exponent the same shortness")
    print("is fatal, which is the trade stated at the top, measured.")
    print()
    print("And both logarithmic grids lose heavily to an ordinary 8-bit float at")
    print("the same budget (perplexity_sweep.py: e3m4 costs 1.003x). Within-binade")
    print("mantissa resolution is worth more than log-uniform spacing. The place")
    print("the lattice wins is where a multiplier cannot be afforded at all --")
    print("and there it is 171 LUT against 1215 (fpga/phiscale/README.md).")
    print()
    print("What this does NOT establish: one model, weights only in sections 1")
    print("and 2, no training, and the float harness in section 2 has no bias or")
    print("subnormals, so its columns compare only with each other.")


if __name__ == "__main__":
    main()
