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

# W994: the reference decoder, for the checks that count TNF words directly.
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, os.environ.get("T27_CONFORMANCE") or str(HERE / "oracles"))
import tnf_ref as _T  # noqa: E402
from fractions import Fraction  # noqa: E402
import math  # noqa: E402


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
    # tol=0 means exact. The relative allowance used to apply to it too, and so
    # passed 8192 against a quoted 8190 (see W993 below).
    if d <= tol or (tol > 0 and rel <= 0.005):
        print(f"  ok  {label}: {got:.2f} (цитируется {want:.2f})")
        ok += 1
    else:
        print(f"  РАСХОЖДЕНИЕ  {label}: пересчитано {got:.4f}, цитируется {want}")
        bad += 1


def field(d, key, label):
    """Read a cited field, or report its absence as a divergence.

    A record that does not carry a field the paper cites is not a crash and not
    a pass. Crashing is worse than it looks: this script died on the first
    missing key, so every check below it -- including the whole W991 competitor
    block -- never ran at all, and a partial verification exited looking like a
    finished one. Returning None instead would route the value into check()'s
    "не вычислено" branch, which increments neither counter and leaves the exit
    code at zero, so a missing measurement would read exactly like a satisfied
    one. Count it against the run.
    """
    global bad
    if not isinstance(d, dict) or key not in d:
        print(f"  РАСХОЖДЕНИЕ  {label}: запись не содержит поля {key!r}")
        bad += 1
        return None
    return d[key]


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
    # W994: of the 2^19 codes W942 compared, only the trit words are TNF16. The
    # count is taken from the reference decoder's own field test (W994 block below).
    check("TNF16 codes checked that are TNF words (W994)",
          sum(1 for _c in range(1 << 19) if _T.is_word(_T.TNFFormat(4, 11), _c)), 331776, tol=0)
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
#
# W994: the TNF4 rows of the eight 2026-08-20 records were trained on a grid that
# decoded codes whose exponent field lies above offset_max -- 57 values up to 3072,
# where TNF4's words are 29 values up to 12. Those rows are not TNF4 and are not
# counted. TNF4 is counted only from records marked "tnf_grid": "trit-words" (the
# W994 reruns, MNIST only: Fashion and KMNIST were not rerun). The fp6 rows do not
# involve a TNF grid and are counted as before.
print("\n== устойчивость: пересчёт по всем записям")
_TH = {"mnist": 60.0, "fashion": 60.0, "kmnist": 40.0}
_tot, _cfgs, _withdrawn, _mn = {}, {}, 0, {}
_trit = {}          # W994 TNF4 records: name -> list of per-seed traces
for _f in sorted(R.glob("stability*.json")):
    _d = json.loads(_f.read_text())
    if "runs" not in _d:
        continue
    _th = _TH[_d.get("task", "mnist")]
    for _fmt, _runs in _d["runs"].items():
        if _fmt == "TNF4" and _d.get("tnf_grid") != "trit-words":
            _withdrawn += len(_runs)
            continue
        if _fmt == "TNF4":
            _trit[_f.name] = list(_runs.values())
        _cfgs[_fmt] = _cfgs.get(_fmt, 0) + 1
        _acc = [_r[-1]["acc"] * 100 for _r in _runs.values()]
        _t = _tot.setdefault(_fmt, [0, 0])
        _t[0] += sum(1 for _a in _acc if _a >= _th)
        _t[1] += len(_acc)
        if _d.get("task", "mnist") == "mnist":
            _m = _mn.setdefault(_fmt, [0, 0])
            _m[0] += sum(1 for _a in _acc if _a >= _th)
            _m[1] += len(_acc)
if _tot:
    check("fp6 stability configurations", _cfgs.get("fp6e3m2", 0), 8, tol=0)
    check("TNF4 stability configurations on TNF words (W994, MNIST)", _cfgs.get("TNF4", 0), 5, tol=0)
    check("TNF4 runs withdrawn (every-code grid, not counted)", _withdrawn, 40, tol=0)
    for _fmt, _want, _n in (("TNF4", 8, 25), ("fp6e3m2", 16, 40), ("fp6e2m3", 12, 40)):
        _s, _nn = _tot.get(_fmt, (None, None))
        check(f"{_fmt}: runs", _nn, _n, tol=0)
        check(f"{_fmt}: successes", _s, _want, tol=0)
    # the same five MNIST recipes, fp6 against TNF4 (the paper's 8 / 12 / 5 of 25)
    for _fmt, _want in (("fp6e3m2", 12), ("fp6e2m3", 5)):
        check(f"{_fmt}: MNIST successes of 25", _mn[_fmt][0], _want, tol=0)
        check(f"{_fmt}: MNIST runs", _mn[_fmt][1], 25, tol=0)
    for _name, _want in (("stability_w994_mnist_nogs_3ep.json", 4),
                         ("stability_w994_mnist_gs_3ep.json", 4),
                         ("stability_w994_mnist_gs_10ep.json", 0),
                         ("stability_w994_mnist_gs_30ep.json", 0),
                         ("stability_w994_mnist_pct0.999_3ep.json", 0)):
        _r = _trit.get(_name)
        check(f"TNF4 {_name}: successes of 5",
              None if _r is None else sum(1 for t in _r if t[-1]["acc"] * 100 >= 60.0), _want, tol=0)
    # The runs that fail at ten and thirty epochs train first and collapse later;
    # under percentile initialisation no run ever trains.
    _late = [t for n in ("stability_w994_mnist_gs_10ep.json", "stability_w994_mnist_gs_30ep.json")
             for t in _trit.get(n, [])]
    if _late:
        _pk = [max(e["acc"] for e in t) * 100 for t in _late]
        _pe = [max(t, key=lambda e: e["acc"])["epoch"] for t in _late]
        check("TNF4 10/30 ep: lowest peak accuracy, %", min(_pk), 94.85, tol=0.005)
        check("TNF4 10/30 ep: highest peak accuracy, %", max(_pk), 97.10, tol=0.005)
        check("TNF4 10/30 ep: earliest peak epoch", min(_pe), 2, tol=0)
        check("TNF4 10/30 ep: latest peak epoch", max(_pe), 6, tol=0)
    _pct = _trit.get("stability_w994_mnist_pct0.999_3ep.json")
    if _pct:
        check("TNF4 percentile init: best accuracy in any epoch, %",
              max(e["acc"] for t in _pct for e in t) * 100, 32.80, tol=0.005)

# W994: ablations of the TNF4 result. Not recipes of the tally, so kept out of the
# stability* glob above.
_abl = {}
for _f in sorted(R.glob("lsq_ablation_w994_*.json")):
    _d = json.loads(_f.read_text())
    _abl[_f.name[len("lsq_ablation_w994_"):-len(".json")]] = [
        t[-1]["acc"] * 100 for t in _d["runs"]["TNF4"].values()]
if _abl:
    print("\n== TNF4 stability ablations (W994)")
    for _k, _want in (("qp3072_3ep", 5), ("qp3072_10ep", 0), ("everycode_qp12_10ep", 5),
                      ("nogs_10ep", 0), ("pct0.999_nogs_3ep", 0)):
        check(f"{_k}: successes of 5",
              sum(1 for a in _abl[_k] if a >= 60.0) if _k in _abl else None, _want, tol=0)

