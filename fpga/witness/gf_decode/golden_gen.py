#!/usr/bin/env python3
# Independent golden for gf_decode_param.v. argv: builddir name N E M BIAS [mode]
# Not derived from the user's gf_decode_ref -- independent struct.pack-based FP32 oracle.
import struct, sys, math, os
builddir=sys.argv[1]; name=sys.argv[2]; N=int(sys.argv[3]); E=int(sys.argv[4]); M=int(sys.argv[5]); BIAS=int(sys.argv[6])
mode = sys.argv[7] if len(sys.argv)>7 else "repr"
EXP_MAX=(1<<E)-1; MANT_MAX=(1<<M)-1
def bits(v):
    if math.isnan(v): return 0x7FC00001
    if math.isinf(v) or abs(v) > 3.4028235e38: return 0xFF800000 if v<0 else 0x7F800000
    try: return struct.unpack(">I", struct.pack(">f", v))[0]
    except OverflowError: return 0xFF800000 if v<0 else 0x7F800000
def decode(raw):
    sign=raw>>(N-1); exp=(raw>>M)&EXP_MAX; mant=raw&((1<<M)-1)
    if exp==EXP_MAX and mant==0: return 0xFF800000 if sign else 0x7F800000
    if exp==EXP_MAX: return 0x7FC00001
    if exp==0 and mant==0: return sign<<31
    if exp==0: mag=(mant/float(1<<M))*(2.0**(1-BIAS))
    elif (exp-BIAS) >= 128: return 0xFF800000 if sign else 0x7F800000
    else:      mag=(1.0+mant/float(1<<M))*(2.0**(exp-BIAS))
    return bits(-mag if sign else mag)
raws=set()
for s in (0,1):
    raws.add(s<<(N-1)); raws.add((s<<(N-1))|(EXP_MAX<<M))
raws.add((EXP_MAX<<M)|1); raws.add((EXP_MAX<<M)|MANT_MAX)
for s in (0,1):
    for mv in {1,MANT_MAX,max(1,MANT_MAX//2),max(1,MANT_MAX//3)}: raws.add((s<<(N-1))|mv)
boundary=BIAS-126
exps=set([1,EXP_MAX-1,max(2,EXP_MAX//2),max(2,EXP_MAX//3)])
for d in range(-5,6): exps.add(boundary+d)
for s in (0,1):
    for e in exps:
        if 1<=e<EXP_MAX:
            for mv in {0,MANT_MAX,max(0,MANT_MAX//2)}: raws.add((s<<(N-1))|(e<<M)|mv)
full=1<<N; step=max(1, full//5000)
for r in range(0,full,step): raws.add(r)
if mode=="exhaustive" and full<=70000: raws=set(range(full))
raws=sorted(r&((1<<N)-1) for r in raws)
os.makedirs(builddir, exist_ok=True)
with open(f"{builddir}/vectors_{name}.txt","w") as f:
    for r in raws: f.write(f"{r:0{(N+3)//4}x} {decode(r):08x}\n")
print(f"{name}: {len(raws)} vectors ({mode})")
