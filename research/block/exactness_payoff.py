"""What does exact accumulation actually buy a language model?

order_spread.py asks: how far does perplexity move when only the SUMMATION ORDER of each
linear contraction changes?  That is a lower bound on what an order-independent accumulator
fixes -- it is the part of float error that reordering happens to expose.

This harness adds the STRONGER measurement, which bounds the payoff from above:

    arm 'exact'  =  every nn.Linear computes its dot product in float64 on the SAME float32
                    weight and activation values, then rounds once to float32.

    A product of two float32 numbers is exact in float64 (24+24 = 48 <= 53 bits), and 2048
    such products accumulate in float64 with relative error ~1e-16, i.e. ~1e-9 of a float32
    ulp.  So the 'exact' arm IS the Z[phi] accumulator, numerically: a correctly-rounded,
    order-independent dot product.  Nothing else in the network changes.

Therefore:
    ppl(fp32 accumulation) - ppl(exact accumulation)   =  the ENTIRE accuracy payoff of
                                                          exactness, not just its
                                                          order-dependent part.
    max-min over permutations of the fp32 arm          =  the reproducibility cost of NOT
                                                          having it.

Weights are quantised to the pure phi^k grid in the NATURAL block order once, and every arm
holds bitwise identical weight VALUES; only the contraction order and the accumulator differ.

Eight self-tests run before any number is printed.
"""
import os
import sys
import json
import time

import numpy as np
import torch
import torch.nn.functional as F
from transformers import AutoModelForCausalLM, AutoTokenizer

WDIR = ("/private/tmp/claude-501/-Users-ssdm4-Desktop-PROJECTS-CLAUDE/"
        "0e868af8-ab2d-4d00-be03-8fea94ba48e4/scratchpad/weights")
OUT = "/Users/ssdm4/Desktop/PROJECTS/CLAUDE/trinity-fpga/research/block"
TAG = sys.argv[1] if len(sys.argv) > 1 else "smollm2"
NW = int(sys.argv[2]) if len(sys.argv) > 2 else 8
THREADS = int(sys.argv[3]) if len(sys.argv) > 3 else 4
MODEL = os.path.join(WDIR, TAG)
K, SEQLEN = 32, 2048
PHI = (1 + 5 ** 0.5) / 2
LOGPHI = np.log(PHI)
torch.set_grad_enabled(False)
torch.set_num_threads(THREADS)      # fixed: thread count itself changes GEMM reduction order

PHIL = torch.tensor([0.0] + [PHI ** (-k) for k in range(6, -1, -1)], dtype=torch.float64)