# W949: the scaling convention is itself a recipe axis, and it is the one that
# decides fp6 e3m2. Derived here rather than quoted, per T797.
# W994: the TNF4 rows of scaleconv_w949.json used the every-code grid (maximum
# 3072) and are not read. TNF4 comes from scaleconv_w994_3ep.json, on its words.
sc = rec("scaleconv_w949.json"); sc4 = rec("scaleconv_w994_3ep.json")
if sc:
    print("\n== конвенция масштаба (W949; TNF4 from W994)")
    for conv, want in (("peak2one", {"fp6e2m3": 4, "fp6e3m2": 0}),
                       ("peak2max", {"fp6e2m3": 5, "fp6e3m2": 5})):
        for fmt, w in want.items():
            a = sc["runs"][conv][fmt]
            check(f"{conv} {fmt}: отказов из {len(a)}", sum(1 for v in a if v < 60.0), w, tol=0)
if sc4:
    check("W994 scaleconv record is on TNF words", sc4.get("tnf_grid") == "trit-words", True, tol=0)
    check("TNF4 grid maximum", sc4["grid_max"]["TNF4"], 12.0, tol=0)
    for conv, w in (("peak2one", 1), ("peak2max", 5)):
        a = sc4["runs"][conv]["TNF4"]
        check(f"{conv} TNF4: failures of {len(a)}", sum(1 for v in a if v < 60.0), w, tol=0)
    check("peak2one TNF4: mean accuracy", sum(sc4["runs"]["peak2one"]["TNF4"]) / 5, 78.28, tol=0.005)
    _g3 = rec("stability_w994_mnist_gs_3ep.json")
    if _g3:
        check("peak2one TNF4 reproduces the W994 gradscale stability runs",
              [round(t[-1]["acc"] * 100, 2) for t in _g3["runs"]["TNF4"].values()]
              == sc4["runs"]["peak2one"]["TNF4"], True, tol=0)

# W994: rerun on TNF4's words (blockscale_w994.json); W949's TNF4 rows used the
# every-code grid. The fp6 rows are bit-identical in both records.
bs = rec("blockscale_w994.json"); bs49 = rec("blockscale_w949.json")
if bs:
    print("\n== блочный масштаб (W949, rerun on TNF words as W994)")
    check("W994 blockscale record is on TNF words", bs.get("tnf_grid") == "trit-words", True, tol=0)
    check("TNF4 grid size (zero included)", bs["grid_size"]["TNF4"], 29, tol=0)
    check("TNF4 binades", bs["binades"]["TNF4"], 6.58, tol=0)
    b32 = bs["res"]["acts_heavy"]["32"]
    check("блок 32, тяж.хвост: TNF4 обнуляет, %", b32["TNF4"]["underflow"] * 100, 1.57, tol=0.005)
    check("блок 32, тяж.хвост: e2m3 обнуляет, %", b32["fp6e2m3"]["underflow"] * 100, 2.51, tol=0.02)
    check("блок 32: RMS TNF4 / RMS e2m3",
          b32["TNF4"]["rel_rmse"] / b32["fp6e2m3"]["rel_rmse"], 3.463, tol=0.001)
    bt = bs["res"]["acts_heavy"][str(bs["n"])]
    check("на весь тензор: e2m3 обнуляет, %", bt["fp6e2m3"]["underflow"] * 100, 44.41, tol=0.05)
    check("per tensor, heavy tail: TNF4 underflow, %", bt["TNF4"]["underflow"] * 100, 29.42, tol=0.005)
    if bs49:
        check("fp6 rows identical to W949",
              all(bs["res"][d][b][f] == bs49["res"][d][b][f] for d in bs["res"]
                  for b in bs["res"][d] for f in ("fp6e2m3", "fp6e3m2")), True, tol=0)

# W950: the surviving claim, tested against the recipe the field actually uses.
# W994: rerun on TNF4's words (blockquant_w994_3ep.json). The fp6 arms are
# bit-identical to W950's; only the TNF4 arms moved.
bq = rec("blockquant_w994_3ep.json"); bq50 = rec("blockquant_w950.json")
if bq:
    print("\n== вычисляемый масштаб MX (W950, rerun on TNF words as W994)")
    check("W994 blockquant record is on TNF words", bq.get("tnf_grid") == "trit-words", True, tol=0)
    for arm in ("block32", "per_tensor"):
        for fmt in ("TNF4", "fp6e2m3", "fp6e3m2"):
            a = bq["runs"][arm][fmt]
            check(f"{arm} {fmt}: отказов из {len(a)}", sum(1 for v in a if v < 60.0), 0, tol=0)
            if bq50 and fmt != "TNF4":
                check(f"{arm} {fmt}: identical to W950", a == bq50["runs"][arm][fmt], True, tol=0)
    import numpy as _np
    for arm, opp, want, wt in (("per_tensor", "fp6e2m3", -0.324, -7.34),
                               ("per_tensor", "fp6e3m2", -0.198, -7.86),
                               ("block32", "fp6e2m3", 0.028, 0.24)):
        t = _np.array(bq["runs"][arm]["TNF4"]); f = _np.array(bq["runs"][arm][opp])
        dd = t - f
        check(f"{arm} TNF4−{opp}, п.п.", float(dd.mean()), want, tol=0.002)
        check(f"{arm} TNF4−{opp}, t", float(dd.mean() / (dd.std(ddof=1) / _np.sqrt(len(dd)))), wt, tol=0.02)

# W994: mechanism_w950.json counted the 40 every-code TNF4 runs. mechanism.py now
# reads TNF4 only from records on TNF words and writes mechanism_w994.json.
mw = rec("mechanism_w994.json")
if mw:
    print("\n== механизм: насыщение против отказа (W950, TNF4 on TNF words as W994)")
    c = mw["confusion"]; tot = sum(c.values())
    check("прогонов в трассах", tot, 105, tol=0)
    for _k, _w in (("tp", 65), ("fp", 7), ("fn", 4), ("tn", 29)):
        check(f"confusion {_k}", c[_k], _w, tol=0)
    check("согласие насыщение<=>отказ, %", (c["tp"] + c["tn"]) / tot * 100, 89.52, tol=0.01)
    _r4 = [r for r in mw["rows"] if r["fmt"] == "TNF4"]
    check("TNF4 rows (MNIST, on TNF words)", len(_r4), 25, tol=0)
    check("TNF4 failures", sum(1 for r in _r4 if r["failed"]), 17, tol=0)
    check("TNF4 failures that saturate the grid maximum 12",
          sum(1 for r in _r4 if r["failed"] and r["saturates"]), 17, tol=0)
    check("TNF4 successes that saturate", sum(1 for r in _r4 if not r["failed"] and r["saturates"]), 0, tol=0)
    check("TNF4 headroom in the record is 12", {r["headroom"] for r in _r4} == {12.0}, True, tol=0)

# W951: the sweep redone under the computed scale, on all three tasks, and
# saturation OBSERVED rather than inferred. All derived, per T797.
# W994: the TNF4 rows of the W951 sweeps used the every-code grid. The rows are now
# derived from the sweep records themselves: fp6 from sweep_w951_*.json, TNF4 only
# from records marked "tnf_grid": "trit-words" (sweep_w994_mnist_*.json; Fashion and
# KMNIST were not rerun). saturation_w951.json is kept, and checked to be exactly
# what the same derivation gives on the W951 records with every row counted.
def _sweep_rows(files, words_only):
    out = []
    for _f in files:
        _d = json.loads(_f.read_text())
        for _fmt, _runs in _d["runs"].items():
            if words_only and _fmt == "TNF4" and _d.get("tnf_grid") != "trit-words":
                continue
            for _tr in _runs.values():
                out.append({"task": _d["task"], "mode": _d["mode"], "blk": _d["block"], "fmt": _fmt,
                            "acc": _tr[-1]["acc"], "failed": _tr[-1]["acc"] < _d["threshold"],
                            "sat": max(max(_e["sat"].values()) for _e in _tr)})
    return out


