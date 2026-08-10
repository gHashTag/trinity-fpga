"""Can the crossover be predicted from the weight distribution alone?

Measured MSE ranks the ladders correctly (T31), but measuring it still needs a
pass over every weight for every candidate. If the MSE has a closed form in the
distribution, the rung follows from a histogram and a budget -- which is a law
rather than a procedure.

Model. Normalise each channel by its maximum, so levels are r^-k for
k = 0..n-1 with n = (2^b - 1)/2 magnitudes.

  * In range, a geometric ladder rounds with bounded RELATIVE error. Rounding
    x to the nearer of r^-k, r^-(k-1) gives |dx|/x <= (r-1)/(r+1), and over a
    log-uniform position within the bin the mean square relative error is
    obtained by integrating; call it c(r)^2.
  * Below half the smallest level the value rounds to zero and the whole of x
    is the error.

  MSE(r,b) ~ c(r)^2 * E[x^2 . 1{x>t}]  +  E[x^2 . 1{x<t}],  t = r^-(n-1)/2

The first term falls as r falls, the second rises. The minimum is the crossover.
"""
import os, sys, json, numpy as np, torch
from transformers import AutoModelForCausalLM
W = ("/private/tmp/claude-501/-Users-ssdm4-Desktop-PROJECTS-CLAUDE/"
     "0e868af8-ab2d-4d00-be03-8fea94ba48e4/scratchpad/weights")
torch.set_grad_enabled(False)
RAT = {"shift  (2^k,   deg 1)": 2.0, "phi    (1.618, deg 2)": (1+5**0.5)/2,
       "supergold (1.4656, d3)": 1.465571231876768,
       "plastic(1.3247, deg 3)": 1.324717957244746}

def c2(r):
    """Mean square relative rounding error of a geometric ladder of ratio r.

    A value at log-position u in [0,1] across a bin sits at r^-u times the upper
    level; it rounds to whichever level is nearer, giving relative error
    |r^-u - 1| below the split and |r^-u - r^-1|/r^-1 above it. Integrating
    over u in [0,1] is one-dimensional and done numerically here rather than in
    closed form, since the split point itself depends on r."""
    u = np.linspace(0, 1, 20001)
    x = r ** (-u)                       # value, relative to the upper level 1
    err = np.minimum(np.abs(x - 1.0), np.abs(x - 1.0 / r) ) / x
    return float(np.mean(err ** 2))

print("  загружаю веса ...", flush=True)
m = AutoModelForCausalLM.from_pretrained(os.path.join(W, sys.argv[1] if len(sys.argv)>1 else "smollm2"), dtype=torch.float32)
xs = []
for nm, mod in m.named_modules():
    if isinstance(mod, torch.nn.Linear) and "lm_head" not in nm:
        w = mod.weight.data.to(torch.float64)
        s = w.abs().amax(dim=1, keepdim=True).clamp_min(1e-12)
        xs.append((w / s).abs().flatten().cpu().numpy().astype(np.float32))
x = np.concatenate(xs); del xs, m
print(f"  нормированных весов: {x.size:,}")
x2 = x.astype(np.float64) ** 2
order = np.argsort(x); xs_ = x[order]; c2s = np.cumsum(x2[order])   # для E[x^2 . 1{x<t}]
tot = c2s[-1]

def predict(r, bits):
    n = (2 ** bits - 1) // 2
    t = r ** (-(n - 1)) / 2
    i = np.searchsorted(xs_, t)
    below = c2s[i - 1] if i > 0 else 0.0
    above = tot - below
    return (c2(r) * above + below) / x.size

meas = {}
for b in (3, 4, 5):
    for nm, r in RAT.items():
        meas[(b, nm)] = predict(r, b)


TAG = sys.argv[1] if len(sys.argv)>1 else "smollm2"
ppl = {(r["bits"], r["ladder"]): r["ppl"]
       for r in json.load(open(f"ladder_ppl_{TAG}.json")) if r["bits"]}
print(f"\n  {'бит':>4} {'формула выбирает':24} {'перплексия выбирает':24} совпало")
agree=0
for b in (3,4,5):
    rows=[(nm, meas[(b,nm)], ppl[(b,nm)]) for nm in RAT if (b,nm) in ppl]
    if not rows: continue
    f=min(rows,key=lambda t:t[1])[0]; m_=min(rows,key=lambda t:t[2])[0]
    ok = f==m_; agree += ok
    print(f"  {b:4} {f:24} {m_:24} {'ДА' if ok else 'нет'}")
print(f"\n  предсказано из одной гистограммы, без прогона модели: {agree}/3")
rr=np.linspace(1.02,2.6,800)
print("  оптимальное r по формуле:")
for b in (3,4,5,6,7,8):
    v=[predict(float(z),b) for z in rr]
    print(f"    {b} бит: r* = {rr[int(np.argmin(v))]:.4f}")