def quant_phi(w):
    """Pure phi^k grid: block scale phi^ceil(log_phi amax), ladder phi^-6..phi^0.

    Every nonzero output is exactly +-phi^m for integer m -- checked by S1.
    The 1e-9 guard in the ceil() stops a value that IS phi^m (whose log lands a few ulp
    above the integer) from being kicked a whole phi-step up.
    """
    n = (w.shape[1] // K) * K
    b = w[:, :n].reshape(-1, K).double()
    amax = b.abs().amax(dim=1).clamp(min=1e-300)
    s = torch.pow(PHI, torch.ceil(torch.log(amax) / LOGPHI - 1e-9))
    a = (b / s[:, None]).abs()
    rec = torch.sign(b) * PHIL[torch.bucketize(a, (PHIL[:-1] + PHIL[1:]) / 2)] * s[:, None]
    out = w.clone()
    out[:, :n] = rec.reshape(-1, n)
    return out


class Lin(torch.nn.Module):
    """Drop-in for nn.Linear: optional contraction-axis permutation, optional exact accum."""

    def __init__(self, mod, perm, exact):
        super().__init__()
        w = mod.weight.data
        b = None if mod.bias is None else mod.bias.data
        if perm is not None:
            w = w[:, perm].contiguous()
        self.perm = perm
        self.exact = exact
        self.register_buffer("w", w)
        self.register_buffer("b", b if b is not None else torch.zeros(0))
        self.has_b = b is not None
        if exact:
            self.register_buffer("w64", w.double())
            self.register_buffer("b64", b.double() if b is not None else torch.zeros(0))

    def forward(self, x):
        if self.perm is not None:
            x = x[..., self.perm]
        if self.exact:
            return F.linear(x.double(), self.w64,
                            self.b64 if self.has_b else None).float()
        return F.linear(x, self.w, self.b if self.has_b else None)


def fail(msg):
    print(f"\n  SELF-TEST FAILED: {msg}\n  No numbers reported.")
    sys.exit(1)


# ------------------------------------------------------------------ data + model plumbing
tok = AutoTokenizer.from_pretrained(MODEL)
import pyarrow.parquet as pq
_t = "\n\n".join(pq.read_table(os.path.join(WDIR, "wikitext2-test.parquet"))
                 .column("text").to_pylist())
_ids = tok(_t, return_tensors="pt").input_ids[0]
_n = (_ids.numel() // SEQLEN) * SEQLEN
ALLW = _ids[:_n].reshape(-1, SEQLEN)
X = ALLW[:NW]


def fresh():
    m = AutoModelForCausalLM.from_pretrained(MODEL, dtype=torch.float32)
    m.eval()
    return m


def targets(m):
    return [(nm, mod) for nm, mod in m.named_modules()
            if isinstance(mod, torch.nn.Linear)
            and not any(h in nm for h in ("lm_head", "embed_out"))]


def swap(m, name, new):
    parent = m.get_submodule(name.rsplit(".", 1)[0]) if "." in name else m
    setattr(parent, name.rsplit(".", 1)[-1], new)


def build(quantise, kind, seed, exact, qc):
    m = fresh()
    names = [nm for nm, _ in targets(m)]
    for i, nm in enumerate(names):
        mod = m.get_submodule(nm)
        if quantise:
            mod.weight.data = qc[nm].clone()
        d = mod.in_features
        if kind == "none":
            p = None
        elif kind == "id":
            p = torch.arange(d)
        elif kind == "rev":
            p = torch.arange(d - 1, -1, -1)
        else:
            p = torch.randperm(d, generator=torch.Generator().manual_seed(seed * 100003 + i))
        swap(m, nm, Lin(mod, p, exact))
    return m, len(names)


def ppl(m, xs):
    tot = 0.0
    for i in range(xs.shape[0]):
        c = xs[i:i + 1]
        tot += m(c, labels=c).loss.double().item()
    return float(np.exp(tot / xs.shape[0]))


# ------------------------------------------------------------------ self-tests
def selftests(qc, names):
    print("  self-tests")

    # S1 the phi arm really lands on the phi^k grid.
    #    Two thresholds, because they test two different things:
    #      (a) in float64, where the quantiser works, the grid must be exact to 1e-9;
    #      (b) after the .float() cast used for inference, phi^m is NOT a float32 number,
    #          so the best achievable is float32 rounding: eps/ln(phi) = 6e-8/0.4812 = 1.2e-7.
    #          A deviation materially above that would mean a real grid error; below it is
    #          just storage. Worth stating on its own: the phi grid is already inexact the
    #          moment it is stored in float32, by 4.9e-8 relative (measured 1.01e-7 in
    #          exponent units x ln phi) -- the same order as, though ~11x smaller than, the
    #          5.2e-7 relative order-scatter of a 2048-term float32 dot product that
    #          exactness would remove. Neither is close to mattering; see exactness_width.py.
    m0 = fresh()
    dev64, dev32, lo, hi = 0.0, 0.0, 99, -99
    for nm, mod in targets(m0)[:12]:
        q64 = quant_phi(mod.weight.data.double())
        n64 = q64[q64 != 0].abs()
        mm = torch.log(n64) / LOGPHI
        dev64 = max(dev64, (mm - mm.round()).abs().max().item())
        lo, hi = min(lo, int(mm.round().min())), max(hi, int(mm.round().max()))
        n32 = qc[nm][qc[nm] != 0].abs().double()
        m32 = torch.log(n32) / LOGPHI
        dev32 = max(dev32, (m32 - m32.round()).abs().max().item())
    del m0
    if dev64 > 1e-9:
        fail(f"phi grid wrong in float64: max |log_phi|w| - round| = {dev64}")
    if dev32 > 3e-7:
        fail(f"phi grid wrong beyond float32 storage: max dev {dev32} (float32 limit 1.2e-7)")
    print(f"    S1 phi^m grid exact in float64 to {dev64:.2e}; after float32 storage "
          f"{dev32:.2e} (float32 floor 1.2e-7), exponents {lo}..{hi}  OK")

    # S2 permutations are bijections
    for s in (1, 2, 3):
        q = torch.randperm(576, generator=torch.Generator().manual_seed(s * 100003))
        if not torch.equal(q.sort().values, torch.arange(576)):
            fail("permutation is not a bijection")
    print("    S2 permutations are bijections  OK")

    # S3 the reindexing is mathematically the identity: integer data small enough that every
    #    partial sum is exact in fp32, so a correct permutation must be BITWISE equal.
    g = torch.Generator().manual_seed(11)
    xi = torch.randint(-8, 9, (37, 256), generator=g).float()
    wi = torch.randint(-8, 9, (53, 256), generator=g).float()
    p = torch.randperm(256, generator=g)
    y0, y1 = F.linear(xi, wi), F.linear(xi[:, p], wi[:, p])
    if float(y0.abs().max()) >= 2 ** 24:
        fail("integer self-test exceeded exact fp32 range")
    if not torch.equal(y0, y1):
        fail("permutation changes an EXACT integer contraction -- reindexing is wrong")
    print(f"    S3 permuted == natural BITWISE on exact integer data "
          f"(max |y| = {int(y0.abs().max())} < 2^24)  OK")

    # S4 on real data that same permutation DOES move fp32 -- there is an effect to measure
    xf = torch.randn(64, 576, generator=g)
    wf = torch.randn(1536, 576, generator=g)
    pp = torch.randperm(576, generator=g)
    z0, z1 = F.linear(xf, wf), F.linear(xf[:, pp], wf[:, pp])
    if torch.equal(z0, z1):
        fail("permutation does not move an fp32 contraction at all -- nothing to measure")
    r32 = float((z0 - z1).abs().max() / z0.abs().mean())
    print(f"    S4 fp32: the same permutation moves one GEMM by {r32:.2e} of a typical "
          f"output  OK")

    # S5 the exact wrapper is a correct linear: bitwise equal to fp32 where fp32 is exact
    e0 = F.linear(xi.double(), wi.double()).float()
    if not torch.equal(e0, y0):
        fail("fp64 accumulation path disagrees with fp32 on exactly-representable data")
    print("    S5 exact-accum path == fp32 BITWISE on exact integer data  OK")

    # S6 the exact arm is order-INDEPENDENT where fp32 is not -- and by a wide margin
    e1 = F.linear(xf[:, pp].double(), wf[:, pp].double()).float()
    ee = F.linear(xf.double(), wf.double()).float()
    r64 = float((ee - e1).abs().max() / ee.abs().mean())
    if r64 > 1e-6:
        fail(f"exact arm not order-stable (rel {r64:.2e})")
    if r32 <= 100 * max(r64, 1e-30):
        fail(f"instrument cannot separate the arms: fp32 {r32:.2e} vs exact {r64:.2e}")
    print(f"    S6 exact arm order-stable to {r64:.2e} vs fp32 {r32:.2e} "
          f"({r32 / max(r64, 1e-30):.0f}x separation)  OK")

    # S7 swapping nn.Linear -> Lin(perm=None, exact=False) changes NOTHING bitwise
    ma = fresh()
    mb, _ = build(False, "none", 0, False, None)
    c = ALLW[0:1, :256]
    la, lb = ma(c).logits, mb(c).logits
    if not torch.equal(la, lb):
        fail(f"module swap perturbs the model (max |d| = {float((la-lb).abs().max()):.3e})")
    print("    S7 nn.Linear -> Lin wrapper is BITWISE transparent on a real forward  OK")

    # S8 identity permutation is bitwise transparent too
    mc, _ = build(False, "id", 0, False, None)
    lc = mc(c).logits
    if not torch.equal(la, lc):
        fail(f"identity permutation perturbs the model "
             f"(max |d| = {float((la-lc).abs().max()):.3e})")
    print("    S8 identity permutation is BITWISE transparent on a real forward  OK")
    del ma, mb, mc
    print()


# ------------------------------------------------------------------ run
_m0 = fresh()
LAY = targets(_m0)
NAMES = [nm for nm, _ in LAY]
t0 = time.time()
QC = {nm: quant_phi(mod.weight.data.double()).float() for nm, mod in LAY}
print(f"  quantised phi^k: {len(QC)} tensors, {time.time()-t0:.1f}s")
del _m0

selftests(QC, NAMES)
print(f"  model {TAG}, {X.shape[0]} windows of {SEQLEN} tokens "
      f"({ALLW.shape[0]} available), threads {torch.get_num_threads()}\n")

ARMS = [
    ("fp32acc/natural",  True,  "none", 0, False),
    ("fp32acc/identity", True,  "id",   0, False),
    ("fp32acc/reverse",  True,  "rev",  0, False),
    ("fp32acc/rand1",    True,  "rand", 1, False),
    ("fp32acc/rand2",    True,  "rand", 2, False),
    ("fp32acc/rand3",    True,  "rand", 3, False),
    ("exact/natural",    True,  "none", 0, True),
    ("exact/rand1",      True,  "rand", 1, True),
]
if os.environ.get("ARMS") == "lite":      # bigger model: drop the two redundant controls
    ARMS = [a for a in ARMS if a[0] not in ("fp32acc/identity", "fp32acc/rand3")]

res = {}
for label, q, kind, seed, ex in ARMS:
    t0 = time.time()
    m, nl = build(q, kind, seed, ex, QC)
    p = ppl(m, X)
    res[label] = p
    del m
    print(f"    {label:17} ppl = {p:13.7f}   ({nl} layers, {time.time()-t0:.0f}s)", flush=True)

# determinism floor: repeat the reference arm, must be bitwise identical
m, _ = build(True, "none", 0, False, QC)
rep = ppl(m, X)
del m
det = abs(rep - res["fp32acc/natural"])
print(f"    {'repeat':17} ppl = {rep:13.7f}   determinism floor = {det:.2e}"
      f"{'  (bitwise identical)' if rep == res['fp32acc/natural'] else '  (NOT identical!)'}")

fp = [v for k, v in res.items() if k.startswith("fp32acc/")]
ordspread = max(fp) - min(fp)
payoff = res["fp32acc/natural"] - res["exact/natural"]
exact_ord = abs(res["exact/natural"] - res["exact/rand1"])

print(f"\n  ORDER SPREAD (fp32 accumulation, 6 orders):  {ordspread:.7f} ppl "
      f"(sd {np.std(fp, ddof=1):.7f})")
print(f"  EXACTNESS PAYOFF  ppl(fp32acc) - ppl(exact):  {payoff:+.7f} ppl")
print(f"  residual order effect INSIDE the exact arm:   {exact_ord:.7f} ppl")
print(f"  campaign margins for scale: phi-vs-2^k Qwen 0.0935, SmolLM2 1.145; "
      f"MXFP4 tie-rule 0.129 / 0.0932")

json.dump({"tag": TAG, "windows": int(X.shape[0]), "layers": len(LAY),
           "threads": THREADS, "runs": res, "repeat": rep,
           "determinism_floor": det, "order_spread_fp32acc": ordspread,
           "order_sd_fp32acc": float(np.std(fp, ddof=1)),
           "exactness_payoff": payoff, "exact_arm_order_effect": exact_ord},
          open(os.path.join(OUT, f"exactness_payoff_{TAG}.json"), "w"), indent=1)
