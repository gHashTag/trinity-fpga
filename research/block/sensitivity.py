#!/usr/bin/env python3
"""If the weights look the same after the scale, the difference is in the loss.

Block-normalised kurtosis is near-constant across checkpoints (see
PREREGISTRATION_SCALE_ABSORBS_2026-08-12.md) while MXFP4's cost spans 21x, from
+8.2% on bloom-560m to +174.4% on gpt-neo-125m. The perturbation the codebook
applies is the same shape everywhere; what differs must be how much the model's
output moves when its weights are perturbed by that shape.

So: perturb by a FIXED RELATIVE SIZE that has nothing to do with any codebook,
and measure the perplexity response. Gaussian noise of relative norm eps applied
to exactly the tensors the campaign quantises, on exactly the windows it scores.

    sensitivity(eps) = (ppl(w + noise) / ppl(w) - 1) / eps^2

The eps^2 divisor is the first-order expectation: for a smooth loss, isotropic
noise of relative size eps raises the loss by (1/2) eps^2 w'Hw to leading order,
so the ratio is scale-free and comparable across checkpoints. Whether it IS
quadratic here is not assumed -- two eps are measured and the ratio is reported,
so a departure from quadratic shows up rather than being hidden by the divisor.

Two controls that decide whether the number means anything:
  * the SAME seed on every checkpoint, so the noise draw is not a confound;
  * a zero-eps run, which must reproduce the fp32 ruler exactly -- if it does
    not, the harness is not measuring what it claims and no eps figure counts.

    MDIR=<tag> python3 sensitivity.py
"""
import json
import os
import sys
import time

import numpy as np
import torch

HERE = os.path.dirname(os.path.abspath(__file__))
W = ("/private/tmp/claude-501/-Users-ssdm4-Desktop-PROJECTS-CLAUDE/"
     "0e868af8-ab2d-4d00-be03-8fea94ba48e4/scratchpad/weights")

_s = open(os.path.join(HERE, "block_tnf.py"), encoding="utf-8").read()
ns = {}
exec(compile(_s.split('print("загружаю модель…", flush=True)')[0],
             "block_tnf.py", "exec"), ns)
target_modules, SEQLEN = ns["target_modules"], ns["SEQLEN"]

import provenance as PV                                          # noqa: E402

SRC = {"smollm2": "HuggingFaceTB/SmolLM2-135M", "qwen": "Qwen/Qwen2.5-0.5B",
       "pythia": "EleutherAI/pythia-160m", "opt": "facebook/opt-125m",
       "gpt2": "gpt2", "gptneo": "EleutherAI/gpt-neo-125m",
       "bloom": "bigscience/bloom-560m", "mamba": "state-spaces/mamba-130m-hf"}
# gpt2's positional table is 1024, so it gets 80 windows for the same token span
NWIN = {"gpt2": 80}
SEQ = {"gpt2": 1024}
EPS = [0.005, 0.01, 0.02, 0.04]
SEED = 20260812


