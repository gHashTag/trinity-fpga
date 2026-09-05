#!/usr/bin/env python3
"""Recompute `tab:tnf16-fill` on exactly the harness of recompute_field_table.py
(same workload, same clip convention) so the fill table, the accuracy table and
the figure cannot disagree. Published row values (3.37e-4, 8.63e-5, 5.46x) came
from an older harness.
"""
import sys, math
import numpy as np
sys.path.insert(0,"../../conformance")
import tnf_ref as T, takum_ref as K
_rng=np.random.default_rng(20260809)
VALS=[float(s)*float(m)*2.0**int(e) for s,m,e in
      zip(_rng.choice([-1,1],6000), _rng.uniform(1,2,6000), _rng.integers(-38,39,6000))]
LO,HI=20,38
def measure(dec):
    tot,n,bad=0.0,0,0
    for v in VALS:
        if not LO<=abs(np.log2(abs(v)))<HI: continue
        try: d=dec(v)
        except Exception: d=None
        if d is not None:
            d=float(d)
            if not np.isfinite(d): d=None
        if d is None or d==0.0:
            bad+=1; continue
        tot+=abs(d-v)/abs(v); n+=1
    return tot/n, bad
_tk=K.TakumFormat("takum16",16)
tk,_=measure(lambda v: K.decode(_tk,K.encode(_tk,v)))
print("takum16 far=%.3e"%tk)
for name,et,M in [("unfilled 4/9",4,9),("adopted 4/11",4,11),("5/10",5,10),("6/9",6,9)]:
    f=T.TNFFormat(et,M)
    e_,bad=measure(lambda v,f=f: T.decode(f,T.encode(f,v)))
    print("%-13s far=%.3e clip=%d vs takum=%.2fx decades=%.0f"%(name,e_,bad,tk/e_,(3**et-1)*math.log10(2)))
