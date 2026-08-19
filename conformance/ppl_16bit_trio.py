#!/usr/bin/env python3
"""ppl_16bit_trio.py — perplexity for the 16-bit-class tie trio, element axis.

The T54 accuracy tie (conformance/tekum_true_bench.py) stands on NRMSE
accumulation: tekum10 8.56e-3 / takum16 5.70e-3 / TNF(4,8) 5.32e-3. The block
axis showed perplexity can reorder NRMSE rankings
(research/block/BLOCK_AXIS_VERDICT_2026-08-10.md). This measures the trio on
the block verdict's own pipeline: SmolLM2-135M, wikitext-2 test, 40 windows of
2048 tokens, the same loss*(SEQLEN-1) accumulation and the same ruler check —
copied from research/block/block_tnf.py, not reimplemented.

Quantisation here is ELEMENTWISE and SCALAR — no block scale of any kind. Each
weight tensor W is pre-scaled by s = amax(|W|) so its largest magnitude lands
exactly on 1.0, which is a code in all three formats (so the top is never
clamped); every element goes value -> nearest code -> decoded value; the same
scalar s inverts the scaling. The rule is identical for all formats.

Oracles are the conformance references, reused not reimplemented:
  * tnf_ref.py        TNF(4,8) / TNF(4,24)  (TRUE_LADDER rungs, 16/32 bits)
  * takum_ref.py      takum16 / takum32     (linear model, post-#606)
  * tekum_true_ref.py tekum10 / tekum20     (true base-3, 15.85 / 31.70 bits)

Fraction oracles are far too slow for 1e8 weights, so quantisation runs through
fast paths that are VALIDATED against the oracles on 1000 random values each,
requiring 0 mismatches before any weight is touched:
  * 16-bit class: the full signed codebook is enumerated through the oracle
    (40449 / 65535 / 59047 codes) and elements are snapped by midpoint
    bucketize — exact nearest-code by construction.
  * 32-bit class: codebooks are too large to enumerate (79 * 2^24 for
    TNF(4,24)), so elements are rounded per binade (binary formats, exact in
    float64 via frexp/ldexp/rint) or per triade (tekum20, float64 with ~2-ulp
    reconstruction noise, seven orders below the format's own step), taking
    the nearest of the neighbour-bucket candidates and 0.

Values below a format's smallest positive code resolve to the nearest of
{0, min_pos} — the flush/clamp rule around the encode domain [min_pos, top).

Two quantisation scopes, both reported:
  * every-tensor: EVERY parameter tensor, deduped by storage (the embedding is
    quantised once and the tied lm_head follows it), norms included.
  * linear-only:  every nn.Linear except lm_head — the exact target set of the
    2026-08-10 block-axis verdict, for comparability with that table.

Determinism: no randomness anywhere in the measurement path; validation draws
use a fixed seed (19). Model and dataset revisions are printed at startup.

Run:  python3 conformance/ppl_16bit_trio.py           (full, 40 windows)
      NWIN=2 python3 conformance/ppl_16bit_trio.py    (smoke)
"""
import glob
import math
import os
import random
import sys
import time
from fractions import Fraction

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

import numpy as np
import torch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import takum_ref  # noqa: E402
import tekum_true_ref as TK  # noqa: E402
import tnf_ref  # noqa: E402

SEQLEN = 2048
NWIN = int(os.environ.get("NWIN", "40"))
SEED = 19
CHUNK = 1 << 22
MODEL_ID = "HuggingFaceTB/SmolLM2-135M"
torch.set_grad_enabled(False)


# ---------------------------------------------------------------- 16-bit class
# Full signed codebooks enumerated through the oracles. Codebook floats are
# float(exact Fraction), i.e. the correctly rounded float64 of the exact code
# value, so equality against the oracle path is exact equality.

def build_tnf_codebook(et, mb):
    f = tnf_ref.TNFFormat(et, mb)
    vals = [Fraction(0)]
    for off in range(1, f.offset_max):
        for m in range(f.mant):
            v = (Fraction(1) + Fraction(m, f.mant)) * Fraction(2) ** (off - f.exp_offset)
            vals.append(v)
            vals.append(-v)
    return f, torch.tensor(sorted(float(v) for v in vals), dtype=torch.float64)


