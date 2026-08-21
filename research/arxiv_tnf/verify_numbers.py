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

# W962: the split sweep. Cost is set by (odd-mantissa bits, max shift), not by range.
cv = rec("curve_w955.json")
if cv:
    print("\n== развёртка по расщеплениям (W955/W962)")
    for f, want in (("fp6_e1m4", 80.0), ("fp6_e2m3", 74.0), ("fp6_e3m2", 82.0),
                    ("fp6_e4m1", 106.0), ("fp10_e3m6", 230.0), ("fp10_e4m5", 215.0),
                    ("fp10_e5m4", 376.0), ("fp10_e6m3", 447.0)):
        check(f"{f}: ячеек на полосу", cv["cost"][f]["per_lane"], want, tol=0.01)
    # немонотонность: меньше диапазон, но дороже -- вот почему «ячеек на бинаду» нет
    check("fp6_e1m4 дороже fp6_e2m3 при МЕНЬШЕМ диапазоне",
          cv["cost"]["fp6_e1m4"]["per_lane"] > cv["cost"]["fp6_e2m3"]["per_lane"]
          and cv["fields"]["fp6_e1m4"]["binades"] < cv["fields"]["fp6_e2m3"]["binades"], True, tol=0)
    check("fp10_e3m6 дороже fp10_e4m5 при МЕНЬШЕМ диапазоне",
          cv["cost"]["fp10_e3m6"]["per_lane"] > cv["cost"]["fp10_e4m5"]["per_lane"]
          and cv["fields"]["fp10_e3m6"]["binades"] < cv["fields"]["fp10_e4m5"]["binades"], True, tol=0)
    # точный закон: одинаковая пара (нечёт, сдвиг) => одинаковая цена
    if rm_ and ld:
        for a, da, b, db, tol_pct in (("TNF4", rm_, "fp6e4m1", rm_, 2.0),
                                      ("TNF8_ladder_10b", ld, "fp10_e5m4", ld, 2.0)):
            fa, fb = da["fields"][a], db["fields"][b]
            check(f"{a}/{b}: пара (нечёт, сдвиг) совпадает",
                  (fa["odd_bits"], fa["max_shift"]) == (fb["odd_bits"], fb["max_shift"]), True, tol=0)
            ca, cb = da["cost"][a]["per_lane"], db["cost"][b]["per_lane"]
            check(f"{a}/{b}: разница цены, %", abs(ca - cb) / cb * 100, 1.5, tol=0.5)
    # перекрёстная сверка между волнами
    for k6, kc in (("fp6e4m1", "fp6_e4m1"), ("fp6e2m3", "fp6_e2m3"), ("fp6e3m2", "fp6_e3m2")):
        if rm_ and k6 in rm_["cost"]:
            check(f"{kc}: W954 против W955",
                  rm_["cost"][k6]["per_lane"] - cv["cost"][kc]["per_lane"], 0.0, tol=0.001)

# W963: the census redone on the ladder's TRUE eighth rung, in the original metric.
cs = rec("census_tnf8_w963.json")
if cs:
    print("\n== перепись на настоящей ступени (W963)")
    for k, dec, con in (("tnf8_ladder_10b", 12.0, 212.57), ("fp10_e5m4", 14.0, 214.57),
                        ("tnf8_as_measured_11b", 29.0, 270.57), ("fp11_e6m4", 16.0, 257.57)):
        check(f"{k}: декодер", cs[k]["decoder_cells"], dec, tol=0.01)
        check(f"{k}: потребитель", cs[k]["consumer_cells"], con, tol=0.01)
    t, f = cs["tnf8_ladder_10b"]["consumer_cells"], cs["fp10_e5m4"]["consumer_cells"]
    check("настоящая ступень против своего float, %", (t - f) / f * 100, -0.93, tol=0.02)
    ts, fs = cs["tnf8_as_measured_11b"]["consumer_cells"], cs["fp11_e6m4"]["consumer_cells"]
    check("подстановка против своего float, %", (ts - fs) / fs * 100, 5.05, tol=0.02)
    check("знак результата инвертируется подстановкой",
          ((t - f) < 0) and ((ts - fs) > 0), True, tol=0)
    check("декодер: подстановка дороже во сколько раз",
          cs["tnf8_as_measured_11b"]["decoder_cells"] / cs["tnf8_ladder_10b"]["decoder_cells"],
          2.417, tol=0.01)

