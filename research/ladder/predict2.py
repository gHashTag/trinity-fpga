"""Second attempt: does weight MSE predict which ladder wins on perplexity?

The first predictor said 'cover the channel's dynamic range' and picked the
coarsest ladder every time. It fails at 4 and 5 bits, and the reason is that
clipping the SMALLEST weights costs almost nothing -- a small weight contributes
little to the output, so under-ranging it is cheap while rounding a large one is
not. The trade is therefore not coverage but total error, and total error is
computable from the weights alone.
"""
import os, json, numpy as np, torch
from transformers import AutoModelForCausalLM
W = ("/private/tmp/claude-501/-Users-ssdm4-Desktop-PROJECTS-CLAUDE/"
     "0e868af8-ab2d-4d00-be03-8fea94ba48e4/scratchpad/weights")
torch.set_grad_enabled(False)
RAT = {"shift  (2^k,   deg 1)": 2.0, "phi    (1.618, deg 2)": (1+5**0.5)/2,
       "supergold (1.4656, d3)": 1.465571231876768,
       "plastic(1.3247, deg 3)": 1.324717957244746}

def codebook(r, bits):
    n = (2**bits - 1)//2
    return np.array([0.0] + [r**(-k) for k in range(n)] + [-r**(-k) for k in range(n)])

m = AutoModelForCausalLM.from_pretrained(os.path.join(W, "smollm2"), dtype=torch.float32)
mods = [(nm, mod) for nm, mod in m.named_modules()
        if isinstance(mod, torch.nn.Linear) and "lm_head" not in nm]
print(f"  слоёв: {len(mods)}")
out = {}
for bits in (3,4,5):
    for nm, r in RAT.items():
        cb = codebook(r, bits); num = den = 0.0
        for _, mod in mods:
            w = mod.weight.data.to(torch.float64)
            s = w.abs().amax(dim=1, keepdim=True).clamp_min(1e-12)
            x = (w/s).cpu().numpy()
            q = cb[np.abs(x[...,None] - cb[None,None,:]).argmin(-1)]
            num += float(((q-x)**2).sum()); den += x.size
        out[(bits,nm)] = num/den
        print(f"    {bits}b {nm:24} MSE={num/den:.6e}", flush=True)
ppl = {(r["bits"], r["ladder"]): r["ppl"] for r in json.load(open("ladder_ppl.json"))
       if r["bits"]}
print("\n  ПРОВЕРКА: совпадает ли порядок MSE с порядком перплексии")
allok = True
for bits in (3,4,5):
    rows = [(nm, out[(bits,nm)], ppl[(bits,nm)]) for nm in RAT]
    bm = min(rows, key=lambda t: t[1])[0]; bp = min(rows, key=lambda t: t[2])[0]
    ok = bm == bp; allok &= ok
    print(f"    {bits}b  MSE-лучшая={bm:24} перплексия-лучшая={bp:24} "
          + ("✓" if ok else "✗"))
    order_m = [t[0] for t in sorted(rows, key=lambda t: t[1])]
    order_p = [t[0] for t in sorted(rows, key=lambda t: t[2])]
    print(f"         порядок MSE : {[o.split()[0] for o in order_m]}")
    print(f"         порядок ppl : {[o.split()[0] for o in order_p]}")
print(f"\n  предсказание по одним весам, без единого прогона модели: "
      + ("РАБОТАЕТ" if allok else "не работает"))
