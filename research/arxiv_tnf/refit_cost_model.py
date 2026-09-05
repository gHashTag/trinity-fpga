#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
refit_cost_model.py — refit the TNF LUT cost model on sweep metrics and report
honestly against the published one.

Published model (paper, sec. on the selector):
    LUT ~ 2.194 M^2 + 53.84 M - 197.1 E_t + 363.5,  R^2 = 0.9989
fitted only on post-route rows with M <= 25.  The paper already records two
defects: the two TNF16 rows at M = 9 and M = 11 are mutually inconsistent with
any smooth model, and the two widest measured rungs grow far more slowly than
M^2.  This script is built so that the sweep can overturn the model rather than
confirm it, and it reports three things separately:

  1. the fit restricted to M <= 25, comparable with the published one;
  2. the fit on all routed rows, which is where flattening would show;
  3. the residual of the published model on the new rows, which is the only
     number that says whether the published coefficients still hold.

A quadratic and a linear model are both fitted and compared by adjusted R^2, so
that "the quadratic term survives" is a measured statement and not an assumption.
Rows recorded as routing-pending are listed and EXCLUDED from every fit, never
imputed, because a fabric limit is not a cost measurement.

Usage: refit_cost_model.py <metrics-dir>
"""
import json
import math
import os
import re
import sys

import numpy as np

PUBLISHED = dict(m2=2.194, m1=53.84, et=-197.1, c=363.5)


def parse(d):
    """Read the key=value metric files the workflow uploads."""
    rows = {}
    for fn in sorted(os.listdir(d)):
        if not fn.endswith(".txt"):
            continue
        kv = {}
        for line in open(os.path.join(d, fn)):
            if "=" in line:
                k, v = line.strip().split("=", 1)
                kv[k] = v
        top = kv.get("top")
        if not top:
            continue
        m = re.match(r"tnf_cost_e(\d+)m(\d+)_(add|mul)_top", top)
        if not m:
            continue
        r = rows.setdefault(top, dict(top=top, et=int(m.group(1)),
                                      m=int(m.group(2)), op=m.group(3)))
        if fn.endswith(".yosys.txt"):
            r["lc"] = int(kv["lc"]) if kv.get("lc", "").isdigit() else None
        if fn.endswith(".pnr.txt"):
            r["status"] = kv.get("status")
            r["luts"] = int(kv["luts"]) if kv.get("luts", "").isdigit() else None
            r["fmax"] = kv.get("fmax")
    return list(rows.values())


def fit(rows, quadratic=True):
    """Least squares on LUT vs (M^2, M, E_t, 1). Returns coefficients, R^2, adj R^2."""
    M = np.array([r["m"] for r in rows], float)
    E = np.array([r["et"] for r in rows], float)
    y = np.array([r["luts"] for r in rows], float)
    cols = [M ** 2, M, E, np.ones_like(M)] if quadratic else [M, E, np.ones_like(M)]
    A = np.column_stack(cols)
    if len(rows) <= A.shape[1]:
        return None
    beta, *_ = np.linalg.lstsq(A, y, rcond=None)
    pred = A @ beta
    ss_res = float(np.sum((y - pred) ** 2))
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    r2 = 1 - ss_res / ss_tot if ss_tot else float("nan")
    n, p = len(rows), A.shape[1]
    adj = 1 - (1 - r2) * (n - 1) / (n - p) if n > p else float("nan")
    return dict(beta=[float(b) for b in beta], r2=r2, adj_r2=adj, n=n,
                rmse=math.sqrt(ss_res / n))


def published_pred(r):
    return (PUBLISHED["m2"] * r["m"] ** 2 + PUBLISHED["m1"] * r["m"]
            + PUBLISHED["et"] * r["et"] + PUBLISHED["c"])


def main(argv):
    if len(argv) < 2:
        print("usage: refit_cost_model.py <metrics-dir>")
        return 2
    rows = parse(argv[1])
    routed = [r for r in rows if r.get("status") == "routed" and r.get("luts")]
    pending = [r for r in rows if r.get("status") == "routing-pending"]
    ysonly = [r for r in rows if r.get("lc") and not r.get("status")]

    print("## TNF cost sweep: refit report\n")
    print(f"- arms with yosys stat only [modelled]: {len(ysonly)}")
    print(f"- arms placed and routed [measured CI-synth]: {len(routed)}")
    print(f"- arms routing-pending (excluded from every fit, not imputed): {len(pending)}")
    for r in pending:
        print(f"  - `{r['top']}` E_t={r['et']} M={r['m']}")
    print()

    if not routed:
        print("No routed rows. Nothing is refitted and no coefficient is claimed.")
        return 0

    print("### Routed rows\n")
    print("| top | E_t | M | LUT (P&R) | published model | residual | Fmax |")
    print("|---|---|---|---|---|---|---|")
    for r in sorted(routed, key=lambda r: (r["et"], r["m"])):
        p = published_pred(r)
        print(f"| `{r['top']}` | {r['et']} | {r['m']} | {r['luts']} | {p:.0f} "
              f"| {r['luts'] - p:+.0f} | {r.get('fmax','?')} |")
    print()

    # Q1: the two E_t = 4 arms at M = 9 and M = 11, measured through one flow
    q1 = {r["m"]: r for r in routed if r["et"] == 4 and r["m"] in (9, 11) and r["op"] == "add"}
    print("### Q1 — are the two TNF16 rows still mutually inconsistent?\n")
    if len(q1) == 2:
        a, b = q1[9], q1[11]
        d = b["luts"] - a["luts"]
        print(f"M = 9 gives {a['luts']} LUT, M = 11 gives {b['luts']} LUT, "
              f"difference {d:+d} over two mantissa bits.")
        print("A smooth quadratic through this region predicts a difference of "
              f"{published_pred(b) - published_pred(a):+.0f}.")
        if d <= 0:
            print("The wider mantissa is not more expensive, so the rows remain "
                  "mutually inconsistent with any monotone smooth model. The "
                  "published caveat stands and must stay in the paper.")
        else:
            print("Both rows now sit on the same monotone trend through one "
                  "identical flow, so the earlier inconsistency was a flow "
                  "artefact. The paper must be corrected to say that, and the "
                  "correction is a retraction of our own caveat, not a result.")
    else:
        print("Both arms did not route, so Q1 is unresolved. No conclusion is drawn.")
    print()

    print("### Q2 — does the quadratic term survive past M = 25?\n")
    for label, sub in (("M <= 25 (comparable with the published fit)",
                        [r for r in routed if r["m"] <= 25]),
                       ("all routed rows", routed)):
        fq, fl = fit(sub, True), fit(sub, False)
        print(f"**{label}**, n = {len(sub)}")
        if fq is None:
            print("- too few rows to fit; nothing claimed\n")
            continue
        b = fq["beta"]
        print(f"- quadratic: LUT ~ {b[0]:.3f} M^2 + {b[1]:.2f} M "
              f"{b[2]:+.1f} E_t {b[3]:+.1f}; R^2 = {fq['r2']:.4f}, "
              f"adj R^2 = {fq['adj_r2']:.4f}, RMSE = {fq['rmse']:.1f}")
        if fl:
            print(f"- linear:    R^2 = {fl['r2']:.4f}, adj R^2 = {fl['adj_r2']:.4f}, "
                  f"RMSE = {fl['rmse']:.1f}")
            better = "quadratic" if fq["adj_r2"] > fl["adj_r2"] else "linear"
            print(f"- better by adjusted R^2: **{better}**")
            if better == "linear":
                print("  The M^2 term does not earn its parameter on these rows. "
                      "The published quadratic must then be labelled a local fit "
                      "over its own M range and not extrapolated.")
        print()

    res = np.array([r["luts"] - published_pred(r) for r in routed])
    print("### Residual of the published coefficients on the new rows\n")
    print(f"- mean {res.mean():+.1f} LUT, median {np.median(res):+.1f}, "
          f"max |residual| {np.abs(res).max():.0f} LUT")
    rel = np.abs(res) / np.array([r["luts"] for r in routed])
    print(f"- worst relative error {rel.max() * 100:.1f} %")
    if rel.max() > 0.15:
        print("- The published coefficients do not reproduce the new rows within "
              "15 %. They are superseded for this region and the paper must say "
              "which region each fit covers.")
    else:
        print("- The published coefficients reproduce the new rows within 15 %, "
              "so they hold over the swept region.")

    json.dump(dict(routed=routed, pending=[r["top"] for r in pending],
                   published=PUBLISHED), open("refit.json", "w"), indent=1)
    print("\nStatus of every number above: yosys stat is [modelled], nextpnr "
          "post-route is [measured CI-synth]. Neither is a hardware measurement; "
          "hardware requires a UART transcript from the AX7203 with a green CI "
          "URL, an artefact SHA256 and IDCODE 0x13636093 on issue #199.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