# W964: accuracy at the ladder's TRUE eighth rung, three recipes.
import glob as _glob
_rung = {}
for _f in sorted(R.glob("rung_w964_*.json")):
    _d = json.loads(_f.read_text())
    _rung[f"{_d['mode']}_b{_d['block']}"] = _d
if _rung:
    print("\n== точность настоящей восьмой ступени (W964)")
    check("конфигураций", len(_rung), 3, tol=0)
    _tot = 0
    for _k, _d in _rung.items():
        for _fmt, _per in _d["runs"].items():
            _a = [t[-1]["acc"] for t in _per.values()]
            _tot += len(_a)
            check(f"{_k} {_fmt}: отказов", sum(1 for x in _a if x < 60.0), 0, tol=0)
    check("прогонов всего", _tot, 45, tol=0)
    for _k, _want, _t in (("computed_b0", -0.010, -0.20), ("computed_b32", -0.018, -0.48),
                          ("learned_b0", 0.060, 0.89)):
        _d = _rung[_k]
        _t1 = np.array([t[-1]["acc"] for t in _d["runs"]["TNF8_true_10b"].values()])
        _f1 = np.array([t[-1]["acc"] for t in _d["runs"]["fp10_e5m4"].values()])
        _dd = _t1 - _f1
        check(f"{_k}: TNF8−fp10, п.п.", float(_dd.mean()), _want, tol=0.002)
        _se = _dd.std(ddof=1) / np.sqrt(len(_dd))
        check(f"{_k}: t", float(_dd.mean() / _se), _t, tol=0.02)

# W965: rung 16, both ladder versions, against width- and range-matched peers.
r16 = rec("rung16_w965.json")
if r16:
    print("\n== ступень 16, структурные параметры (W965)")
    for k, w, vals, bina, ob, sm in (
            ("TNF16_v1research_17b", 17, 129025, 127.0, 10, 135),
            ("TNF16_v2spec_19b", 19, 516097, 127.0, 12, 137),
            ("fp17_e7m9", 17, 131071, 136.0, 10, 135),
            ("fp19_e7m11", 19, 524287, 138.0, 12, 137),
            ("fp17_e6m10", 17, 131071, 73.0, 11, 72),
            ("fp19_e6m12", 19, 524287, 75.0, 13, 74)):
        check(f"{k}: ширина", r16[k]["width"], w, tol=0)
        check(f"{k}: значений", r16[k]["values"], vals, tol=0)
        check(f"{k}: бинад", r16[k]["binades"], bina, tol=0.01)
        check(f"{k}: нечёт", r16[k]["odd_bits"], ob, tol=0)
        check(f"{k}: сдвиг", r16[k]["max_shift"], sm, tol=0)
    for t, f in (("TNF16_v1research_17b", "fp17_e7m9"), ("TNF16_v2spec_19b", "fp19_e7m11")):
        check(f"{t}/{f}: пара (нечёт, сдвиг) совпадает",
              (r16[t]["odd_bits"], r16[t]["max_shift"]) == (r16[f]["odd_bits"], r16[f]["max_shift"]),
              True, tol=0)
        check(f"{t}/{f}: шина совпадает", r16[t]["aligned"] - r16[f]["aligned"], 0, tol=0)
        check(f"{f} несёт больше значений", r16[f]["values"] > r16[t]["values"], True, tol=0)
        check(f"{f} несёт больше диапазона", r16[f]["binades"] > r16[t]["binades"], True, tol=0)

