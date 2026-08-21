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

# W949: the scaling convention is itself a recipe axis, and it is the one that
# decides fp6 e3m2. Derived here rather than quoted, per T797.
sc = rec("scaleconv_w949.json")
if sc:
    print("\n== конвенция масштаба (W949)")
    for conv, want in (("peak2one", {"TNF4": 0, "fp6e2m3": 4, "fp6e3m2": 0}),
                       ("peak2max", {"TNF4": 0, "fp6e2m3": 5, "fp6e3m2": 5})):
        for fmt, w in want.items():
            a = sc["runs"][conv][fmt]
            check(f"{conv} {fmt}: отказов из {len(a)}", sum(1 for v in a if v < 60.0), w, tol=0)
    check("peak2one воспроизводит запись W946 (TNF4)",
          sum(sc["runs"]["peak2one"]["TNF4"]) / 5, 96.70, tol=0.02)

bs = rec("blockscale_w949.json")
if bs:
    print("\n== блочный масштаб (W949)")
    b32 = bs["res"]["acts_heavy"]["32"]
    check("блок 32, тяж.хвост: TNF4 обнуляет, %", b32["TNF4"]["underflow"] * 100, 0.01, tol=0.005)
    check("блок 32, тяж.хвост: e2m3 обнуляет, %", b32["fp6e2m3"]["underflow"] * 100, 2.51, tol=0.02)
    check("блок 32: RMS TNF4 / RMS e2m3",
          b32["TNF4"]["rel_rmse"] / b32["fp6e2m3"]["rel_rmse"], 3.47, tol=0.03)
    bt = bs["res"]["acts_heavy"][str(bs["n"])]
    check("на весь тензор: e2m3 обнуляет, %", bt["fp6e2m3"]["underflow"] * 100, 44.41, tol=0.05)

# W950: the surviving claim, tested against the recipe the field actually uses.
bq = rec("blockquant_w950.json")
if bq:
    print("\n== вычисляемый масштаб MX (W950)")
    for arm in ("block32", "per_tensor"):
        for fmt in ("TNF4", "fp6e2m3", "fp6e3m2"):
            a = bq["runs"][arm][fmt]
            check(f"{arm} {fmt}: отказов из {len(a)}", sum(1 for v in a if v < 60.0), 0, tol=0)
    import numpy as _np
    for arm, opp, want, wt in (("per_tensor", "fp6e2m3", -0.376, -7.24),
                               ("per_tensor", "fp6e3m2", -0.250, -5.15),
                               ("block32", "fp6e2m3", 0.010, 0.11)):
        t = _np.array(bq["runs"][arm]["TNF4"]); f = _np.array(bq["runs"][arm][opp])
        dd = t - f
        check(f"{arm} TNF4−{opp}, п.п.", float(dd.mean()), want, tol=0.002)
        check(f"{arm} TNF4−{opp}, t", float(dd.mean() / (dd.std(ddof=1) / _np.sqrt(len(dd)))), wt, tol=0.02)

mw = rec("mechanism_w950.json")
if mw:
    print("\n== механизм: насыщение против отказа (W950)")
    c = mw["confusion"]; tot = sum(c.values())
    check("прогонов в трассах", tot, 120, tol=0)
    check("согласие насыщение<=>отказ, %", (c["tp"] + c["tn"]) / tot * 100, 90.83, tol=0.02)
    check("fp6e2m3: отказы с насыщением", c["tp"] >= 48, True, tol=0)

# W951: the sweep redone under the computed scale, on all three tasks, and
# saturation OBSERVED rather than inferred. All derived, per T797.
sat = rec("saturation_w951.json")
if sat:
    print("\n== свод и наблюдённое насыщение (W951)")
    check("прогонов в своде W951", len(sat), 135, tol=0)
    comp = [r for r in sat if r["mode"] == "computed"]
    lrn = [r for r in sat if r["mode"] == "learned"]
    check("вычисляемый масштаб: прогонов", len(comp), 90, tol=0)
    check("вычисляемый масштаб: отказов", sum(1 for r in comp if r["failed"]), 0, tol=0)
    check("обучаемый масштаб: отказов из 45", sum(1 for r in lrn if r["failed"]), 9, tol=0)
    check("TNF4 отказов во всём своде W951",
          sum(1 for r in sat if r["fmt"] == "TNF4" and r["failed"]), 0, tol=0)
    ok_s = [r["sat"] for r in lrn if not r["failed"]]
    bad_s = [r["sat"] for r in lrn if r["failed"]]
    check("худший перелёт среди успехов", max(ok_s), 1509.7, tol=0.5)
    check("лучший перелёт среди отказов", min(bad_s), 84775.4, tol=0.5)
    check("разделяются ли распределения", max(ok_s) < min(bad_s), True, tol=0)
    check("вычисляемый масштаб: максимум перелёта",
          max(r["sat"] for r in comp), 2.0, tol=0.001)

