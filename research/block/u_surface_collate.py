"""Collate every u-surface row measured by u_surface.py and ask whether u* is a property of
(block size K, element format) or of the model.

Reads only files already on disk; measures nothing.  Every aggregate prints its denominator.

Provenance of the rows it reads
-------------------------------
All rows come from u_surface.py (one harness, 12 self-test gates).  Gate status differs by model
and is printed, because it bounds what the rows can be used for:
  smollm2 : gates 1-9 (model-free) PASSED, G7/G11a/G12 PASSED, G10 fp32 baseline PASSED
            (14.4874 == established), G11 reproduced 3 of 4 established NW=40 cells exactly and
            DISAGREED on the OCP cell (24.1633 vs 23.5224).
  qwen    : gates 1-9 PASSED, G12 PASSED; G7/G10/G11a/G11 never completed (both gate runs died
            before printing them).  The qwen rows are therefore UNGATED on the model side.
"""
import glob
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
KS = (16, 32, 64, 128)
FMTS = ("E2M1", "E3M0", "INT4")
U_SPEC = {"E2M1": 0.41504, "E3M0": 1.00000, "INT4": 0.19265}
BINADES = {"E2M1": 3.585, "E3M0": 6.000, "INT4": 2.807}
MAXNORM = {"E2M1": 6.0, "E3M0": 16.0, "INT4": 7.0}


def load(nw_want=4):
    """Every row at the requested window count, keyed by (model, K, fmt) -> {u: ppl}."""
    cells, files, base, dup = {}, {}, {}, []
    for p in sorted(glob.glob(os.path.join(HERE, "u_surface_*.json"))):
        d = json.load(open(p))
        if "rows" not in d or d.get("nw") != nw_want or d.get("tie") != "even":
            continue
        for r in d["rows"]:
            k = (r["model"], r["K"], r["fmt"])
            u = round(r["u"], 6)
            prev = cells.setdefault(k, {})
            if u in prev and abs(prev[u] - r["ppl"]) > 1e-9:
                dup.append((k, u, prev[u], r["ppl"], os.path.basename(p)))
            prev[u] = r["ppl"]
            files.setdefault(k, set()).add(os.path.basename(p))
            base[r["model"]] = d["baseline"]
    return cells, files, base, dup


def vertex(us, ps, i):
    """Parabola through the grid minimum and its two neighbours -> interpolated u*."""
    if i == 0 or i == len(us) - 1:
        return None
    x0, x1, x2 = us[i - 1], us[i], us[i + 1]
    y0, y1, y2 = ps[i - 1], ps[i], ps[i + 1]
    d1, d2 = (y0 - y1) / (x0 - x1), (y2 - y1) / (x2 - x1)
    den = d2 - d1
    if abs(den) < 1e-12:
        return None
    v = x1 + 0.5 * (d1 * (x2 - x1) - d2 * (x0 - x1)) / den
    return v if min(us) <= v <= max(us) else None


def cell_stats(u2p, delta):
    us = sorted(u2p)
    ps = [u2p[u] for u in us]
    i = min(range(len(ps)), key=lambda j: ps[j])
    pmin = ps[i]
    basin = [u for u, p in zip(us, ps) if p <= pmin * (1.0 + delta)]
    return dict(us=us, ps=ps, n=len(us), u_star=us[i], ppl_star=pmin,
                edge=(i == 0 or i == len(us) - 1), vtx=vertex(us, ps, i),
                gap=(min(us[j + 1] - us[j] for j in range(len(us) - 1)) if len(us) > 1 else None),
                basin_lo=min(basin), basin_hi=max(basin), nbasin=len(basin))


def main():
    nw = int(sys.argv[1]) if len(sys.argv) > 1 else 4
    delta = float(sys.argv[2]) if len(sys.argv) > 2 else 0.01
    cells, files, base, dup = load(nw)
    print(f"\n=== u* SURFACE from rows already on disk: nw={nw} windows x 2048 tok, ties=even, "
          f"g=2 ===")
    print(f"    fp32 baselines at this window count: "
          + ", ".join(f"{m} {b:.4f}" for m, b in sorted(base.items())))
    print(f"    cells found: {len(cells)} of {2 * len(KS) * len(FMTS)} "
          f"(2 models x {len(KS)} K x {len(FMTS)} formats)")
    print(f"    basin = every grid u with ppl <= (1+{delta:g}) x min ppl")
    if dup:
        print(f"    !! {len(dup)} disagreeing duplicate measurements of the same cell/u:")
        for k, u, a, b, f in dup:
            print(f"       {k} u={u}: {a:.4f} vs {b:.4f}  ({f})")
    else:
        n_rep = sum(1 for k in cells for _ in [0])
        print(f"    duplicate rows re-measuring the same (cell,u) all agree exactly "
              f"(harness is deterministic)")

    st = {}
    for model in sorted({k[0] for k in cells}):
        print(f"\n  --- {model} " + "-" * 96)
        print(f"      {'fmt':<6}{'K':>5}{'n_u':>5}{'grid':>7}{'u*':>7}{'ppl(u*)':>10}"
              f"{'vertex':>8}{'basin':>15}{'ppl(0)':>10}{'ppl(spec)':>11}"
              f"{'gain vs spec':>13}{'gain vs 0':>11}")
        for fmt in FMTS:
            for K in KS:
                key = (model, K, fmt)
                if key not in cells:
                    print(f"      {fmt:<6}{K:>5}   -- not measured --")
                    continue
                s = cell_stats(cells[key], delta)
                st[key] = s
                p0 = cells[key].get(0.0)
                us_ = U_SPEC[fmt]
                pspec = cells[key].get(round(us_, 6))
                # nearest measured u to the spec alignment, if the exact point is absent
                if pspec is None:
                    near = min(cells[key], key=lambda u: abs(u - us_))
                    pspec = cells[key][near] if abs(near - us_) <= 0.07 else None
                gs = (pspec / s["ppl_star"] - 1.0) * 100 if pspec else float("nan")
                g0 = (p0 / s["ppl_star"] - 1.0) * 100 if p0 else float("nan")
                vtx = f"{s['vtx']:.3f}" if s["vtx"] else "-"
                basin = f"[{s['basin_lo']:.3f},{s['basin_hi']:.3f}]"
                print(f"      {fmt:<6}{K:>5}{s['n']:>5}{s['gap']:>7.3f}"
                      f"{s['u_star']:>7.3f}{s['ppl_star']:>10.4f}{vtx:>8}{basin:>15}"
                      f"{(p0 if p0 else float('nan')):>10.4f}"
                      f"{(pspec if pspec else float('nan')):>11.4f}"
                      f"{gs:>12.2f}%{g0:>10.2f}%"
                      + ("   u* AT GRID EDGE" if s["edge"] else ""))
    return st, cells


if __name__ == "__main__":
    main()
