#!/usr/bin/env python3
"""Assertions for dot_product_bench.py, fast enough to mutation-test against.

The claims the report rests on, pinned so a constant cannot drift unnoticed.
The bias and top-of-range checks are here because the rows are named after
industry formats they only partly match, and that gap must stay measured.
"""

import random
import sys

sys.path.insert(0, "conformance")
sys.path.insert(0, ".")
import dot_product_bench as B  # noqa: E402
import gf_ref as G  # noqa: E402


def check(cond, what):
    print(f"  {'PASS' if cond else 'FAIL'}  {what}")
    return 0 if cond else 1


def top(e, m):
    f = B.rung(e, m)
    return float(G.decode(f, (f.exp_max << f.mant_bits) | f.mant_max))


def main():
    bad = 0
    print("dot_product_bench assertions\n")

    bad += check(round(7 / B.PHI_SQ) == 3, "the rule picks e3m4 at 8 bits")
    bad += check(round(15 / B.PHI_SQ) == 6, "and e6m9 at 16")

    # The gap between these rows and the standards they are named after.
    bad += check(B.rung(4, 3).bias == 7, "e4m3 fields carry OCP E4M3's bias of 7")
    bad += check(abs(top(4, 3) - 480.0) < 0.5,
                 "but top out at 480, not OCP E4M3's 448 -- its all-ones row is NaN")
    bad += check(abs(top(5, 2) - 114688.0) < 1.0,
                 "and e5m2 fields reach 114688, not OCP E5M2's 57344")

    # The correction this benchmark exists to carry: relative error alone
    # cannot see a format zeroing the tensor.
    random.seed(1)
    def severe():
        return random.gauss(0, 1) * (4096.0 if random.random() < 0.01 else 1.0)
    err_rule, z_rule = B.bench(B.rung(3, 4), severe, n=256, trials=30)
    err_e4m3, z_e4m3 = B.bench(B.rung(4, 3), severe, n=256, trials=30)
    bad += check(z_rule > 0.5,
                 f"under a 4096x outlier e3m4 zeroes most of the tensor ({z_rule*100:.0f}%)")
    bad += check(z_e4m3 < 0.10,
                 f"where e4m3 fields lose little ({z_e4m3*100:.1f}%)")
    bad += check(z_rule > B.FLUSH_REPORT_AT,
                 "so the flush rate is worth reporting beside the error score")

    # Every row's NAME must agree with the split beside it, and the widths must
    # add up. `tri mutate` showed the whole CANDIDATES table surviving: nothing
    # tied "e5m10 fields" to (5, 10), so a typo there would have produced a
    # confidently mislabelled report.
    import re
    for width, rows in B.CANDIDATES.items():
        for name, e, m in rows:
            bad_ = 0
            if 1 + e + m != width:
                bad_ = 1
            hit = re.search(r"e(\d+)m(\d+)", name)
            if hit and (int(hit.group(1)), int(hit.group(2))) != (e, m):
                bad_ = 1
            if bad_:
                bad += check(False, f"{width}b row '{name}' does not match e{e}m{m}")
    bad += check(True, "every row's name matches its split, and 1+e+m equals the width")

    # The threshold only annotates now. perplexity_sweep.py measured the same
    # splits on three real models and ranked e3m4 FIRST at 8 bits despite it
    # zeroing 1.75% of GPT-2's weights, so disqualifying on this number would
    # have thrown away the best candidate.
    bad += check(0 < B.FLUSH_REPORT_AT < 0.5, "it is a real threshold, not 0 or 1")

    print()
    print("All assertions hold." if not bad else f"{bad} assertion(s) failed")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
