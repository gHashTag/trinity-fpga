"""Is the thin 5-bit plastic-vs-supergolden margin a stable sign, or window noise?

`more_families.py` reports one perplexity per ladder, so a 0.85 % gap on OPT is a single
point estimate with no spread attached -- it cannot distinguish "plastic is consistently
slightly better" from "the two are tied and one window decided it".

This keeps the per-window NLL for both ladders and pairs them on the SAME window, which
removes window-to-window difficulty (the dominant variance) from the comparison. Reported:
the paired mean difference, its standard error, and how many of the N windows plastic wins.
The sign test needs no normality assumption and is the one to trust if the two disagree.

Same quantiser, same targets, same seqlen rule as more_families.py -- only the accounting
differs. Perplexity is exp(mean NLL), so ordering by mean NLL is the same ordering.
"""
import os, sys, json, math
import numpy as np, torch
from transformers import AutoModelForCausalLM, AutoTokenizer

W = ("/private/tmp/claude-501/-Users-ssdm4-Desktop-PROJECTS-CLAUDE/"
     "0e868af8-ab2d-4d00-be03-8fea94ba48e4/scratchpad/weights")
MD = sys.argv[1]
_cfg = json.load(open(os.path.join(W, MD, "config.json")))
SEQLEN = min(2048, _cfg.get("max_position_embeddings") or _cfg.get("n_positions") or 2048)
NW = int(os.environ.get("NW", 40))
BITS = 5
torch.set_grad_enabled(False)
RAT = {"plastic": 1.324717957244746, "supergold": 1.465571231876768}
HEADS = ("lm_head", "embed_out")

try:
    from transformers.pytorch_utils import Conv1D
except Exception:
    Conv1D = ()


def targets(m):
    out = []
    for nm, mod in m.named_modules():
        if any(h in nm for h in HEADS):
            continue
        if isinstance(mod, torch.nn.Linear) or (Conv1D and isinstance(mod, Conv1D)):
            if getattr(mod, "weight", None) is not None and mod.weight.dim() == 2:
                out.append((nm, mod))
    return out


def codebook(r, bits):
    n = (2 ** bits - 1) // 2
    return np.sort(np.array([0.0] + [r ** (-k) for k in range(n)]
                            + [-(r ** (-k)) for k in range(n)]))


tok = AutoTokenizer.from_pretrained(os.path.join(W, MD))
import pyarrow.parquet as pq
text = "\n\n".join(pq.read_table(os.path.join(W, "wikitext2-test.parquet"))
                   .column("text").to_pylist())
ids = tok(text, return_tensors="pt").input_ids[0]
if ids.numel() // SEQLEN < NW:
    sys.exit(f"  only {ids.numel() // SEQLEN} windows available, {NW} requested -- refusing")


def nlls(m):
    x = ids[:(ids.numel() // SEQLEN) * SEQLEN].reshape(-1, SEQLEN)[:NW]
    return np.array([m(x[i:i+1], labels=x[i:i+1]).loss.double().item()
                     for i in range(x.shape[0])])


def run(r):
    m = AutoModelForCausalLM.from_pretrained(os.path.join(W, MD), dtype=torch.float32)
    m.eval()
    cb = codebook(r, BITS)
    cb_t = torch.tensor(cb, dtype=torch.float64)
    mid_t = torch.tensor((cb[:-1] + cb[1:]) / 2, dtype=torch.float64)
    tg = targets(m)
    if len(tg) == 0:
        sys.exit("  no layers matched -- refusing to report a comparison")
    for _, mod in tg:
        w = mod.weight.data.to(torch.float64)
        ax = 1 if isinstance(mod, torch.nn.Linear) else 0
        s = w.abs().amax(dim=ax, keepdim=True).clamp_min(1e-12)
        mod.weight.data = (cb_t[torch.bucketize(w / s, mid_t)] * s).to(mod.weight.dtype)
    v = nlls(m); del m
    return v


pl, sg = run(RAT["plastic"]), run(RAT["supergold"])
d = sg - pl                                   # >0 means plastic is better on that window
se = d.std(ddof=1) / np.sqrt(len(d))
wins = int((d > 0).sum())
print(f"\n  {MD}: {len(d)} windows x {SEQLEN} tok, 5 bits")
print(f"  ppl  plastic={np.exp(pl.mean()):.3f}  supergold={np.exp(sg.mean()):.3f}"
      f"  lead={(np.exp(sg.mean()) / np.exp(pl.mean()) - 1) * 100:.2f}%")
print(f"  paired dNLL mean={d.mean():+.5f}  sd={d.std(ddof=1):.5f}  se={se:.5f}"
      f"  t={d.mean() / se:+.2f}")
n = len(d)
tail = sum(math.comb(n, k) for k in range(min(wins, n - wins) + 1)) / 2 ** n
print(f"  plastic wins {wins}/{n} windows  (sign test, p_two-sided={min(1.0, 2 * tail):.2e})")