sat51 = rec("saturation_w951.json")
if sat51:
    _key = lambda r: (r["task"], r["mode"], r["blk"], r["fmt"], round(r["acc"], 2),
                      round(r["sat"], 1), r["failed"])
    check("saturation_w951.json = derivation from the W951 sweeps, all rows",
          sorted(map(_key, _sweep_rows(sorted(R.glob("sweep_w951_*.json")), False)))
          == sorted(map(_key, sat51)), True, tol=0)
sat = _sweep_rows(sorted(R.glob("sweep_w951_*.json")), True) + \
    _sweep_rows(sorted(R.glob("sweep_w994_*.json")), True)
if sat:
    print("\n== свод и наблюдённое насыщение (W951; TNF4 on TNF words, MNIST, W994)")
    check("прогонов в своде", len(sat), 105, tol=0)
    check("TNF4 rows (MNIST only)", sum(1 for r in sat if r["fmt"] == "TNF4"), 15, tol=0)
    comp = [r for r in sat if r["mode"] == "computed"]
    lrn = [r for r in sat if r["mode"] == "learned"]
    check("вычисляемый масштаб: прогонов", len(comp), 70, tol=0)
    check("вычисляемый масштаб: отказов", sum(1 for r in comp if r["failed"]), 0, tol=0)
    check("обучаемый масштаб: прогонов", len(lrn), 35, tol=0)
    check("обучаемый масштаб: отказов", sum(1 for r in lrn if r["failed"]), 10, tol=0)
    check("TNF4 отказов во всём своде",
          sum(1 for r in sat if r["fmt"] == "TNF4" and r["failed"]), 1, tol=0)
    ok_s = [r["sat"] for r in lrn if not r["failed"]]
    bad_s = [r["sat"] for r in lrn if r["failed"]]
    check("худший перелёт среди успехов", max(ok_s), 1509.7, tol=0.5)
    check("лучший перелёт среди отказов", min(bad_s), 54788.4, tol=0.5)
    check("разделяются ли распределения", max(ok_s) < min(bad_s), True, tol=0)
    check("вычисляемый масштаб: максимум перелёта",
          max(r["sat"] for r in comp), 2.0, tol=0.001)

# W952: what the dynamic range costs in silicon. Two numbers, deliberately: one
# implementation-specific (fixed-point MAC lane), one forced by arithmetic (the
# block-32 accumulator width). Quoting only the first would be the same error as
# quoting a decoder-only census.
# W994: the TNF4 lane of W952 was sized for the every-code maximum 3072 (17-bit
# values); on TNF4's words the maximum is 12 and the value is 9 bits. Rerun as
# mac_w994.json / acc_w994.json; the fp6 lanes are bit-identical. widths_w952.json
# carries only the every-code TNF4 widths and is not read.
mac = rec("mac_w994.json"); acc = rec("acc_w994.json")
mac52 = rec("mac_w952.json"); acc52 = rec("acc_w952.json")
if mac:
    print("\n== ширины, вынужденные диапазоном (W952, TNF4 on TNF words as W994)")
    for f, w, wp, a in (("TNF4", 9, 17, 22), ("fp6e3m2", 10, 19, 24), ("fp6e2m3", 7, 13, 18)):
        check(f"{f}: бит на значение", mac["widths"][f]["value"], w, tol=0)
        check(f"{f}: бит на произведение", mac["widths"][f]["product"], wp, tol=0)
        check(f"{f}: accumulator bits, block 32", mac["widths"][f]["acc32"], a, tol=0)
    print("\n== полоса MAC в фиксированной точке (W952, TNF4 on TNF words as W994)")
    for f, want in (("TNF4", 213.0), ("fp6e3m2", 308.0), ("fp6e2m3", 159.0)):
        check(f"{f}: ячеек на полосу", mac["cost"][f]["per_lane"], want, tol=0.01)
        check(f"{f}: R2 линейности", mac["cost"][f]["r2"], 1.0, tol=0.0001)
        if mac52 and f != "TNF4":
            check(f"{f}: identical to W952", mac["cost"][f]["points"] == mac52["cost"][f]["points"], True, tol=0)
    check("TNF4 / fp6e2m3, полоса",
          mac["cost"]["TNF4"]["per_lane"] / mac["cost"]["fp6e2m3"]["per_lane"], 1.34, tol=0.005)
    check("TNF4 / fp6e3m2, lane",
          mac["cost"]["TNF4"]["per_lane"] / mac["cost"]["fp6e3m2"]["per_lane"], 0.69, tol=0.005)
if acc:
    print("\n== аккумулятор блока-32, неизбежная часть (W952, TNF4 on TNF words as W994)")
    for f, want in (("TNF4", 28.0), ("fp6e3m2", 30.0), ("fp6e2m3", 23.0)):
        check(f"{f}: ячеек на аккумулятор", acc["cost"][f]["per_acc"], want, tol=0.01)
        if acc52 and f != "TNF4":
            check(f"{f}: identical to W952", acc["cost"][f]["points"] == acc52["cost"][f]["points"], True, tol=0)
    check("TNF4 / fp6e2m3, аккумулятор",
          acc["cost"]["TNF4"]["per_acc"] / acc["cost"]["fp6e2m3"]["per_acc"], 1.217, tol=0.001)
    check("надбавка на элемент, аморт. по 32",
          (acc["cost"]["TNF4"]["per_acc"] - acc["cost"]["fp6e2m3"]["per_acc"]) / 32, 0.156, tol=0.001)

# W953: the third datapath, which closes the W952 bracket.
# W994: the TNF4 float-style lane (108 cells, odd 2 / shift 15) was built on the
# every-code grid; on TNF4's words the pair is (2, 7). The float-lane rigs do not
# synthesise under the yosys installed on 2026-09-27 (multiple drivers), so the
# TNF4 cell count is not recomputed and is not checked. The fp6 rows stand.
fl = rec("flane_w953.json")
if fl:
    print("\n== полоса MAC во флоатном стиле (W953; TNF4 withdrawn, W994)")
    for f, want in (("fp6e3m2", 82.0), ("fp6e2m3", 74.0)):
        check(f"{f}: ячеек на флоат-полосу", fl["cost"][f]["per_lane"], want, tol=0.01)
        check(f"{f}: R2 линейности", fl["cost"][f]["r2"], 1.0, tol=0.0001)
    check("нечётная мантисса fp6e2m3, бит", fl["fields"]["fp6e2m3"]["odd_bits"], 4, tol=0)
    if mac:
        check("флоат дешевле фикс.точки для fp6e2m3",
              mac["cost"]["fp6e2m3"]["per_lane"] > fl["cost"]["fp6e2m3"]["per_lane"], True, tol=0)


def _odd_shift(values):
    """(odd-mantissa bits, max shift) of a value set, as rung16.stats defines them."""
    nz = [abs(Fraction(v)) for v in values if v != 0]
    fb = max(f.denominator.bit_length() - 1 for f in nz)
    ob = smax = 0
    for f in nz:
        m = f.numerator << (fb - (f.denominator.bit_length() - 1))
        sh = (m & -m).bit_length() - 1
        ob, smax = max(ob, (m >> sh).bit_length()), max(smax, sh)
    return ob, smax


def _tnf_words(et, mb):
    f = _T.TNFFormat(et, mb)
    out = set()
    for c in range(1 << (f.sign_shift + 1)):
        if _T.is_word(f, c):
            v = _T.decode(f, c)
            if isinstance(v, Fraction):
                out.add(v)
    return out


