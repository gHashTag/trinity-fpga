#!/usr/bin/env python3
"""Two checks that a reader should not have to do by hand.

CHECK 1 -- the prefactor of Theorem thm:scaleradix.
The theorem states the expected relative error of a scale r^e with a significand
uniformly quantised over [1,r) by M bits, on a log-uniform workload, as
    (1/4) * kappa(r) * 2^-M,     kappa(r) = (r-1)^2 / (r ln r).
An earlier draft stated it without the 1/4: the proof took the mean absolute
rounding error to be half a step (that is the maximum) and then absorbed a second
factor of two into a convention. Monte Carlo settles it. Status of the empirical
column: [measured -- software].

CHECK 2 -- the taxonomy counts close on the catalogue size.
The catalogue has 83 entries. 11 carry no exponent field, 18 span fewer than six
binades, 1 needs probes wider than were generated, so 53 are classified and the
four class counts must sum to 53. An earlier draft wrote the geometric count as 8
against a member list of seven (takum8/16/32/64 and tekum8/16/32), which made the
whole thing sum to 84 and contradicted the binding catalogue size of 83.
This asserts rather than reports.
"""
import json
import math
import pathlib
import sys

import numpy as np

CATALOGUE = 83
NO_EXPONENT = 11
TOO_NARROW = 18
TOO_WIDE_TO_PROBE = 1
CLASSES = {"constant": 38, "wobble": 3, "arithmetic": 5, "geometric": 7}
GEOMETRIC_MEMBERS = ["takum8", "takum16", "takum32", "takum64",
                     "tekum8", "tekum16", "tekum32"]


def kappa(r):
    return (r - 1) ** 2 / (r * math.log(r))


def empirical_mean_rel_error(r, m, n=8_000_000, seed=20260814):
    rng = np.random.default_rng(seed)
    s = r ** rng.random(n)                       # log-uniform on [1, r)
    step = (r - 1) * 2.0 ** -m
    q = np.round((s - 1) / step) * step + 1.0
    return float(np.mean(np.abs(q - s) / s))


def main():
    # CHECK 2 first: it is an assertion, not a measurement.
    classified = CATALOGUE - NO_EXPONENT - TOO_NARROW - TOO_WIDE_TO_PROBE
    assert classified == 53, f"classified is {classified}, expected 53"
    assert sum(CLASSES.values()) == classified, (
        f"class counts sum to {sum(CLASSES.values())}, expected {classified}")
    assert CLASSES["geometric"] == len(GEOMETRIC_MEMBERS), (
        "geometric count disagrees with its own member list")
    total = NO_EXPONENT + TOO_NARROW + TOO_WIDE_TO_PROBE + sum(CLASSES.values())
    assert total == CATALOGUE, f"taxonomy totals {total}, catalogue is {CATALOGUE}"

    rows = []
    for r, m in ((2, 8), (2, 11), (3, 8), (3, 11)):
        emp = empirical_mean_rel_error(r, m)
        pred = 0.25 * kappa(r) * 2.0 ** -m
        rows.append({"r": r, "M": m,
                     "empirical": float(f"{emp:.4e}"),
                     "predicted_quarter_kappa": float(f"{pred:.4e}"),
                     "ratio": round(pred / emp, 4)})
        print(f"r={r} M={m:2d}  empirical {emp:.4e}  (1/4)kappa*2^-M {pred:.4e}"
              f"  ratio {pred/emp:.4f}")

    worst = max(abs(row["ratio"] - 1.0) for row in rows)
    assert worst < 0.002, f"prefactor disagrees by {worst:.4f}"

    out = {
        "kappa": {"2": round(kappa(2), 7), "3": round(kappa(3), 7),
                  "ratio_3_over_2": round(kappa(3) / kappa(2), 4)},
        "prefactor": "one quarter",
        "prefactor_status": "[measured -- software]",
        "monte_carlo_draws": 8_000_000,
        "rows": rows,
        "taxonomy": {"catalogue": CATALOGUE, "no_exponent": NO_EXPONENT,
                     "too_narrow": TOO_NARROW,
                     "too_wide_to_probe": TOO_WIDE_TO_PROBE,
                     "classified": classified, "classes": CLASSES,
                     "geometric_members": GEOMETRIC_MEMBERS,
                     "closes_on_catalogue": True},
    }
    dest = pathlib.Path(__file__).resolve().parent / "tnf_kappa_taxonomy.json"
    dest.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(f"\ntaxonomy closes on {CATALOGUE}: "
          f"{NO_EXPONENT}+{TOO_NARROW}+{TOO_WIDE_TO_PROBE}+{classified}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