def build_takum_codebook(name):
    fmt = takum_ref.FORMATS[name]
    vals = []
    for raw in range(1 << fmt.n):
        v = takum_ref.decode(fmt, raw)
        if isinstance(v, takum_ref.Special):
            continue
        vals.append(float(v))
    return fmt, torch.tensor(sorted(vals), dtype=torch.float64)


def build_tekum_codebook(n, lo=Fraction(1, 10 ** 50), hi=Fraction(4)):
    # tekum10 reaches 3^±365, which overflows float64; codes outside
    # [1e-50, 4] can never be the nearest code to a pre-scaled weight
    # (|y| <= 1, |y_nonzero| >= float32_min/amax >> 1e-50), so they are
    # dropped BEFORE float conversion, on the exact Fraction.
    vals = [0.0]
    for v in range(-TK.vmax(n) + 1, TK.vmax(n)):
        if v == 0:
            continue
        val = TK.decode(n, v)
        if lo <= abs(val) <= hi:
            vals.append(float(val))
    return torch.tensor(sorted(vals), dtype=torch.float64)


def make_codebook_qfun(cb):
    bnd = (cb[:-1] + cb[1:]) / 2
    def q(y):  # y: float64 tensor, any shape
        return cb[torch.bucketize(y, bnd)]
    return q


# ---------------------------------------------------------------- 32-bit class
# Vectorised nearest-code per exponent bucket. For each element the candidates
# are the rounded code in its own bucket, in both neighbour buckets (clipped
# to the bucket's code range), and 0; the nearest candidate wins. Neighbour
# buckets cover every taper transition and the flush region exactly.

def q_binary_mags(av, emin, emax, p_of_e):
    """Nearest code to positive magnitudes av for a binary-binade format
    value=(1+m/2^p(e))*2^e, e in [emin,emax], m in [0,2^p-1]. Exact float64."""
    m0, E = np.frexp(av)
    e0 = (E - 1).astype(np.int64)
    cands = [np.zeros_like(av)]
    for de in (-1, 0, 1):
        eb = np.clip(e0 + de, emin, emax)
        p = p_of_e[eb - emin]
        x = np.ldexp(av, -eb) - 1.0
        mi = np.rint(np.ldexp(x, p))
        mi = np.clip(mi, 0.0, np.ldexp(1.0, p) - 1.0)
        cands.append(np.ldexp(np.ldexp(1.0, p) + mi, eb - p))
    C = np.stack(cands, 0)
    j = np.argmin(np.abs(C - av[None, :]), axis=0)
    return C[j, np.arange(av.size)]


def tekum_p_of_abs_e(n):
    # exponent-trit count c per regime (Def. 7/8, mirrored in tekum_true_ref):
    # |e|<=2: c=0; 3..5: 1; 6..14: 2; 15..41: 3; 42..122: 4; 123..365: 5.
    P = np.zeros(366, dtype=np.int64)
    for u in range(366):
        c = 0 if u <= 2 else 1 if u <= 5 else 2 if u <= 14 else \
            3 if u <= 41 else 4 if u <= 122 else 5
        P[u] = n - 3 - c
    return P


def q_ternary_mags(av, n, want_codes=False):
    """Nearest code to positive magnitudes av for tekum-n:
    value=(1+F/3^p)*3^e, F in [-(3^p-1)/2,(3^p-1)/2], p per regime taper.
    Reconstruction in float64 carries <=2 ulp; the code CHOICE is validated
    against the oracle."""
    P3 = tekum_p_of_abs_e(n)
    e0 = np.floor(np.log(av) / np.log(3.0)).astype(np.int64)
    for _ in range(3):  # settle f=a/3^e into (1/2,3/2]
        r = av / np.power(3.0, e0.astype(np.float64))
        e0 += (r > 1.5).astype(np.int64)
        e0 -= (r <= 0.5).astype(np.int64)
    cands, meta = [np.zeros_like(av)], [None]
    for de in (-1, 0, 1):
        eb = np.clip(e0 + de, -365, 365)
        p = P3[np.abs(eb)]
        p3 = np.power(3.0, p.astype(np.float64))          # exact, p<=n-3<=29
        f = av / np.power(3.0, eb.astype(np.float64)) - 1.0
        Fmax = (p3 - 1.0) / 2.0
        Fi = np.clip(np.rint(f * p3), -Fmax, Fmax)
        cands.append((p3 + Fi) * np.power(3.0, (eb - p).astype(np.float64)))
        meta.append((eb, Fi, p))
    C = np.stack(cands, 0)
    j = np.argmin(np.abs(C - av[None, :]), axis=0)
    out = C[j, np.arange(av.size)]
    if not want_codes:
        return out
    codes = []
    for i in range(av.size):
        if j[i] == 0:
            codes.append(None)  # flushed to zero
        else:
            eb, Fi, p = meta[j[i]]
            codes.append((int(eb[i]), int(Fi[i]), int(p[i])))
    return out, codes