# W954: cost tracks RANGE, not the lattice. Range-matched peers, both widths.
# W994: the TNF rows (TNF4 108, TNF8 380) and their ratios were built on the
# every-code grids and are withdrawn; the float rows stand.
rm_ = rec("rangematch_w954.json"); ld = rec("ladder_w954.json")
if rm_:
    print("\n== согласование по диапазону, 6 бит (W954; TNF4 withdrawn, W994)")
    for f, want in (("fp6e4m1", 106.0), ("fp6e3m2", 82.0), ("fp6e2m3", 74.0)):
        check(f"{f}: ячеек на полосу", rm_["cost"][f]["per_lane"], want, tol=0.01)
if ld:
    print("\n== ступень 10 бит (W954; TNF8 withdrawn, W994)")
    check("fp10_e5m4: ячеек на полосу", ld["cost"]["fp10_e5m4"]["per_lane"], 376.0, tol=0.01)
    check("fp10_e6m3 дороже fp10_e5m4 (шире диапазон)",
          ld["cost"]["fp10_e6m3"]["per_lane"] > ld["cost"]["fp10_e5m4"]["per_lane"], True, tol=0)

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
    # W994: the "same (odd, shift) pair, same cost" pairing of TNF4 with fp6 e4m1 and
    # of TNF8 with fp10 e5m4 held only on the every-code grids. On the words the
    # pairs differ, so the pairing is withdrawn; the pairs are computed here.
    for (et, mb), peer, want_t, want_f in (((2, 1), "fp6_e4m1", (2, 7), (2, 15)),
                                           ((3, 4), "fp10_e5m4", (5, 28), (5, 34))):
        _p = _odd_shift(_tnf_words(et, mb))
        _q = (cv["fields"][peer]["odd_bits"], cv["fields"][peer]["max_shift"])
        check(f"TNF({et},{mb}) words: odd bits", _p[0], want_t[0], tol=0)
        check(f"TNF({et},{mb}) words: max shift", _p[1], want_t[1], tol=0)
        check(f"{peer}: max shift", _q[1], want_f[1], tol=0)
        check(f"TNF({et},{mb}) / {peer}: (odd, shift) pair differs", _p != _q, True, tol=0)
    # перекрёстная сверка между волнами
    for k6, kc in (("fp6e4m1", "fp6_e4m1"), ("fp6e2m3", "fp6_e2m3"), ("fp6e3m2", "fp6_e3m2")):
        if rm_ and k6 in rm_["cost"]:
            check(f"{kc}: W954 против W955",
                  rm_["cost"][k6]["per_lane"] - cv["cost"][kc]["per_lane"], 0.0, tol=0.001)

# W963: the census redone on the ladder's TRUE eighth rung, in the original metric.
# W994: the TNF decoders of census_tnf8_w963.json were built on the every-code
# grid. Rerun as census_tnf8_w994.json; the float rows are unchanged.
cs = rec("census_tnf8_w994.json"); cs63 = rec("census_tnf8_w963.json")
if cs:
    print("\n== перепись на настоящей ступени (W963, TNF on TNF words as W994)")
    for k, dec, con in (("tnf8_ladder_10b", 11.0, 211.57), ("fp10_e5m4", 14.0, 214.57),
                        ("tnf8_as_measured_11b", 27.0, 268.57), ("fp11_e6m4", 16.0, 257.57)):
        check(f"{k}: декодер", cs[k]["decoder_cells"], dec, tol=0.01)
        check(f"{k}: потребитель", cs[k]["consumer_cells"], con, tol=0.01)
        if cs63 and k.startswith("fp"):
            check(f"{k}: identical to W963", cs[k] == cs63[k], True, tol=0)
    t, f = cs["tnf8_ladder_10b"]["consumer_cells"], cs["fp10_e5m4"]["consumer_cells"]
    check("настоящая ступень против своего float, %", (t - f) / f * 100, -1.40, tol=0.005)
    ts, fs = cs["tnf8_as_measured_11b"]["consumer_cells"], cs["fp11_e6m4"]["consumer_cells"]
    check("подстановка против своего float, %", (ts - fs) / fs * 100, 4.27, tol=0.005)
    check("знак результата инвертируется подстановкой",
          ((t - f) < 0) and ((ts - fs) > 0), True, tol=0)
    check("декодер: подстановка дороже во сколько раз",
          cs["tnf8_as_measured_11b"]["decoder_cells"] / cs["tnf8_ladder_10b"]["decoder_cells"],
          2.4545, tol=0.0001)

# W964: accuracy at the ladder's TRUE eighth rung, three recipes.
# W994: rerun on TNF8's words (rung_w994_*.json). With the computed per-tensor scale
# TNF8 and fp10 e5m4 give the same accuracy on every seed, so the difference is 0
# and t is undefined; that case is checked as "all five differences are zero".
# The learned-scale arm is LSQ training, which does not reproduce bit-exactly on
# this torch build; its pass counts do.
_rung = {}
for _f in sorted(R.glob("rung_w994_*.json")):
    _d = json.loads(_f.read_text())
    _rung[f"{_d['mode']}_b{_d['block']}"] = _d
if _rung:
    print("\n== точность настоящей восьмой ступени (W964, on TNF words as W994)")
    check("конфигураций", len(_rung), 3, tol=0)
    check("every rung record is on TNF words",
          all(_d.get("tnf_grid") == "trit-words" for _d in _rung.values()), True, tol=0)
    _tot = 0
    for _k, _d in _rung.items():
        for _fmt, _per in _d["runs"].items():
            _a = [t[-1]["acc"] for t in _per.values()]
            _tot += len(_a)
            check(f"{_k} {_fmt}: отказов", sum(1 for x in _a if x < 60.0), 0, tol=0)
    check("прогонов всего", _tot, 45, tol=0)
    for _k, _want, _t in (("computed_b0", 0.0, None), ("computed_b32", 0.0, 0.0),
                          ("learned_b0", 0.038, 0.74)):
        _d = _rung[_k]
        _t1 = np.array([t[-1]["acc"] for t in _d["runs"]["TNF8_true_10b"].values()])
        _f1 = np.array([t[-1]["acc"] for t in _d["runs"]["fp10_e5m4"].values()])
        _dd = _t1 - _f1
        check(f"{_k}: TNF8−fp10, п.п.", float(_dd.mean()), _want, tol=0.0005)
        _sd = _dd.std(ddof=1)
        if _t is None:
            check(f"{_k}: all five differences are zero", bool(np.all(_dd == 0)), True, tol=0)
        else:
            check(f"{_k}: t", float(_dd.mean() / (_sd / np.sqrt(len(_dd)))), _t, tol=0.005)

# W965: rung 16, both ladder versions, against width- and range-matched peers.
# W994: the TNF16 rows of rung16_w965.json enumerated every code (129,025 and
# 516,097 values, 127 binades). On the words, rung16_w994.json: 80,897 and 323,585
# values (zero included), 79 binades, and the (odd, shift) pairs (10, 87) and
# (12, 89) no longer equal those of the range-matched floats, (10, 135) and
# (12, 137). The float rows are unchanged.
r16 = rec("rung16_w994.json"); r65 = rec("rung16_w965.json")
if r16:
    print("\n== ступень 16, структурные параметры (W965, TNF on TNF words as W994)")
    for k, w, vals, bina, ob, sm in (
            ("TNF16_v1research_17b", 17, 80897, 79.0, 10, 87),
            ("TNF16_v2spec_19b", 19, 323585, 79.0, 12, 89),
            ("fp17_e7m9", 17, 131071, 136.0, 10, 135),
            ("fp19_e7m11", 19, 524287, 138.0, 12, 137),
            ("fp17_e6m10", 17, 131071, 73.0, 11, 72),
            ("fp19_e6m12", 19, 524287, 75.0, 13, 74)):
        check(f"{k}: ширина", r16[k]["width"], w, tol=0)
        check(f"{k}: значений", r16[k]["values"], vals, tol=0)
        check(f"{k}: бинад", r16[k]["binades"], bina, tol=0.01)
        check(f"{k}: нечёт", r16[k]["odd_bits"], ob, tol=0)
        check(f"{k}: сдвиг", r16[k]["max_shift"], sm, tol=0)
        if r65 and k.startswith("fp"):
            check(f"{k}: identical to W965", r16[k] == r65[k], True, tol=0)
    for t, f in (("TNF16_v1research_17b", "fp17_e7m9"), ("TNF16_v2spec_19b", "fp19_e7m11")):
        check(f"{t}/{f}: (odd, shift) pair differs",
              (r16[t]["odd_bits"], r16[t]["max_shift"]) != (r16[f]["odd_bits"], r16[f]["max_shift"]),
              True, tol=0)
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