def main():
    import pyarrow.parquet as pq
    from transformers import AutoModelForCausalLM, AutoTokenizer

    tag = os.environ["MDIR"]
    src = SRC[tag]
    seqlen, nwin = SEQ.get(tag, SEQLEN), NWIN.get(tag, 40)

    txt = "\n\n".join(pq.read_table(
        os.path.join(W, "wikitext2-test.parquet")).column("text").to_pylist())
    tok = AutoTokenizer.from_pretrained(src)
    mdl = AutoModelForCausalLM.from_pretrained(src, dtype=torch.float32)
    mdl.eval()
    ids = tok(txt, return_tensors="pt").input_ids[0]
    win = ids[:(ids.numel() // seqlen) * seqlen].view(-1, seqlen)[:nwin]
    if win.shape[0] < nwin:
        print(f"ABORT: {win.shape[0]} windows, {nwin} required")
        return 3

    mods = [t[1] if isinstance(t, tuple) else t for t in target_modules(mdl)]
    orig = [m.weight.data.clone() for m in mods]
    nelem = sum(o.numel() for o in orig)
    print(f"  {tag}: {len(mods)} tensors, {nelem:,} elements, "
          f"{nwin} x {seqlen} windows", flush=True)

    def ppl():
        with torch.no_grad():
            return float(np.exp(np.mean(
                [float(mdl(win[i:i + 1], labels=win[i:i + 1]).loss)
                 for i in range(nwin)])))

    def perturb(eps):
        g = torch.Generator().manual_seed(SEED)
        for m, o in zip(mods, orig):
            n = torch.randn(o.shape, generator=g, dtype=o.dtype)
            # relative to the tensor's own RMS, so eps means the same thing on a
            # tensor of any scale -- the point is a fixed RELATIVE perturbation
            m.weight.data = o + n * (eps * o.pow(2).mean().sqrt() / n.pow(2).mean().sqrt())

    t0 = time.time()
    p0 = ppl()
    print(f"   eps=0      ppl {p0:.4f}   ({time.time()-t0:.0f}s)", flush=True)

    # CONTROL: eps=0 through the perturbation path must return the same number.
    perturb(0.0)
    pz = ppl()
    if abs(pz / p0 - 1) > 1e-9:
        print(f"ABORT: the eps=0 perturbation changed ppl {p0:.6f} -> {pz:.6f}. "
              "The harness is not measuring what it claims.")
        return 4
    print("   eps=0 through the perturbation path is bit-identical  CONTROL OK",
          flush=True)

    out = {"model": tag, "src": src, "nwin": nwin, "seqlen": seqlen,
           "n_tensors": len(mods), "n_elements": nelem, "seed": SEED,
           "ppl_fp32": p0, "eps": {},
           "provenance": PV.describe(joined_text=txt, src=src)}
    for eps in EPS:
        t0 = time.time()
        perturb(eps)
        p = ppl()
        rel = p / p0 - 1
        out["eps"][str(eps)] = {"ppl": p, "rel": rel, "sens": rel / eps ** 2}
        print(f"   eps={eps:<6} ppl {p:9.4f}   rel {100*rel:+7.2f}%   "
              f"sens {rel/eps**2:8.2f}   ({time.time()-t0:.0f}s)", flush=True)

    # Fit rel = C * eps^alpha. A smooth second-order expansion around a
    # minimum gives alpha = 2 exactly; anything else says the quadratic form
    # does not govern at these perturbation sizes, which is a statement about
    # half the quantisation literature's standing assumption. So the exponent is
    # FITTED and reported, never assumed -- and the per-step ratios are printed
    # beside it, because a single fitted alpha can hide curvature.
    le = np.log(np.array(EPS))
    lr = np.log(np.array([out["eps"][str(e)]["rel"] for e in EPS]))
    alpha, logC = np.polyfit(le, lr, 1)
    resid = float(np.max(np.abs(lr - (alpha * le + logC))))
    steps = [out["eps"][str(b)]["rel"] / out["eps"][str(a)]["rel"]
             for a, b in zip(EPS, EPS[1:])]
    out["power_law"] = {"alpha": float(alpha), "logC": float(logC),
                        "max_log_residual": resid,
                        "step_ratios": steps,
                        "quadratic_alpha": 2.0}
    print(f"   fitted  rel ~ eps^{alpha:.3f}   (quadratic would be 2.000), "
          f"max log residual {resid:.4f}", flush=True)
    print("   per-step ratios at 2x eps: "
          + ", ".join(f"{r:.3f}" for r in steps)
          + "   (quadratic would be 4.000 each)", flush=True)

    for m, o in zip(mods, orig):
        m.weight.data = o
    p = os.path.join(HERE, f"sensitivity_{tag}.json")
    json.dump(out, open(p, "w"), indent=1)
    print(f"  wrote {os.path.basename(p)}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
