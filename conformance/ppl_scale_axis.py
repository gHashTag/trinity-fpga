#!/usr/bin/env python3
"""The scale-format axis, measured on perplexity.

The stop-rule memory closed this axis on NRMSE only (SCALE_AXIS_2026-08-09.md):
TNF-scale (3 balanced-ternary trits of exponent + 3 mantissa bits) tied ue5m3 at
1.006 on synthetic Normal weights. NRMSE and perplexity have disagreed on this
programme before (METRIC_DISAGREEMENT_2026-08-11.md), so the tie is re-asked on
the metric the stop-rule actually names: wikitext-2 perplexity of a live model.

WHAT IS HELD FIXED (identical for every candidate):
  element format   FP4 E2M1, levels {0, .5, 1, 1.5, 2, 3, 4, 6}  (all 8 codes,
                   no Inf/NaN reservation -- OCP MX elements are all finite)
  block            K=32 along the contraction (last) axis of every nn.Linear
                   weight except lm_head; embeddings/norms stay fp32
  ideal scale      s = amax / 6           (E2M1 top = 6)
  reconstruction   w_hat = sign(w) * nearest_E2M1(|w| / q(s)) * q(s)

WHAT VARIES: the scale codec q(.), one of
  fp32    unquantised scale (the floor set by element quantisation alone)
  e8m0    2^round(log2 s)                       -- original MX, 8 bits
  ue4m3   unsigned minifloat, 4 exp + 3 mant    -- NVFP4-style, 8 bits (probe's
          codec: no per-tensor renormalisation, which real NVFP4 adds)
  ue5m3   unsigned minifloat, 5 exp + 3 mant    -- IBM arXiv:2601.19026, 8 bits
  tnf33   3 balanced-ternary trits of exponent (e in [-13, 13]) + 3 mantissa
          bits -- the SCALE_AXIS_2026-08-09 tie config, ~7.75 bits (216 codes)

PROVENANCE OF THE INSTRUMENTS (reused, not reimplemented):
  - scale quantisers: research/block/scale_axis_probe.py, imported directly and
    used as the oracle for the vectorised torch ports (exact-match gate below).
    tnf33 is q_scale_tef8's codec with ET=3, MB=1->3, the doc's tie row.
  - evaluation loop and settings: research/block/block_tnf.py, the 2026-08-10
    block-axis pipeline (SmolLM2-135M fp32, wikitext-2 test, 40 windows of
    2048 tokens, ruler band 10 < ppl_base < 60).

CONVENTION NOTE (MXFP4_SCALE_CONVENTION_2026-08-11.md): this file quantises
s = amax/6 through the candidate codec. block_tnf.py's E8M0 row quantised amax
against a top-1-normalised codebook with ceil -- a different, non-commuting
convention worth up to 7.3%. Rows here are therefore comparable WITH EACH OTHER
and with this file's own fp32 baseline, not digit-for-digit with the 2026-08-10
MXFP4 rows.

DETERMINISM: no randomness in the measurement path (deterministic quantisation,
fixed first-40 windows). Seeds fixed anyway for the port self-check sampling.
Model: HuggingFaceTB/SmolLM2-135M snapshot 93efa2f097d58c2a74874c7e644dbc9b0cee75a2
Data:  Salesforce/wikitext wikitext-2-raw-v1 test parquet, dataset snapshot
       b08601e04326c79dfdd32d625aee71d232d685c3
"""
import math
import os
import random
import sys

import numpy as np
import torch

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "research", "block"))
import scale_axis_probe as probe  # noqa: E402  (the 2026-08-09 scale quantisers)

MODEL = os.path.expanduser(
    "~/.cache/huggingface/hub/models--HuggingFaceTB--SmolLM2-135M/"
    "snapshots/93efa2f097d58c2a74874c7e644dbc9b0cee75a2")
WIKI = os.path.expanduser(
    "~/.cache/huggingface/hub/datasets--Salesforce--wikitext/"
    "snapshots/b08601e04326c79dfdd32d625aee71d232d685c3/"
    "wikitext-2-raw-v1/test-00000-of-00001.parquet")

