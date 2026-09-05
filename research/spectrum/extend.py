"""Full enumeration at degree 9 and 10 (memory-light: keeps only summaries).

The degree<=8 pass in spectrum.py stores every ratio.  At degree 9/10 the ratio
count runs into the millions, so here we keep only what the questions need:
the count, the minimum ratio overall and per adder cost, and the nearest ratio
to each target overall and per adder cost.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np

from spectrum import (ALPHABETS, ROOT_HI, IMAG_TOL, ABOVE_ONE, TRUE_ROOT_GAP,
                      coeff_table, companion_batch, poly_desc, deflate_at_one,
                      newton_refine, optimal_ratio)

HERE = Path(__file__).resolve().parent

TARGETS = {n: optimal_ratio(n) for n in (4, 5, 6, 7, 8, 9, 10)}


class Acc:
    """Streaming accumulator: min ratio and nearest-to-target, per adder cost."""

    def __init__(self):
        self.n = 0
        self.min_overall = None
        self.min_by_adders: dict[int, tuple] = {}
        self.near: dict[tuple, tuple] = {}   # (target_name, adders|None) -> (dist, r, coef)

    def add(self, r, adders, coef):
        self.n += 1
        rec = (r, adders, coef)
        if self.min_overall is None or r < self.min_overall[0]:
            self.min_overall = rec
        cur = self.min_by_adders.get(adders)
        if cur is None or r < cur[0]:
            self.min_by_adders[adders] = rec
        for name, t in TARGETS.items():
            dist = abs(np.log(r) - np.log(t))
            for key in ((name, None), (name, adders)):
                c = self.near.get(key)
                if c is None or dist < c[0]:
                    self.near[key] = (dist, r, coef)

    def dump(self):
        return {
            "hits": self.n,
            "min_overall": self.min_overall,
            "min_by_adders": {str(k): v for k, v in sorted(self.min_by_adders.items())},
            "nearest": {f"{k[0]}|{'any' if k[1] is None else k[1]}": v
                        for k, v in sorted(self.near.items(),
                                           key=lambda kv: (kv[0][0], -1 if kv[0][1] is None else kv[0][1]))},
        }


def scan(d: int, alphabet_name: str, chunk: int = 60_000) -> Acc:
    alphabet = ALPHABETS[alphabet_name]
    hi = ROOT_HI[alphabet_name]
    A = coeff_table(d, alphabet)
    total = A.shape[0]
    acc = Acc()
    t0 = time.time()
    for s in range(0, total, chunk):
        blk = A[s:s + chunk]
        w = np.linalg.eigvals(companion_batch(blk))
        good = (np.abs(w.imag) < IMAG_TOL) & (w.real > 1.0 + ABOVE_ONE) & (w.real < hi)
        rows, cols = np.nonzero(good)
        if rows.size:
            defl: dict[int, list[int]] = {}
            for ridx, r0 in zip(rows, w.real[rows, cols]):
                ridx = int(ridx)
                q = defl.get(ridx)
                if q is None:
                    q = deflate_at_one([int(x) for x in poly_desc(blk[ridx])])
                    defl[ridx] = q
                if len(q) < 2:
                    continue
                r = newton_refine(q, float(r0))
                if r <= 1.0 + TRUE_ROOT_GAP or r > hi:
                    continue
                a = blk[ridx]
                acc.add(r, int(np.count_nonzero(a)) - 1, tuple(int(x) for x in a))
        if s % (chunk * 5) == 0:
            print(f"    d={d} {s + len(blk):,}/{total:,}  ({time.time() - t0:.0f}s)",
                  flush=True)
    print(f"  d={d} [{alphabet_name}]: {total:,} polys, {acc.n:,} root hits, "
          f"{time.time() - t0:.0f}s", flush=True)
    return acc


def main():
    degrees = [int(x) for x in sys.argv[1:]] or [9]
    out = {}
    for d in degrees:
        for name in ("pm1", "pm2"):
            out[f"{name}_d{d}"] = scan(d, name).dump()
            (HERE / "extend.json").write_text(json.dumps(out, indent=1))
    print(f"wrote {HERE / 'extend.json'}")


if __name__ == "__main__":
    main()