# W952: what the dynamic range costs in silicon. Two numbers, deliberately: one
# implementation-specific (fixed-point MAC lane), one forced by arithmetic (the
# block-32 accumulator width). Quoting only the first would be the same error as
# quoting a decoder-only census.
mac = rec("mac_w952.json"); acc = rec("acc_w952.json"); wid = rec("widths_w952.json")
if wid:
    print("\n== ширины, вынужденные диапазоном (W952)")
    for f, w, wp, a in (("TNF4", 17, 33, 38), ("fp6e3m2", 10, 19, 24), ("fp6e2m3", 7, 13, 18)):
        check(f"{f}: бит на значение", wid[f]["w"], w, tol=0)
        check(f"{f}: бит на произведение", wid[f]["w_prod"], wp, tol=0)
if mac:
    print("\n== полоса MAC в фиксированной точке (W952)")
    for f, want in (("TNF4", 768.0), ("fp6e3m2", 308.0), ("fp6e2m3", 159.0)):
        check(f"{f}: ячеек на полосу", mac["cost"][f]["per_lane"], want, tol=0.01)
        check(f"{f}: R2 линейности", mac["cost"][f]["r2"], 1.0, tol=0.0001)
    check("TNF4 / fp6e2m3, полоса",
          mac["cost"]["TNF4"]["per_lane"] / mac["cost"]["fp6e2m3"]["per_lane"], 4.83, tol=0.01)
if acc:
    print("\n== аккумулятор блока-32, неизбежная часть (W952)")
    for f, want in (("TNF4", 48.0), ("fp6e3m2", 30.0), ("fp6e2m3", 23.0)):
        check(f"{f}: ячеек на аккумулятор", acc["cost"][f]["per_acc"], want, tol=0.01)
    check("TNF4 / fp6e2m3, аккумулятор",
          acc["cost"]["TNF4"]["per_acc"] / acc["cost"]["fp6e2m3"]["per_acc"], 2.087, tol=0.01)
    check("надбавка на элемент, аморт. по 32",
          (acc["cost"]["TNF4"]["per_acc"] - acc["cost"]["fp6e2m3"]["per_acc"]) / 32, 0.781, tol=0.005)

# W953: the third datapath, which closes the W952 bracket.
fl = rec("flane_w953.json")
if fl:
    print("\n== полоса MAC во флоатном стиле (W953)")
    for f, want in (("TNF4", 108.0), ("fp6e3m2", 82.0), ("fp6e2m3", 74.0)):
        check(f"{f}: ячеек на флоат-полосу", fl["cost"][f]["per_lane"], want, tol=0.01)
        check(f"{f}: R2 линейности", fl["cost"][f]["r2"], 1.0, tol=0.0001)
    check("TNF4 / fp6e2m3, флоат-полоса",
          fl["cost"]["TNF4"]["per_lane"] / fl["cost"]["fp6e2m3"]["per_lane"], 1.459, tol=0.005)
    check("нечётная мантисса TNF4, бит", fl["fields"]["TNF4"]["odd_bits"], 2, tol=0)
    check("нечётная мантисса fp6e2m3, бит", fl["fields"]["fp6e2m3"]["odd_bits"], 4, tol=0)
    if mac:
        check("флоат дешевле фикс.точки для TNF4",
              mac["cost"]["TNF4"]["per_lane"] > fl["cost"]["TNF4"]["per_lane"], True, tol=0)
        check("флоат дешевле фикс.точки для fp6e2m3",
              mac["cost"]["fp6e2m3"]["per_lane"] > fl["cost"]["fp6e2m3"]["per_lane"], True, tol=0)

# W954: cost tracks RANGE, not the lattice. Range-matched peers, both widths.
rm_ = rec("rangematch_w954.json"); ld = rec("ladder_w954.json")
if rm_:
    print("\n== согласование по диапазону, 6 бит (W954)")
    for f, want in (("TNF4", 108.0), ("fp6e4m1", 106.0), ("fp6e3m2", 82.0), ("fp6e2m3", 74.0)):
        check(f"{f}: ячеек на полосу", rm_["cost"][f]["per_lane"], want, tol=0.01)
    check("TNF4 / fp6e4m1 (диапазон согласован)",
          rm_["cost"]["TNF4"]["per_lane"] / rm_["cost"]["fp6e4m1"]["per_lane"], 1.019, tol=0.005)
    check("TNF4 / fp6e2m3 (только ширина)",
          rm_["cost"]["TNF4"]["per_lane"] / rm_["cost"]["fp6e2m3"]["per_lane"], 1.459, tol=0.005)
if ld:
    print("\n== ступень TNF8 лестницы, 10 бит (W954)")
    check("TNF8(3,4): ячеек на полосу", ld["cost"]["TNF8_ladder_10b"]["per_lane"], 380.0, tol=0.01)
    check("fp10_e5m4: ячеек на полосу", ld["cost"]["fp10_e5m4"]["per_lane"], 376.0, tol=0.01)
    check("TNF8 / fp10_e5m4 (диапазон согласован)",
          ld["cost"]["TNF8_ladder_10b"]["per_lane"] / ld["cost"]["fp10_e5m4"]["per_lane"], 1.011, tol=0.005)
    check("fp10_e6m3 дороже обоих (шире диапазон)",
          ld["cost"]["fp10_e6m3"]["per_lane"] > ld["cost"]["TNF8_ladder_10b"]["per_lane"], True, tol=0)

print(f"\n  ИТОГ: сошлось {ok}, расхождений {bad}, пропущено блоков {skip}")
sys.exit(1 if bad else 0)
