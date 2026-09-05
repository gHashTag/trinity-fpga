"""Spec-faithful re-measurement of the scale frontier.

!!! THIS SCRIPT'S NUMBERS ARE NOT USABLE AS WRITTEN. Its own self-tests fail. !!!

Run it and it prints phi^j = 39.5555 against 2^k = 23.5380 on SmolLM2 -- 16 points the wrong way
-- and reports the SAME value under all three tie rules, which is impossible if the tie switch
does anything. Two bugs, both caught by self-test before any number was reported:

  BUG 1 -- the tie switch is a no-op. On the seven exact midpoints of the E2M1 grid
  (0.25, 0.75, 1.25, 1.75, 2.5, 3.5, 5.0) all of 'even', 'zero' and 'away' return
  [0, 0.5, 1, 1.5, 2, 3, 4]. `torch.bucketize` with the default right=False already places a
  value equal to a boundary in the lower bin, so `is_tie` never selects anything different.

  BUG 2 -- the phi scale points the wrong way. `floor(log_phi(amax/6))` gives phi^j <= amax/6,
  so amax/s lands in [6.85, 9.55] for test inputs -- ABOVE max_norm=6 -- and every block maximum
  clamps. That is the entire 16-point deficit; it measures a broken quantiser, not phi.

The trustworthy numbers for this comparison are the independent verification's, whose harness
carried 37 hand-computed self-tests including all seven exact midpoints under ties-to-even and
the saturation case, and which reproduced the campaign's fp32 baselines exactly.

ONE THING HERE IS REAL AND WORTH KEEPING (self-test 3, no quantiser involved):
at equal field width a phi ladder covers LESS dynamic range than a power-of-two ladder --
16 phi-steps span 16*log2(phi) = 11.11 binades against 2^k's 16.00, a factor of 1.44. Any
comparison of "phi^k vs 2^k at n bits of scale field" is therefore not a like-for-like span
comparison, and that asymmetry belongs in the write-up of the block-axis result.

Original intent follows.
--------------------------------------------------------------------------------------

An independent verification found two deviations in scale_frontier.py, both of which make MXFP4
look BETTER than the OCP spec, and therefore understate this campaign's own margin:

  (a) SCALE RULE. `k = ceil(log2(amax/6))` gives amax/X in (3,6] -- the block maximum never
      saturates. The OCP MX rule is X = 2^(floor(log2 amax) - emax), emax=2 for E2M1, giving
      amax/X in [4,8), so the maximum CLAMPS to max_norm=6 whenever amax's mantissa exceeds 1.5.
      Measured to occur in 46.57% of SmolLM2 blocks and 40.18% of Qwen blocks.

  (b) TIE RULE. `torch.bucketize` breaks exact midpoints in a fixed direction. OCP inherits
      IEEE round-to-nearest-EVEN. Both checkpoints are bf16-origin (8 mantissa bits) and the
      scale is a power of two, so exact midpoints are common: 1.159% of SmolLM2 elements,
      1.339% of Qwen.

Consequence for the headline: on Qwen the reported phi^k-over-2^k margin at 4 bits is 0.0935,
while switching the tie rule alone moves 2^k by 0.0932 -- the same size as the entire claimed
advantage. On SmolLM2 the margin (1.145) dwarfs the tie effect (0.129) and is safe.

So this script re-measures the 4-bit scale comparison with BOTH defects fixed and the tie rule
made explicit, and reports whether phi^k still beats 2^k once nothing is left uncontrolled.
Ties-to-even is implemented on the mantissa bit of the E2M1 code, which is what IEEE means by
'even'; the alternative conventions are measured too, so the answer does not depend on a choice
made silently.
"""
import os
import sys

import numpy as np
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

W = ("/private/tmp/claude-501/-Users-ssdm4-Desktop-PROJECTS-CLAUDE/"
     "0e868af8-ab2d-4d00-be03-8fea94ba48e4/scratchpad/weights")
SEQLEN, NW, K = 2048, 40, 32
PHI = (1 + 5 ** 0.5) / 2
torch.set_grad_enabled(False)

# E2M1 magnitudes WITH the subnormal, and the mantissa bit of each code.
MAG = torch.tensor([0.0, 0.5, 1.0, 1.5, 2.0, 3.0, 4.0, 6.0], dtype=torch.float64)
MBIT = torch.tensor([0, 1, 0, 1, 0, 1, 0, 1], dtype=torch.bool)   # m=1 for .5-mantissa codes
MAXN = 6.0
EMAX = 2