# W983: half the on-die clauses were constants, and the repaired control fails.
cl = rec("clauses_w983.json")
if cl:
    print("\n== свёрнутые клаузы и первое честное чтение (W983)")
    t = cl["census_of_todays_sources"]["totals"]
    check("обёрток в переписи", t["wrappers"], 7, tol=0)
    check("клауз всего", t["clauses"], 28, tol=0)
    check("свёрнуто в константу", t["folded"], 14, tol=0)
    check("ровно половина", t["folded"] * 2, t["clauses"], tol=0)
    check("свёрнуто + реально = всего", t["folded"] + t["real"], t["clauses"], tol=0)
    cen = cl["census_of_todays_sources"]
    check("dot4 не свёрнут ни разу", cen["gft_signed_dot4_jtag.v"]["folded"], 0, tol=0)
    check("smul: свёрнуто 2", cen["gft_smul_jtag.v"]["folded"], 2, tol=0)
    check("sadd: свёрнуто 3", cen["gft_sadd_jtag.v"]["folded"], 3, tol=0)
    check("сумма по обёрткам = итог",
          sum(v["folded"] for k, v in cen.items() if k.endswith(".v")), t["folded"], tol=0)
    rp = cl["the_repair"]
    check("keep оказался недостаточен", "INSUFFICIENT" in rp["attempted_first"], True, tol=0)
    check("после починки свёрнутых нет", "0 folded" in rp["verified"], True, tol=0)
    fh = cl["first_honest_four_clause_reads"]
    check("честных чтений", len(fh["reads"]), 3, tol=0)
    check("нетлист один на все сборки", len({r["seed"] for r in fh["reads"]}), 3, tol=0)
    check("контроль падает", sum(1 for r in fh["reads"] if r["c_self"] == 0), 2, tol=0)
    seed7 = [r for r in fh["reads"] if r["seed"] == 7][0]
    check("на зерне 7 контроль ложен", seed7["c_self"], 0, tol=0)
    check("а коммутативность истинна", seed7["c_comm"], 1, tol=0)
    check("вывод: дело не в порядке операндов",
          "not about operand order" in cl["first_honest_four_clause_reads"]["consequence"],
          True, tol=0)

# W984: the folded-clause class closed, and two designs re-read with real clauses.
uf = rec("unfold_w984.json")
if uf:
    print("\n== свёртка снята по корпусу (W984)")
    t = uf["totals"]
    check("обёрток починено", t["wrappers_repaired"], 8, tol=0)
    check("свёрнуто было", t["folded_before"], 14, tol=0)
    check("свёрнуто стало", t["folded_after"], 0, tol=0)
    check("клауз теперь настоящих", t["clauses_now_real"], 36, tol=0)
    check("ни одна обёртка не свёрнута",
          sum(uf["after"].values()), 0, tol=0)
    check("обёрток в списке после", len(uf["after"]), 9, tol=0)
    check("keep признан нерабочим",
          "(* keep *)" in uf["repair_recipe"]["what_does_not_work"], True, tol=0)
    check("проверка стала гейтом", "GATE" in uf["gated"], True, tol=0)
    dr = uf["die_reads_with_every_clause_real"]
    check("чтений с настоящими клаузами", len(dr), 2, tol=0)
    check("обе прошли", sum(1 for r in dr if r["ok"] == 1), 2, tol=0)
    check("smul: все четыре клаузы истинны",
          dr[0]["clauses"] == "1111", True, tol=0)
    check("оговорка о смене нетлиста записана",
          "NEW measurements, not re-runs" in uf["honest_caveat"], True, tol=0)

# W985: the seed sweep the single-placement result of W984 could not stand in for.
sw = rec("sweep_w985.json")
if sw:
    print("\n== развёртка по размещениям (W985)")
    tot = pas = 0
    for name, d in sw["sweep"].items():
        r = d["reads"]
        tot += len(r); pas += sum(1 for x in r if x["ok"] == 1)
        check(f"{name}: чтений", len(r), 4, tol=0)
        check(f"{name}: все слова совпали", len({x["word"] for x in r}), 1, tol=0)
        check(f"{name}: все клаузы 1111",
              all(x["clauses"] == "1111" for x in r), True, tol=0)
        check(f"{name}: рост LUT, %", 100 * (d["LUT"] / d["was_LUT"] - 1),
              43.1 if "smul" in name else 120.9, tol=0.6)
    check("чтений всего", tot, 8, tol=0)
    check("прошло", pas, 8, tol=0)
    check("оговорка о неразделимости записана",
          "cannot be separated" in sw["what_cannot_be_concluded"], True, tol=0)
    check("дефектные обёртки заморожены", len(sw["mitigation"]["files"]), 2, tol=0)
    check("и проверены как всё ещё дефектные",
          "2 folded" in sw["mitigation"]["verified_still_defective"], True, tol=0)

# W986: the frozen reproducer, and the comparison W985 called impossible.
fz = rec("frozen_w986.json")
if fz:
    print("\n== замороженный воспроизводитель (W986)")
    d = fz["frozen_dup_sweep"]; r = d["reads"]
    check("размещений", len(r), 4, tol=0)
    check("проходов", sum(1 for x in r if x["ok"] == 1), 2, tol=0)
    check("отказов", sum(1 for x in r if x["ok"] == 0), 2, tol=0)
    check("два различных вердикта", len({x["clauses"] for x in r}), 2, tol=0)
    check("расщепление зафиксировано", d["verdict"].startswith("SPLIT"), True, tol=0)
    passing = {x["seed"] for x in r if x["ok"] == 1}
    check("проходят зёрна 1 и 42", passing == {1, 42}, True, tol=0)
    failing = {x["seed"] for x in r if x["ok"] == 0}
    check("падают зёрна 7 и 1234", failing == {7, 1234}, True, tol=0)
    cc = fz["the_controlled_comparison"]
    check("починенные: 8 из 8", "8 placements, 8 passes" in cc["repaired_designs"], True, tol=0)
    check("вывод: свойство свёрнутой схемы",
          "property of the FOLDED DESIGN" in cc["conclusion"], True, tol=0)
    check("smul записан как ABSENT",
          fz["frozen_smul_sweep"]["status"].startswith("ABSENT"), True, tol=0)

