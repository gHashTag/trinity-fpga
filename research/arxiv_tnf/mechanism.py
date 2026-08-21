#!/usr/bin/env python3
"""W950: recover the mechanism that T798 withdrew, from traces already recorded.

The withdrawn explanation was UNDERFLOW: narrow grids zero what falls below their
smallest value. Under the convention the runs actually used, that ordering is
inverted, so it cannot be the cause.

The traces suggest the opposite direction. Every failing run shows the activation
scale COLLAPSING (0.81 -> 0.29 -> 0.0065). A shrinking s makes x/s GROW, and a
format then needs headroom ABOVE its initialisation point, not resolution below it.
Under the peak2one convention the peak starts at grid value 1.0, so the headroom is
exactly max(grid): 3072 for TNF4, 28 for fp6 e3m2, 7.5 for fp6 e2m3 -- a 400x spread.

Prediction: in failing runs the scale falls far enough that max|x|/s exceeds the
grid maximum, i.e. the tensor SATURATES. This checks it against every record.
"""
import json, pathlib, sys
import numpy as np

R = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else ".")
GMAX = {"TNF4": 3072.0, "fp6e3m2": 28.0, "fp6e2m3": 7.5}
TH = {"mnist": 60.0, "fashion": 60.0, "kmnist": 40.0}

rows = []
for f in sorted(R.glob("stability*.json")):
    d = json.loads(f.read_text())
    if "runs" not in d:
        continue
    task, th = d.get("task", "mnist"), TH[d.get("task", "mnist")]
    for fmt, runs in d["runs"].items():
        gm = GMAX.get(fmt)
        if gm is None:
            continue
        for seed, tr in runs.items():
            acc = tr[-1]["acc"] * 100
            s0 = np.array(tr[0]["act_scales"], dtype=float)
            sN = np.array(tr[-1]["act_scales"], dtype=float)
            drop = float((s0 / np.maximum(sN, 1e-30)).max())      # worst collapse
            rows.append({"file": f.name, "task": task, "fmt": fmt, "seed": seed,
                         "acc": acc, "failed": acc < th, "collapse": drop,
                         "headroom": gm, "saturates": drop > gm})

print(f"  записей прогонов: {len(rows)}\n")
print(f"  {'формат':9} {'исход':10} {'n':>4} {'медиана падения масштаба':>26} {'запас сверху':>13} {'насыщение':>11}")
for fmt in ("TNF4", "fp6e3m2", "fp6e2m3"):
    for failed in (False, True):
        sub = [r for r in rows if r["fmt"] == fmt and r["failed"] == failed]
        if not sub:
            continue
        med = np.median([r["collapse"] for r in sub])
        sat = sum(1 for r in sub if r["saturates"])
        print(f"  {fmt:9} {'ОТКАЗ' if failed else 'успех':10} {len(sub):4d} "
              f"{med:26.1f}x {GMAX[fmt]:12.1f}x {sat:6d}/{len(sub):<4d}")

print("\n  Проверка предсказания: насыщение <=> отказ")
tp = sum(1 for r in rows if r["saturates"] and r["failed"])
fp = sum(1 for r in rows if r["saturates"] and not r["failed"])
fn = sum(1 for r in rows if not r["saturates"] and r["failed"])
tn = sum(1 for r in rows if not r["saturates"] and not r["failed"])
print(f"    насыщение и отказ      {tp:4d}      насыщение без отказа  {fp:4d}")
print(f"    отказ без насыщения    {fn:4d}      ни того ни другого    {tn:4d}")
den = tp + fp + fn + tn
print(f"    согласие: {(tp+tn)/den*100:.1f}%  ({tp+tn}/{den})")
json.dump({"rows": rows, "confusion": {"tp": tp, "fp": fp, "fn": fn, "tn": tn}},
          open(R / "mechanism_w950.json", "w"), indent=1)
print("\nWROTE " + str(R / "mechanism_w950.json"))
