#!/usr/bin/env python3
"""W944: re-derive every headline number from the committed records.

The standing instruction is "check all the numbers again" every wave. Doing that
by reading is how the width error survived three instruments. This recomputes each
quoted figure from its record and reports agreement or drift, so the check is a
command rather than an act of attention.
"""
import json, pathlib, sys
import numpy as np

# W948d: this page exists so somebody else can refute the numbers, and a hard-coded
# author path makes that impossible. Records sit beside this script (upstream:
# research/arxiv_tnf/measurements/) or in the directory named by T27_RECORDS.
import os
R = pathlib.Path(os.environ.get("T27_RECORDS") or pathlib.Path(__file__).resolve().parent)
if (R / "measurements").is_dir():
    R = R / "measurements"
ok = bad = skip = 0


def rec(name):
    p = R / name
    return json.loads(p.read_text()) if p.exists() else None


def check(label, got, want, tol=0.02):
    global ok, bad
    if got is None:
        print(f"  ??  {label}: не вычислено")
        return
    d = abs(got - want)
    rel = d / max(abs(want), 1e-9)
    if d <= tol or rel <= 0.005:
        print(f"  ok  {label}: {got:.2f} (цитируется {want:.2f})")
        ok += 1
    else:
        print(f"  РАСХОЖДЕНИЕ  {label}: пересчитано {got:.4f}, цитируется {want}")
        bad += 1


def paired(d, task, a, b, key="formats"):
    p = d["tasks"][task][key] if key in d["tasks"][task] else d["tasks"][task]
    x = np.array(p[a]); y = np.array(p[b])
    return float((x - y).mean() * 100)


def drop(d, task, fmt, key="formats", base="baseline"):
    p = d["tasks"][task]
    b = np.array(p[base]); a = np.array(p[key][fmt])
    return float((b - a).mean() * 100)


print("== цена (структурные и таблично-оракульные декодеры)")
st = rec("structural_w942.json"); orl = rec("oracle_rtl_w941.json")
if st and orl:
    check("TNF4 потребитель, структура", st["tnf4"]["consumer_cells"], 55.29)
    check("TNF16 потребитель, структура", st["tnf16"]["consumer_cells"], 450.29)
    check("fp8 e4m3 потребитель, таблица", orl["fp8_e4m3"]["consumer_cells"], 152.57)
    check("TNF4/fp8 отношение", orl["fp8_e4m3"]["consumer_cells"] / st["tnf4"]["consumer_cells"], 2.76, tol=0.03)
    check("TNF16 физическая ширина", st["tnf16"]["physical_bits"], 19, tol=0)
    check("кодов сверено у TNF16", st["tnf16"]["codes_checked"], 524288, tol=0)
    check("расхождений у TNF16", st["tnf16"]["mismatches"], 0, tol=0)
else:
    skip += 1; print("  пропуск: нет записей цены")

print("\n== точность, PTQ")
big = rec("accuracy_seeds_big_w940.json"); sml = rec("accuracy_seeds_w939.json")
if big and sml:
    check("MLP PTQ MNIST, TNF4−fp4", paired(big, "mnist", "4b/TNF4", "4b/fp4e2m1"), 37.88, tol=0.05)
    check("MLP PTQ Fashion, TNF4−fp4", paired(big, "fashion", "4b/TNF4", "4b/fp4e2m1"), 64.42, tol=0.05)
    check("малая сеть MNIST, TNF4−fp4", paired(sml, "mnist", "4b/TNF4", "4b/fp4e2m1"), 8.40, tol=0.05)
    check("малая сеть Fashion, TNF4−fp4", paired(sml, "fashion", "4b/TNF4", "4b/fp4e2m1"), 27.75, tol=0.05)
    # Two networks, two different maxima -- the first version of this check
    # compared the small net's quoted 0.13 against the big net's record and
    # reported a drift that was its own.
    mb = max(abs(drop(big, t, f)) for t in ("mnist", "fashion")
             for f in big["tasks"]["mnist"]["formats"] if f.startswith("8b/"))
    ms = max(abs(drop(sml, t, f)) for t in ("mnist", "fashion")
             for f in sml["tasks"]["mnist"]["formats"] if f.startswith("8b/"))
    check("максимум |падения| на 8 битах, сеть 269k", mb, 0.04, tol=0.02)
    check("максимум |падения| на 8 битах, сеть 25k", ms, 0.37, tol=0.02)