def make_mag_qfun(mag_fun):
    """Wrap a positive-magnitude quantiser into a signed, chunked tensor op.
    All three 32-bit formats are value-symmetric (takum-linear verified by
    full takum16 enumeration; tekum by digit inversion; TNF by sign bit)."""
    def q(y):
        flat = y.reshape(-1).numpy()
        out = np.zeros_like(flat)
        nz = np.flatnonzero(flat)
        for lo in range(0, nz.size, CHUNK):
            ix = nz[lo:lo + CHUNK]
            out[ix] = np.copysign(mag_fun(np.abs(flat[ix])), flat[ix])
        return torch.from_numpy(out.reshape(y.shape))
    return q


# ------------------------------------------------------------------ validation
def validate(name, qfun, oracle_fun, lo_exp, hi_exp, k=1000, rel_tol=0.0):
    """qfun (tensor path) vs oracle (value -> encode -> decode -> float) on k
    seeded random signed values, magnitudes 10^U(lo_exp, hi_exp). 0 mismatches
    or the whole run stops."""
    rnd = random.Random(SEED)
    xs = [(-1 if rnd.random() < 0.5 else 1) * 10.0 ** rnd.uniform(lo_exp, hi_exp)
          for _ in range(k)]
    mine = qfun(torch.tensor(xs, dtype=torch.float64)).tolist()
    bad = 0
    for x, q in zip(xs, mine):
        o = oracle_fun(x)
        if rel_tol == 0.0:
            ok = (o == q)
        else:
            ok = (o == q) or (o != 0 and abs(q - o) <= rel_tol * abs(o))
        bad += 0 if ok else 1
    print(f"  {name:<28} {k} random values in 10^[{lo_exp},{hi_exp}]: "
          f"{bad} mismatches")
    if bad:
        sys.exit(f"VALIDATION FAILED for {name}: fast path disagrees with "
                 f"the oracle; refusing to measure.")


def validate_tekum20_exact(n, k=1000):
    """Exact code-level check for the ternary fast path: reconstruct the chosen
    (e,F,p) as an exact Fraction and compare with the oracle's exact value."""
    rnd = random.Random(SEED)
    xs = [(-1 if rnd.random() < 0.5 else 1) * 10.0 ** rnd.uniform(-45, 0.6)
          for _ in range(k)]
    av = np.abs(np.array(xs, dtype=np.float64))
    _, codes = q_ternary_mags(av, n, want_codes=True)
    bad = 0
    for x, code in zip(xs, codes):
        o = TK.decode(n, TK.encode(n, Fraction(x)))
        if code is None:
            mine = Fraction(0)
        else:
            e, F, p = code
            mine = (3 ** p + F) * Fraction(3) ** (e - p)
        if abs(x) < 0 or mine != abs(o) * (1 if o >= 0 else -1) * (1 if x >= 0 else 1):
            pass  # sign handled below
        if mine != abs(o):
            bad += 1
    print(f"  {'tekum%d (exact codes)' % n:<28} {k} random values in "
          f"10^[-45,0.6]: {bad} mismatches")
    if bad:
        sys.exit(f"VALIDATION FAILED for tekum{n} exact-code check.")


# ------------------------------------------------------- model plumbing (copied
# from research/block/block_tnf.py -- same eval loop, same settings)
def target_linear(model):
    return [(n, m.weight) for n, m in model.named_modules()
            if isinstance(m, torch.nn.Linear) and "lm_head" not in n]


def every_weight_tensor(model):
    seen, out = set(), []
    for n, p in model.named_parameters():
        if p.data_ptr() in seen:
            continue
        seen.add(p.data_ptr())
        out.append((n, p))
    return out