# W966: structural cost against a float built in TNF's own discipline (FTZ).
st = rec("struct966.json")
if st:
    print("\n== структурная цена в равной дисциплине (W966)")
    for k, bits, dec, con in (("tnf16_v2spec", 19, 27.0, 450.29),
                              ("fp19_e7m11", 19, 18.0, 441.29),
                              ("fp19_e6m12", 19, 22.0, 445.29),
                              ("tnf8_true", 10, 18.0, 230.57),
                              ("fp10_e5m4", 10, 13.0, 225.57)):
        check(f"{k}: ширина", st[k]["physical_bits"], bits, tol=0)
        check(f"{k}: декодер", st[k]["decoder_cells"], dec, tol=0.01)
        check(f"{k}: потребитель", st[k]["consumer_cells"], con, tol=0.01)
        check(f"{k}: расхождений с эталоном", st[k]["mismatches"], 0, tol=0)
    check("TNF16 против диапазон-соперника, %",
          (st["tnf16_v2spec"]["consumer_cells"] - st["fp19_e7m11"]["consumer_cells"])
          / st["fp19_e7m11"]["consumer_cells"] * 100, 2.04, tol=0.02)
    check("TNF8 против fp10_e5m4, %",
          (st["tnf8_true"]["consumer_cells"] - st["fp10_e5m4"]["consumer_cells"])
          / st["fp10_e5m4"]["consumer_cells"] * 100, 2.22, tol=0.02)
    sw = rec("structural_w942.json")
    if sw:
        check("TNF16 воспроизводит запись W942",
              st["tnf16_v2spec"]["consumer_cells"] - sw["tnf16"]["consumer_cells"], 0.0, tol=0.005)

# W969: the activations record regenerated on the ladder's TRUE eighth rung.
a69 = rec("activations_w969.json"); a41 = rec("activations_w941.json")
if a69 and a41:
    print("\n== перегенерация на настоящей ступени (W969)")
    for task, mode, want in (("mnist", "weights_only", -0.008),
                             ("mnist", "weights_and_activations", 0.018),
                             ("fashion", "weights_only", -0.016),
                             ("fashion", "weights_and_activations", -0.068)):
        o = np.array(a41["tasks"][task][mode]["TNF8"], dtype=float)
        n = np.array(a69["tasks"][task][mode]["TNF8"], dtype=float)
        if o.max() <= 1: o = o * 100
        if n.max() <= 1: n = n * 100
        check(f"{task}/{mode}: ступень − подстановка, п.п.", float((n - o).mean()), want, tol=0.002)
        d = n - o
        se = d.std(ddof=1) / np.sqrt(len(d))
        check(f"{task}/{mode}: |t| ниже 2", abs(float(d.mean() / se)) < 2.0, True, tol=0)

# W970: the last two records regenerated on the true rung. Damage: none in accuracy.
c70 = rec("conv_w970.json"); c43 = rec("conv_w943.json")
if c70 and c43:
    print("\n== conv, перегенерация (W970)")
    for task, want in (("mnist", 0.014), ("fashion", -0.020)):
        o = np.array(c43["tasks"][task]["formats"]["TNF8"], dtype=float)
        n = np.array(c70["tasks"][task]["formats"]["TNF8"], dtype=float)
        if o.max() <= 1: o = o * 100
        if n.max() <= 1: n = n * 100
        check(f"conv {task}: ступень − подстановка, п.п.", float((n - o).mean()), want, tol=0.002)
s70 = rec("accuracy_seeds_w970.json"); s39 = rec("accuracy_seeds_w939.json")
if s70 and s39:
    print("\n== accuracy_seeds, перегенерация (W970)")
    for task, want, wt in (("mnist", 0.064, 1.42), ("fashion", 0.040, 0.65)):
        o = np.array(s39["tasks"][task]["formats"]["8b/TNF8"], dtype=float) * 100
        n = np.array(s70["tasks"][task]["formats"]["8b/TNF8"], dtype=float) * 100
        d = n - o
        check(f"seeds {task}: ступень − подстановка, п.п.", float(d.mean()), want, tol=0.002)
        se = d.std(ddof=1) / np.sqrt(len(d))
        check(f"seeds {task}: t", float(d.mean() / se), wt, tol=0.02)

