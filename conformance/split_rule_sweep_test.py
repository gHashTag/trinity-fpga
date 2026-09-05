#!/usr/bin/env python3
"""Assertions for split_rule_sweep.py, fast enough to mutation-test against.

The sweep's report carries numbers; this file carries the claims those numbers
rest on. `tri mutate` against the sweep showed the bias formula surviving every
mutation -- the directional assertions below could not see it -- so the bias is
now pinned to something checkable: an e=8, m=23 rung must behave like IEEE
binary32, because that is the split the report compares the golden rule against.
"""

import sys

sys.path.insert(0, "conformance")
sys.path.insert(0, ".")
import split_rule_sweep as S  # noqa: E402

PHI_SQ = S.PHI_SQ


def check(cond, what):
    print(f"  {'PASS' if cond else 'FAIL'}  {what}")
    return 0 if cond else 1


def main():
    bad = 0
    print("split_rule_sweep assertions\n")

    bad += check(round(15 / PHI_SQ) == 6, "the rule picks e=6 at 16 bits")
    bad += check(round(31 / PHI_SQ) == 12, "the rule picks e=12 at 32 bits")

    # Pin the bias. An e=8, m=23 rung is binary32's split, so 1.0 must round
    # trip exactly and the largest finite value must sit near 3.4e38. Without
    # this the bias could be anything and every directional test still passed.
    f = S.rung(8, 23)
    bad += check(S.round_trip(f, 1.0) == 1.0, "e=8 m=23 holds 1.0 exactly")
    bad += check(S.round_trip(f, -1.0) == -1.0, "and -1.0")
    big = S.round_trip(f, 3.0e38)
    bad += check(big is not None and 3.0e38 <= big < 3.5e38,
                 "and reaches binary32's top of range, so the bias is binary32's")
    # This line said `... or True` in its first version, which made it pass
    # unconditionally -- a vacuous assertion inside the file written to stop
    # vacuous assertions. Rewriting it truthfully then FAILED, which is how the
    # next fact turned up: this rung has has_inf = False and bias 126, so it
    # does not overflow to Inf -- it SATURATES, and its top of range is 4x
    # binary32's. It shares binary32's field widths and not its behaviour.
    # This line said `... or True` in its first version, which made it pass
    # unconditionally -- a vacuous assertion inside the file written to stop
    # vacuous assertions.
    #
    # Rewriting it truthfully failed, and chasing that failure produced a
    # FABRICATED finding: I read bias 126 and a 4x top of range, and wrote up an
    # "unreachable top binade". Both numbers came from a file my own mutation
    # test had left perturbed on disk. On the clean file the bias is 127, the
    # widest encodable pattern and the encoder's saturation point are the SAME
    # value, and there is no gap. Measurements taken while a mutation harness is
    # running are not measurements.
    huge = S.round_trip(f, 1e50)
    bad += check(huge is not None and abs(huge / 3.4028235e38 - 2.0) < 0.01,
                 "saturates at 6.81e38, twice binary32's top: bias 127, no Inf row")

    import gf_ref as _G
    widest = float(_G.decode(f, (f.exp_max << f.mant_bits) | f.mant_max))
    bad += check(widest == huge,
                 "and the encoder reaches the widest encodable pattern exactly")

    # Direction, at both ends of the dynamic-range axis.
    a, _ = S.score(S.rung(8, 23), 2, n=200)
    b, _ = S.score(S.rung(12, 19), 2, n=200)
    bad += check(b > a, "at 2 decades the binary32-like split beats the golden rule")

    c, _ = S.score(S.rung(8, 23), 80, n=200)
    d, _ = S.score(S.rung(12, 19), 80, n=200)
    bad += check(d < c, "at 80 decades the golden rule wins, as its extra range implies")

    print()
    if bad:
        print(f"{bad} assertion(s) failed")
    else:
        print("All assertions hold.")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
