#!/usr/bin/env python3
"""Is alpha < 2 a property of the loss, or of using one seed?

sensitivity.py fits rel ~ eps^alpha and OPT came back at alpha = 1.600 with
per-step ratios 2.691, 3.042, 3.399 -- rising toward the quadratic 4.0 rather
than sitting at it. The tempting reading is that the second-order form does not
govern, which would be a statement about a standing assumption in the
quantisation literature.

That reading has a confound and it must be killed before the claim is made.

For isotropic noise n, the first-order term g.n has expectation ZERO, so an
average over seeds is purely second-order to leading order. But a SINGLE draw
realises g.n of typical size |g| * eps * |w|, which scales as eps^1. A one-seed
measurement therefore mixes an O(eps) term into what it calls the response, and
that alone would bend alpha below 2 at small eps -- exactly the shape observed.

So: the same eps ladder, S seeds, and both statistics reported.

  * mean over seeds of the relative shift -> the linear term cancels in
    expectation, so alpha should approach 2 if the loss is locally quadratic;
  * the spread ACROSS seeds at each eps -> if that spread scales as eps^1 while
    the mean scales as eps^2, the linear term is present and single-seed
    measurements are contaminated, which is the confound demonstrated rather
    than argued.

Whichever way it comes out, one of two things is established: either alpha < 2 is
real and survives seed-averaging, or it was an artefact of one draw and every
single-seed sensitivity number in this directory has to be re-read.

    MDIR=<tag> SEEDS=5 python3 seed_control.py
"""
import json
import os
import sys
import time

import numpy as np
import torch

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import sensitivity as S                                          # noqa: E402
import provenance as PV                                          # noqa: E402

EPS = [0.005, 0.01, 0.02, 0.04]


def main():
    import pyarrow.parquet as pq
    from transformers import AutoModelForCausalLM, AutoTokenizer

    tag = os.environ["MDIR"]
    nseed = int(os.environ.get("SEEDS", "5"))
    src = S.SRC[tag]
    seqlen, nwin = S.SEQ.get(tag, S.SEQLEN), S.NWIN.get(tag, 40)

    txt = "\n\n".join(pq.read_table(
        os.path.join(S.W, "wikitext2-test.parquet")).column("text").to_pylist())
    tok = AutoTokenizer.from_pretrained(src)
    mdl = AutoModelForCausalLM.from_pretrained(src, dtype=torch.float32)
    mdl.eval()
    ids = tok(txt, return_tensors="pt").input_ids[0]
    win = ids[:(ids.numel() // seqlen) * seqlen].view(-1, seqlen)[:nwin]
    mods = [t[1] if isinstance(t, tuple) else t
            for t in S.target_modules(mdl)]
    orig = [m.weight.data.clone() for m in mods]

    def ppl():
        with torch.no_grad():
            return float(np.exp(np.mean(
                [float(mdl(win[i:i + 1], labels=win[i:i + 1]).loss)
                 for i in range(nwin)])))

    def perturb(eps, seed):
        g = torch.Generator().manual_seed(seed)
        for m, o in zip(mods, orig):
            n = torch.randn(o.shape, generator=g, dtype=o.dtype)
            m.weight.data = o + n * (eps * o.pow(2).mean().sqrt()
                                     / n.pow(2).mean().sqrt())

    p0 = ppl()
    perturb(0.0, 1)
    if abs(ppl() / p0 - 1) > 1e-9:
        print("ABORT: the eps=0 path is not bit-identical.")
        return 4
    print(f"  {tag}: ppl {p0:.4f}, {nseed} seeds x {len(EPS)} eps, "
          "eps=0 control bit-identical", flush=True)

    out = {"model": tag, "src": src, "nwin": nwin, "seqlen": seqlen,
           "nseed": nseed, "ppl_fp32": p0, "eps": {},
           "provenance": PV.describe(joined_text=txt, src=src)}
    for eps in EPS:
        t0 = time.time()
        rels = []
        for s in range(nseed):
            perturb(eps, S.SEED + s)
            rels.append(ppl() / p0 - 1)
        m, sd = float(np.mean(rels)), float(np.std(rels, ddof=1))
        out["eps"][str(eps)] = {"rels": rels, "mean": m, "sd": sd}
        print(f"   eps={eps:<6} mean {100*m:+7.3f}%   sd across seeds "
              f"{100*sd:.4f}pp   ({time.time()-t0:.0f}s)", flush=True)

    le = np.log(np.array(EPS))
    am, _ = np.polyfit(le, np.log([out["eps"][str(e)]["mean"] for e in EPS]), 1)
    asd, _ = np.polyfit(le, np.log([out["eps"][str(e)]["sd"] for e in EPS]), 1)
    out["alpha_mean"], out["alpha_sd"] = float(am), float(asd)
    print(f"   MEAN over seeds  ~ eps^{am:.3f}   (quadratic = 2.000)", flush=True)
    print(f"   SD across seeds  ~ eps^{asd:.3f}   (a linear term gives 1.000)",
          flush=True)
    verdict = ("the linear term is present and single-seed numbers are "
               "contaminated" if asd < 1.5 and am > asd + 0.4 else
               "seed-averaging does not restore alpha = 2; alpha < 2 survives")
    out["verdict"] = verdict
    print(f"   -> {verdict}", flush=True)

    for m_, o in zip(mods, orig):
        m_.weight.data = o
    json.dump(out, open(os.path.join(HERE, f"seedctl_{tag}.json"), "w"), indent=1)
    print(f"  wrote seedctl_{tag}.json", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
