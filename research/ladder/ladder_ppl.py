"""Does a finer multiply-free ladder help a network, at matched bits?

Theorem thm:hierarchy says the multiply-free scales are 2 (shift), phi (1.618),
and at degree 3 the plastic number (1.3247), supergolden (1.4656) and tribonacci
(1.8393). A finer ratio quantises magnitudes more finely -- and at a FIXED code
budget it therefore spans less dynamic range. That is the paper's own
range-against-precision law applied to the scale hierarchy, so the question is
not which ladder is finer but which wins once both are charged the same bits.

Weights are quantised to +-r^k with a per-output-channel scale, the codebook
sized to exactly 2^bits entries including zero and the sign.
"""
import os, sys, math, json
import numpy as np, torch
from transformers import AutoModelForCausalLM, AutoTokenizer

W = ("/private/tmp/claude-501/-Users-ssdm4-Desktop-PROJECTS-CLAUDE/"
     "0e868af8-ab2d-4d00-be03-8fea94ba48e4/scratchpad/weights")
MODEL = os.path.join(W, sys.argv[1] if len(sys.argv) > 1 else "smollm2")
TAG = os.path.basename(MODEL)
SEQLEN, WINDOWS = 2048, 12
torch.set_grad_enabled(False)

RATIOS = {
    "shift  (2^k,   deg 1)": 2.0,
    "phi    (1.618, deg 2)": (1 + 5 ** 0.5) / 2,
    "supergold (1.4656, d3)": 1.465571231876768,
    "plastic(1.3247, deg 3)": 1.324717957244746,
}

def codebook(r, bits):
    """2^bits entries: zero, and +-r^k over the widest window that fits."""
    n_mag = (2 ** bits - 1) // 2            # magnitudes per sign
    # geometric ladder r^0 .. r^-(n_mag-1), normalised so the top level is 1
    return np.array([0.0] + [ r ** (-k) for k in range(n_mag) ]
                          + [-r ** (-k) for k in range(n_mag) ], dtype=np.float64)

def quantise_(w, cb):
    """Per-output-channel scale, then nearest codebook entry. In place."""
    orig = w.data.to(torch.float64)
    s = orig.abs().amax(dim=1, keepdim=True).clamp_min(1e-12)
    x = (orig / s).cpu().numpy()
    idx = np.abs(x[..., None] - cb[None, None, :]).argmin(axis=-1)
    w.data = torch.from_numpy(cb[idx]).to(torch.float64).mul_(s).to(w.dtype)

def perplexity(model, ids):
    n = (ids.numel() // SEQLEN) * SEQLEN
    x = ids[:n].reshape(-1, SEQLEN)[:WINDOWS]
    nll = cnt = 0
    for i in range(x.shape[0]):
        c = x[i:i+1]
        nll += model(c, labels=c).loss.double().item() * (SEQLEN - 1)
        cnt += SEQLEN - 1
    return float(np.exp(nll / cnt))

print(f"loading {MODEL} ...", flush=True)
tok = AutoTokenizer.from_pretrained(MODEL)
import pyarrow.parquet as pq
text = "\n\n".join(pq.read_table(os.path.join(W, "wikitext2-test.parquet"))
                   .column("text").to_pylist())
ids = tok(text, return_tensors="pt").input_ids[0]

def fresh():
    m = AutoModelForCausalLM.from_pretrained(MODEL, dtype=torch.float32); m.eval(); return m

base = perplexity(fresh(), ids)
print(f"baseline fp32 ppl = {base:.4f}", flush=True)
rows = []
for bits in (3, 4, 5):
    for name, r in RATIOS.items():
        m = fresh()
        cb = codebook(r, bits)
        for nm, mod in m.named_modules():
            if isinstance(mod, torch.nn.Linear) and "lm_head" not in nm:
                quantise_(mod.weight, cb)
        p = perplexity(m, ids)
        span = r ** ((2 ** bits - 1) // 2 - 1)
        rows.append((bits, name, r, len(cb), span, p))
        print(f"  {bits}b  {name:24} codes={len(cb):3}  span={span:9.1f}x  ppl={p:9.4f}",
              flush=True)
        del m
json.dump([{"bits": b, "ladder": n, "r": r, "codes": c, "span": s, "ppl": p}
           for b, n, r, c, s, p in rows] + [{"bits": None, "ladder": "fp32", "ppl": base}],
          open(f"ladder_ppl_{TAG}.json", "w"), indent=1)
print(f"written ladder_ppl_{TAG}.json")
