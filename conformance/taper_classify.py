import importlib, math, random
from fractions import Fraction as F
random.seed(11)
MODS=["ieee_ref","posit_ref","takum_ref","tekum_ref","lns_ref","bf16_ref","fp8_ref",
      "mxfp_ref","legacy_ref","gf_ref","extended_ref","nf4_ref"]
cat=[]
for mn in MODS:
    try: m=importlib.import_module(mn)
    except Exception: continue
    for k,v in getattr(m,"FORMATS",{}).items(): cat.append((mn,k,v,m))
import tnf_ref as G
for nm,Et,M in [("tef8",3,4),("tef16",4,9),("tef32",6,25),("tef64",7,52)]:
    cat.append(("tnf_ref",nm,G.TEFFormat(Et,M),G))

def probe(mod,fmt,e,n=40):
    """средняя относит. ошибка round-trip на бинаде |e|; None если формат туда не достаёт"""
    tot=F(0); k=0
    for _ in range(n):
        s=F(random.getrandbits(600),1<<600)
        v=(1+s)*(F(2)**e)*(1 if random.random()<.5 else -1)
        try: d=mod.decode(fmt,mod.encode(fmt,v))
        except Exception: continue
        if not isinstance(d,F) or d==0: continue
        tot+=abs(d-v)/abs(v); k+=1
    if k<n//2: return None
    return float(tot/k)

def usable_range(mod,fmt,cap=300):
    """наибольшее |e|, где формат ещё не насыщен (ошибка < 25%)"""
    hi=0
    for e in range(1,cap):
        a=probe(mod,fmt,e,12); b=probe(mod,fmt,-e,12)
        if a is None or b is None or a>0.25 or b>0.25: break
        hi=e
    return hi

def meff(r):
    if r is None or r<=0 or r>=1: return None
    return -math.log2(2*r/0.7213)-1

def fit(xs,ys):
    n=len(xs); mean=sum(ys)/n
    r_c=sum((y-mean)**2 for y in ys)/n
    def lin(fx):
        fs=[fx(x) for x in xs]; mf=sum(fs)/n
        den=sum((f-mf)**2 for f in fs)
        if den<1e-12: return 0.0,float('inf')
        b=sum((f-mf)*(y-mean) for f,y in zip(fs,ys))/den
        a=mean-b*mf
        return -b,sum((y-(a+b*f))**2 for f,y in zip(fs,ys))/n
    ba,ra=lin(lambda x:x); bg,rg=lin(lambda x:math.log2(1+x))
    if max(ys)-min(ys) < 0.30: return "constant",0.0
    c=[("arithmetic",ba,ra)] if ba>0 else []
    if bg>0: c.append(("geometric",bg,rg))
    if not c: return "constant",0.0
    f,b,_=min(c,key=lambda t:t[2]); return f,b

rows=[]
for mn,nm,fmt,mod in cat:
    R=usable_range(mod,fmt)
    if R<6: rows.append((nm,mn,R,None,"диапазон<6",0)); continue
    # 6 полос ВНУТРИ измеренного диапазона (до 90%, чтобы не задеть границу)
    top=int(R*0.9); es=[max(1,round(top*(i+1)/6)) for i in range(6)]
    xs=[];ys=[]
    for e in sorted(set(es)):
        vs=[meff(probe(mod,fmt,e)),meff(probe(mod,fmt,-e))]
        vs=[v for v in vs if v is not None]
        if vs: xs.append(e); ys.append(sum(vs)/len(vs))
    if len(xs)<4: rows.append((nm,mn,R,None,"мало точек",0)); continue
    form,b=fit(xs,ys)
    rad=getattr(fmt,'radix',getattr(fmt,'base',2)) or 2
    if rad>2: form,b="wobble",__import__('math').log2(rad)
    elif b<0.05: form,b="constant",0.0
    rows.append((nm,mn,R,ys[0],form,b))

print(f"{'формат':15s}{'модуль':10s}{'диапазон':>9s}{'M_eff':>8s}  {'форма':11s}{'параметр':>9s}")
order={"constant":0,"wobble":1,"arithmetic":2,"geometric":3}
for r in sorted(rows,key=lambda r:(order.get(r[4],9),-(r[3] or 0))):
    me=f"{r[3]:.2f}" if r[3] is not None else "—"
    print(f"{r[0]:15s}{r[1].replace('_ref',''):10s}{r[2]:9d}{me:>8s}  {r[4]:11s}{r[5]:9.3f}")
from collections import Counter
print("\nИТОГО:",dict(Counter(r[4] for r in rows)))
