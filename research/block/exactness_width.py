"""At what accumulator width would summation order start to matter at campaign scale?

The perplexity experiment answers the question for a float32 accumulator and gets
"order moves perplexity by ~7e-6, which is ~14000x below the smallest margin the campaign
treats as meaningful". That is an answer about float32, not about the problem. An exact
ternary datapath does not compete with float32 accumulation on a CPU; it competes with
whatever the accelerator actually accumulates in.

So: hold the contraction fixed, vary ONLY the accumulator mantissa, and measure how the
order-induced scatter grows. No model, no perplexity -- this is a property of the
accumulator, measured directly, and it converts the perplexity result into a threshold.

Accumulation is a balanced binary tree at every width, so the comparison is fair: sequential
accumulation would flatter the wide accumulator by giving the narrow one O(n) error growth
that no real hardware would accept.
"""
import json
import math

import numpy as np

RNG = np.random.default_rng(20260811)
N = 2048            # a real contraction length in SmolLM2 / Qwen MLPs
TRIALS = 64         # independent dot products
PERMS = 24          # orderings per dot product
PHI = (1 + 5 ** 0.5) / 2


def round_mant(x, bits):
    """Round a float64 array to `bits` mantissa bits, keeping the float64 exponent range.

    Exponent range is deliberately NOT clipped: this isolates the precision axis from the
    overflow axis, which is a separate (and for an integer accumulator, non-existent) issue.
    """
    if bits >= 52:
        return x
    m, e = np.frexp(x)
    s = 2.0 ** bits
    return np.ldexp(np.rint(m * s) / s, e)


def tree_sum(v, bits):
    """Balanced pairwise sum with every partial result rounded to `bits` mantissa bits."""
    a = round_mant(v.astype(np.float64), bits)
    while a.shape[-1] > 1:
        n = a.shape[-1]
        if n % 2:
            a = np.concatenate([a, np.zeros(a.shape[:-1] + (1,))], axis=-1)
            n += 1
        a = round_mant(a[..., 0::2] + a[..., 1::2], bits)
    return a[..., 0]


# ---------------------------------------------------------------- self-tests
def fail(m):
    raise SystemExit(f"SELF-TEST FAILED: {m}\nNo numbers reported.")


# W1 round_mant really truncates to the stated mantissa
probe = np.array([1.0 + 2.0 ** -k for k in range(1, 20)])
for bits in (8, 11, 24):
    r = round_mant(probe, bits)
    reps = np.frexp(r)[0] * 2.0 ** bits
    if np.abs(reps - np.rint(reps)).max() > 1e-9:
        fail(f"round_mant({bits}) left a value off the {bits}-bit grid")
print("  W1 round_mant lands on the b-bit mantissa grid for b in 8,11,24  OK")

# W2 at 52 bits the tree sum reproduces float64 summation of an exactly-summable case
xi = RNG.integers(-4, 5, size=(3, N)).astype(np.float64)
if not np.allclose(tree_sum(xi, 52), xi.sum(-1), rtol=0, atol=0):
    fail("tree_sum at 52 bits disagrees with exact integer summation")
print("  W2 tree_sum(52 bits) is exact on integer data  OK")

# W3 an 8-bit-mantissa accumulator must be strictly worse than a 24-bit one on real data
tv = RNG.normal(size=(4, N)) * 0.02
ref = tv.sum(-1, dtype=np.float64)
e24 = np.abs(tree_sum(tv, 24) - ref).mean()
e8 = np.abs(tree_sum(tv, 8) - ref).mean()
if not e8 > e24 > 0:
    fail(f"width ordering violated: 8-bit {e8:.3e} vs 24-bit {e24:.3e}")
print(f"  W3 narrower accumulator is worse: 8-bit {e8:.2e} > 24-bit {e24:.2e} > 0  OK\n")

# ---------------------------------------------------------------- measurement
# Realistic terms: phi^k-quantised weights times a heavy-ish activation, as in an MLP.
w = PHI ** RNG.integers(-6, 1, size=(TRIALS, N)) * RNG.choice([-1.0, 1.0], (TRIALS, N))
x = RNG.standard_t(df=6, size=(TRIALS, N)) * 0.5
terms = w * x
# reference: math.fsum is correctly rounded, so this is the exact dot product
exact = np.array([math.fsum(t.tolist()) for t in terms])

# significand bits, implicit leading 1 included: fp64 53, fp32 24, fp16 11, bf16 8
WIDTHS = [("float64 (53)", 53), ("float32 (24)", 24), ("float16 (11)", 11),
          ("bfloat16 (8)", 8), ("6-bit", 6), ("4-bit", 4)]

rows = []
print(f"  {N}-term dot products, {TRIALS} trials x {PERMS} orderings, balanced tree sum")
print(f"  {'accumulator':16}{'order sd / |dot|':>20}{'vs float32':>14}")
for name, bits in WIDTHS:
    vals = np.empty((TRIALS, PERMS))
    for j in range(PERMS):
        p = RNG.permutation(N)
        vals[:, j] = tree_sum(terms[:, p], bits)
    scale = np.abs(exact).clip(1e-30)
    sd = (vals.std(axis=1, ddof=1) / scale).mean()
    rows.append({"accumulator": name, "mantissa_bits": bits, "order_sd_rel": float(sd)})
    print(f"  {name:16}{sd:20.3e}{'-' if name.startswith('float64') else '':>14}")

f32 = [r for r in rows if r["mantissa_bits"] == 24][0]["order_sd_rel"]
if not f32 > 0:
    fail("float32 accumulator showed zero order scatter -- nothing to scale from")
print(f"\n  MEASURED perplexity spread at float32 accumulation: 6.75e-6 ppl (SmolLM2, 40 windows)")
print(f"  smallest campaign margin: 0.0935 ppl  ->  order must grow {0.0935/6.75e-6:.0f}x to matter")
need = 0.0935 / 6.75e-6
for r in rows:
    r["ppl_spread_derived"] = 6.75e-6 * r["order_sd_rel"] / f32
    r["reaches_margin"] = bool(r["ppl_spread_derived"] >= 0.0935)
print(f"  {'accumulator':16}{'derived ppl spread':>22}{'>= 0.0935?':>13}")
for r in rows:
    print(f"  {r['accumulator']:16}{r['ppl_spread_derived']:22.3e}"
          f"{'YES' if r['reaches_margin'] else 'no':>13}")
print("\n  DERIVED, not measured: the ppl column assumes perplexity spread scales linearly with"
      "\n  accumulator scatter, which is only checked at the float32 point.")

json.dump({"n": N, "trials": TRIALS, "perms": PERMS, "rows": rows,
           "ppl_spread_fp32_measured": 6.75e-6, "smallest_margin": 0.0935,
           "growth_needed": need},
          open("/Users/ssdm4/Desktop/PROJECTS/CLAUDE/trinity-fpga/research/block/"
               "exactness_width.json", "w"), indent=1)
