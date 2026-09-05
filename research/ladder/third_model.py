"""A: the only test that actually exercises lambda -- a third family, at the crossover budget.

Six bits held on both models but did not test lambda: at that budget almost nothing is flushed,
so the second term is negligible and the single-term closed form already predicts correctly.
Four bits is the crossover, where reach and resolution are comparable and lambda decides.

Pythia-160m is a third family: GPT-NeoX rather than Llama, trained on the Pile rather than
FineWeb/Qwen data, its own tokenizer, and a different attention layout (fused query_key_value).
Nothing about it entered the lambda fit.

PREDICTIONS ARE PRINTED BEFORE THE MEASUREMENT, for all three budgets and both second terms.
Four bits is the one that counts.

Note: Pythia's output head is `embed_out`, not `lm_head`. Filtering only on "lm_head" would
quantise the head and change what is being compared -- so both names are excluded.
"""
import os
import numpy as np, torch
from transformers import AutoModelForCausalLM, AutoTokenizer

W = ("/private/tmp/claude-501/-Users-ssdm4-Desktop-PROJECTS-CLAUDE/"
     "0e868af8-ab2d-4d00-be03-8fea94ba48e4/scratchpad/weights")
MD, SEQLEN, NW = os.path.join(W, "pythia"), 2048, 8
LAM_N, LAM_E = 0.01, 0.79
torch.set_grad_enabled(False)
RAT = {"shift": 2.0, "phi": (1 + 5 ** 0.5) / 2,
       "supergold": 1.465571231876768, "plastic": 1.324717957244746}
HEADS = ("lm_head", "embed_out")


def is_target(nm, mod):
    return isinstance(mod, torch.nn.Linear) and not any(h in nm for h in HEADS)


def codebook(r, bits):
    n = (2 ** bits - 1) // 2
    return np.sort(np.array([0.0] + [r ** (-k) for k in range(n)]
                            + [-(r ** (-k)) for k in range(n)]))


def parts(x, r, bits):
    n = (2 ** bits - 1) // 2
    cb = codebook(r, bits); mid = (cb[:-1] + cb[1:]) / 2
    mse = float(((cb[np.searchsorted(mid, x)] - x) ** 2).mean())
    a = np.abs(x); below = a < r ** (-(n - 1)) / 2
    return mse, float(below.mean()), float((a[below] ** 2).sum() / (a ** 2).sum())


tok = AutoTokenizer.from_pretrained(MD)
import pyarrow.parquet as pq
text = "\n\n".join(pq.read_table(os.path.join(W, "wikitext2-test.parquet"))
                   .column("text").to_pylist())
ids = tok(text, return_tensors="pt").input_ids[0]


def load():
    m = AutoModelForCausalLM.from_pretrained(MD, dtype=torch.float32); m.eval(); return m


def ppl(m):
    n = (ids.numel() // SEQLEN) * SEQLEN
    x = ids[:n].reshape(-1, SEQLEN)[:NW]
    return float(np.exp(sum(m(x[i:i+1], labels=x[i:i+1]).loss.double().item()
                            for i in range(x.shape[0])) / x.shape[0]))


m = load()
tg = [(nm, mod) for nm, mod in m.named_modules() if is_target(nm, mod)]
acc = []
for nm, mod in tg:
    w = mod.weight.data.to(torch.float64)
    s = w.abs().amax(dim=1, keepdim=True).clamp_min(1e-12)
    z = (w / s).cpu().numpy().ravel()
    acc.append(z[:: max(1, z.size // 120000)])
x = np.concatenate(acc)
base = ppl(m); del m
k = float(((x - x.mean()) ** 4).mean() / x.std() ** 4 - 3)
print(f"\n  Pythia-160m: {len(tg)} linear layers, fp32 ppl {base:.4f}, "
      f"weight excess kurtosis {k:+.2f}\n")
print("  PREDICTIONS (made before measuring):")
PRED = {}
for bits in (3, 4, 5):
    pn = min(RAT, key=lambda kk: (lambda t: t[0] + LAM_N * t[1])(parts(x, RAT[kk], bits)))
    pe = min(RAT, key=lambda kk: (lambda t: t[0] + LAM_E * t[2])(parts(x, RAT[kk], bits)))
    p0 = min(RAT, key=lambda kk: parts(x, RAT[kk], bits)[0])
    PRED[bits] = (p0, pn, pe)
    print(f"    {bits}b   MSE-only={p0:10} count={pn:10} energy={pe:10}"
          + ("     <-- the crossover budget" if bits == 4 else ""))

print("\n  MEASURED:")
for bits in (3, 4, 5):
    res = []
    for kk, r in RAT.items():
        mm = load(); cb = codebook(r, bits)
        cb_t = torch.tensor(cb, dtype=torch.float64)
        mid_t = torch.tensor((cb[:-1] + cb[1:]) / 2, dtype=torch.float64)
        for nm, mod in mm.named_modules():
            if is_target(nm, mod):
                w = mod.weight.data.to(torch.float64)
                s = w.abs().amax(dim=1, keepdim=True).clamp_min(1e-12)
                mod.weight.data = (cb_t[torch.bucketize(w / s, mid_t)] * s).to(mod.weight.dtype)
        res.append((kk, ppl(mm))); del mm
    win = min(res, key=lambda t: t[1])[0]
    p0, pn, pe = PRED[bits]
    print(f"    {bits}b  " + "  ".join(f"{a}={b:.3f}" for a, b in sorted(res, key=lambda t: t[1]))
          + f"\n         winner={win}   MSE-only:{'ok' if p0==win else 'X'}"
          f"  count:{'ok' if pn==win else 'X'}  energy:{'ok' if pe==win else 'X'}")
