"""What does exactness buy? Measure the perplexity spread caused by summation order alone.

The Z[phi] theorem gives order-independent accumulation: the same terms summed in any
order give bitwise the same result. Float32 does not. This script measures how much
perplexity moves when NOTHING changes except the order in which a linear layer's
contraction is summed -- so the campaign can say whether bit-reproducibility is a
correctness curiosity or a precondition for its own margins being real.

Construction. For every nn.Linear (lm_head excluded) draw a permutation P of the
in_features axis, permute the WEIGHT columns and the ACTIVATION components together:

    sum_k x[k] w[:,k]  ==  sum_k x[P[k]] w[:,P[k]]

Mathematically identical -- the same multiset of products -- so any change in output is
float non-associativity and nothing else. Weights are quantised in the NATURAL block
order first, so every arm holds bitwise identical weight VALUES; only their order differs.

Three regimes, because a spread measured in one regime says nothing about another:
    fp32        healthy control, no quantisation
    MXFP4-spec  E2M1 elements, OCP scale rule X=2^(floor(log2 amax)-emax), ties-to-even
    phi^k       pure phi grid: every nonzero weight is exactly +-phi^m, m integer
                (ladder phi^-6..phi^0, block scale phi^ceil(log_phi amax))

Every number below is preceded by self-tests that must pass. The campaign has already
been burned once by a harness that reported a broken quantiser as a result.
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
TAG = sys.argv[1] if len(sys.argv) > 1 else "smollm2"
NW = int(sys.argv[2]) if len(sys.argv) > 2 else 40
MODEL = os.path.join(WDIR, TAG)
K, SEQLEN = 32, 2048
PHI = (1 + 5 ** 0.5) / 2
LOGPHI = np.log(PHI)
torch.set_grad_enabled(False)
torch.set_num_threads(8)          # fixed: thread count changes GEMM reduction order

# ---------------------------------------------------------------- element grids
E2M1 = torch.tensor([0.0, .5, 1., 1.5, 2., 3., 4., 6.], dtype=torch.float64)
E2M1_EVEN = torch.tensor([1, 0, 1, 0, 1, 0, 1, 0], dtype=torch.bool)  # mantissa bit == 0
EMAX, MAXN = 2, 6.0
PHIL = torch.tensor([0.0] + [PHI ** (-k) for k in range(6, -1, -1)], dtype=torch.float64)


def q_e2m1(a):
    """|a| -> E2M1 magnitude, round-to-nearest-even on the mantissa bit, saturating at 6."""
    mid = (E2M1[:-1] + E2M1[1:]) / 2
    # bucketize(right=False) puts a value EQUAL to a boundary in the LOWER bin, so idx is
    # already the nearest level except at exact midpoints, where it is the lower candidate.
    idx = torch.bucketize(a, mid)
    hi = (idx + 1).clamp(max=len(E2M1) - 1)
    tie = (idx < len(E2M1) - 1) & (a == (E2M1[idx] + E2M1[hi]) / 2)
    idx = torch.where(tie & ~E2M1_EVEN[idx], hi, idx)   # tie -> the even-mantissa neighbour
    return E2M1[idx].clamp(max=MAXN)


def q_ladder(a, lad):
    """|a| -> nearest level of an arbitrary ascending ladder (ties to the lower level)."""
    return lad[torch.bucketize(a, (lad[:-1] + lad[1:]) / 2)]


def quant_mxfp4(w):
    n = (w.shape[1] // K) * K
    b = w[:, :n].reshape(-1, K).double()
    amax = b.abs().amax(dim=1).clamp(min=1e-30)
    s = torch.pow(2.0, torch.floor(torch.log2(amax)) - EMAX)      # OCP MX rule; max may clamp
    rec = torch.sign(b) * q_e2m1((b / s[:, None]).abs()) * s[:, None]
    out = w.clone()
    out[:, :n] = rec.reshape(-1, n)
    return out


def quant_phi(w):
    """Pure phi^k grid: scale phi^ceil(log_phi amax), ladder phi^-6..phi^0 -> value = +-phi^m."""
    n = (w.shape[1] // K) * K
    b = w[:, :n].reshape(-1, K).double()
    amax = b.abs().amax(dim=1).clamp(min=1e-300)
    # log(phi^m)/log(phi) lands a few ulp either side of the integer m, and a bare ceil()
    # then jumps an entire block one phi-step. The 1e-9 guard snaps those back; it is far
    # smaller than any real fractional exponent. (Caught by the idempotence self-test.)
    s = torch.pow(PHI, torch.ceil(torch.log(amax) / LOGPHI - 1e-9))   # amax/s <= 1, no clamp
    rec = torch.sign(b) * q_ladder((b / s[:, None]).abs(), PHIL) * s[:, None]
    out = w.clone()
    out[:, :n] = rec.reshape(-1, n)
    return out


REGIMES = {"fp32": None, "mxfp4": quant_mxfp4, "phi": quant_phi}

# ---------------------------------------------------------------- self-tests
def fail(msg):
    print(f"\n  SELF-TEST FAILED: {msg}\n  No numbers reported.")
    sys.exit(1)


def selftests():
    print("  self-tests")
    # T1 ladder shape
    r = (PHIL[2:] / PHIL[1:-1]).sub(PHI).abs().max().item()
    if len(PHIL) != 8 or r > 1e-12 or abs(PHIL[-1].item() - 1.0) > 0:
        fail(f"phi ladder malformed (max ratio dev {r})")
    print(f"    T1 phi ladder: 8 codes, consecutive ratio = phi to {r:.2e}, top = 1.0  OK")

    # T2 E2M1 ties-to-even on all seven exact midpoints, hand-computed
    mids = torch.tensor([.25, .75, 1.25, 1.75, 2.5, 3.5, 5.0], dtype=torch.float64)
    want = torch.tensor([0., 1., 1., 2., 2., 4., 4.], dtype=torch.float64)
    got = q_e2m1(mids)
    if not torch.equal(got, want):
        fail(f"E2M1 ties-to-even: got {got.tolist()} want {want.tolist()}")
    print(f"    T2 E2M1 ties-to-even on all 7 exact midpoints -> {want.tolist()}  OK")

    # T2b saturation and nearest away from ties
    probe = torch.tensor([0.1, 0.4, 0.6, 2.9, 4.9, 6.0, 7.5, 1e3], dtype=torch.float64)
    wantp = torch.tensor([0., .5, .5, 3., 4., 6., 6., 6.], dtype=torch.float64)
    if not torch.equal(q_e2m1(probe), wantp):
        fail(f"E2M1 nearest/saturate: got {q_e2m1(probe).tolist()}")
    print(f"    T2b E2M1 nearest + saturation at max_norm 6  OK")

    # T3 the phi arm really lands on the phi^k grid: log_phi|w| integral for every nonzero
    g = torch.Generator().manual_seed(7)
    w = torch.randn(64, 128, generator=g, dtype=torch.float64) * 0.03
    qw = quant_phi(w)
    nz = qw[qw != 0].abs()
    m = torch.log(nz) / LOGPHI
    dev = (m - m.round()).abs().max().item()
    if dev > 1e-9:
        fail(f"phi arm off the phi^k grid, max |log_phi|w| - round| = {dev}")
    print(f"    T3 every nonzero phi-arm weight is exactly +-phi^m: max dev {dev:.2e}, "
          f"{int(m.round().min())}..{int(m.round().max())} exponents used  OK")

    # T4 idempotence. A power-of-two scale is exact in binary float, so mxfp4 must be
    # BITWISE idempotent. A phi scale is not representable, so re-applying it round-trips
    # level*scale and moves values by ~1 ulp; what must NOT happen is a jump of a level or
    # a scale step, which would show as a relative change of phi-1 = 0.618 or 1/phi.
    if not torch.equal(quant_mxfp4(quant_mxfp4(w)), quant_mxfp4(w)):
        fail("mxfp4 quantiser not bitwise idempotent")
    a = quant_phi(w)
    b = quant_phi(a)
    rel = ((b - a).abs() / a.abs().clamp(min=1e-300))[a != 0].max().item()
    if rel > 1e-13:
        fail(f"phi quantiser jumped a level or scale step on re-application (rel {rel:.2e})")
    print(f"    T4 mxfp4 bitwise idempotent; phi idempotent to {rel:.2e} relative "
          f"(no level/scale jump; a jump would be >= 0.38)  OK")

    # T5 THE CRITICAL ONE: the permutation is mathematically the identity.
    # Integer-valued data small enough that every partial sum is exact in fp32,
    # so a correct reindexing must be BITWISE equal, with zero rounding cover.
    gi = torch.Generator().manual_seed(11)
    xi = torch.randint(-8, 9, (37, 256), generator=gi).float()
    wi = torch.randint(-8, 9, (53, 256), generator=gi).float()
    p = torch.randperm(256, generator=gi)
    y0 = F.linear(xi, wi)
    y1 = F.linear(xi[:, p], wi[:, p])
    if not torch.equal(y0, y1):
        fail("permutation changes an EXACT integer contraction -- reindexing is wrong")
    if y0.abs().max() > 2 ** 24:
        fail("integer self-test exceeded exact fp32 range")
    print(f"    T5 permuted == natural BITWISE on exact integer data "
          f"(max |y| = {int(y0.abs().max())} < 2^24)  OK")

    # T6 on real-valued data the same permutation DOES move the result -- the effect exists
    xf = torch.randn(64, 576, generator=gi)
    wf = torch.randn(1536, 576, generator=gi)
    pp = torch.randperm(576, generator=gi)
    z0 = F.linear(xf, wf)
    z1 = F.linear(xf[:, pp], wf[:, pp])
    rel = ((z0 - z1).abs().max() / z0.abs().mean()).item()
    if torch.equal(z0, z1):
        fail("permutation does not move a float32 contraction at all -- nothing to measure")
    print(f"    T6 on float32 the same permutation moves one GEMM by "
          f"{rel:.2e} of a typical output  OK")

    # T7 permutations are bijections
    perms = [torch.randperm(64, generator=torch.Generator().manual_seed(s)) for s in range(4)]
    for q in perms:
        if not torch.equal(q.sort().values, torch.arange(64)):
            fail("permutation is not a bijection")
    print("    T7 permutations are bijections  OK")
    print()


# ---------------------------------------------------------------- model plumbing
tok = AutoTokenizer.from_pretrained(MODEL)
import pyarrow.parquet as pq
_text = "\n\n".join(pq.read_table(os.path.join(WDIR, "wikitext2-test.parquet"))
                    .column("text").to_pylist())
_ids = tok(_text, return_tensors="pt").input_ids[0]
_n = (_ids.numel() // SEQLEN) * SEQLEN
X = _ids[:_n].reshape(-1, SEQLEN)[:NW]


def fresh():
    m = AutoModelForCausalLM.from_pretrained(MODEL, dtype=torch.float32)
    m.eval()
    return m


def targets(m):
    return [(nm, mod) for nm, mod in m.named_modules()
            if isinstance(mod, torch.nn.Linear)
            and not any(h in nm for h in ("lm_head", "embed_out"))]


def apply_perm(m, kind, seed):
    """kind: 'none' | 'id' | 'rev' | 'rand'. Returns number of layers wrapped."""
    if kind == "none":
        return 0
    n = 0
    for i, (nm, mod) in enumerate(targets(m)):
        d = mod.in_features
        if kind == "id":
            p = torch.arange(d)
        elif kind == "rev":
            p = torch.arange(d - 1, -1, -1)
        else:
            p = torch.randperm(d, generator=torch.Generator().manual_seed(seed * 100003 + i))
        mod.weight.data = mod.weight.data[:, p].contiguous()
        mod.register_forward_pre_hook(lambda _m, args, _p=p: (args[0][..., _p],) + args[1:])
        n += 1
    return n


def ppl(m):
    tot = 0.0
    for i in range(X.shape[0]):
        c = X[i:i + 1]
        tot += m(c, labels=c).loss.double().item()
    return float(np.exp(tot / X.shape[0]))


def build(regime, kind, seed, qcache):
    m = fresh()
    if regime != "fp32":
        for nm, mod in targets(m):
            mod.weight.data = qcache[nm].clone()
    nwrap = apply_perm(m, kind, seed)
    return m, nwrap


# ---------------------------------------------------------------- run
selftests()
print(f"  model {TAG}, {NW} windows of {SEQLEN} tokens "
      f"({X.shape[0]} used, {_n // SEQLEN} available), threads {torch.get_num_threads()}")

_m0 = fresh()
LAYERS = targets(_m0)
print(f"  linear layers permuted: {len(LAYERS)}")
QC = {}
for rg, fn in REGIMES.items():
    if fn is None:
        continue
    t0 = time.time()
    QC[rg] = {nm: fn(mod.weight.data.double()).float() for nm, mod in LAYERS}
    print(f"  quantised {rg}: {time.time()-t0:.1f}s")
del _m0

ORDERS = [("natural", "none", 0), ("identity", "id", 0), ("reverse", "rev", 0),
          ("rand1", "rand", 1), ("rand2", "rand", 2), ("rand3", "rand", 3),
          ("rand4", "rand", 4)]
if TAG != "smollm2":
    ORDERS = [o for o in ORDERS if o[0] in ("natural", "identity", "reverse", "rand1", "rand2")]

res = {}
for rg in ("fp32", "mxfp4", "phi"):
    res[rg] = {}
    print(f"\n  regime {rg}")
    for label, kind, seed in ORDERS:
        t0 = time.time()
        m, nw = build(rg, kind, seed, QC.get(rg))
        p = ppl(m)
        res[rg][label] = p
        print(f"    {label:9} ppl = {p:12.6f}   ({nw} layers wrapped, {time.time()-t0:.0f}s)",
              flush=True)
        del m
    # determinism of the instrument: repeat the natural arm, must be bitwise identical
    m, _ = build(rg, "none", 0, QC.get(rg))
    rep = ppl(m)
    del m
    ok = rep == res[rg]["natural"]
    res[rg]["natural_repeat"] = rep
    print(f"    {'repeat':9} ppl = {rep:12.6f}   instrument noise floor = "
          f"{abs(rep - res[rg]['natural']):.2e} {'(bitwise identical)' if ok else '(NOT identical!)'}")
    if not ok:
        print("    WARNING: run-to-run nondeterminism present; spread below is not order alone")

print("\n  SPREAD INDUCED BY SUMMATION ORDER ALONE")
print(f"  {'regime':8}{'natural':>13}{'min':>13}{'max':>13}{'spread':>12}{'sd':>11}")
summary = {}
for rg, r in res.items():
    vals = [v for k, v in r.items() if k not in ("natural_repeat",)]
    lo, hi = min(vals), max(vals)
    sd = float(np.std(vals, ddof=1))
    summary[rg] = {"natural": r["natural"], "min": lo, "max": hi,
                   "spread": hi - lo, "sd": sd,
                   "identity_delta": r["identity"] - r["natural"]}
    print(f"  {rg:8}{r['natural']:13.6f}{lo:13.6f}{hi:13.6f}{hi-lo:12.6f}{sd:11.6f}")

json.dump({"tag": TAG, "windows": int(X.shape[0]), "layers": len(LAYERS),
           "runs": res, "summary": summary},
          open(f"/Users/ssdm4/Desktop/PROJECTS/CLAUDE/trinity-fpga/research/block/"
               f"order_spread_{TAG}.json", "w"), indent=1)
print(f"\n  campaign margins for scale: phi-vs-2^k on Qwen 0.0935; "
      f"SmolLM2 1.145; MXFP4 tie-rule effect 0.129 (SmolLM2) / 0.0932 (Qwen)")