K, SEQLEN, NWIN = 32, 2048, 40
torch.set_grad_enabled(False)
torch.manual_seed(20260819)
random.seed(20260819)
np.random.seed(20260819)


# ---------------------------------------------------------------- scale codecs
def q_scale_tnf33(s):
    """The SCALE_AXIS_2026-08-09 tie config: scale_axis_probe.q_scale_tef8's
    codec with ET=3 trits (3^3 = 27 exponent codes, e in [-13, 13]) and MB=3
    binary mantissa bits. 27 * 8 = 216 codes ~ 7.75 bits."""
    if s <= 0:
        return 0.0
    ET = 3
    MB = 3
    half = (3 ** ET - 1) // 2
    e = math.floor(math.log2(s))
    e = max(-half, min(e, half))
    frac = s / 2.0 ** e - 1.0
    m = round(frac * (1 << MB))
    if m == (1 << MB):
        e, m = e + 1, 0
    return (1 + m / (1 << MB)) * 2.0 ** e


def t_e8m0(s):
    return torch.pow(2.0, torch.round(torch.log2(s)))


def t_fp(s, eb, mb):
    bias = (1 << (eb - 1)) - 1
    e = torch.floor(torch.log2(s)).clamp(1 - bias, (1 << eb) - 2 - bias)
    frac = s / torch.pow(2.0, e) - 1.0
    m = torch.round(frac * (1 << mb))
    e = e + (m == (1 << mb)).to(e.dtype)
    m = torch.where(m == (1 << mb), torch.zeros_like(m), m)
    return (1 + m / (1 << mb)) * torch.pow(2.0, e)