else:
    skip += 1; print("  пропуск: нет записей точности")

print("\n== точность, активации и QAT")
act = rec("activations_w941.json"); qat = rec("qat_w943.json"); cnv = rec("conv_w943.json")
if act:
    mx = 0.0
    for t in ("mnist", "fashion"):
        b = np.array(act["tasks"][t]["baseline"])
        for f, v in act["tasks"][t]["weights_and_activations"].items():
            if f.endswith("8") or "8" in f:
                mx = max(mx, abs(float((b - np.array(v)).mean() * 100)))
    check("максимум |падения| на 8 битах (веса+акт)", mx, 0.06, tol=0.03)
if qat:
    check("QAT MNIST, TNF4−fp4", paired(qat, "mnist", "TNF4", "fp4e2m1", key="qat"), 0.19, tol=0.02)
    check("QAT Fashion, TNF4−fp4", paired(qat, "fashion", "TNF4", "fp4e2m1", key="qat"), 0.89, tol=0.02)
if cnv:
    check("CNN MNIST, TNF4−fp4", paired(cnv, "mnist", "TNF4", "fp4e2m1"), 12.98, tol=0.05)
    check("CNN Fashion, TNF4−fp4", paired(cnv, "fashion", "TNF4", "fp4e2m1"), 24.90, tol=0.05)

print("\n== приор и эталон")
pr = rec("prior_sensitivity_w937.json"); hh = rec("head_to_head_w937.json")
if pr:
    f = pr["published_uniform_77_binades"]["formats"]
    check("TNF16 против posit16 при опубликованном приоре",
          f["posit16"]["median_rel_err"] / f["TNF16"]["median_rel_err"], 14.63, tol=0.05)
    g = pr["standard_normal"]["formats"]
    check("то же при стандартном нормальном",
          g["posit16"]["median_rel_err"] / g["TNF16"]["median_rel_err"], 1.02, tol=0.02)
if hh:
    check("PACoGen экстракция posit16", hh["pacogen_data_extract_n16_es2"]["cells_per_unit"], 92.0)
    check("PACoGen сумматор posit16", hh["pacogen_posit_add_n16_es2"]["cells_per_unit"], 693.0)
    check("TNF сумматор 16 ячеек", hh["tnf_e4m8_add_16cells"]["cells_per_unit"], 561.67, tol=0.05)

# W948d: the published tally said fp6 e2m3 failed 29 of 40; recomputing it from
# the records gives 28. One document said 20/20 successes, another 29/40 failures
# -- the same measurement in two polarities, which is how the off-by-one survived
# three documents. So the tallies are now DERIVED here, in one polarity, from
# every stability record present, rather than copied forward by hand.
print("\n== устойчивость: пересчёт по всем записям")
_TH = {"mnist": 60.0, "fashion": 60.0, "kmnist": 40.0}
_tot, _cfg = {}, 0
for _f in sorted(R.glob("stability*.json")):
    _d = json.loads(_f.read_text())
    if "runs" not in _d:
        continue
    _cfg += 1
    _th = _TH[_d.get("task", "mnist")]
    for _fmt, _runs in _d["runs"].items():
        _acc = [_r[-1]["acc"] * 100 for _r in _runs.values()]
        _t = _tot.setdefault(_fmt, [0, 0])
        _t[0] += sum(1 for _a in _acc if _a >= _th)
        _t[1] += len(_acc)
if _tot:
    check("конфигураций устойчивости", _cfg, 8, tol=0)
    for _fmt, _want in (("TNF4", 40), ("fp6e3m2", 16), ("fp6e2m3", 12)):
        if _fmt in _tot:
            _s, _n = _tot[_fmt]
            check(f"успехов {_fmt} из {_n}", _s, _want, tol=0)

print(f"\n  ИТОГ: сошлось {ok}, расхождений {bad}, пропущено блоков {skip}")
sys.exit(1 if bad else 0)