# W987: the operator table with every clause real, and what honesty cost in area.
op = rec("operators_w987.json")
if op:
    print("\n== таблица операторов с настоящими клаузами (W987)")
    o = op["operators"]
    check("операторов в таблице", len(o), 5, tol=0)
    passed = [k for k, v in o.items() if v.get("ok") and all(x == 1 for x in v["ok"])]
    absent = [k for k, v in o.items() if "ABSENT" in v.get("verdict", "")]
    check("прошли", len(passed), 3, tol=0)
    check("отсутствуют по потолку PnR", len(absent), 2, tol=0)
    check("dot4 впервые на кремнии",
          "FIRST TIME" in o["gft_signed_dot4"]["verdict"], True, tol=0)
    check("dot4: все клаузы истинны", o["gft_signed_dot4"]["clauses"][0] == "1111", True, tol=0)
    check("mac подтверждает починку W978",
          "W978" in o["gft_signed_mac"]["significance"], True, tol=0)
    check("mac: было 0011", "0011" in o["gft_signed_mac"]["before"], True, tol=0)
    check("mac: стало 1111", o["gft_signed_mac"]["clauses"][0] == "1111", True, tol=0)
    check("sadd прошёл на двух размещениях", len(o["gft_sadd"]["seeds"]), 2, tol=0)
    check("train1 отсутствует на обоих зёрнах",
          all(c == "ABSENT" for c in o["gft_train1"]["clauses"]), True, tol=0)
    # the cost of honesty, recomputed from the LUT counts rather than quoted
    g = op["the_cost_of_honesty"]["growth"]
    check("рост sadd, раз", 4231 / 1312, 3.2, tol=0.05)
    check("рост dup, раз", 1763 / 798, 2.2, tol=0.05)
    check("рост xorpercep, раз", 28217 / 10799, 2.6, tol=0.05)
    check("рост smul, раз", 1877 / 1312, 1.4, tol=0.05)
    check("все четыре роста записаны", len(g), 4, tol=0)
    sm = op["summary"]
    check("измерено с настоящими клаузами", sm["measured_with_all_clauses_real"], 5, tol=0)
    check("отказов ноль", sm["fail"], 0, tol=0)
    check("оговорка про одно размещение записана",
          "single placement" in sm["caveat"], True, tol=0)

# W988: the cap, the slope it was derived from, and the two designs it hid.
cp = rec("cap_w988.json")
if cp:
    print("\n== потолок стадии и наклон размещения (W988)")
    c = cp["the_cap"]
    check("потолок был", c["was"], 600, tol=0)
    check("потолок стал", c["now"], 1800, tol=0)
    check("во сколько раз поднят", c["now"] / c["was"], 3.0, tol=0.01)
    sl = cp["the_documented_slope_was_wrong"]
    check("в документации, мс/LUT", sl["documented"], 21.0, tol=0)
    m = sl["measured_from_completed_builds"]
    check("замеров наклона", len(m), 3, tol=0)
    check("наклон dot4", m["gft_signed_dot4"], 50.4, tol=0.1)
    check("наклон mac", m["gft_signed_mac"], 51.0, tol=0.1)
    check("наклон train1", m["gft_train1"], 33.7, tol=0.1)
    check("совокупный наклон", sl["aggregate"], 50.7, tol=0.1)
    check("во сколько раз ошибка", sl["factor_off"], sl["aggregate"] / sl["documented"], tol=0.05)
    # the spread is what refutes the single-slope model, so derive it here
    rates = [v for v in m.values()]
    check("разброс замеров, раз", max(rates) / min(rates), 1.51, tol=0.02)
    check("наибольший проект -- не самый медленный на LUT",
          m["gft_train1"] < m["gft_signed_dot4"], True, tol=0)
    r = {x["design"]: x for x in cp["results"]}
    check("train1 попал на кристалл", r["gft_train1"]["ok"], 1, tol=0)
    check("train1: все клаузы", r["gft_train1"]["clauses"] == "1111", True, tol=0)
    check("train1: PnR внутри старого потолка был бы",
          r["gft_train1"]["pnr_s"] < 600, True, tol=0)
    check("прошлый отказ был краевым",
          "marginal, not structural" in r["gft_train1"]["note"], True, tol=0)
    check("xorpercep всё ещё отсутствует",
          r["gft_xorpercep"]["verdict"].startswith("ABSENT"), True, tol=0)
    t = cp["table_now"]
    check("измерено операторов", t["measured_with_all_clauses_real"], 6, tol=0)
    check("из семи", t["of"], 7, tol=0)
    check("остался один", len(t["still_absent"]), 1, tol=0)

# W989: the table stops being transcribed and starts being derived.
sc = rec("schema_w989.json")
if sc:
    print("\n== схема записей и производная таблица (W989)")
    b = sc["before_after"]
    check("размещаемых чтений было", b["placeable_before"], 10, tol=0)
    check("всего чтений было", b["total"], 38, tol=0)
    check("доля до, %", 100 * b["placeable_before"] / b["total"], b["pct_before"], tol=1)
    check("размещаемых стало", b["placeable_after"], 39, tol=0)
    check("доля после, %", 100 * b["placeable_after"] / b["total_after"], 100, tol=0)
    f = sc["fix"]
    check("записей нормализовано", f["records_normalised"], 10, tol=0)
    check("чтений канонизировано", f["reads_canonicalised"], 39, tol=0)
    t = sc["totals"]
    check("схем в таблице", t["designs"], 8, tol=0)
    check("чтений в таблице", t["die_reads"], 39, tol=0)
    check("пропущено", t["skipped"], 0, tol=0)
    dt = sc["derived_table"]
    check("сумма чтений по строкам", sum(v["reads"] for v in dt.values()), t["die_reads"], tol=0)
    check("сумма прошедших", sum(v["pass"] for v in dt.values()), t["ok"], tol=0)
    check("сумма прошедших и упавших",
          sum(v["pass"] + v["fail"] for v in dt.values()), t["die_reads"], tol=0)
    split = [k for k, v in dt.items() if len(v["verdicts"]) > 1]
    check("схем с расхождением", len(split), 5, tol=0)
    check("предел инструмента заявлен",
          "cannot tell them apart" in sc["the_tools_own_limit"], True, tol=0)
    check("незавершённое названо, а не опущено",
          sc["in_flight"]["design"] == "gft_xorpercep", True, tol=0)

# W990: both spec fixes confirmed on silicon, the MAC across four placements.
cf = rec("confirm_w990.json")
if cf:
    print("\n== подтверждение двух починок на кристалле (W990)")
    w = cf["already_confirmed_in_w987"]
    check("mac: было 0011", "0011" in w["gft_signed_mac"]["before"], True, tol=0)
    check("mac: стало 1111", w["gft_signed_mac"]["clauses"] == "1111", True, tol=0)
    check("dot4: было ABSENT", w["gft_signed_dot4"]["before"].startswith("ABSENT"), True, tol=0)
    check("dot4: стало 1111", w["gft_signed_dot4"]["clauses"] == "1111", True, tol=0)
    check("оговорка про одно размещение",
          "cannot distinguish" in w["caveat"], True, tol=0)
    m = cf["confirmation_sweep"]["gft_signed_mac"]
    check("mac: размещений", m["placements"], 4, tol=0)
    check("mac: все прошли", sum(m["ok"]), 4, tol=0)
    check("mac: один вердикт на все", len(set(m["clauses"])), 1, tol=0)
    check("mac: различных площадок BSCAN", len(set(m["sites"])), 3, tol=0)
    check("mac: слово одинаково", m["identical_in_every_build"], True, tol=0)
    check("инструмент не называет это доказательством",
          "not a proof" in m["tool_note"], True, tol=0)
    d4 = cf["confirmation_sweep"]["gft_signed_dot4"]
    check("dot4: подтверждено размещений", d4["placements_done"], 2, tol=0)
    check("dot4: обе площадки различны", len(set(d4["sites"])), 2, tol=0)
    check("dot4: один вердикт", len(set(d4["clauses"])), 1, tol=0)
    check("dot4: повторяемость на одном зерне",
          "same word both times" in d4["repeatability"], True, tol=0)
    check("dot4: остальное названо",
          "still placing" in d4["status"], True, tol=0)
    _canon = field(cf, "die_reads_canonical", "чтения канонизированы")
    if _canon is not None:
        check("чтения канонизированы", len(_canon), 6, tol=0)
    _given = field(cf, "what_was_given_up_for_it", "прерванное названо, а не скрыто")
    if _given is not None:
        check("прерванное названо, а не скрыто", "killed" in _given, True, tol=0)