# W972: the last convention removed -- a float peer WITH subnormals, normaliser paid for.
s72 = rec("struct972.json")
if s72 and st:
    print("\n== соперник с субнормалями (W972)")
    check("fp19_e7m11_sub: декодер", s72["fp19_e7m11_sub"]["decoder_cells"], 78.0, tol=0.01)
    check("fp19_e7m11_sub: потребитель", s72["fp19_e7m11_sub"]["consumer_cells"], 501.29, tol=0.01)
    check("цена субнормалей, ячеек",
          s72["fp19_e7m11_sub"]["consumer_cells"] - s72["fp19_e7m11"]["consumer_cells"], 60.0, tol=0.01)
    t16 = st["tnf16_v2spec"]["consumer_cells"]
    check("TNF16 против FTZ-соперника, %",
          (t16 - s72["fp19_e7m11"]["consumer_cells"]) / s72["fp19_e7m11"]["consumer_cells"] * 100,
          2.04, tol=0.02)
    check("TNF16 против субнормального соперника, %",
          (t16 - s72["fp19_e7m11_sub"]["consumer_cells"]) / s72["fp19_e7m11_sub"]["consumer_cells"] * 100,
          -10.17, tol=0.02)
    check("знаки противоположны",
          (t16 > s72["fp19_e7m11"]["consumer_cells"]) and (t16 < s72["fp19_e7m11_sub"]["consumer_cells"]),
          True, tol=0)

# W973: first silicon numbers -- synthesis and timing on the real part.
bw = rec("bitstream_w973.json")
if bw:
    print("\n== битстрим на xc7a200tfbg676-1 (W973)")
    check("LUT", bw["cells"]["LUT"], 123, tol=0)
    check("CARRY4", bw["cells"]["CARRY4"], 52, tol=0)
    check("DSP48E1", bw["cells"]["DSP48E1"], 0, tol=0)
    check("BSCANE2", bw["cells"]["BSCANE2"], 1, tol=0)
    check("Fmax, МГц", bw["fmax_mhz"], 80.35, tol=0.01)
    check("запас над целью, %",
          (bw["fmax_mhz"] - bw["target_mhz"]) / bw["target_mhz"] * 100, 13.53, tol=0.02)
    check("DUT-эквивалентов", bw["dut_equivalents"], 1.19, tol=0.005)
    check("байт битстрима", bw["bitstream_bytes"], 9730834, tol=0)
    check("смещение слова синхронизации", bw["sync_word_offset"], 230, tol=0)
    check("собрано без Docker", "no Docker" in bw["toolchain"], True, tol=0)

# W974: the format's own operators on xc7a200tfbg676-1.
sw = rec("silicon_w974.json")
if sw:
    print("\n== операторы формата на кристалле (W974)")
    want = {"mvp_ternary_classifier": (123, 52, 80.35, "cfgmclk"),
            "gft_sadd": (1312, 257, 18.24, "slowclk"),
            "gft_signed_mac": (6466, 1237, 9.14, "slowclk"),
            "gft_signed_dot4": (12872, 2043, 5.50, "slowclk")}
    for k, (lut, c4, fm, clk) in want.items():
        d = sw["designs"][k]
        check(f"{k}: LUT", d["LUT"], lut, tol=0)
        check(f"{k}: CARRY4", d["CARRY4"], c4, tol=0)
        check(f"{k}: Fmax МГц", d["fmax_mhz"], fm, tol=0.01)
        check(f"{k}: клок совпадает", d["clock"] == clk, True, tol=0)
        check(f"{k}: DSP48E1", d["DSP48E1"], 0, tol=0)
    # сопоставимая тройка на slowclk: падение МГц/kLUT в 32 раза
    a = sw["designs"]["gft_sadd"]["mhz_per_klut"]
    b = sw["designs"]["gft_signed_dot4"]["mhz_per_klut"]
    check("падение МГц/kLUT по slowclk, раз", a / b, 32.56, tol=0.05)
    check("dot4 помечен неполным", sw["designs"]["gft_signed_dot4"]["complete"], False, tol=0)
    check("у dot4 два отдельных отказа", len(sw["designs"]["gft_signed_dot4"]["failures"]), 2, tol=0)
    check("mac даёт больше DUT-эквивалентов, чем sadd",
          sw["designs"]["gft_signed_mac"]["dut_equivalents"] >
          sw["designs"]["gft_sadd"]["dut_equivalents"], True, tol=0)

