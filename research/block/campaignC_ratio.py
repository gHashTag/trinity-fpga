#!/usr/bin/env python3
"""Second part: does the sixteenth-codeword gain track the alphabet ratio?

T40 measured ONE number -- at a 4-bit index, spending the wasted +0/-0 codeword
is worth 4.43 %. The conjecture on offer is that the gain is a function of how
much the ALPHABET grows: from 2n-1 to 2n values, a factor 2n/(2n-1).

    b = 3   n = 4    7 -> 8   values   ratio  8/7  = +14.29 % more values
    b = 4   n = 8   15 -> 16  values   ratio 16/15 = + 6.67 %
    b = 5   n = 16  31 -> 32  values   ratio 32/31 = + 3.23 %

If the conjecture is a law, k = improvement / ratio is the same at every width.
This reads campaignC_width_<model>.json (produced by campaignC_width.py, same
construction at every width, only the extra codeword differs) and reports k with
a paired CI at each width, pooled and per model.

A second, independent test needs no new measurement: hold the ratio FIXED at
16/15 and vary WHERE the codeword is spent. Campaign B's asymmetric variants of
MXFP4 and JOINT-KL are all 15 -> 16 -- identical ratio, five different
placements. If the ratio predicted the gain they would all land together.
Those rows are included when campaignB_<model>.json is present.

    python3 campaignC_ratio.py
"""
import json
import math
import os

import numpy as np
from scipy import stats

HERE = os.path.dirname(os.path.abspath(__file__))
MODELS = ["smollm2", "qwen", "pythia", "opt"]
LABEL = {"smollm2": "SmolLM2-135M", "qwen": "Qwen2.5-0.5B",
         "pythia": "Pythia-160M", "opt": "OPT-125M"}
BITS = [3, 4, 5]


def paired(d):
    """d = nll_asym - nll_sym per window. Negative mean = the asymmetric book
    is better. Returns the improvement in percent, positive = better."""
    n = len(d)
    mean = float(d.mean())
    se = float(d.std(ddof=1)) / math.sqrt(n)
    tc = float(stats.t.ppf(0.975, n - 1))
    t = mean / se if se > 0 else float("nan")
    p = float(2 * stats.t.sf(abs(t), n - 1)) if se > 0 else float("nan")
    # improvement% = 100*(1 - exp(mean d)); CI endpoints swap under the negation
    imp = 100 * (1 - math.exp(mean))
    hi = 100 * (1 - math.exp(mean - tc * se))
    lo = 100 * (1 - math.exp(mean + tc * se))
    return {"n": n, "imp": imp, "lo": lo, "hi": hi, "t": t, "p": p,
            "mean_d": mean, "n_better": int((d < 0).sum())}


def ratio_pct(b):
    n = 1 << (b - 1)
    return 100.0 / (2 * n - 1)


def load_width():
    out = {}
    for m in MODELS:
        f = os.path.join(HERE, f"campaignC_width_{m}.json")
        if os.path.exists(f):
            out[m] = json.load(open(f))
    return out


def load_B():
    out = {}
    for m in MODELS:
        f = os.path.join(HERE, f"campaignB_{m}.json")
        if os.path.exists(f):
            j = json.load(open(f))
            if j.get("rulers_reproduce"):
                out[m] = j
    return out


def load_C():
    out = {}
    for m in MODELS:
        f = os.path.join(HERE, f"campaignC_{m}.json")
        if os.path.exists(f):
            j = json.load(open(f))
            if j.get("rulers_reproduce"):
                out[m] = j
    return out


