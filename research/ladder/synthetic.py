"""What in the shape of a distribution moves the optimal ladder ratio?

The closed form was fitted to one model's weights. If it is a law rather than a
fit, it should say something about distributions in general -- and the cheapest
way to see what it says is to feed it distributions whose shape we choose.
"""
import numpy as np
RAT = {"shift": 2.0, "phi": (1+5**0.5)/2, "supergold": 1.465571231876768,
       "plastic": 1.324717957244746, "deg4": 1.178724176}

def c2(r):
    u = np.linspace(0, 1, 20001); x = r ** (-u)
    return float(np.mean((np.minimum(np.abs(x-1.0), np.abs(x-1.0/r))/x) ** 2))
C2 = {k: c2(v) for k, v in RAT.items()}

def mse(x, r, bits):
    """x: |w| normalised so max = 1."""
    n = (2**bits - 1)//2
    t = r ** (-(n-1)) / 2
    below = x < t
    return (c2(r) * float((x[~below]**2).sum()) + float((x[below]**2).sum())) / x.size

def r_star(x, bits, grid=np.linspace(1.02, 2.6, 500)):
    return float(grid[int(np.argmin([mse(x, float(v), bits) for v in grid]))])

rng = np.random.default_rng(7)
N = 400_000
shapes = {
    "gaussian":            np.abs(rng.normal(size=N)),
    "laplace  (heavier)":  np.abs(rng.laplace(size=N)),
    "student-t df=3":      np.abs(rng.standard_t(3, size=N)),
    "lognormal s=0.5":     rng.lognormal(0, 0.5, size=N),
    "lognormal s=1.0":     rng.lognormal(0, 1.0, size=N),
    "lognormal s=2.0":     rng.lognormal(0, 2.0, size=N),
    "uniform":             rng.uniform(0, 1, size=N),
}
print(f"  {'распределение':22} {'экс.куртозис':>13} {'r*(3b)':>8} {'r*(4b)':>8} {'r*(5b)':>8} {'r*(6b)':>8}")
for nm, s in shapes.items():
    x = (s / s.max()).astype(np.float64)
    k = float(((x - x.mean())**4).mean() / ((x - x.mean())**2).mean()**2 - 3)
    rs = [r_star(x, b) for b in (3,4,5,6)]
    print(f"  {nm:22} {k:13.2f} " + " ".join(f"{v:8.4f}" for v in rs))
print()
print("  и какая РЕАЛЬНАЯ лестница выигрывает по формуле:")
for nm, s in shapes.items():
    x = (s / s.max()).astype(np.float64)
    win = [min(RAT, key=lambda k_: mse(x, RAT[k_], b)) for b in (3,4,5,6)]
    print(f"    {nm:22} " + " ".join(f"{w:>10}" for w in win))