# W974: the first verdict read off the die.
dv = rec("die_verdict_w974.json")
if dv:
    print("\n== вердикт с кристалла (W974)")
    check("Done", dv["hardware"]["B1_done"], 1, tol=0)
    check("ok", dv["hardware"]["ok"], 1, tol=0)
    check("beat", dv["hardware"]["beat"], 1, tol=0)
    check("слово USER2 == 0xa5a5a5a7", dv["hardware"]["B2_word"] == "0xa5a5a5a7", True, tol=0)
    check("IDCODE == 0x3636093", dv["idcode"] == "0x3636093", True, tol=0)
    check("плата 1:5 (не 1:4 по умолчанию)", dv["board"] == "1:5", True, tol=0)
    check("тот же битстрим, что в W973", dv["build"]["bitstream_bytes"], 9730834, tol=0)
    check("Fmax совпадает с W973", dv["build"]["fmax_mhz"], 80.35, tol=0.01)

# W975: the format's operators read off the die, with the control satisfied.
od = rec("operators_die_w975.json")
if od:
    print("\n== операторы формата на кристалле (W975)")
    check("контроль: чужой битстрим уронил Done", od["control"]["A1_wrong_part_done"], 0, tol=0)
    sa, mc = od["operators"]["gft_sadd"], od["operators"]["gft_signed_mac"]
    check("sadd: клаузы на кристалле == 1111", sa["die_clauses"] == "1111", True, tol=0)
    check("sadd: ok", sa["ok"], 1, tol=0)
    check("sadd: симуляция без падений", sa["sim_failed"], 0, tol=0)
    check("mac: клаузы на кристалле == 0011", mc["die_clauses"] == "0011", True, tol=0)
    check("mac: ok", mc["ok"], 0, tol=0)
    check("mac: жив (beat)", mc["beat"], 1, tol=0)
    check("mac: симуляция без падений", mc["sim_failed"], 0, tol=0)
    check("mac: тестов в симуляции меньше, чем клауз на кристалле",
          mc["sim_passed"] < 4, True, tol=0)
    check("mac: запас по частоте, раз", mc["fmax_mhz"] / mc["target_mhz"], 4.13, tol=0.02)
    check("контроль прогонялся", mc["control_run"], True, tol=0)

# W976: the failing clauses decoded and diagnosed.
cd_ = rec("clause_diagnosis_w976.json")
if cd_:
    print("\n== диагноз клауз (W976)")
    d = cd_["decoded"]
    check("магия слова", d["magic"] == "0xA5A5", True, tol=0)
    check("версия слова", d["version"], 3, tol=0)
    check("идентификатор дизайна", d["design"], 13, tol=0)
    check("c_zero падает", d["c_zero"], 0, tol=0)
    check("c_comm падает", d["c_comm"], 0, tol=0)
    check("c_cancel держится", d["c_cancel"], 1, tol=0)
    check("c_ind держится", d["c_ind"], 1, tol=0)
    check("ZERO воспроизводится в симуляции",
          cd_["clauses"]["ZERO"]["sim"].startswith("FALSE"), True, tol=0)
    check("COMM в симуляции не воспроизведён",
          cd_["clauses"]["COMM"]["sim"].startswith("TRUE"), True, tol=0)
    check("попыток воспроизвести COMM", len(cd_["clauses"]["COMM"]["attempts"]), 3, tol=0)
    check("тестов в спеке", len(cd_["spec_tests"]), 2, tol=0)
    check("падающие клаузы не покрыты тестами",
          "untested" in cd_["coverage_finding"], True, tol=0)

# W977: root cause of the ZERO defect, and seven operators to the die.
rc_ = rec("root_cause_w977.json")
if rc_:
    print("\n== корневая причина и таблица операторов (W977)")
    ev = rc_["root_cause"]["evidence"]
    check("охранников нуля в GftSmul", len(ev["smul_zero_guards"]), 2, tol=0)
    check("охранников нуля в GftSignedMac", len(ev["mac_zero_guards"]), 0, tol=0)
    check("общая строка со скрытой единицей",
          ev["shared_hidden_bit_line"].startswith("prod = __mul_noop"), True, tol=0)
    check("W976 подтверждён стробированием",
          "stands" in rc_["validation_of_w976"]["verdict"], True, tol=0)
    check("опровергнутых гипотез", len(rc_["refuted_hypotheses"]), 3, tol=0)
    ops = rc_["operators"]
    check("smul: ZERO держится", ops["gft_smul"]["clauses"]["c_zero"], 1, tol=0)
    check("smul: COMM падает", ops["gft_smul"]["clauses"]["c_comm"], 0, tol=0)
    check("smul: IND падает", ops["gft_smul"]["clauses"]["c_ind"], 0, tol=0)
    check("train1: проходит", ops["gft_train1"]["ok"], 1, tol=0)
    check("операторов в таблице", len(rc_["table"]), 7, tol=0)
    passes = sum(1 for v in rc_["table"].values() if "PASS" in v)
    check("проходят на кристалле", passes, 2, tol=0)