# W991: the competitor table, computed from the committed oracles.
cm = rec("compare_w991.json")
if cm:
    print("\n== сравнение с конкурентами при равной ФИЗИЧЕСКОЙ ширине (W991)")
    lw = cm["ladder_physical_widths"]
    check("TNF16 шириной 19 бит", lw["TNF16"], 19, tol=0)
    check("TNF8 шириной 10 бит", lw["TNF8"], 10, tol=0)
    check("TNF4 шириной 6 бит", lw["TNF4"], 6, tol=0)
    m = cm["matched_width_results"]
    t19 = m["19_bits"]["TNF16 (4t,11m)"]; p19 = m["19_bits"]["posit19 es=1"]
    # The TNF rows of this record count every code, including exponent fields
    # above the special row that no computation produces; W993 supersedes them.
    # The paper now quotes these figures only in its correction paragraph.
    check("19 бит: значений у TNF16", t19["values"], 516096, tol=0)
    check("19 бит: значений у posit19", p19["values"], 524286, tol=0)
    check("19 бит: TNF беднее по значениям", p19["values"] > t19["values"], True, tol=0)
    check("W991 all codes: the quoted 8190 is a difference of value counts",
          p19["values"] - t19["values"], 8190, tol=0)
    check("W991 all codes: what the checker computed and passed", 2**19 - t19["values"], 8192, tol=0)
    check("W991 all codes: TNF16 binades", t19["binades"], 127.0, tol=0)
    check("W991 all codes: TNF8 values", m["10_bits"]["TNF8 (3t,4m)"]["values"], 960, tol=0)
    check("W991 all codes: TNF8 binades", m["10_bits"]["TNF8 (3t,4m)"]["binades"], 31.0, tol=0)
    check("W991 all codes: TNF4 values", m["6_bits"]["TNF4 (2t,1m)"]["values"], 56, tol=0)
    check("W991 all codes: TNF4 binades", m["6_bits"]["TNF4 (2t,1m)"]["binades"], 14.6, tol=0)
    check("19 бит: шаг в 1.0 хуже во сколько раз",
          t19["step_at_1_pct"] / p19["step_at_1_pct"], 12.0, tol=0.5)
    t10 = m["10_bits"]["TNF8 (3t,4m)"]; p10 = m["10_bits"]["posit10 es=1"]
    check("10 бит: TNF беднее по значениям", p10["values"] > t10["values"], True, tol=0)
    check("10 бит: шаг хуже во сколько раз",
          t10["step_at_1_pct"] / p10["step_at_1_pct"], 4.0, tol=0.05)
    t6 = m["6_bits"]["TNF4 (2t,1m)"]; p6 = m["6_bits"]["posit6 es=1"]
    check("6 бит: TNF беднее по значениям", p6["values"] > t6["values"], True, tol=0)
    check("6 бит: шаг хуже во сколько раз",
          t6["step_at_1_pct"] / p6["step_at_1_pct"], 2.0, tol=0.05)
    check("ловушка ширины зафиксирована",
          "516096 is more than 2^16" in cm["the_trap_it_fell_into_first"]["arithmetic"], True, tol=0)
    check("сказано, что это не про цену",
          "cost figure" in cm["what_this_does_not_say"], True, tol=0)
    check("dot4: канонических чтений", len(cm["die_reads_canonical"]), 2, tol=0)

# W993: the matched-width table, counting for TNF only the words it produces.
mw = rec("matched_width_w993.json")
if mw:
    print("\n== matched physical width, words the format produces (W993)")
    r = mw["matched_width_results"]
    quoted = {  # tab:matchedwidth, row by row: values, binades, step at 1.0 in %
        ("19_bits", "TNF16 (4t,11m)"): (323584, 79.0, 0.024),
        ("19_bits", "posit19 es=1"): (524286, 68.0, 0.002),
        ("19_bits", "posit19 es=2"): (524286, 136.0, 0.003),
        ("19_bits", "takum19"): (524286, 510.0, 0.003),
        ("10_bits", "TNF8 (3t,4m)"): (800, 25.0, 3.125),
        ("10_bits", "posit10 es=1"): (1022, 32.0, 0.781),
        ("10_bits", "posit10 es=2"): (1022, 64.0, 1.562),
        ("6_bits", "TNF4 (2t,1m)"): (28, 6.6, 25.0),
        ("6_bits", "posit6 es=1"): (62, 16.0, 12.5),
        ("6_bits", "posit6 es=2"): (62, 32.0, 25.0),
    }
    for (w, name), (v, b, st) in quoted.items():
        row = r[w][name]
        check(f"{name}: values", row["values"], v, tol=0)
        check(f"{name}: binades", row["binades"], b, tol=0)
        check(f"{name}: step at 1.0 (%)", row["step_at_1_pct"], st, tol=0)

    def dominates(a, b, strict):
        better = (a["values"] > b["values"], a["binades"] > b["binades"],
                  a["step_at_1_pct"] < b["step_at_1_pct"])
        no_worse = (a["values"] >= b["values"], a["binades"] >= b["binades"],
                    a["step_at_1_pct"] <= b["step_at_1_pct"])
        return all(better) if strict else all(no_worse)

    tnf = {"19_bits": "TNF16 (4t,11m)", "10_bits": "TNF8 (3t,4m)", "6_bits": "TNF4 (2t,1m)"}
    for w, n in (("19_bits", 19), ("10_bits", 10), ("6_bits", 6)):
        check(f"{n} bits: posit es=2 weakly dominates TNF",
              dominates(r[w][f"posit{n} es=2"], r[w][tnf[w]], strict=False), True, tol=0)
    for w, n in (("10_bits", 10), ("6_bits", 6)):
        check(f"{n} bits: posit es=1 dominates TNF on every column",
              dominates(r[w][f"posit{n} es=1"], r[w][tnf[w]], strict=True), True, tol=0)
    check("19 bits: TNF16 still has more binades than posit19 es=1",
          r["19_bits"]["TNF16 (4t,11m)"]["binades"] > r["19_bits"]["posit19 es=1"]["binades"],
          True, tol=0)
    for w, n, ratio, tol in (("19_bits", 19, 12.0, 0.5), ("10_bits", 10, 4.0, 0.05),
                             ("6_bits", 6, 2.0, 0.05)):
        check(f"{n} bits: posit es=1 step finer by", r[w][tnf[w]]["step_at_1_pct"]
              / r[w][f"posit{n} es=1"]["step_at_1_pct"], ratio, tol=tol)

    c16 = mw["tnf_code_census"]["TNF16 (4t,11m)"]
    check("TNF16: trit-word exponent rows", c16["trit_word_rows"], 81, tol=0)
    check("TNF16: exponent rows", c16["exponent_rows"], 128, tol=0)
    check("TNF16: rows above the special row", c16["rows_above_special"], 47, tol=0)
    check("TNF16: words per row", c16["words_per_row"], 4096, tol=0)
    check("TNF16: unreachable words", c16["words_outside_format"], 192512, tol=0)
    check("TNF16: unreachable words are more than a third",
          3 * c16["words_outside_format"] > 2**19, True, tol=0)
    check("TNF16: words without a finite non-zero value (paper B)",
          c16["words_without_finite_nonzero_value"], 200704, tol=0)
    check("TNF16: every produced word survives encode(decode(w))",
          c16["roundtrip_below_special_ok"], c16["words_with_finite_nonzero_value"], tol=0)
    check("TNF16: no word above the special row survives it",
          c16["above_special_survive_roundtrip"], 0, tol=0)
    check("W991 TNF rows reproduced by counting every code",
          all(mw["w991_rows_reproduced_by_all_codes"].values()), True, tol=0)

