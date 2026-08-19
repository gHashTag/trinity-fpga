#!/usr/bin/env python3
"""Recompute `tab:law` for the specification ladder, in exact rationals.

The published rows mixed generations: TNF16 at the unfilled M=9 and TNF32 at the
specification's M=25, while the ladder table beside it used the oracle's M=21.
Here every row is the specification width (Table `tab:ladder-sweep`, `source =
spec` where one exists, reconciled M for the 16-bit rung), so one ladder is
measured and the mantissa width is printed next to the number it produced.
"""
import random, sys
from fractions import Fraction as F
sys.path.insert(0, "../../conformance")
import tnf_ref as T

SPEC = [("TNF8",3,4),("TNF16",4,11),("TNF32",6,25),("TNF64",7,52),
        ("TNF128",8,115),("TNF256",9,242),("TNF512",10,497),("TNF1024",11,1006)]
BINS=[(0,8),(8,20),(20,38)]
rnd=random.Random(20260809); PREC=1200
WORK=[]
for _ in range(600):
    e=rnd.randint(-38,38); m=1+F(rnd.getrandbits(PREC),1<<PREC)
    s=rnd.choice([-1,1]); WORK.append((s*m*(F(2)**e if e>=0 else F(1,2**-e)), abs(e)))

for name,et,M in SPEC:
    fmt=T.TNFFormat(et,M); band=[]
    for lo,hi in BINS:
        tot,n=F(0),0
        for v,ae in WORK:
            if not lo<=ae<hi: continue
            try: d=T.decode(fmt,T.encode(fmt,v))
            except Exception: continue
            if d is None or d==0: continue
            if isinstance(d,float) and d in (float('inf'),float('-inf')): continue
            rel=abs(F(d)-v)/abs(v)
            if rel>F(1,2): continue
            tot+=rel; n+=1
        band.append(float(tot/n) if n else None)
    ok=[b for b in band if b]
    mean=sum(ok)/len(ok); u=2.0**-(M+1)
    print("%-8s M=%-5d u=%.2e measured=%.2e ratio=%.2f flatness=%.3f" %
          (name,M,u,mean,mean/u,max(ok)/min(ok)))