# W978: the MAC fixed in the spec, and the cost figures it invalidates.
mf = rec("mac_fix_w978.json")
if mf:
    print("\n== правка MAC (W978)")
    check("охранников добавлено в smul", len(mf["fix"]["smul_guards_added"]), 3, tol=0)
    check("охранников добавлено в sadd", len(mf["fix"]["sadd_guards_added"]), 2, tol=0)
    se = mf["side_effect"]
    check("LUT до", se["LUT"]["before"], 6466, tol=0)
    check("LUT после", se["LUT"]["after"], 5484, tol=0)
    check("LUT, изменение %", se["LUT"]["delta_pct"], -15.2, tol=0.05)
    check("CARRY4, изменение %", se["CARRY4"]["delta_pct"], -22.3, tol=0.05)
    check("Fmax, изменение %", se["fmax_mhz"]["delta_pct"], 7.8, tol=0.05)
    check("правка уменьшила дизайн", se["LUT"]["after"] < se["LUT"]["before"], True, tol=0)
    check("правка ускорила дизайн",
          se["fmax_mhz"]["after"] > se["fmax_mhz"]["before"], True, tol=0)
    check("тестов в спеке стало 4", mf["tests_added"]["after"].startswith("4"), True, tol=0)
    check("вердикт с кристалла НЕ получен",
          mf["verification"]["die"].startswith("NOT OBTAINED"), True, tol=0)
    # T821's MAC row was measured on the defective build
    if sw:
        check("T821 мерил дефектную сборку",
              sw["designs"]["gft_signed_mac"]["LUT"], se["LUT"]["before"], tol=0)

# W979: the corpus guard audit.
ga = rec("guard_audit_w979.json")
if ga:
    print("\n== аудит охранников по корпусу (W979)")
    a = ga["audit"]
    check("определений просмотрено", a["definitions_scanned"], 134, tol=0)
    check("спек в разовом аудите", a["specs"], 26, tol=0)
    check("найдено без охранников", a["unguarded_found"], 1, tol=0)
    check("это gft_signed_dot4 :: smul",
          a["unguarded"][0].endswith("gft_signed_dot4.t27 :: smul"), True, tol=0)
    check("аудит совпал с измерением W838", "W838" in a["note"], True, tol=0)
    check("охранников добавлено", len(ga["fix"]["guards_added"]), 2, tol=0)
    check("tri guards встроен в tri audit", ga["tool"]["wired_into"] == "tri audit", True, tol=0)
    check("расхождение счётчиков объяснено", len(ga["why_counts_differ"]) > 100, True, tol=0)

# W980: clause-vs-test coverage across the wrappers.
cv80 = rec("coverage_w980.json")
if cv80:
    print("\n== покрытие клауз тестами (W980)")
    t = cv80["totals"]
    check("обёрток", t["wrappers"], 9, tol=0)
    check("клауз всего", t["clauses"], 36, tol=0)
    check("без одноимённого теста", t["without_same_named_test"], 30, tol=0)
    check("доля, %", t["pct"], 83, tol=1)
    pw = cv80["per_wrapper"]
    check("mac: тестов стало 4", pw["gft_signed_mac_jtag.v"]["tests"], 4, tol=0)
    check("xorpercep: тестов всего 1", pw["gft_xorpercep_jtag.v"]["tests"], 1, tol=0)
    check("smul: comm не покрыт", "comm" in pw["gft_smul_jtag.v"]["uncovered"], True, tol=0)
    check("smul: ind не покрыт", "ind" in pw["gft_smul_jtag.v"]["uncovered"], True, tol=0)
    check("предел инструмента заявлен", "OVER-REPORTS" in cv80["limit"], True, tol=0)
    check("жёсткий сигнал назван", "1010" in cv80["hard_signal"], True, tol=0)

