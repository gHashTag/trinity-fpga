"""B: what in a distribution's shape moves the optimal ladder.  C: do activations differ?

B -- SYNTHETIC. The two-term score reproduces all six measured winners with one lambda, but
lambda was fitted to those six outcomes. Before treating it as a law, it is worth seeing what it
says about distributions in general: sweep log-normal tail weight and read off r* and the winning
named ladder. If r* moves smoothly and monotonically with tail weight, the criterion is at least
describing a real dependence rather than memorising two histograms.

C -- ACTIVATIONS. Everything measured so far is weights. Activations are heavier-tailed (measured
separately: within-block excess kurtosis 3.5 against 0.05 for weights), so the optimal rung may
differ. If it does, a ternary node needs two different ladders on its two sides -- a concrete
consequence for the hardware, and one that follows from the criterion rather than from taste.

No perplexity ground truth exists for either case, so both produce PREDICTIONS, labelled as such.
"""
import os
import numpy as np, torch
from transformers import AutoModelForCausalLM

LAM = 0.01                      # from two_term.py; fitted to six measured winners
RAT = {"shift": 2.0, "phi": (1 + 5 ** 0.5) / 2,
       "supergold": 1.465571231876768, "plastic": 1.324717957244746}


def codebook(r, bits):
    n = (2 ** bits - 1) // 2
    return np.sort(np.array([0.0] + [r ** (-k) for k in range(n)]
                            + [-(r ** (-k)) for k in range(n)]))


def score(x, r, bits, lam=LAM):
    n = (2 ** bits - 1) // 2
    cb = codebook(r, bits); mid = (cb[:-1] + cb[1:]) / 2
    mse = float(((cb[np.searchsorted(mid, x)] - x) ** 2).mean())
    flush = float((np.abs(x) < r ** (-(n - 1)) / 2).mean())
    return mse + lam * flush, mse, flush


def best_named(x, bits):
    return min(RAT, key=lambda k: score(x, RAT[k], bits)[0])


def r_star(x, bits, grid=np.linspace(1.05, 2.6, 60)):
    return float(grid[int(np.argmin([score(x, float(v), bits)[0] for v in grid]))])


print("B -- SYNTHETIC: log-normal tail weight vs the optimal rung\n")
rng = np.random.default_rng(0)
print(f"  {'sigma':>6}{'excess kurt':>13}{'r*(3b)':>9}{'r*(4b)':>9}{'r*(5b)':>9}"
      f"   winners 3b / 4b / 5b")
for sg in (0.2, 0.4, 0.6, 0.8, 1.0, 1.3, 1.6, 2.0):
    v = rng.lognormal(0.0, sg, 120000) * rng.choice([-1.0, 1.0], 120000)
    v = v / np.abs(v).max()
    k = float(((v - v.mean()) ** 4).mean() / v.std() ** 4 - 3)
    print(f"  {sg:>6.1f}{k:>13.1f}"
          + "".join(f"{r_star(v, b):>9.4f}" for b in (3, 4, 5))
          + "   " + " / ".join(best_named(v, b) for b in (3, 4, 5)))

print("\n\nC -- ACTIVATIONS vs WEIGHTS (SmolLM2, real forward pass)\n")
W = ("/private/tmp/claude-501/-Users-ssdm4-Desktop-PROJECTS-CLAUDE/"
     "0e868af8-ab2d-4d00-be03-8fea94ba48e4/scratchpad/weights")
torch.set_grad_enabled(False)
from transformers import AutoTokenizer
import pyarrow.parquet as pq
tok = AutoTokenizer.from_pretrained(os.path.join(W, "smollm2"))
m = AutoModelForCausalLM.from_pretrained(os.path.join(W, "smollm2"),
                                         dtype=torch.float32).eval()
text = "\n\n".join(pq.read_table(os.path.join(W, "wikitext2-test.parquet"))
                   .column("text").to_pylist())
ids = tok(text, return_tensors="pt").input_ids[0][:2048].view(1, 2048)
caps = {}


def mk(n):
    def h(mod, inp, out):
        if n not in caps:
            a = inp[0].detach().double().reshape(-1, inp[0].shape[-1])
            s = a.abs().amax(dim=1, keepdim=True).clamp_min(1e-12)
            caps[n] = (a / s).cpu().numpy().ravel()[::29]
    return h


hs = [mod.register_forward_hook(mk(n)) for n, mod in m.named_modules()
      if isinstance(mod, torch.nn.Linear) and "lm_head" not in n]
m(ids)
for h in hs:
    h.remove()
act = np.concatenate(list(caps.values()))
wts = []
for n, mod in m.named_modules():
    if isinstance(mod, torch.nn.Linear) and "lm_head" not in n:
        w = mod.weight.data.to(torch.float64)
        s = w.abs().amax(dim=1, keepdim=True).clamp_min(1e-12)
        z = (w / s).cpu().numpy().ravel()
        wts.append(z[:: max(1, z.size // 60000)])
wts = np.concatenate(wts)


def kurt(z):
    return float(((z - z.mean()) ** 4).mean() / z.std() ** 4 - 3)


print(f"  weights     {wts.size:>10,} samples   excess kurtosis {kurt(wts):+8.2f}")
print(f"  activations {act.size:>10,} samples   excess kurtosis {kurt(act):+8.2f}\n")
print(f"  {'bits':>5}{'r* weights':>12}{'r* acts':>10}   winner weights / activations"
      f"   flushed w / a")
for b in (3, 4, 5):
    rw, ra = r_star(wts, b), r_star(act, b)
    bw, ba = best_named(wts, b), best_named(act, b)
    fw = score(wts, RAT[bw], b)[2] * 100
    fa = score(act, RAT[ba], b)[2] * 100
    flag = "  <-- DIFFERENT" if bw != ba else ""
    print(f"  {b:>5}{rw:>12.4f}{ra:>10.4f}   {bw:10} / {ba:<10}"
          f"   {fw:5.1f}% / {fa:5.1f}%{flag}")
print("\n  PREDICTIONS only -- no activation-quantised perplexity has been measured.")
