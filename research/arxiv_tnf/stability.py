#!/usr/bin/env python3
"""W946: what is the sigma = 46 actually made of?

The one surviving claim from W945 is stability: with quantised activations on
MNIST, fp6 e2m3 lands at sigma = 46.09 and fp6 e3m2 at 32.33, while TNF4 sits at
0.21. A standard deviation that large is not "noise" -- it is a mixture of runs
that trained and runs that did not, and the useful question is what separates them.

This logs, per seed and per epoch: test accuracy, and the learned activation scale
of each layer. If the scale diverges or collapses in the failing runs, the finding
is about the RECIPE (a scale that runs away on a sparse grid) rather than about the
format -- and that distinction decides whether the claim survives.
"""
import gzip, json, pathlib, sys, time
import numpy as np
import torch
import torch.nn as nn

# W948d: T27_WORK is where datasets live and records are written; T27_CONFORMANCE
# points at the oracles (repo: conformance/). Defaults keep the original bench
# working, but a replicator needs neither path to exist.
import os as _env
SC = pathlib.Path(_env.environ.get("T27_WORK") or
                  "/private/tmp/claude-501/-Users-playom-t27--claude-worktrees-igla-fpga-improvements-3f5e1a/"
                  "eeed4a0e-20e8-40f4-aa16-1ecfee4ad92d/scratchpad")
sys.path.insert(0, _env.environ.get("T27_CONFORMANCE") or str(SC / "upstream-wt/conformance"))
import tnf_ref as T, fp8_ref as F8

SEEDS = [20260820, 7, 1337, 424242, 99991]
FORMATS = {"TNF4": (T, T.TNFFormat(2, 1), 6),
           "fp6e2m3": (F8, F8.FORMATS["fp6_e2m3"], 6),
           "fp6e3m2": (F8, F8.FORMATS["fp6_e3m2"], 6)}
# W949: the published copy had this hard-coded at 3 while the copy that produced
# the 10- and 30-epoch records read it from the environment. FALSIFY-ME.md tells
# a replicator to set EPOCHS; on the published rig that knob did not exist.
EPOCHS = int(_env.environ.get("EPOCHS", "3"))


def value_set(mod, fmt, bits):
    v = []
    for c in range(1 << bits):
        try:
            x = float(mod.decode(fmt, c))
        except Exception:
            continue
        if np.isfinite(x):
            v.append(x)
    a = np.unique(np.array(sorted(set(v)), dtype=np.float32))
    assert (a < 0).any()
    return torch.from_numpy(a)


def snap(x, vals):
    i = torch.bucketize(x, vals).clamp(1, len(vals) - 1)
    lo, hi = vals[i - 1], vals[i]
    return torch.where((x - lo).abs() <= (hi - x).abs(), lo, hi)


class LSQ(torch.autograd.Function):
    """LSQ with the gradient-scaling factor the paper prescribes.

    Esser et al. scale the step-size gradient by 1/sqrt(N * Qp) so that the scale
    parameter moves on the same footing as the weights. Omitting it is exactly how
    a scale runs away: W946 measured layer-2 scales collapsing 0.81 -> 0.29 ->
    0.0065 in every failing run and stabilising in every surviving one.
    """
    @staticmethod
    def forward(ctx, x, s, vals):
        xs = x / s
        q = snap(xs, vals)
        ctx.save_for_backward(xs, q)
        ctx.gscale = 1.0 / max((x.numel() * max(float(vals.abs().max()), 1.0)) ** 0.5, 1.0)
        return q * s

    @staticmethod
    def backward(ctx, g):
        xs, q = ctx.saved_tensors
        gs = ctx.gscale if GRAD_SCALE else 1.0
        return g, (g * (q - xs)).sum().reshape(1) * gs, None


GRAD_SCALE = True
import os
INIT_PCT = float(os.environ['INIT_PCT']) if os.environ.get('INIT_PCT') else None