# W981: the representable set, and the expiry date of every live stimulus source.
dm = rec("domain_w981.json")
if dm:
    print("\n== область представимости и срок годности стимулов (W981)")
    rs = dm["representable_set"]
    check("потолок смещения", rs["offset_ceiling"], 80, tol=0)
    check("наибольшая магнитуда", rs["max_magnitude"], (80 << 9) | 511, tol=0)
    check("представимых слов", rs["representable_words"], 2 * 41472, tol=0)
    check("потолок прочитан, а не вписан",
          "read, not hardcoded" in rs["offset_ceiling_source"], True, tol=0)
    ip = dm["identity_is_partial"]
    check("слов всего", ip["words_total"], 131072, tol=0)
    check("представимых слов", ip["representable_words"], 82944, tol=0)
    check("на представимых тождество падает ровно раз", ip["representable_failing"], 1, tol=0)
    check("исключение -- отрицательный ноль", ip["the_one_exception"]["word"], 65536, tol=0)
    check("и оно нормализуется в +0", ip["the_one_exception"]["result"], 0, tol=0)
    check("непредставимых слов", ip["non_representable_words"], 48128, tol=0)
    check("вне области падает всё",
          ip["non_representable_failing"], ip["non_representable_words"], tol=0)
    check("разбиение полное",
          ip["representable_words"] + ip["non_representable_words"], ip["words_total"], tol=0)
    check("держится = всего - падает",
          ip["representable_holding"],
          ip["words_total"] - ip["non_representable_failing"] - ip["representable_failing"], tol=0)
    check("первый отказ вне области -- смещение 81",
          ip["first_out_of_range_failure"]["offset"], 81, tol=0)
    bm = ip["by_magnitude_unsigned"]
    check("по магнитудам: держится + падает", bm["holds"] + bm["fails"], bm["total"], tol=0)
    ct = dm["commutativity_is_total"]
    check("контрпримеров коммутативности", ct["counterexamples"], 0, tol=0)
    check("пар проверено", int(ct["method"].split()[0]), 2359296, tol=0)
    check("живых источников", dm["counts"]["sources"], 17, tol=0)
    check("все покидают область",
          dm["counts"]["leaving_the_set"], dm["counts"]["sources"], tol=0)
    check("не объясняет открытый отказ",
          dm["does_it_explain_the_open_failure"].startswith("NO"), True, tol=0)

# W981: nine die reads that refuted the site hypothesis and tested the clock.
pn = rec("pnr_w981.json")
if pn:
    print("\n== place-and-route: девять чтений с кристалла (W981)")
    check("чтений с кристалла", len(pn["die_reads"]), 9, tol=0)
    fails = [r for r in pn["die_reads"] if r["verdict"] == "FAIL"]
    passes = [r for r in pn["die_reads"] if r["verdict"] == "PASS"]
    check("отказов", len(fails), 3, tol=0)
    check("проходов", len(passes), 6, tol=0)
    check("все отказы -- зерно 7", {r["seed"] for r in fails} == {7}, True, tol=0)
    check("отказ на площадке BSCAN3 есть",
          any(r["site"] == 3 for r in fails), True, tol=0)
    check("проход на площадке BSCAN1 есть",
          any(r["site"] == 1 for r in passes), True, tol=0)
    check("проход на площадке BSCAN2 есть",
          any(r["site"] == 2 for r in passes), True, tol=0)
    # The clock test: same seed, same site, one octave apart, same answer.
    clk = [r for r in pn["die_reads"] if r["seed"] == 7 and r["site"] == 3]
    check("пара для теста частоты", len(clk), 2, tol=0)
    check("обе половины теста -- отказ",
          all(r["clauses"] == "1101" for r in clk), True, tol=0)
    # Reported Fmax must interleave, or it would carry signal about the verdict.
    fmin, fmax_ = min(r["fmax"] for r in fails), max(r["fmax"] for r in fails)
    check("Fmax отказов лежит внутри диапазона проходов",
          any(r["fmax"] < fmin for r in passes) and any(r["fmax"] > fmax_ for r in passes),
          True, tol=0)
    fd = pn["fasm_diff_is_not_decisive"]["measured"]
    check("логических LUT, зерно 42 (проход)", fd["seed42_PASS"]["logic_luts"], 1164, tol=0)
    check("логических LUT, зерно 1 (проход)", fd["seed1_PASS"]["logic_luts"], 1165, tol=0)
    check("два прохода различаются по логическим LUT",
          fd["seed42_PASS"]["logic_luts"] != fd["seed1_PASS"]["logic_luts"], True, tol=0)
    check("предел метода назван",
          "not a function-preservation invariant" in pn["fasm_diff_is_not_decisive"]["why_it_fails"],
          True, tol=0)
    check("воспроизведено на другом стенде",
          "reproduced exactly" in pn["reproduction_of_w977"]["verdict"], True, tol=0)
    sh = pn["self_heal"]
    check("самовосстановлений", len(sh), 3, tol=0)
    check("аудит убивала собственная новая строка",
          sh["tri_audit_was_dying_at_its_own_new_line"]["introduced"] == "W980", True, tol=0)
    check("оракулы теперь в репозитории",
          "conformance/oracles/" in sh["oracles_were_only_in_a_scratchpad"]["fix"], True, tol=0)
    check("починка проверена на доремонтном корпусе",
          "exit 1" in sh["xorpercep_lfsr"]["validated"], True, tol=0)
    check("зелёных строк аудита", len(pn["audit_after"]["rows_green"]), 9, tol=0)
    check("красных строк аудита", len(pn["audit_after"]["rows_red"]), 1, tol=0)