def q_elem(y, tie):
    """Quantise |y| to the E2M1 magnitude grid. `tie` in {'even','zero','away'}."""
    a = y.abs()
    idx = torch.bucketize(a, (MAG[:-1] + MAG[1:]) / 2).clamp(0, len(MAG) - 1)
    lo = (idx - 1).clamp(0, len(MAG) - 1)
    # exact midpoint between MAG[lo] and MAG[idx]?
    mid = (MAG[lo] + MAG[idx]) / 2
    is_tie = (a == mid) & (idx > 0)
    if tie == "even":
        pick_lo = MBIT[idx] & ~MBIT[lo]          # upper is odd-mantissa, lower is even -> take lower
        idx = torch.where(is_tie & pick_lo, lo, idx)
    elif tie == "zero":
        idx = torch.where(is_tie, lo, idx)
    # 'away' keeps bucketize's upper choice
    return MAG[idx].clamp(max=MAXN)


def scale_ocp(amax):
    """OCP MX: X = 2^(floor(log2 amax) - emax). amax/X lands in [4,8); the max may clamp."""
    return torch.pow(2.0, torch.floor(torch.log2(amax.clamp(min=1e-30))) - EMAX)


def scale_pow2_field(amax, nbits):
    """Power-of-two scale on a finite exponent field of nbits, same rule, window per tensor."""
    k = torch.floor(torch.log2(amax.clamp(min=1e-30))) - EMAX
    lo = k.min()
    return torch.pow(2.0, torch.clamp(k - lo, 0, 2 ** nbits - 1) + lo)


def scale_phi_field(amax, nbits):
    """phi^j scale on a finite field: the same construction with ratio phi instead of 2."""
    j = torch.floor(torch.log(amax.clamp(min=1e-30) / MAXN) / np.log(PHI))
    lo = j.min()
    j = torch.clamp(j - lo, 0, 2 ** nbits - 1) + lo
    return torch.pow(PHI, j)


def quantise(w, scale_fn, tie):
    n = (w.shape[1] // K) * K
    if n == 0:
        return w
    b = w[:, :n].reshape(-1, K).double()
    s = scale_fn(b.abs().amax(dim=1)).clamp(min=1e-30)
    rec = torch.sign(b) * q_elem(b / s[:, None], tie) * s[:, None]
    out = w.clone()
    out[:, :n] = rec.reshape(-1, n).to(w.dtype)
    return out


def run(md):
    tok = AutoTokenizer.from_pretrained(os.path.join(W, md))
    import pyarrow.parquet as pq
    text = "\n\n".join(pq.read_table(os.path.join(W, "wikitext2-test.parquet"))
                       .column("text").to_pylist())
    ids = tok(text, return_tensors="pt").input_ids[0]

    def load():
        m = AutoModelForCausalLM.from_pretrained(os.path.join(W, md), dtype=torch.float32)
        m.eval()
        return m

    def ppl(m):
        n = (ids.numel() // SEQLEN) * SEQLEN
        x = ids[:n].reshape(-1, SEQLEN)[:NW]
        return float(np.exp(sum(m(x[i:i + 1], labels=x[i:i + 1]).loss.double().item()
                                for i in range(x.shape[0])) / x.shape[0]))

    m = load()
    base = ppl(m)
    del m
    print(f"\n  {md}: fp32 = {base:.4f}  ({NW} windows)")
    print(f"  {'scheme':<34}{'ties=even':>12}{'ties=zero':>12}{'ties=away':>12}")
    rows = {}
    for name, fn in (("MXFP4 (E8M0, OCP rule)", scale_ocp),
                     ("2^k, 4-bit field", lambda a: scale_pow2_field(a, 4)),
                     ("phi^j, 4-bit field", lambda a: scale_phi_field(a, 4))):
        vals = []
        for tie in ("even", "zero", "away"):
            mm = load()
            for nm, mod in mm.named_modules():
                if isinstance(mod, torch.nn.Linear) and not any(
                        h in nm for h in ("lm_head", "embed_out")):
                    mod.weight.data = quantise(mod.weight.data.to(torch.float64),
                                               fn, tie).to(mod.weight.dtype)
            vals.append(ppl(mm))
            del mm
        rows[name] = vals
        print(f"  {name:<34}" + "".join(f"{v:>12.4f}" for v in vals))
    for tie_i, tie in enumerate(("even", "zero", "away")):
        p2 = rows["2^k, 4-bit field"][tie_i]
        pp = rows["phi^j, 4-bit field"][tie_i]
        print(f"    ties={tie:<5} phi^j - 2^k = {pp - p2:+.4f}  "
              f"({'phi wins' if pp < p2 else '2^k wins'})")
    return rows


for md in (sys.argv[1:] or ["smollm2", "qwen"]):
    run(md)
print("\n  The comparison is only meaningful if the tie rule is held fixed across the row;")
print("  the campaign's reported Qwen margin (0.0935) is the size of the tie effect alone.")
