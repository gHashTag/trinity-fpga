#!/usr/bin/env python3
"""mxgf4 decode conformance — 4-bit → FP32. 2-byte frame."""
import serial, struct, time, random, sys, argparse
N,E,M,BIAS = 4,1,2,0
EM = (1<<E)-1
def decode(raw):
    raw &= (1<<N)-1
    s=raw>>(N-1); e=(raw>>M)&EM; m=raw&((1<<M)-1)
    if e==EM:
        if m==0: return 0xFF800000 if s else 0x7F800000
        return 0x7FC00001
    if e==0:
        if m==0: return s<<31
        v=(m/float(1<<M))*(2.0**(1-BIAS))
    else: v=(1+m/float(1<<M))*(2.0**(e-BIAS))
    if abs(v)>3.4e38: return 0xFF800000 if v<0 else 0x7F800000
    if abs(v)<1.2e-38: return s<<31
    return struct.unpack(">I",struct.pack(">f",-v if s else v))[0]
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--port",default="/dev/cu.usbserial-120")
    ap.add_argument("--baud",type=int,default=160000)
    args=ap.parse_args()
    codes=set()
    MMAX=(1<<M)-1
    for s in (0,1):
        codes.add(s<<(N-1)); codes.add((s<<(N-1))|(EM<<M))
    codes.add((EM<<M)|1); codes.add((EM<<M)|MMAX)
    for s in (0,1):
        for mv in [1,MMAX,max(1,MMAX//2)]:
            codes.add((s<<(N-1))|mv)
    for e in [1,2,max(2,BIAS%EM),EM-1]:
        if 1<=e<EM:
            for mv in [0,MMAX,max(0,MMAX//2)]:
                for s in (0,1): codes.add((s<<(N-1))|(e<<M)|mv)
    rng=random.Random(4)
    for _ in range(min(2000,(1<<N)-1)): codes.add(rng.randrange(1<<N))
    codes=sorted(codes)
    port=serial.Serial(args.port,args.baud,timeout=3)
    ok=0; fails=[]
    for raw in codes:
        g=decode(raw)
        port.write(bytes([0xAA,0x55,0,raw&0xFF,(raw>>8)&0xFF,0]))
        time.sleep(0.004)
        r=port.read(5)
        if len(r)>=5 and r[0]==0xA5:
            d=r[1]|(r[2]<<8)|(r[3]<<16)|(r[4]<<24)
            gn=(g>>23&0xFF)==0xFF and g&0x7FFFFF
            dn=(d>>23&0xFF)==0xFF and d&0x7FFFFF
            if gn and dn or d==g: ok+=1
            else:
                if len(fails)<5: fails.append(f"raw={raw:#x} g={g:#010x} d={d:#010x}")
        else:
            if len(fails)<5: fails.append(f"raw={raw:#x} noresp")
    print(f"HW RESULT: {ok}/{len(codes)} bit-exact (fails={len(codes)-ok})")
    for f in fails: print(f"  {f}",file=sys.stderr)
    port.close()
if __name__=="__main__": main()