# W982: the minimal reproducer, the SAT proof, and the third method that failed.
mt = rec("miter_w982.json")
if mt:
    print("\n== минимальный воспроизводитель и доказательство (W982)")
    mr = mt["minimal_reproducer"]
    check("чтений с кристалла", len(mr["die_reads"]), 4, tol=0)
    P = [r for r in mr["die_reads"] if r["verdict"] == "PASS"]
    F = [r for r in mr["die_reads"] if r["verdict"] == "FAIL"]
    check("проходов", len(P), 2, tol=0)
    check("отказов", len(F), 2, tol=0)
    check("все проходы -- один нетлист", len({r["LUT"] for r in P}), 1, tol=0)
    check("все отказы -- другой нетлист", len({r["LUT"] for r in F}), 1, tol=0)
    check("нетлисты различны", P[0]["LUT"] != F[0]["LUT"], True, tol=0)
    check("проходящий нетлист, LUT", P[0]["LUT"], 430, tol=0)
    check("отказывающий нетлист, LUT", F[0]["LUT"], 452, tol=0)
    check("сокращение от 798 LUT, %", 100 * (1 - F[0]["LUT"] / 798), 43.4, tol=0.2)
    check("зерно не предсказывает",
          {r["seed"] for r in P} != {1, 42}, True, tol=0)
    sp = mt["sat_proof_on_the_mapped_netlist"]
    check("smul: ячеек после отображения", sp["gft_smul"]["cells_after_mapping"], 277, tol=0)
    check("smul: переменных SAT", sp["gft_smul"]["sat_variables"], 1822, tol=0)
    check("sadd: переменных SAT", sp["gft_sadd"]["sat_variables"], 48200, tol=0)
    check("оба доказаны",
          sp["gft_smul"]["result"].startswith("proved") and
          sp["gft_sadd"]["result"].startswith("proved"), True, tol=0)
    check("фронтенд оправдан", "exonerated" in sp["consequence"], True, tol=0)
    tm = mt["third_method_that_failed_its_control"]
    ctrl = tm["result"]["42_vs_1_PASS_PASS"]
    tests = [tm["result"][k] for k in tm["result"] if "PASS_FAIL" in k]
    check("контрольная пара расходится", ctrl, 591, tol=0)
    check("контроль не меньше тестов", min(tests) <= ctrl <= max(tests) or ctrl > min(tests),
          True, tol=0)
    check("метод признан неубедительным",
          tm["verdict"].startswith("INCONCLUSIVE"), True, tol=0)

print(f"\n  ИТОГ: сошлось {ok}, расхождений {bad}, пропущено блоков {skip}")
sys.exit(1 if bad else 0)
