"""Three regimes, not one law: why the closed form gets 3 and 5 bits and misses 4.

Measured flush fraction (weights below the smallest level, deleted rather than rounded):

    3 bits   42-76% flushed   -> coverage dominates; flush order EQUALS perplexity order
    4 bits    3-33% flushed   -> neither flush nor MSE orders correctly
    5 bits  0.01-3.8% flushed -> resolution dominates; MSE order equals perplexity order

So the two budgets the closed form predicts are the two where a single factor dominates and MSE
happens to align with it. Four bits is the CROSSOVER, where reach and resolution are comparable
and an energy-weighted criterion mis-ranks: phi carries more squared error than supergolden and
deletes 8 points fewer weights, and perplexity prefers the deletion.

A criterion that spans all three regimes therefore needs both terms:

    score(r, b) = MSE(r, b) + lambda * flush(r, b)

This sweeps lambda and asks whether ANY single value ranks all three budgets on BOTH models. If
one does, the law extends. If none does, the two effects are not exchangeable at a fixed rate and
the honest statement is that 4 bits is a genuine crossover requiring measurement.
"""
import json, os
import numpy as np, torch
from transformers import AutoModelForCausalLM

W = ("/private/tmp/claude-501/-Users-ssdm4-Desktop-PROJECTS-CLAUDE/"
     "0e868af8-ab2d-4d00-be03-8fea94ba48e4/scratchpad/weights")
torch.set_grad_enabled(False)
RAT = {"shift": 2.0, "phi": (1 + 5 ** 0.5) / 2,
       "supergold": 1.465571231876768, "plastic": 1.324717957244746}
NAME = {"shift": "shift  (2^k,   deg 1)", "phi": "phi    (1.618, deg 2)",
        "supergold": "supergold (1.4656, d3)", "plastic": "plastic(1.3247, deg 3)"}


def codebook(r, bits):
    n = (2 ** bits - 1) // 2
    return np.sort(np.array([0.0] + [r ** (-k) for k in range(n)]
                            + [-(r ** (-k)) for k in range(n)]))


D = {}
for MDIR in ("smollm2", "qwen"):
    ppl = {(r["bits"], r["ladder"]): r["ppl"]
           for r in json.load(open(f"ladder_ppl_{MDIR}.json")) if r["bits"]}
    m = AutoModelForCausalLM.from_pretrained(os.path.join(W, MDIR), dtype=torch.float32)
    parts = []
    for nm, mod in m.named_modules():
        if isinstance(mod, torch.nn.Linear) and "lm_head" not in nm:
            w = mod.weight.data.to(torch.float64)
            s = w.abs().amax(dim=1, keepdim=True).clamp_min(1e-12)
            x = (w / s).cpu().numpy().ravel()
            parts.append(x[:: max(1, x.size // 400000)])
    x = np.concatenate(parts); del m
    for bits in (3, 4, 5):
        n = (2 ** bits - 1) // 2
        for k, r in RAT.items():
            cb = codebook(r, bits); mid = (cb[:-1] + cb[1:]) / 2
            mse = float(((cb[np.searchsorted(mid, x)] - x) ** 2).mean())
            flush = float((np.abs(x) < r ** (-(n - 1)) / 2).mean())
            D[(MDIR, bits, k)] = (mse, flush, ppl[(bits, NAME[k])])
    print(f"  {MDIR}: {x.size:,} sampled weights")

print("\n  score = MSE + lambda * flush     (sweeping lambda)\n")
print(f"  {'lambda':>10}  {'smollm2 correct':>16}  {'qwen correct':>14}  both")
best = []
for lam in [0.0, 1e-4, 3e-4, 1e-3, 2e-3, 3e-3, 5e-3, 1e-2, 2e-2, 5e-2, 1e-1, 1e0]:
    res = {}
    for MDIR in ("smollm2", "qwen"):
        ok = 0
        for bits in (3, 4, 5):
            rows = [(k,) + D[(MDIR, bits, k)] for k in RAT]
            bs = min(rows, key=lambda t: t[1] + lam * t[2])[0]
            bp = min(rows, key=lambda t: t[3])[0]
            ok += (bs == bp)
        res[MDIR] = ok
    both = res["smollm2"] == 3 and res["qwen"] == 3
    if both:
        best.append(lam)
    print(f"  {lam:>10.0e}  {res['smollm2']:>13}/3  {res['qwen']:>11}/3  "
          + ("ALL SIX" if both else ""))
print(f"\n  lambdas ranking all three budgets on both models: "
      + (f"{best}" if best else "NONE"))
if best:
    lam = best[len(best) // 2]
    print(f"\n  at lambda = {lam:.0e}:")
    for MDIR in ("smollm2", "qwen"):
        for bits in (3, 4, 5):
            rows = [(k,) + D[(MDIR, bits, k)] for k in RAT]
            o_s = [t[0] for t in sorted(rows, key=lambda t: t[1] + lam * t[2])]
            o_p = [t[0] for t in sorted(rows, key=lambda t: t[3])]
            print(f"    {MDIR:8} {bits}b  score={o_s}  ppl={o_p}  "
                  f"{'FULL ORDER' if o_s == o_p else 'winner only' if o_s[0]==o_p[0] else 'WRONG'}")