# W994: the grid every TNF rig must read. tnf_ref.decode used to turn a code whose
# exponent field lies above offset_max (= 3^Et - 1) into a number; those codes are
# not TNF words, and encode never emits them. decode now refuses them, and every
# figure below is counted on the words alone, from the oracle, not from a record.
print("\n== W994: TNF grids counted on TNF words only")


def _census(et, mb):
    f = _T.TNFFormat(et, mb)
    n = 1 << (f.sign_shift + 1)
    words = refused = 0
    vals, every = set(), set()
    same = True
    for c in range(n):
        ve = _T.decode_every_code(f, c)
        if isinstance(ve, Fraction) and ve != 0:
            every.add(ve)
        if not _T.is_word(f, c):
            try:
                _T.decode(f, c)
            except ValueError:
                refused += 1
            continue
        words += 1
        v = _T.decode(f, c)
        if isinstance(v, Fraction):
            same = same and v == ve
            if v != 0:
                vals.add(v)
        elif isinstance(ve, Fraction):
            same = False
    return f, n, words, refused, vals, every, same


def _binades(vals):
    pos = [v for v in vals if v > 0]
    return math.log2(max(pos) / min(pos))


f4, n4, w4, r4, v4, e4, s4 = _census(2, 1)
check("TNF4 (2,1): codes", n4, 64, tol=0)
check("TNF4: TNF words", w4, 36, tol=0)
check("TNF4: non-words refused by decode", r4, 28, tol=0)
check("TNF4: finite non-zero values", len(v4), 28, tol=0)
check("TNF4: values, zero included", len(v4) + 1, 29, tol=0)
check("TNF4: largest value", float(max(v4)), 12.0, tol=0)
check("TNF4: smallest positive value", float(min(v for v in v4 if v > 0)), 0.125, tol=0)
check("TNF4: binades", _binades(v4), 6.58, tol=0.005)
check("TNF4: decode equals decode_every_code on every word", s4, True, tol=0)
check("TNF4: every-code values, zero included (the withdrawn grid)", len(e4) + 1, 57, tol=0)
check("TNF4: every-code grid minus the words = the 14 magnitudes 32 .. 3072",
      {abs(v) for v in e4 - v4} == {m * 2 ** j for j in range(5, 12) for m in (1, Fraction(3, 2))},
      True, tol=0)
check("TNF4: largest every-code value", float(max(e4)), 3072.0, tol=0)

f8, n8, w8, r8, v8, e8, s8 = _census(3, 4)
check("TNF8 (3,4): TNF words of 1024", w8, 864, tol=0)
check("TNF8: non-words refused by decode", r8, 160, tol=0)
check("TNF8: finite non-zero values", len(v8), 800, tol=0)
check("TNF8: binades", _binades(v8), 24.95, tol=0.005)
check("TNF8: decode equals decode_every_code on every word", s8, True, tol=0)
check("TNF8: every-code finite non-zero values (withdrawn)", len(e8), 960, tol=0)

_f43 = _census(4, 3)
check("TNF (4,3): finite non-zero values", len(_f43[4]), 1264, tol=0)
check("TNF (4,3): binades", _binades(_f43[4]), 78.91, tol=0.005)

# 192,512 at (4,11): the figure that replaces W991's "8,190 unreachable".
for (et, mb), want_w, want_n in (((4, 9), 82944, 131072), ((4, 11), 331776, 524288)):
    _f = _T.TNFFormat(et, mb)
    _n = 1 << (_f.sign_shift + 1)
    _w = sum(1 for c in range(_n) if _T.is_word(_f, c))
    check(f"TNF ({et},{mb}): codes", _n, want_n, tol=0)
    check(f"TNF ({et},{mb}): TNF words", _w, want_w, tol=0)
    check(f"TNF ({et},{mb}): codes that are not TNF words", _n - _w, want_n - want_w, tol=0)
    check(f"TNF ({et},{mb}): finite non-zero values by field count",
          2 * (_f.offset_max - 1) * _f.mant, {9: 80896, 11: 323584}[mb], tol=0)

# encode never emits a non-word: every word value, every midpoint between
# neighbouring values, and magnitudes far outside the range.
for _f, _v in ((f4, v4), (f8, v8)):
    _pos = sorted(v for v in _v if v > 0)
    _probe = _pos + [(a + b) / 2 for a, b in zip(_pos, _pos[1:])] + \
        [Fraction(1, 10 ** 9), Fraction(10 ** 9), _pos[-1] * 2, _pos[0] / 3]
    _probe += [-x for x in _probe]
    check(f"TNF ({_f.exp_trits},{_f.mant_bits}): encode emits only words ({len(_probe)} probes)",
          all(_T.is_word(_f, _T.encode(_f, x)) for x in _probe), True, tol=0)

for (et, mb), _v, want in (((2, 1), v4, (2, 7)), ((3, 4), v8, (5, 28))):
    _p = _odd_shift(_v)
    check(f"TNF ({et},{mb}) words: odd-mantissa bits", _p[0], want[0], tol=0)
    check(f"TNF ({et},{mb}) words: max shift", _p[1], want[1], tol=0)

_conf = HERE.parent.parent / "conformance" / "tnf_ref.py"
if _conf.exists():
    check("conformance/tnf_ref.py and oracles/tnf_ref.py are byte-identical",
          _conf.read_bytes() == (HERE / "oracles" / "tnf_ref.py").read_bytes(), True, tol=0)
else:
    print("  --  conformance/tnf_ref.py not in this checkout: byte-identity not checked")

# W992: the chipdb deletion, its audit, and the sequencing error.
dl = rec("deletion_w992.json")
if dl:
    print("\n== удаление чипдб и состязательный аудит (W992)")
    a = dl["audit"]
    check("углов поиска", len(a["sweep_verdicts"]), 4, tol=0)
    check("все четыре сказали 'безопасно'",
          all(v == "SAFE_TO_DELETE" for v in a["sweep_verdicts"]), True, tol=0)
    check("агентов", a["agents"], 12, tol=0)
    check("агенты = 4 угла + 2 скептика на угол", a["agents"], 4 + 4 * 2, tol=0)
    r = dl["refutations_that_landed"]
    check("опровержений", len(r), 3, tol=0)
    check("подтверждённых опровержений",
          sum(1 for x in r if x["status"].startswith("CONFIRMED")), 2, tol=0)
    check("литеральный grep назван причиной",
          "cannot see a consumer that CONSTRUCTS" in r[0]["refutation"], True, tol=0)
    check("ничего не сломано", dl["what_is_actually_broken_now"].startswith("nothing"), True, tol=0)
    check("цена регенерации названа", "bbaexport" in dl["the_real_cost"], True, tol=0)
    check("ошибка порядка признана",
          "BEFORE the refutation phase finished" in dl["my_sequencing_error"], True, tol=0)
    e = dl["environment"]
    check("освобождено ГиБ", e["free_gib_after"] - e["free_gib_before"], 0.73, tol=0.02)

print(f"\n  ИТОГ: сошлось {ok}, расхождений {bad}, пропущено блоков {skip}")
sys.exit(1 if bad else 0)
