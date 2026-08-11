#!/usr/bin/env python3
"""Campaign B pooled analysis: per-model and pooled OUT-OF-SAMPLE paired tests.

Reads campaignB_measure_{smollm2,qwen,pythia}.json. Nothing is measured here.

Pooling rule -- an arm's out-of-sample set is every model it was NOT fitted on:
  MXFP4, NF4, NF4-sym, BOF4-S(paper)  -> all three models (fitted on no model
                                          of ours; NF4/BOF4-S(paper) come from a
                                          Gaussian prior, MXFP4 is hand-designed)
  Lloyd-Max, BOF4, BOF4-S             -> qwen + pythia (fitted on smollm2)
  BOF4 refit                          -> in-sample everywhere, excluded
The paired unit is a window: d_i = nll_i(arm) - nll_i(MXFP4) on the SAME window
of the SAME model, so pooling differences across models is a pooled paired test,
which is what the nSSE transfer result reported.
"""
import json
import math
import os

import numpy as np
from scipy import stats

HERE = os.path.dirname(os.path.abspath(__file__))
MODELS = ["smollm2", "qwen", "pythia"]
MX = "MXFP4 (E2M1)"
FITTED_ON = {
    MX: set(),
    "Lloyd-Max (MSE opt, 8 mag)": {"smollm2"},
    "NF4 (bitsandbytes, 16 lvl)": set(),
    "NF4-sym (15 lvl, 8 mag)": set(),
    "BOF4 (my impl of their method)": {"smollm2"},
    "BOF4-S (signed scale, +1b/blk)": {"smollm2"},
    "BOF4-S paper Table7 I=32": set(),
}
BUDGET = {MX: 4.25, "Lloyd-Max (MSE opt, 8 mag)": 4.25,
          "NF4 (bitsandbytes, 16 lvl)": 4.25, "NF4-sym (15 lvl, 8 mag)": 4.25,
          "BOF4 (my impl of their method)": 4.25,
          "BOF4-S (signed scale, +1b/blk)": 4.28125,
          "BOF4-S paper Table7 I=32": 4.28125}


def paired(d):
    n = len(d)
    mean, sd = float(d.mean()), float(d.std(ddof=1))
    se = sd / math.sqrt(n)
    t = mean / se
    p = float(2 * stats.t.sf(abs(t), n - 1))
    c = float(stats.t.ppf(0.975, n - 1))
    lo, hi = mean - c * se, mean + c * se
    return dict(n=n, mean=mean, se=se, t=t, p=p,
                pct=100 * (math.exp(mean) - 1),
                lo=100 * (math.exp(lo) - 1), hi=100 * (math.exp(hi) - 1),
                nbetter=int((d < 0).sum()), nworse=int((d > 0).sum()))


def main():
    R = {}
    for m in MODELS:
        f = os.path.join(HERE, f"campaignB_measure_{m}.json")
        if not os.path.exists(f):
            print(f"MISSING {f}")
            return 1
        R[m] = json.load(open(f))
        assert R[m]["rulers_reproduce"], f"{m}: rulers did NOT reproduce"
    print("rulers reproduced on all three models\n")

    print("=" * 92)
    print("PER-MODEL PERPLEXITY (block 32, E8M0 scale, lm_head excluded)")
    print("=" * 92)
    hdr = f"{'arm':<34}{'b/elem':>8}" + "".join(f"{m:>18}" for m in MODELS)
    print(hdr)
    arms = [MX] + [a for a in FITTED_ON if a != MX]
    print(f"{'fp32 (unquantised)':<34}{32.0:>8.2f}" +
          "".join(f"{R[m]['ppl']['fp32']:>18.4f}" for m in MODELS))
    for a in arms:
        row = f"{a:<34}{BUDGET[a]:>8.5f}"
        for m in MODELS:
            p = R[m]["ppl"][a]
            pm = R[m]["ppl"][MX]
            row += f"{p:>11.4f}{100*(p/pm-1):>+7.2f}%" if a != MX \
                else f"{p:>11.4f}{'  ruler':>7}"
        print(row)
    ins = [k for k in R["smollm2"]["ppl"] if "IN-SAMPLE" in k]
    for a in ins:
        row = f"{'BOF4 refit per-model (IN-SAMPLE)':<34}{4.25:>8.5f}"
        for m in MODELS:
            k = [x for x in R[m]["ppl"] if "IN-SAMPLE" in x][0]
            p, pm = R[m]["ppl"][k], R[m]["ppl"][MX]
            row += f"{p:>11.4f}{100*(p/pm-1):>+7.2f}%"
        print(row)
        break

    print("\n" + "=" * 92)
    print("PAIRED PER-WINDOW TESTS vs MXFP4   (negative % = beats MXFP4)")
    print("=" * 92)
    summary = {}
    for a in arms:
        if a == MX:
            continue
        oos = [m for m in MODELS if m not in FITTED_ON[a]]
        print(f"\n{a}   [out-of-sample: {', '.join(oos)}]")
        print(f"  {'model':<12}{'n':>4}{'d ppl %':>10}{'95% CI':>22}"
              f"{'t':>9}{'p':>10}{'better':>10}")
        pool = []
        for m in MODELS:
            d = np.array(R[m]["per_window_nll"][a]) - \
                np.array(R[m]["per_window_nll"][MX])
            s = paired(d)
            tag = "" if m in oos else "  (in-sample)"
            print(f"  {m:<12}{s['n']:>4}{s['pct']:>+9.2f}%"
                  f"{f'[{s[chr(108)+chr(111)]:+.2f},{s[chr(104)+chr(105)]:+.2f}]':>22}"
                  f"{s['t']:>+9.2f}{s['p']:>10.3g}"
                  f"{s['nbetter']:>7}/{s['n']}{tag}")
            if m in oos:
                pool.append(d)
        if pool:
            dp = np.concatenate(pool)
            s = paired(dp)
            summary[a] = s
            print(f"  {'POOLED OOS':<12}{s['n']:>4}{s['pct']:>+9.2f}%"
                  f"{f'[{s[chr(108)+chr(111)]:+.2f},{s[chr(104)+chr(105)]:+.2f}]':>22}"
                  f"{s['t']:>+9.2f}{s['p']:>10.3g}"
                  f"{s['nbetter']:>7}/{s['n']}")

    print("\n" + "=" * 92)
    print("VERDICT: does anything in the learned-codebook class beat MXFP4 "
          "out of sample?")
    print("=" * 92)
    any_win = False
    for a, s in summary.items():
        beats = s["hi"] < 0
        loses = s["lo"] > 0
        v = ("BEATS MXFP4" if beats else
             "LOSES to MXFP4" if loses else "indistinguishable from MXFP4")
        any_win |= beats
        print(f"  {a:<34}{s['pct']:>+7.2f}%  CI[{s['lo']:+.2f},{s['hi']:+.2f}]"
              f"  p={s['p']:.3g}   {v}")
    print(f"\n  -> {'YES' if any_win else 'NO'}: "
          f"{'at least one arm' if any_win else 'no arm'} in this class beats "
          f"MXFP4 out of sample with a CI excluding zero.")

    json.dump({k: {kk: float(vv) for kk, vv in v.items()}
               for k, v in summary.items()},
              open(os.path.join(HERE, "campaignB_pooled.json"), "w"), indent=1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
