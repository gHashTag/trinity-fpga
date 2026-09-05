"""The four-bit transposition, tried with second-order sensitivity.

Activation weighting explained one model and failed on the other. The next
candidate is the quantity the transposition is really about: how much the LOSS
moves when a weight moves. To first order that is the gradient, and the standard
diagonal approximation to the curvature is its square, so rank the ladders by

    sum_ij g_ij^2 dw_ij^2 ,   g = dL/dw

instead of by sum dw^2. Unlike the activation norm, this is a property of the
loss surface rather than of one operand's distribution, so if the transposition
is a loss-sensitivity effect this should catch it on BOTH models or on neither.
"""
import os, sys, json, numpy as np, torch
from transformers import AutoModelForCausalLM, AutoTokenizer
W = ("/private/tmp/claude-501/-Users-ssdm4-Desktop-PROJECTS-CLAUDE/"
     "0e868af8-ab2d-4d00-be03-8fea94ba48e4/scratchpad/weights")
TAG = sys.argv[1] if len(sys.argv) > 1 else "smollm2"
MODEL = os.path.join(W, TAG)
RAT = {"shift  (2^k,   deg 1)": 2.0, "phi    (1.618, deg 2)": (1+5**0.5)/2,
       "supergold (1.4656, d3)": 1.465571231876768,
       "plastic(1.3247, deg 3)": 1.324717957244746}

def codebook(r, bits):
    n = (2**bits - 1)//2
    return np.array([0.0] + [r**(-k) for k in range(n)] + [-r**(-k) for k in range(n)])

tok = AutoTokenizer.from_pretrained(MODEL)
m = AutoModelForCausalLM.from_pretrained(MODEL, dtype=torch.float32); m.eval()
import pyarrow.parquet as pq
text = "\n\n".join(pq.read_table(os.path.join(W,"wikitext2-test.parquet")).column("text").to_pylist())
ids = tok(text, return_tensors="pt").input_ids[0][:2048*4].reshape(4, 2048)

lin = [(nm, mod) for nm, mod in m.named_modules()
       if isinstance(mod, torch.nn.Linear) and "lm_head" not in nm]
for p in m.parameters(): p.requires_grad_(False)
for _, mod in lin: mod.weight.requires_grad_(True)
fisher = {nm: torch.zeros_like(mod.weight) for nm, mod in lin}
for i in range(ids.shape[0]):
    m.zero_grad(set_to_none=True)
    c = ids[i:i+1]
    m(c, labels=c).loss.backward()
    for nm, mod in lin:
        if mod.weight.grad is not None: fisher[nm] += mod.weight.grad.detach() ** 2
    print(f"  окно {i+1}/{ids.shape[0]}", flush=True)
for nm in fisher: fisher[nm] /= ids.shape[0]
torch.set_grad_enabled(False)
f0 = fisher[lin[0][0]].cpu().numpy()
print(f"  чувствительность: max/median = {f0.max()/max(np.median(f0),1e-30):.3g}", flush=True)

rows = {}
for bits in (4, 5):
    for nm, r in RAT.items():
        cb = codebook(r, bits); plain = fw = den = 0.0
        for lname, mod in lin:
            w = mod.weight.data.double()
            sc = w.abs().amax(dim=1, keepdim=True).clamp_min(1e-12)
            x = (w/sc).cpu().numpy()
            q = cb[np.abs(x[...,None]-cb[None,None,:]).argmin(-1)]
            d2 = (q-x)**2
            g2 = fisher[lname].double().cpu().numpy()
            plain += float(d2.sum()); fw += float((d2*g2).sum()); den += d2.size
        rows[(bits,nm)] = (plain/den, fw/den)
        print(f"  {bits}b {nm:24} MSE={plain/den:.4e}  fisher={fw/den:.4e}", flush=True)

ppl = {(r["bits"], r["ladder"]): r["ppl"]
       for r in json.load(open(f"ladder_ppl_{TAG}.json")) if r["bits"]}
print(f"\n  {'бит':>4} {'по MSE':24} {'по Фишеру':24} {'по перплексии':24}")
for bits in (4,5):
    rr = [(nm, rows[(bits,nm)][0], rows[(bits,nm)][1], ppl[(bits,nm)]) for nm in RAT]
    a_=min(rr,key=lambda t:t[1])[0]; b_=min(rr,key=lambda t:t[2])[0]; c_=min(rr,key=lambda t:t[3])[0]
    print(f"  {bits:4} {a_:24} {b_:24} {c_:24}"
          + ("   <-- ФИШЕР ИСПРАВИЛ" if a_!=c_ and b_==c_ else
             "   (не исправил)" if a_!=c_ else "   (и так совпадало)"))
json.dump({str(k): v for k, v in rows.items()}, open(f"fisher_{TAG}.json","w"), indent=1)