def load_wikitext():
    import pyarrow.parquet as pq
    paths = glob.glob(os.path.expanduser(
        "~/.cache/huggingface/hub/datasets--Salesforce--wikitext/snapshots/"
        "*/wikitext-2-raw-v1/test-00000-of-00001.parquet"))
    if not paths:
        sys.exit("BLOCKED: wikitext-2 test parquet not in the local HF cache.")
    print(f"dataset: {paths[0]}")
    t = pq.read_table(paths[0])
    return "\n\n".join(t.column("text").to_pylist())


def perplexity(model, ids, limit_windows=None):
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


def quantise_scope(params, orig, qfun):
    """value -> nearest code -> decoded value, per-tensor amax pre-scaling.
    Returns (global NRMSE over the scope, fraction of nonzeros flushed to 0)."""
    se = ss = flz = nnz = 0.0
    for name, p in params:
        w = orig[name]
        s = w.abs().amax().double()
        if s == 0:
            continue
        y = w.double() / s
        q = qfun(y)
        se += float(((q - y) ** 2).sum() * s * s)
        ss += float((y ** 2).sum() * s * s)
        flz += float(((y != 0) & (q == 0)).sum())
        nnz += float((y != 0).sum())
        p.copy_((q * s).to(p.dtype))
    return math.sqrt(se / ss), flz / max(nnz, 1)


