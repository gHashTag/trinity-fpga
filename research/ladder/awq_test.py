"""Why does perplexity prefer a coarser ladder than weight MSE does?

The transposition is reproducible: at four bits the closed form picks
supergolden and perplexity picks phi, on both models, in the same direction.
Plain MSE treats every weight alike. The output error of a linear layer is
sum_j dw_ij x_j, so a weight multiplying a large-magnitude input channel costs
more than one multiplying a small one -- and transformer activations are known
to carry a few channels far larger than the rest.

So the quantity that should rank the ladders is not sum dw^2 but
sum_j a_j^2 dw_ij^2, with a_j the RMS of input channel j. If that reverses the
transposition, the discrepancy is explained rather than tolerated.
"""
import os, sys, json, numpy as np, torch
from transformers import AutoModelForCausalLM, AutoTokenizer
W = ("/private/tmp/claude-501/-Users-ssdm4-Desktop-PROJECTS-CLAUDE/"
     "0e868af8-ab2d-4d00-be03-8fea94ba48e4/scratchpad/weights")
TAG = sys.argv[1] if len(sys.argv) > 1 else "smollm2"
MODEL = os.path.join(W, TAG)
torch.set_grad_enabled(False)
RAT = {"shift  (2^k,   deg 1)": 2.0, "phi    (1.618, deg 2)": (1+5**0.5)/2,
       "supergold (1.4656, d3)": 1.465571231876768,
       "plastic(1.3247, deg 3)": 1.324717957244746}

def codebook(r, bits):
    n = (2**bits - 1)//2
    return np.array([0.0] + [r**(-k) for k in range(n)] + [-r**(-k) for k in range(n)])

tok = AutoTokenizer.from_pretrained(MODEL)
m = AutoModelForCausalLM.from_pretrained(MODEL, dtype=torch.float32); m.eval()
import pyarrow.parquet as pq
text = "\n\n".join(pq.read_table(os.path.join(W, "wikitext2-test.parquet"))
                   .column("text").to_pylist())
ids = tok(text, return_tensors="pt").input_ids[0][:2048*2].reshape(2, 2048)

# среднеквадратичная амплитуда КАЖДОГО входного канала каждого линейного слоя
scale = {}
def mk(nm):
    def hook(mod, inp, out):
        a = inp[0].detach().reshape(-1, inp[0].shape[-1]).to(torch.float64)
        s = (a**2).mean(dim=0).sqrt()
        scale[nm] = s if nm not in scale else torch.maximum(scale[nm], s)
    return hook
hs = [mod.register_forward_hook(mk(nm)) for nm, mod in m.named_modules()
      if isinstance(mod, torch.nn.Linear) and "lm_head" not in nm]
for i in range(ids.shape[0]): m(ids[i:i+1])
for h in hs: h.remove()
print(f"  каналов измерено в {len(scale)} слоях", flush=True)
k = list(scale)[0]
s0 = scale[k].cpu().numpy()
print(f"  пример слоя {k}: разброс амплитуд каналов max/median = "
      f"{s0.max()/np.median(s0):.1f}x", flush=True)

rows = {}
for bits in (4, 5):
    for nm, r in RAT.items():
        cb = codebook(r, bits); plain = aw = den = 0.0
        for lname, mod in m.named_modules():
            if not (isinstance(mod, torch.nn.Linear) and "lm_head" not in lname): continue
            w = mod.weight.data.to(torch.float64)
            sc = w.abs().amax(dim=1, keepdim=True).clamp_min(1e-12)
            x = (w/sc).cpu().numpy()
            q = cb[np.abs(x[...,None]-cb[None,None,:]).argmin(-1)]
            d2 = (q-x)**2
            a = scale[lname].cpu().numpy()[None, :]      # (1, in_features)
            plain += float(d2.sum()); aw += float((d2 * a**2).sum()); den += d2.size
        rows[(bits, nm)] = (plain/den, aw/den)
        print(f"  {bits}b {nm:24} MSE={plain/den:.4e}  act-weighted={aw/den:.4e}", flush=True)

ppl = {(r["bits"], r["ladder"]): r["ppl"]
       for r in json.load(open(f"ladder_ppl_{TAG}.json")) if r["bits"]}
print(f"\n  {'бит':>4} {'по MSE':24} {'по акт.-взвеш.':24} {'по перплексии':24}")
for bits in (4,5):
    rr = [(nm, rows[(bits,nm)][0], rows[(bits,nm)][1], ppl[(bits,nm)]) for nm in RAT]
    a_ = min(rr,key=lambda t:t[1])[0]; b_ = min(rr,key=lambda t:t[2])[0]; c_ = min(rr,key=lambda t:t[3])[0]
    print(f"  {bits:4} {a_:24} {b_:24} {c_:24}"
          + ("   <-- взвешивание ИСПРАВИЛО" if a_!=c_ and b_==c_ else
             "   (не исправило)" if a_!=c_ else "   (и так совпадало)"))
json.dump({str(k_): v for k_, v in rows.items()}, open(f"awq_{TAG}.json","w"), indent=1)
