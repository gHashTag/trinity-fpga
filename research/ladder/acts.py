"""Does the ladder law hold on ACTIVATIONS, where the tails are heavier?

Everything measured so far is weights. Activations of a transformer are known to
carry outliers that weights do not, and the synthetic sweep says the optimal
ratio rises monotonically with tail weight. If activations are heavier-tailed,
the two sides of a ternary node want DIFFERENT rungs -- which is a fact about
how to build the node, not just about how to store it.
"""
import os, sys, json, numpy as np, torch
from transformers import AutoModelForCausalLM, AutoTokenizer
W = ("/private/tmp/claude-501/-Users-ssdm4-Desktop-PROJECTS-CLAUDE/"
     "0e868af8-ab2d-4d00-be03-8fea94ba48e4/scratchpad/weights")
TAG = sys.argv[1] if len(sys.argv) > 1 else "smollm2"
MODEL = os.path.join(W, TAG)
torch.set_grad_enabled(False)
RAT = {"shift": 2.0, "phi": (1+5**0.5)/2, "supergold": 1.465571231876768,
       "plastic": 1.324717957244746, "deg4": 1.178724176}

def c2(r):
    u = np.linspace(0, 1, 20001); x = r ** (-u)
    return float(np.mean((np.minimum(np.abs(x-1.0), np.abs(x-1.0/r))/x) ** 2))

def mse(x, r, bits):
    n = (2**bits - 1)//2; t = r ** (-(n-1)) / 2
    b = x < t
    return (c2(r) * float((x[~b]**2).sum()) + float((x[b]**2).sum())) / x.size

def r_star(x, bits, grid=np.linspace(1.02, 2.6, 400)):
    return float(grid[int(np.argmin([mse(x, float(v), bits) for v in grid]))])

tok = AutoTokenizer.from_pretrained(MODEL)
m = AutoModelForCausalLM.from_pretrained(MODEL, dtype=torch.float32); m.eval()
import pyarrow.parquet as pq
text = "\n\n".join(pq.read_table(os.path.join(W, "wikitext2-test.parquet"))
                   .column("text").to_pylist())
ids = tok(text, return_tensors="pt").input_ids[0][:2048*2].reshape(2, 2048)

# ловлю ВХОДЫ линейных слоёв -- это то, что умножается на веса
caught = []
def hook(mod, inp, out):
    a = inp[0].detach().reshape(-1, inp[0].shape[-1]).abs().to(torch.float64)
    s = a.amax(dim=1, keepdim=True).clamp_min(1e-12)          # нормировка на строку, как у весов на канал
    # Take a fixed small sample per layer. The first version kept every
    # activation of all 210 layers and did not finish; a sweep that cannot
    # complete measures nothing.
    v = (a/s).flatten()
    caught.append(v[::max(1, v.numel()//20000)].cpu().numpy().astype(np.float32))
hs = [mod.register_forward_hook(hook) for nm, mod in m.named_modules()
      if isinstance(mod, torch.nn.Linear) and "lm_head" not in nm]
for i in range(ids.shape[0]): m(ids[i:i+1])
for h in hs: h.remove()
a = np.concatenate(caught).astype(np.float64); del caught
print(f"  активаций собрано: {a.size:,}")

# те же веса, для сравнения на одной шкале
ws = []
for nm, mod in m.named_modules():
    if isinstance(mod, torch.nn.Linear) and "lm_head" not in nm:
        w = mod.weight.data.to(torch.float64)
        s = w.abs().amax(dim=1, keepdim=True).clamp_min(1e-12)
        vv = (w/s).abs().flatten()
        ws.append(vv[::max(1, vv.numel()//20000)].cpu().numpy().astype(np.float32))
wv = np.concatenate(ws).astype(np.float64); del ws
print(f"  весов (та же выборка):  {wv.size:,}\n")

def kurt(x): 
    mu=x.mean(); return float(((x-mu)**4).mean()/((x-mu)**2).mean()**2 - 3)
print(f"  {'что':12} {'экс.куртозис':>13} {'доля < 1/64':>12} " +
      " ".join(f"{'r*('+str(b)+'b)':>9}" for b in (3,4,5,6)))
for nm, x in (("веса", wv), ("активации", a)):
    print(f"  {nm:12} {kurt(x):13.2f} {float((x<1/64).mean()):12.4f} " +
          " ".join(f"{r_star(x,b):9.4f}" for b in (3,4,5,6)))
print()
print("  победитель по формуле:")
for nm, x in (("веса", wv), ("активации", a)):
    print(f"    {nm:12} " + " ".join(f"{min(RAT,key=lambda k:mse(x,RAT[k],b)):>10}" for b in (3,4,5,6)))
json.dump({"tag":TAG,"kurt_w":kurt(wv),"kurt_a":kurt(a),
           "rstar_w":[r_star(wv,b) for b in (3,4,5,6)],
           "rstar_a":[r_star(a,b) for b in (3,4,5,6)]}, open(f"acts_{TAG}.json","w"), indent=1)