def main():
    t_start = time.time()
    print(__doc__.split("\n")[0])
    print(f"torch {torch.__version__}, numpy {np.__version__}, seed {SEED}, "
          f"NWIN={NWIN}, SEQLEN={SEQLEN}\n")

    # ---- codebooks and fast paths, validated before any weight is touched
    print("building codebooks through the oracles ...")
    f_tnf16, cb_tnf16 = build_tnf_codebook(4, 8)     # TRUE_LADDER[16]
    tk16, cb_tk16 = build_takum_codebook("takum16")
    cb_tek10 = build_tekum_codebook(10)
    print(f"  TNF(4,8)  {cb_tnf16.numel()} finite codes (stored width 16 bits)")
    print(f"  takum16   {cb_tk16.numel()} finite codes (16 bits)")
    print(f"  tekum10   {2 * TK.vmax(10) - 1} finite codes, "
          f"{cb_tek10.numel()} inside [1e-50, 4] (10 trits = "
          f"{10 * math.log2(3):.2f} bits)")

    q16 = {
        "TNF(4,8)": make_codebook_qfun(cb_tnf16),
        "takum16": make_codebook_qfun(cb_tk16),
        "tekum10": make_codebook_qfun(cb_tek10),
    }
    f_tnf32 = tnf_ref.TRUE_LADDER[32]                # TNF(4,24)
    tk32 = takum_ref.FORMATS["takum32"]
    p_tnf32 = np.full(79, 24, dtype=np.int64)        # e in [-39, 39]
    p_tk32 = np.array([27 - ((abs(c)).bit_length() - 1) if c < 0
                       else 27 - ((c + 1).bit_length() - 1)
                       for c in range(-255, 255)], dtype=np.int64)
    q32 = {
        "TNF(4,24)": make_mag_qfun(lambda a: q_binary_mags(a, -39, 39, p_tnf32)),
        "takum32": make_mag_qfun(lambda a: q_binary_mags(a, -255, 254, p_tk32)),
        "tekum20": make_mag_qfun(lambda a: q_ternary_mags(a, 20)),
    }

    print("\nvalidating fast paths against the oracles (hard stop on any "
          "mismatch) ...")
    # 16-bit class: exact float equality (codebook floats ARE oracle floats).
    # TNF draws stay inside the encode domain [min_pos=2^-39, 1); the flush
    # rule below min_pos is by construction of the codebook (0 is a code).
    validate("TNF(4,8)", q16["TNF(4,8)"],
             lambda x: float(tnf_ref.decode(f_tnf16, tnf_ref.encode(f_tnf16, Fraction(x)))),
             -11.5, 0.0)
    validate("takum16", q16["takum16"],
             lambda x: float(takum_ref.decode(tk16, takum_ref.encode(tk16, Fraction(x)))),
             -45.0, 0.0)
    validate("tekum10", q16["tekum10"],
             lambda x: float(TK.decode(10, TK.encode(10, Fraction(x)))),
             -45.0, 0.0)
    # 32-bit class. Binary formats are exact in float64 -> exact equality.
    validate("TNF(4,24)", q32["TNF(4,24)"],
             lambda x: float(tnf_ref.decode(f_tnf32, tnf_ref.encode(f_tnf32, Fraction(x)))),
             -11.5, 0.0)
    validate("takum32", q32["takum32"],
             lambda x: float(takum_ref.decode(tk32, takum_ref.encode(tk32, Fraction(x)))),
             -45.0, 0.0)
    # tekum20: the tensor path reconstructs values in float64 (<=2 ulp), so the
    # value check allows 1e-12 relative (format step is ~8e-9, four orders
    # coarser); the CODE choice is then checked exactly via Fractions.
    validate("tekum20 (float64 values)", q32["tekum20"],
             lambda x: float(TK.decode(20, TK.encode(20, Fraction(x)))),
             -45.0, 0.6, rel_tol=1e-12)
    validate_tekum20_exact(20)

    # ---- model, data, ruler
    print("\nloading model and data (offline, local HF cache) ...")
    from transformers import AutoModelForCausalLM, AutoTokenizer
    snap = glob.glob(os.path.expanduser(
        "~/.cache/huggingface/hub/models--HuggingFaceTB--SmolLM2-135M/snapshots/*"))
    print(f"model: {MODEL_ID} @ {os.path.basename(snap[0]) if snap else '?'}")
    tok = AutoTokenizer.from_pretrained(MODEL_ID)
    model = AutoModelForCausalLM.from_pretrained(MODEL_ID, dtype=torch.float32)
    model.eval()
    ids = tok(load_wikitext(), return_tensors="pt").input_ids

    base = perplexity(model, ids, NWIN)
    print(f"\nRULER: fp32 baseline perplexity = {base:.4f}  ({NWIN} windows)")
    if not (10.0 < base < 60.0):
        sys.exit("RULER BROKEN — baseline outside the plausible band; stop.")
    print("ruler in band (block-axis verdict measured 14.4874 on the same "
          "pipeline)\n")

    scopes = {
        "every-tensor": every_weight_tensor(model),
        "linear-only": target_linear(model),
    }
    orig = {name: p.detach().clone() for name, p in scopes["every-tensor"]}
    for name, p in scopes["linear-only"]:
        orig.setdefault(name, p.detach().clone())

    def restore():
        for scope in scopes.values():
            for name, p in scope:
                p.copy_(orig[name])

    rows = []
    for scope_name, fmts in (("every-tensor", q16), ("linear-only", q16),
                             ("every-tensor", q32)):
        cls = "16-bit class" if fmts is q16 else "32-bit class (sanity)"
        print(f"═══ {cls}, scope = {scope_name} "
              f"({len(scopes[scope_name])} tensors) ═══")
        print(f"  {'format':<12} {'bits':>6} {'ppl':>9} {'vs fp32':>9} "
              f"{'weight NRMSE':>13} {'flushed':>9} {'sec':>6}")
        for fname, qfun in fmts.items():
            t0 = time.time()
            nrmse, flush = quantise_scope(scopes[scope_name], orig, qfun)
            p = perplexity(model, ids, NWIN)
            restore()
            bits = {"TNF(4,8)": 16.0, "takum16": 16.0,
                    "tekum10": 10 * math.log2(3), "TNF(4,24)": 32.0,
                    "takum32": 32.0, "tekum20": 20 * math.log2(3)}[fname]
            rows.append((cls, scope_name, fname, bits, p, nrmse, flush))
            print(f"  {fname:<12} {bits:>6.2f} {p:>9.4f} {p / base:>8.4f}x "
                  f"{nrmse:>13.3e} {flush:>8.2e} {time.time() - t0:>6.0f}",
                  flush=True)
        print()

    print(f"fp32 baseline {base:.4f}; total {time.time() - t_start:.0f}s")
    print("\nFINAL TABLE (copy into research/PPL_16BIT_TRIO_2026-08-19.md)")
    print(f"{'class':<22} {'scope':<13} {'format':<10} {'bits':>6} "
          f"{'ppl':>9} {'vs fp32':>9} {'NRMSE':>10}")
    print(f"{'—':<22} {'—':<13} {'fp32':<10} {'32':>6} {base:>9.4f} "
          f"{'1.0000x':>9} {'0':>10}")
    for cls, sc, fn, b, p, nr, fl in rows:
        print(f"{cls:<22} {sc:<13} {fn:<10} {b:>6.2f} {p:>9.4f} "
              f"{p / base:>8.4f}x {nr:>10.3e}")


if __name__ == "__main__":
    main()