def t_tnf33(s):
    half = float((3 ** 3 - 1) // 2)          # 13
    e = torch.floor(torch.log2(s)).clamp(-half, half)
    frac = s / torch.pow(2.0, e) - 1.0
    m = torch.round(frac * 8)
    e = e + (m == 8).to(e.dtype)
    m = torch.where(m == 8, torch.zeros_like(m), m)
    return (1 + m / 8) * torch.pow(2.0, e)


ARMS = [
    # (label, torch codec or None for the unquantised-scale floor)
    ("fp32 scale (floor)", None),
    ("e8m0 (MX)", t_e8m0),
    ("ue4m3 (NVFP4-style)", lambda s: t_fp(s, 4, 3)),
    ("ue5m3 (IBM)", lambda s: t_fp(s, 5, 3)),
    ("TNF-scale 3t+3m", t_tnf33),
]


# --------------------------------------------------- port self-check (a gate)
def check_ports():
    """The torch ports must agree with scale_axis_probe's scalar codecs.
    A verifier that has not itself been verified is a second instrument, not a
    check (iteration 104's lesson). Refuse to measure if the port drifts."""
    rng = random.Random(20260819)
    samples = [2.0 ** rng.uniform(-20, 12) for _ in range(20000)]
    samples += [2.0 ** k for k in range(-20, 13)]                  # exact powers
    samples += [2.0 ** k * 1.0625 for k in range(-16, 9)]
    pairs = [
        ("e8m0", probe.q_scale_e8m0, t_e8m0),
        ("ue4m3", probe.q_scale_ue4m3, lambda s: t_fp(s, 4, 3)),
        ("ue5m3", probe.q_scale_ue5m3, lambda s: t_fp(s, 5, 3)),
        ("tnf33", q_scale_tnf33, t_tnf33),
    ]
    t = torch.tensor(samples, dtype=torch.float64)
    for name, scalar_fn, torch_fn in pairs:
        want = torch.tensor([scalar_fn(s) for s in samples], dtype=torch.float64)
        got = torch_fn(t)
        bad = (want != got)
        if bad.any():
            i = int(bad.nonzero()[0])
            sys.exit(f"PORT MISMATCH {name}: s={samples[i]!r} "
                     f"scalar={float(want[i])!r} torch={float(got[i])!r} "
                     f"({int(bad.sum())} of {len(samples)}) -- refusing to measure.")
        print(f"  port check {name:6s}: {len(samples)} samples, exact match")


# ------------------------------------------------------------- quantisation
LV = torch.tensor([0.0, 0.5, 1.0, 1.5, 2.0, 3.0, 4.0, 6.0], dtype=torch.float64)
BND = (LV[:-1] + LV[1:]) / 2


def quantise_weight(w, scale_fn):
    """Block-scaled E2M1 quantisation along the contraction (last) axis.
    scale_fn None => unquantised fp32 scale (the floor)."""
    n = (w.shape[1] // K) * K
    if n == 0:
        return w, 0, 0
    head = w[:, :n].reshape(-1, K).double()
    amax = head.abs().amax(dim=1)
    s_ideal = amax / 6.0
    s_q = s_ideal if scale_fn is None else scale_fn(s_ideal.clamp(min=1e-300))
    s_q = torch.where(amax > 0, s_q, torch.zeros_like(s_q))
    y = (head / s_q.clamp(min=1e-300)[:, None]).abs().clamp(max=6.0)
    idx = torch.bucketize(y, BND)
    rec = torch.sign(head) * LV[idx] * s_q[:, None]
    out = w.clone()
    out[:, :n] = rec.reshape(-1, n).to(w.dtype)
    nz_blocks = int((amax > 0).sum())
    dead = int(((s_q == 0) & (amax > 0)).sum())    # live block, zeroed scale
    return out, nz_blocks, dead


def target_modules(model):
    return [(n, m) for n, m in model.named_modules()
            if isinstance(m, torch.nn.Linear) and "lm_head" not in n]


# ------------------------------------------------------------------- eval loop
def perplexity(model, ids, limit_windows=None):
    """Verbatim from research/block/block_tnf.py (the 2026-08-10 pipeline)."""
    flat = ids.reshape(-1)
    n = (flat.numel() // SEQLEN) * SEQLEN
    x = flat[:n].view(-1, SEQLEN)
    if limit_windows:
        x = x[:limit_windows]
    nll = cnt = 0.0
    for i in range(x.shape[0]):
        c = x[i:i + 1]
        nll += model(c, labels=c).loss.double().item() * (SEQLEN - 1)
        cnt += SEQLEN - 1
    return float(np.exp(nll / cnt))


def block_scales():
    """Ideal block scales s = amax/6 of every quantisable weight, from the
    checkpoint directly (no model forward needed)."""
    from safetensors.torch import load_file
    sd = load_file(os.path.join(MODEL, "model.safetensors"))
    out = []
    for name, w in sd.items():
        if w.ndim != 2 or "embed" in name or "norm" in name:
            continue
        n = (w.shape[1] // K) * K
        if n == 0:
            continue
        a = w[:, :n].reshape(-1, K).double().abs().amax(dim=1)
        out.append(a[a > 0] / 6.0)
    return torch.cat(out)


def diagnose():
    """The mechanism numbers quoted in research/PPL_SCALE_AXIS_2026-08-19.md,
    recomputable without the perplexity loop."""
    s = block_scales()
    tot = s.numel()
    print(f"blocks with amax>0: {tot}")
    lo, hi = math.log2(float(s.min())), math.log2(float(s.max()))
    print(f"occupied ideal-scale range: log2 s in [{lo:.2f}, {hi:.2f}]"
          f"  ({hi - lo:.2f} binades)")
    # (1) TNF-scale vs ue5m3: identical function on the occupied range?
    diff = int((t_tnf33(s) != t_fp(s, 5, 3)).sum())
    print(f"tnf33 vs ue5m3 quantised scales differing: {diff} of {tot}")
    # (2) ue4m3 failure-region occupancy
    sub = int((s < 2.0 ** -6).sum())
    print(f"blocks below ue4m3 min normal 2^-6: {sub} = {100 * sub / tot:.3f}%")
    dead = int((t_fp(s, 4, 3) == 0).sum())
    print(f"blocks ue4m3 collapses to scale 0: {dead}")
    # (3) e8m0 round-to-nearest underscaling (clips the block max)
    for label, q in (("e8m0 round", t_e8m0(s)), ("tnf33", t_tnf33(s)),
                     ("ue5m3", t_fp(s, 5, 3))):
        under = int((q < s).sum())
        print(f"{label:11s}: quantised scale below ideal on {under} blocks"
              f" = {100 * under / tot:.2f}%")


def main():
    from transformers import AutoModelForCausalLM, AutoTokenizer
    import pyarrow.parquet as pq

    print("port self-check against scale_axis_probe ...", flush=True)
    check_ports()

    if "--diagnose" in sys.argv:
        diagnose()
        return

    print("loading model and data ...", flush=True)
    tok = AutoTokenizer.from_pretrained(MODEL)
    model = AutoModelForCausalLM.from_pretrained(MODEL, dtype=torch.float32)
    model.eval()
    text = "\n\n".join(pq.read_table(WIKI).column("text").to_pylist())
    ids = tok(text, return_tensors="pt").input_ids
    print(f"  tokens: {ids.numel()}, windows of {SEQLEN}: {ids.numel() // SEQLEN},"
          f" using first {NWIN}", flush=True)

    lins = target_modules(model)
    base = {n: m.weight.detach().clone() for n, m in lins}
    print(f"  quantisable linear tensors: {len(base)}", flush=True)

    ppl_base = perplexity(model, ids, NWIN)
    print(f"\nRULER CHECK -- fp32 baseline perplexity: {ppl_base:.4f} ({NWIN} windows)",
          flush=True)
    if not (10.0 < ppl_base < 60.0):
        sys.exit("baseline outside the plausible band for SmolLM2-135M; stopping.")
    print("  in band; proceeding.\n", flush=True)

    # occupied scale range, for the range argument
    lo, hi = math.inf, -math.inf
    for n, m in lins:
        w = m.weight.detach()
        nn_ = (w.shape[1] // K) * K
        if nn_ == 0:
            continue
        a = w[:, :nn_].reshape(-1, K).double().abs().amax(dim=1)
        a = a[a > 0] / 6.0
        lo = min(lo, math.log2(float(a.min())))
        hi = max(hi, math.log2(float(a.max())))
    print(f"occupied ideal-scale range: log2 s in [{lo:.2f}, {hi:.2f}]"
          f"  ({hi - lo:.2f} binades)\n", flush=True)

    hdr = (f"{'scale codec':<22}{'ppl':>10}{'vs fp32':>9}{'vs floor':>10}"
           f"{'zeroed blocks':>15}")
    print(hdr)
    print(f"{'fp32 (unquantised)':<22}{ppl_base:>10.4f}{'1.000x':>9}{'--':>10}{'--':>15}")
    results = {}
    floor_ppl = None
    for label, fn in ARMS:
        tot_blocks = tot_dead = 0
        for n, m in lins:
            qw, nz, dead = quantise_weight(base[n].double(), fn)
            m.weight.copy_(qw.to(m.weight.dtype))
            tot_blocks += nz
            tot_dead += dead
        p = perplexity(model, ids, NWIN)
        results[label] = p
        if floor_ppl is None:
            floor_ppl = p
        vsf = f"{p / floor_ppl:.3f}x"
        print(f"{label:<22}{p:>10.4f}{p / ppl_base:>8.3f}x{vsf:>10}"
              f"{tot_dead:>9d}/{tot_blocks:<6d}", flush=True)
    for n, m in lins:
        m.weight.copy_(base[n])

    print("\n'vs floor' is the cost of scale quantisation alone: 1.000x means the")
    print("scale codec adds nothing on top of E2M1 element quantisation.")
    print("'zeroed blocks' counts live blocks whose quantised scale collapsed to 0")
    print("(the block reconstructs as all-zero).")


if __name__ == "__main__":
    main()