def main():
    Wd = load_width()
    if not Wd:
        print("!! NO campaignC_width_*.json ON DISK -- part A (varying the "
              "alphabet ratio across\n"
              "!! bit widths) cannot be evaluated; it needs a fresh sweep over "
              "the checkpoints.\n"
              "!! Part B below varies PLACEMENT at a FIXED ratio and needs no "
              "new measurement.\n")
    print("=" * 92)
    print("A. SAME CONSTRUCTION, VARYING ALPHABET RATIO  (normal-quantile book, "
          "sym vs asym at each width)")
    print("=" * 92)
    print("models measured:", ", ".join(LABEL[m] for m in Wd))
    print(f"\n{'width':<7}{'n mag':>6}{'alphabet':>11}{'ratio':>9}{'model':<15}"
          f"{'improvement':>13}{'95% CI':>20}{'k=imp/ratio':>13}")
    rows = {}
    for b in BITS:
        n = 1 << (b - 1)
        r = ratio_pct(b)
        for m in Wd:
            nl = Wd[m]["per_window_nll"]
            key_s, key_a = f"b{b}-sym", f"b{b}-asym"
            if key_s not in nl or key_a not in nl:
                continue
            d = np.array(nl[key_a]) - np.array(nl[key_s])
            st = paired(d)
            rows[(b, m)] = st
            print(f"b={b:<5}{n:>6}{f'{2*n-1}->{2*n}':>11}{r:>+8.2f}%"
                  f"  {LABEL[m]:<13}{st['imp']:>+12.2f}%"
                  f"{f'[{st['lo']:+.2f}, {st['hi']:+.2f}]':>20}"
                  f"{st['imp']/r:>13.3f}")
        print()

    print("=" * 92)
    print("A-pooled  (all measured models concatenated; k constant <=> the "
          "ratio predicts the gain)")
    print("=" * 92)
    print(f"{'width':<7}{'ratio':>9}{'improvement':>14}{'95% CI':>21}"
          f"{'t':>9}{'p':>11}{'k = imp/ratio':>16}{'CI on k':>20}")
    pooled = {}
    for b in BITS:
        ds = []
        for m in Wd:
            nl = Wd[m]["per_window_nll"]
            if f"b{b}-sym" in nl and f"b{b}-asym" in nl:
                ds.append(np.array(nl[f"b{b}-asym"]) - np.array(nl[f"b{b}-sym"]))
        if not ds:
            continue
        st = paired(np.concatenate(ds))
        r = ratio_pct(b)
        pooled[b] = dict(st, ratio=r, k=st["imp"] / r,
                         k_lo=st["lo"] / r, k_hi=st["hi"] / r)
        print(f"b={b:<5}{r:>+8.2f}%{st['imp']:>+13.2f}%"
              f"{f'[{st['lo']:+.2f}, {st['hi']:+.2f}]':>21}"
              f"{st['t']:>+9.2f}{st['p']:>11.2e}{st['imp']/r:>16.3f}"
              f"{f'[{st['lo']/r:.3f}, {st['hi']/r:.3f}]':>20}")

    verdict_A = None
    if len(pooled) >= 2:
        ks = [(b, pooled[b]) for b in sorted(pooled)]
        overlap = True
        for i in range(len(ks)):
            for j in range(i + 1, len(ks)):
                a, bb = ks[i][1], ks[j][1]
                if a["k_hi"] < bb["k_lo"] or bb["k_hi"] < a["k_lo"]:
                    overlap = False
        verdict_A = ("k is CONSTANT within CI -- the ratio predicts"
                     if overlap else
                     "k is NOT constant -- the ratio does NOT predict the gain")
        print(f"\n  -> {verdict_A}")
        # log-log slope: imp ~ ratio^s. s = 1 <=> proportional.
        xs = np.log([pooled[b]["ratio"] for b in sorted(pooled)])
        ys = np.log([max(pooled[b]["imp"], 1e-9) for b in sorted(pooled)])
        if len(xs) >= 2:
            s = float(np.polyfit(xs, ys, 1)[0])
            print(f"  -> log-log slope of improvement vs ratio: {s:+.2f} "
                  f"(proportional would be +1.00)")

    # ---------------------------------------------------------------- B
    Bd, Cd = load_B(), load_C()
    print("\n" + "=" * 92)
    print("B. SAME RATIO (16/15 EXACTLY), VARYING WHERE THE CODEWORD GOES")
    print("=" * 92)
    if not Bd and not Cd:
        print("  no campaignB_*.json / campaignC_*.json available yet")
    else:
        pairs = []
        if Cd:
            pairs.append(("NF4", "NF4-sym", Cd, "normal-quantile"))
        for a in ("MX-asym-TOP", "MX-asym-MID", "MX-asym-MID2",
                  "MX-asym-NEAR0", "MX-asym-MIDN"):
            pairs.append((a, "MXFP4", Bd, "E2M1 + 1 codeword"))
        for a in ("JK-asym-TOP", "JK-asym-MID", "JK-asym-MID2", "JK-asym-NEAR0"):
            pairs.append((a, "JOINT-KL", Bd, "JOINT-KL + 1 codeword"))
        print(f"{'asym book':<16}{'vs sym parent':<12}{'models':<24}"
              f"{'improvement':>13}{'95% CI':>20}{'k=imp/6.67':>12}")
        rB = ratio_pct(4)
        got = []
        for a, ref, src, fam in pairs:
            ds = []
            ms = []
            for m in MODELS:
                if m in src and a in src[m]["per_window_nll"]:
                    ds.append(np.array(src[m]["per_window_nll"][a])
                              - np.array(src[m]["per_window_nll"][ref]))
                    ms.append(m)
            if not ds:
                continue
            st = paired(np.concatenate(ds))
            got.append((a, st))
            print(f"{a:<16}{ref:<12}{'+'.join(LABEL[x].split('-')[0] for x in ms):<24}"
                  f"{st['imp']:>+12.2f}%"
                  f"{f'[{st['lo']:+.2f}, {st['hi']:+.2f}]':>20}"
                  f"{st['imp']/rB:>12.3f}")
        if len(got) >= 2:
            v = [s["imp"] for _, s in got]
            print(f"\n  -> at ONE fixed ratio the improvement spans "
                  f"{min(v):+.2f}% .. {max(v):+.2f}%  (span {max(v)-min(v):.2f} pp)")

    json.dump({"width_rows": {f"b{b}|{m}": v for (b, m), v in rows.items()},
               "width_pooled": {f"b{b}": v for b, v in pooled.items()},
               "models_width": list(Wd), "verdict_A": verdict_A},
              open(os.path.join(HERE, "campaignC_ratio.json"), "w"), indent=1)
    print("\nwrote campaignC_ratio.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
