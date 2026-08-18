import sys
sys.path.insert(0,'conformance'); sys.path.insert(0,'.')
import split_rule_sweep as S
# fast, deterministic assertions over the same machinery the report uses
assert round(15/S.PHI_SQ) == 6, "the rule must pick e=6 at 16 bits"
a,_ = S.score(S.rung(8,23), 2, n=200)
b,_ = S.score(S.rung(12,19), 2, n=200)
assert b > a, "at 2 decades the IEEE-like split must beat the rule"
c,_ = S.score(S.rung(8,23), 80, n=200)
d,_ = S.score(S.rung(12,19), 80, n=200)
assert d < c, "at 80 decades the rule must win"
