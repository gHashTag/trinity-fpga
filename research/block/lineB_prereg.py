#!/usr/bin/env python3
"""LINE B: freeze the X/G prediction for a checkpoint BEFORE its perplexity exists.

X/G survived T41's wreckage by inspection of components AFTER the primary
predictor failed.  That makes it post-hoc, and post-hoc means "a hypothesis that
has not been tested yet".  This file turns it into one that has been.

=== THE RULE, CLOSED FORM, NO FREE PARAMETER ==============================

For a checkpoint, summing exactly over every quantised element of every target
tensor (block 32, E8M0, lm_head excluded), with c = 3/4 READ OFF MX-asym-TOP's
own negative ladder and y = w/s the E8M0-scaled weight:

    S = { i : y_i < -c }                 elements the arm saturates
    R = complement of S                  elements that stay in range
    e_B = Q_MXFP4(w) - w                 parent error
    e_A = Q_TOP(w)   - w                 arm error

    X = sum_S (e_A^2 - e_B^2)            clipping cost      (T41 Prop. 2)
    G = sum_R  e_B^2                     granular error of the parent
    Y = sum_R (e_B^2 - e_A^2)            granular gain      (T41 Prop. 2)

    PREDICTOR  =  X / G                  dimensionless, scale-free

B1 (RANK).  The clipping arm's perplexity margin
        m = 100 * (ppl_TOP / ppl_MXFP4 - 1)
    is INCREASING in X/G.  Predicted Spearman rho(X/G, m) > 0 on the NEW
    checkpoints alone.

B2 (SIGN).  sign(m) = sign(X/G): the arm wins iff its net clipping cost is
    negative.  The threshold is ZERO and zero is not fitted -- X is a difference
    of two squared errors, so its own zero is the point where the arm's one-sided
    saturation is exactly neutral on the tail it clips.  T41 Corollary 2 says why
    that zero is not trivial: saturated elements below beta = (1+c)/2 are
    reconstructed BETTER by the arm and only those above beta pay, so X is a
    near-cancellation of two large opposed sums and its sign is genuinely
    informative rather than structurally fixed.
    Every constant here -- c = 3/4, beta = 7/8, the E2M1 ladder -- is read off
    the format.  None comes from the four discovery margins.
    Its in-sample record is 3/4: it calls Pythia, Qwen and SmolLM2 correctly and
    OPT wrong.  Registered anyway, because that is what it predicts.

CO-REGISTERED CONTROLS, so the new data says WHICH HALF of the derivation is wrong:

C1  T41 PRIMARY, dD / D_B = (X - Y) / D_B.  Rank: m increasing in dD/D_B.
    Sign: T41's crossover is X < Y, i.e. dD < 0 => arm favourable.
    Already refuted on the discovery four (rho = -0.400, sign wrong on two).
C2  GRANULAR GAIN ALONE, -Y/G.  Rank only.  T41's rotation table shows this
    tracks the primary's sign pattern exactly, which is the clue that dD is
    numerically almost entirely the Y term.

=== PROTOCOL ==============================================================

Registration is INCREMENTAL and per checkpoint, so a slow download never forces
a prediction to be written after an outcome.  A model is registered only if
lineB_ruler_<m>.json does NOT yet exist; once registered its entry is frozen and
never rewritten.  The rule block above is written once and asserted unchanged.

    python3 lineB_prereg.py
"""
import glob
import hashlib
import json
import os
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REG = os.path.join(HERE, "lineB_prereg.json")
DISCOVERY = ["pythia", "qwen", "opt", "smollm2"]
NWIN_PREREG = 40          # fixed here, before any new checkpoint is measured

RULE = {
    "predictor": "X / G  with X = sum_{y<-c}(e_A^2 - e_B^2), G = sum_rest e_B^2",
    "B1_rank": "m = 100*(ppl_TOP/ppl_MXFP4 - 1) is INCREASING in X/G; "
               "predicted Spearman rho > 0 on the NEW checkpoints alone",
    "B2_sign": "sign(m) = sign(X/G); threshold zero, read off the format",
    "C1_control": "T41 primary dD/D_B; rank increasing, sign dD<0 => m<0",
    "C2_control": "granular gain alone, -Y/G; rank only",
    "nwin_preregistered": NWIN_PREREG,
    "arm": "MX-asym-TOP", "parent": "MXFP4", "c": 0.75, "beta": 0.875,
    "free_parameters": 0,
}


def entry(d):
    return {
        "X": d["X"], "Y": d["Y"], "G": d["G"],
        "D_MXFP4": d["D_MXFP4"], "dD": d["dD"],
        "X_over_G": d["X_over_G"], "Y_over_G": d["Y_over_G"],
        "dD_over_DB": d["dD"] / d["D_MXFP4"],
        "n_elements": d["n_elements"], "n_blocks": d["n_blocks"],
        "pred_sign_B2": 1 if d["X_over_G"] > 0 else -1,
        "pred_sign_C1": 1 if d["dD"] > 0 else -1,
    }


def main():
    reg = (json.load(open(REG)) if os.path.exists(REG)
           else {"rule": RULE, "discovery": {}, "registered": {}})
    assert reg["rule"] == RULE, "the rule block changed after registration began"

    for p in sorted(glob.glob(os.path.join(HERE, "lineD_decompose_*.json"))):
        d = json.load(open(p))
        m = d["model"]
        assert abs(d["c"] - 0.75) < 1e-12, m
        if m in DISCOVERY:
            reg["discovery"][m] = entry(d)          # context, not under test
            continue
        if m in reg["registered"]:
            print(f"  {m:<14} already registered "
                  f"{reg['registered'][m]['registered_utc']} -- left untouched")
            continue
        if os.path.exists(os.path.join(HERE, f"lineB_ruler_{m}.json")):
            print(f"  {m:<14} REFUSED: perplexity already measured; a prediction "
                  f"written after the outcome is not a prediction")
            continue
        e = entry(d)
        e["registered_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        reg["registered"][m] = e
        print(f"  {m:<14} REGISTERED  X/G = {e['X_over_G']:+.6f}  "
              f"B2 predicts m {'>' if e['pred_sign_B2'] > 0 else '<'} 0  "
              f"| C1 dD/D_B = {e['dD_over_DB']:+.4%}  "
              f"C1 predicts m {'>' if e['pred_sign_C1'] > 0 else '<'} 0")

    body = json.dumps(reg, indent=1, sort_keys=True)
    open(REG, "w").write(body)
    h = hashlib.sha256(body.encode()).hexdigest()

    new = reg["registered"]
    order = sorted(new, key=lambda m: new[m]["X_over_G"])
    print("\nREGISTERED PREDICTIONS  (weights only, no forward pass)")
    print(f"{'model':<14}{'X/G':>13}{'Y/G':>11}{'dD/D_B':>11}{'B2':>5}{'C1':>5}"
          f"   registered")
    for m in order:
        e = new[m]
        print(f"{m:<14}{e['X_over_G']:>+13.6f}{e['Y_over_G']:>11.5f}"
              f"{e['dD_over_DB']:>+11.4%}"
              f"{'+' if e['pred_sign_B2'] > 0 else '-':>5}"
              f"{'+' if e['pred_sign_C1'] > 0 else '-':>5}   "
              f"{e['registered_utc']}")
    print(f"\nB1 predicted order (arm's best first): {' < '.join(order) or '-'}")
    print(f"sha256 {h}\nwrote {REG}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
