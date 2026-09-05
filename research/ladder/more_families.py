"""B: fourth and fifth families on the two budgets that replicated.

3 bits -> shift and 5 bits -> plastic hold on SmolLM2 (Llama), Qwen (Qwen2) and Pythia (GPT-NeoX).
Three families is enough to be interesting and not enough to be settled -- all three are recent
decoder-only models trained on broadly similar web corpora. GPT-2 (2019, WebText, learned
positional embeddings, Conv1D-style projections) and OPT-125m (2022, different tokenizer and
init) are further away in design space than the three already tested.

Only 3 and 5 bits are measured. Four bits is closed as model-dependent, so spending runs on it
would add nothing.

Head names differ per family and getting this wrong silently changes the experiment: `lm_head`
(Llama/Qwen/OPT), `embed_out` (Pythia). GPT-2's head is also `lm_head` but is TIED to wte, and
its projections are `Conv1D`, not `nn.Linear` -- so a filter on nn.Linear alone would quantise
NOTHING on GPT-2 and silently report the fp32 perplexity four times. Both are handled explicitly.
"""
import os, sys
import numpy as np, torch
from transformers import AutoModelForCausalLM, AutoTokenizer

W = ("/private/tmp/claude-501/-Users-ssdm4-Desktop-PROJECTS-CLAUDE/"
     "0e868af8-ab2d-4d00-be03-8fea94ba48e4/scratchpad/weights")
MD = sys.argv[1]
# GPT-2's context is 1024, not 2048; feeding it 2048 raises IndexError inside the positional
# embedding. Take the limit from the model's own config instead of assuming a common value.
import json as _json
_cfg = _json.load(open(os.path.join(W, MD, "config.json")))
SEQLEN = min(2048, _cfg.get("max_position_embeddings") or _cfg.get("n_positions") or 2048)
NW = int(os.environ.get("NW", 8))
BITS = tuple(int(b) for b in os.environ.get("BITS", "3,5").split(","))
torch.set_grad_enabled(False)
RAT = {"shift": 2.0, "phi": (1 + 5 ** 0.5) / 2,
       "supergold": 1.465571231876768, "plastic": 1.324717957244746}
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


def load():
    m = AutoModelForCausalLM.from_pretrained(os.path.join(W, MD), dtype=torch.float32)
    m.eval(); return m


AVAIL = ids.numel() // SEQLEN
if AVAIL < NW:
    sys.exit(f"  only {AVAIL} windows of {SEQLEN} available, {NW} requested -- refusing")


def ppl(m):
    n = (ids.numel() // SEQLEN) * SEQLEN
    x = ids[:n].reshape(-1, SEQLEN)[:NW]
    return float(np.exp(sum(m(x[i:i+1], labels=x[i:i+1]).loss.double().item()
                            for i in range(x.shape[0])) / x.shape[0]))


m = load()
tg = targets(m)
nw = sum(mod.weight.numel() for _, mod in tg)
base = ppl(m); del m
print(f"\n  {MD}: {len(tg)} quantisable 2-D layers, {nw:,} weights, "
      f"seqlen {SEQLEN}, fp32 ppl {base:.4f}")
if len(tg) == 0:
    sys.exit("  no layers matched -- refusing to report a comparison")

for bits in BITS:
    res = []
    for k, r in RAT.items():
        mm = load(); cb = codebook(r, bits)
        cb_t = torch.tensor(cb, dtype=torch.float64)
        mid_t = torch.tensor((cb[:-1] + cb[1:]) / 2, dtype=torch.float64)
        for nm, mod in targets(mm):
            w = mod.weight.data.to(torch.float64)
            # Conv1D stores [in, out]; scale along the contraction axis in both layouts
            ax = 1 if isinstance(mod, torch.nn.Linear) else 0
            s = w.abs().amax(dim=ax, keepdim=True).clamp_min(1e-12)
            mod.weight.data = (cb_t[torch.bucketize(w / s, mid_t)] * s).to(mod.weight.dtype)
        res.append((k, ppl(mm))); del mm
    win = min(res, key=lambda t: t[1])[0]
    exp = "shift" if bits == 3 else "plastic"
    print(f"  {bits}b  " + "  ".join(f"{a}={b:.3f}" for a, b in sorted(res, key=lambda t: t[1]))
          + f"\n       winner={win}  expected={exp}  {'HOLDS' if win == exp else 'BREAKS'}")
