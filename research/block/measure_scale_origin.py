"""Blocker #1: does a fixed scale-field origin cover every model?

MXFP4's E8M0 scale is an unsigned byte with bias 127, so its representable
exponents are 2^-127 .. 2^127 -- 255 octaves, a superset of fp32's. A finer
ladder buys resolution by spending range: at step 2^(k/N) the same 8-bit field
spans 255/N octaves. The question is whether 255/N octaves, placed at some fixed
origin, still covers what real weights ask for.

This measures the ASKED-FOR index on every model available, for the two ladders
that matter: our five-trit 2^(k/3) (243 codes, 81 octaves) and the finest
2^(k/16) (255 codes, 15.9 octaves).
"""
import glob, math, os, sys
import numpy as np

WROOT = "/private/tmp/claude-501/-Users-ssdm4-Desktop-PROJECTS-CLAUDE/0e868af8-ab2d-4d00-be03-8fea94ba48e4/scratchpad/weights"
K, EMAX = 32, 2          # block size, E2M1's emax

def tensors(model):
    # safetensors.numpy cannot read bfloat16; torch can, and every model here
    # that stores bf16 is exactly the two the numpy path dropped silently.
    import torch
    from safetensors.torch import load_file
    pats = ("proj", "fc", "mlp", "c_attn", "c_fc", "dense", "query_key_value",
            "out_proj", "k_proj", "q_proj", "v_proj")
    for f in sorted(glob.glob(os.path.join(WROOT, model, "*.safetensors"))):
        d = load_file(f)
        for name, a in d.items():
            if a.ndim == 2 and any(s in name for s in pats):
                yield name, a.to(torch.float32).numpy()

def index_range(model, N):
    """Chosen ladder index m for X = 2^(m/N), over every block, min and max."""
    lo, hi, nblocks = None, None, 0
    for _, a in tensors(model):
        v = a.reshape(-1)
        v = v[: (v.size // K) * K].reshape(-1, K)
        amax = np.abs(v).max(axis=1)
        amax = amax[amax > 0]
        if amax.size == 0: continue
        # the ladder point just below amax/2^emax, in index units of 1/N octave
        m = np.floor((np.log2(amax) - EMAX) * N).astype(np.int64)
        lo = m.min() if lo is None else min(lo, int(m.min()))
        hi = m.max() if hi is None else max(hi, int(m.max()))
        nblocks += amax.size
    return lo, hi, nblocks

MODELS = [d for d in ("smollm2","qwen","gpt2","pythia")
          if os.path.isdir(os.path.join(WROOT, d))]
# The span real weights ask for, in octaves, decides the finest ladder that fits.
print("=== какой шаг ещё влезает в 8-битное поле ===")
span_oct = None
for N in (1,):
    lo=hi=None
    for m in MODELS:
        try: l,h,_ = index_range(m, N)
        except Exception: continue
        if l is None: continue
        lo = l if lo is None else min(lo,l); hi = h if hi is None else max(hi,h)
    span_oct = hi - lo + 1
print(f"  диапазон, запрошенный весами: {span_oct} октав (по четырём моделям)")
for N in (3, 8, 16, 19, 20, 24):
    codes = 3**5 if N == 3 else 255
    need = span_oct * N + 1
    print(f"  2^(k/{N:2d}): нужно ~{need:4d} кодов из {codes}  "
          f"{'✓' if need <= codes else '✗'}   {codes/N:5.1f} октав в поле")
print()

for N, label in ((3, "2^(k/3), 5 trits, 243 codes"), (16, "2^(k/16), 255 codes")):
    span = (243 if N == 3 else 255)
    print(f"\n=== {label} — поле вмещает {span} кодов = {span/N:.1f} октав ===")
    allo, ahi = [], []
    for m in MODELS:
        try:
            lo, hi, nb = index_range(m, N)
        except Exception as e:
            print(f"  {m:9s} ошибка: {str(e)[:60]}"); continue
        if lo is None: print(f"  {m:9s} нет блоков"); continue
        allo.append(lo); ahi.append(hi)
        need = hi - lo + 1
        print(f"  {m:9s} m ∈ [{lo:5d},{hi:5d}]  нужно {need:4d} кодов  из {span}"
              f"  {'✓' if need <= span else '✗ НЕ ВЛЕЗАЕТ'}  ({nb:,} блоков)")
    if allo:
        L, H = min(allo), max(ahi); need = H - L + 1
        print(f"  {'ВСЕ':9s} m ∈ [{L:5d},{H:5d}]  нужно {need:4d} из {span}"
              f"  {'✓ ОДНА КОНСТАНТА ПОКРЫВАЕТ ВСЕ' if need <= span else '✗'}"
              + (f"  запас {span-need} кодов" if need <= span else ""))
