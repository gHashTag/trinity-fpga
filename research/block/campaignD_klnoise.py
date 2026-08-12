#!/usr/bin/env python3
"""Campaign D: how much of the KL bin profile is signal?

The first P3 run showed mirror bins +k and -k -- which carry mass and squared
error equal to four significant figures -- differing by up to a factor of 50,
and one repair that made the model worse.  The mask was audited against an
independent instrument and is exact (campaignD_audit.py), so the remaining
explanations are a real sign effect or window noise.  This separates them.

Every arm is evaluated on the SAME windows, so each bin's contribution is a
PAIRED per-window quantity and gets a CI.  A mirror pair whose difference has a
CI containing zero is a TIE, and a profile made of ties is not a predictor.
"""
import json
import math
import os
import sys

import numpy as np
from scipy import stats

HERE = os.path.dirname(os.path.abspath(__file__))


def ci(d, alpha=0.05):
    d = np.asarray(d, dtype=float)
    n = len(d)
    m, se = float(d.mean()), float(d.std(ddof=1) / math.sqrt(n))
    tc = float(stats.t.ppf(1 - alpha / 2, n - 1))
    t = m / se if se > 0 else float("nan")
    return m, m - tc * se, m + tc * se, (float(2 * stats.t.sf(abs(t), n - 1))
                                         if se > 0 else float("nan"))


def main():
    mdir = sys.argv[1] if len(sys.argv) > 1 else "smollm2"
    d = json.load(open(os.path.join(HERE, f"campaignD_kl_{mdir}.json")))
    if "per_window_kl_repair" not in d:
        raise SystemExit("this json predates per-window storage; re-run campaignD_kl.py")
    base = np.array(d["per_window_kl_mxfp4"])
    rep = {int(k): np.array(v) for k, v in d["per_window_kl_repair"].items()}
    n = len(base)
    print(f"{mdir}: {n} windows, KL(fp32||MXFP4) = {base.mean():.6f}\n")

    print(f"{'bin':>5}{'contribution':>14}{'95% CI':>26}{'share %':>10}{'':>8}")
    for b in sorted(rep):
        m, lo, hi, p = ci(base - rep[b])
        tag = "" if (lo > 0 or hi < 0) else "  TIE with 0"
        print(f"{b:>+5d}{m:>14.6f}  [{lo:>9.6f},{hi:>9.6f}]"
              f"{100*m/base.mean():>10.3f}{tag}")

    print(f"\nmirror pairs -- equal mass and equal SSE by construction:")
    print(f"{'pair':>8}{'contrib(-k)':>13}{'contrib(+k)':>13}{'difference':>13}"
          f"{'95% CI':>26}{'':>8}")
    for k in range(1, 8):
        if -k not in rep or k not in rep:
            continue
        dneg, dpos = base - rep[-k], base - rep[k]
        m, lo, hi, p = ci(dneg - dpos)
        tag = "TIE" if (lo <= 0 <= hi) else "SEPARATED"
        print(f"{'-'+str(k)+'/+'+str(k):>8}{dneg.mean():>13.6f}{dpos.mean():>13.6f}"
              f"{m:>13.6f}  [{lo:>9.6f},{hi:>9.6f}]  {tag}")


if __name__ == "__main__":
    main()