class QLinear(nn.Linear):
    vals = None
    act_vals = None

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.ws = nn.Parameter(torch.ones(1))
        self.as_ = nn.Parameter(torch.ones(1))
        self._init = False

    def forward(self, x):
        if QLinear.vals is None:
            return nn.functional.linear(x, self.weight, self.bias)
        if not self._init:
            with torch.no_grad():
                # W949: SCALE_RULE names the convention. peak2one maps the tensor
                # peak onto grid value 1.0 -- what produced every record in this
                # project, kept as the default so they stay reproducible. peak2max
                # maps it onto the format's maximum, which is the standard max rule
                # and the one the withdrawn range mechanism assumed. The two are not
                # cosmetic: they move fp6 e3m2 from 0/5 failures to 5/5 (T798a).
                _d = 1.0 if _env.environ.get("SCALE_RULE", "peak2one") == "peak2one" \
                    else float(QLinear.vals.abs().max())
                self.ws.fill_(max(float(self.weight.abs().max()) / _d, 1e-8))
                # W947: a max-rule scale is the worst case for a narrow-range grid --
                # fp6 e2m3 spans 5.9 binades against TNF4's 14.6, so under max
                # scaling everything below 1.67 % of the peak underflows. A
                # percentile init is the standard mitigation; INIT_PCT selects it.
                if INIT_PCT is not None and x.numel():
                    v = float(np.quantile(np.abs(x.detach().numpy()), INIT_PCT))
                    self.as_.fill_(max(v / _d, 1e-8))
                else:
                    self.as_.fill_(max(float(x.abs().max()) / _d, 1e-8) if x.numel() else 1.0)
            self._init = True
        w = LSQ.apply(self.weight, self.ws.abs().clamp(min=1e-8), QLinear.vals)
        if QLinear.act_vals is not None:
            x = LSQ.apply(x, self.as_.abs().clamp(min=1e-8), QLinear.act_vals)
        return nn.functional.linear(x, w, self.bias)


def idx(path, kind):
    raw = gzip.open(path, "rb").read()
    if kind == "img":
        n = int.from_bytes(raw[4:8], "big")
        return np.frombuffer(raw[16:], np.uint8).reshape(n, 784).astype(np.float32) / 255.0
    return np.frombuffer(raw[8:], np.uint8).astype(np.int64)


def main():
    import os as _os
    d = SC / _os.environ.get("TASK", "mnist")
    Xtr, ytr = idx(d / "train-images-idx3-ubyte.gz", "img"), idx(d / "train-labels-idx1-ubyte.gz", "lab")
    Xte, yte = idx(d / "t10k-images-idx3-ubyte.gz", "img"), idx(d / "t10k-labels-idx1-ubyte.gz", "lab")
    Xv, yv = torch.from_numpy(Xte), torch.from_numpy(yte)
    Xt, yt = torch.from_numpy(Xtr), torch.from_numpy(ytr)
    sets = {k: value_set(*v) for k, v in FORMATS.items()}
    out = {"task": __import__("os").environ.get("TASK","mnist"), "seeds": SEEDS, "epochs": EPOCHS, "runs": {}}
    for name, vals in sets.items():
        QLinear.vals = QLinear.act_vals = vals
        for seed in SEEDS:
            torch.manual_seed(seed)
            net = nn.Sequential(QLinear(784, 256), nn.ReLU(), QLinear(256, 256), nn.ReLU(), QLinear(256, 10))
            opt = torch.optim.Adam(net.parameters(), lr=1e-3)
            lf = nn.CrossEntropyLoss()
            trace = []
            for ep in range(EPOCHS):
                perm = torch.randperm(len(Xt))
                for i in range(0, len(Xt), 256):
                    b = perm[i:i + 256]
                    opt.zero_grad(); lf(net(Xt[b]), yt[b]).backward(); opt.step()
                with torch.no_grad():
                    acc = (net(Xv).argmax(1) == yv).float().mean().item()
                    scales = [float(m.as_.abs()) for m in net if isinstance(m, QLinear)]
                    wsc = [float(m.ws.abs()) for m in net if isinstance(m, QLinear)]
                trace.append({"epoch": ep + 1, "acc": acc,
                              "act_scales": [round(s, 5) for s in scales],
                              "w_scales": [round(s, 5) for s in wsc]})
            out["runs"].setdefault(name, {})[str(seed)] = trace
            f = trace[-1]
            print(f"  {name:8} сид {seed:8}: точность {f['acc']*100:6.2f}%  "
                  f"масштабы активаций {f['act_scales']}  весов {f['w_scales']}", flush=True)
        QLinear.vals = QLinear.act_vals = None
    # W948d: EPOCHS belongs in the name. Without it a 10-epoch and a 30-epoch run
    # on the same task+recipe write the same path, and the second silently
    # destroys the first -- two W948 records survived only because they had
    # already been copied into the repository under a wave-suffixed name.
    # W949: the convention belongs in the name too -- peak2one and peak2max are
    # different experiments (T798a), not different runs of one.
    _pref = "stability_" if _env.environ.get("SCALE_RULE", "peak2one") == "peak2one" else "stability_p2m_"
    _task = _env.environ.get("TASK", "mnist")
    _rec = f"pct{INIT_PCT}" if INIT_PCT else "gs"
    p = SC / f"{_pref}{_task}_{_rec}_{EPOCHS}ep.json"
    p.write_text(json.dumps(out, indent=1))
    print("\nWROTE " + str(p), flush=True)


if __name__ == "__main__":
    main()
