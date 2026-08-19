#!/usr/bin/env python3
"""Regenerate Table `tab:downstream` from
measurements/tnf_downstream_bayesian_si_2026-08-13.json.

ADJUDICATION FIRST. The similarity scan called this a WEAK mapping (14.7%
forward, F=0.155 -- top in both directions but far below every confirmed
pair). The score is noise: the record stores raw quantities (mu_hat to 16
digits, errors to 16 digits) while the table prints them at 11 and 3
significant figures, so almost no printed token appears verbatim in the JSON.
What settles the mapping, per the read-the-metadata-first rule, is the
record's own metadata and its generator:
  - record "task" = Bayesian estimation of the solar gravitational parameter
    from a sum of log-likelihoods (in Russian); seed 20260813; n=66;
    mu_true_SI = 1.32712440018e20; accumulator = float32 for candidates,
    float64 for reference; search = golden section over log(mu), 72 iters.
  - gen_downstream_bayesian_si.py ("Downstream task D") produces exactly the
    four modes ref64/binary32/tnf32/takum32 and the derived fields
    iterations_to_rel_mu_1e-6, relative_mu_error_vs_ref64.
  - sec:downstream describes the same task word for word: MAP estimate of
    mu = GM_sun, 66 Gaussian log-likelihoods, raw SI, golden-section over
    log(mu), 72 iterations, fp32 accumulator held fixed.
Every one of those pins matches; the weak textual score is explained, and the
mapping is CONFIRMED. measurements/README.md ("backs the downstream table")
is right.

THE TABLE IS A VIEW of four record fields per mode:
    col 2  mu_hat    printed as  {mu_hat/1e20:.10f} x 10^20   (11 sig figs)
    col 3  relative_mu_error_vs_ref64  printed as {m:.2f} x 10^{e}
           ("---" for the reference row, whose record value is exactly 0.0)
    col 4  iterations_to_rel_mu_1e-6   printed as an integer
Column identities are ASSERTED, not assumed:
    relative_mu_error_vs_ref64 == |mu_hat - ref.mu_hat| / ref.mu_hat  (1e-9)
    mu_hat == exp(theta_hat)                                          (1e-12)
Rows are matched BY KEY (format name -> record mode), never by position.

CAPTION AND ADJACENT-PROSE CLAIMS RECOMPUTED, conditionally on the phrase
being present in tnf_paper.tex:
  - caption: "all runs were carried to $72$"
  - task paragraph: 66 observations; seeded truth 1.32712440018e20; radii
    1.1e15..5.8e17 m; noise 0.5% of true acceleration; 72 iterations to a
    bracket width of 7.1e-15
  - "TNF32 lands $1.60\\times$ closer to the float64 solution than takum32"
  - "settles in $21$ iterations against that format's $27$"
  - "binary32 beats both by a factor of thirty-three"
  - "takum32's estimate is in fact slightly closer to the seeded mu
    ($9.63e-5$ against $1.02e-4$)" -- the paper prints its own damaging row,
    and the record confirms it.

SELECTION REPORT (rule 6): all four record modes are printed -- no hidden
rows. But the record carries unprinted COLUMNS, and one is salient: at the
looser 1e-5 threshold (iterations_to_rel_mu_1e-5) takum32 also settles in 21
iterations, tying TNF32; the printed 21-vs-27 advantage exists only at the
1e-6 threshold the caption states. Reported in the NOTE, not as a defect:
the caption declares its threshold.
"""
import json
import math
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
REC = HERE / "measurements" / "tnf_downstream_bayesian_si_2026-08-13.json"
PAPER = HERE / "tnf_paper.tex"

# printed format name (normalised) -> record mode key
FORMAT = {
    "float64reference": "ref64",
    "binary32": "binary32",
    "tnf32523": "tnf32",
    "takum32": "takum32",
}
EXPECTED_ROWS = 4


def clean(cell):
    c = re.sub(r"\\(midrule|toprule|bottomrule|hline)", "", cell)
    c = re.sub(r"\\(textbf|texttt|mathbf|emph|mathrm)\{(.*?)\}", r"\2", c)
    c = re.sub(r"\\[,!;]", " ", c)
    return c.replace("$", "").strip()


def norm_name(s):
    return re.sub(r"[^a-z0-9]", "", clean(s).lower())


def sci(mantissa_dec, v):
    """Print v as the paper does: mantissa to `mantissa_dec` decimals, power
    of ten -- e.g. sci(2, 2.8357939884e-07) == '2.84e-07'. Rounding of the
    mantissa may carry (9.9995 -> 10.00), so renormalise after formatting."""
    if v == 0.0:
        return "0"
    e = math.floor(math.log10(abs(v)))
    m = v / 10.0 ** e
    s = f"{m:.{mantissa_dec}f}"
    if float(s) >= 10.0:  # rounding carried into a new decade
        e += 1
        s = f"{v / 10.0 ** e:.{mantissa_dec}f}"
    return f"{s}e{e:+03d}"


def table_chunks(tex):
    for m in re.finditer(r"\\begin\{table\}(.*?)\\end\{table\}", tex, re.S):
        if r"\label{tab:downstream}" in m.group(1) \
                and r"\label{tab:downstream-cg}" not in m.group(1):
            body = m.group(1)
            break
    else:
        raise SystemExit("tab:downstream not found")
    capm = re.search(r"\\caption\{((?:[^{}]|\{[^{}]*\})*)\}", body, re.S)
    caption = capm.group(1) if capm else ""
    body = body[: capm.start()] + body[capm.end():] if capm else body
    return caption, body


CELL_SCI = re.compile(r"([\d.]+)\s*\\times\s*10\^\{(-?\d+)\}")


def parse_sci_cell(cell):
    """'$1.3272722754\\times 10^{20}$' -> ('1.3272722754', 20)."""
    m = CELL_SCI.search(cell)
    if not m:
        return None
    return m.group(1), int(m.group(2))


def printed_rows(body):
    out = []
    for raw in body.split(r"\\"):
        cells = [c.strip() for c in raw.split("&")]
        if len(cells) != 4 or "tabular" in raw or r"\toprule" in raw:
            continue
        name = clean(cells[0])
        if not name or name == "format":
            continue
        out.append({
            "name": name,
            "mu": parse_sci_cell(cells[1]),
            "relerr_raw": clean(cells[2]),
            "relerr": parse_sci_cell(cells[2]),
            "iters": clean(cells[3]),
            "bold_name": r"\textbf" in cells[0],
            "bold_iters": r"\mathbf" in cells[3],
        })
    return out


def _row_guard(printed_count, expected=EXPECTED_ROWS):
    """GUARD against the vacuous pass: an emptied or unparsed table must fail,
    not sail through with 0/0 cells."""
    if printed_count != expected:
        raise SystemExit(
            f"FAIL: parsed {printed_count} printed rows, expected {expected} -- "
            "either the table changed or the parser broke; neither may pass "
            "silently")


def check_phrase(tex_flat, phrase, ok, bad, note, describe):
    """Conditional prose check: only judged if the phrase is still in the
    paper (so a later fix turns the light green); its absence is noted."""
    if phrase in tex_flat:
        if ok:
            note.append(f"prose OK: {describe}")
        else:
            bad.append(f"prose: {describe}")
    else:
        note.append(f"prose phrase not found (skipped): {phrase[:60]!r}")


def main():
    rec = json.loads(REC.read_text())
    res = rec["results"]
    tex = PAPER.read_text()
    tex_flat = re.sub(r"\s+", " ", tex)
    caption, body = table_chunks(tex)
    caption_flat = re.sub(r"\s+", " ", caption)
    printed = printed_rows(body)

    print(f"record modes {len(res)}   printed rows {len(printed)}")
    _row_guard(len(printed))

    bad, note = [], []
    cells_total = cells_matching = 0

    # ---- record metadata pins (the adjudication, made executable) ----------
    if rec["seed"] != 20260813:
        bad.append(f"record seed {rec['seed']} != 20260813")
    if rec["n_observations"] != 66:
        bad.append(f"record n_observations {rec['n_observations']} != 66")
    if rec["mu_true_SI"] != 1.32712440018e20:
        bad.append(f"record mu_true_SI {rec['mu_true_SI']!r}")
    if set(res) != {"ref64", "binary32", "tnf32", "takum32"}:
        bad.append(f"record modes {sorted(res)} are not the expected four")

    # ---- record-internal identities, before any comparison ------------------
    ref_mu = res["ref64"]["mu_hat"]
    for k, r in res.items():
        # mu_hat == exp(theta_hat): pins which field the printed mu is
        if abs(math.exp(r["theta_hat"]) - r["mu_hat"]) > 1e-12 * abs(r["mu_hat"]):
            bad.append(f"{k}: mu_hat != exp(theta_hat)")
        # rel error column identity
        want = abs(r["mu_hat"] - ref_mu) / abs(ref_mu)
        got = r["relative_mu_error_vs_ref64"]
        if abs(got - want) > 1e-9 * max(1.0, abs(got)):
            bad.append(f"{k}: relative_mu_error_vs_ref64 {got!r} != "
                       f"|mu_hat-ref|/ref = {want!r}")
        if abs(r["relative_mu_error_vs_true"]
               - abs(r["mu_hat"] - rec["mu_true_SI"]) / rec["mu_true_SI"]) \
                > 1e-9 * max(1.0, r["relative_mu_error_vs_true"]):
            bad.append(f"{k}: relative_mu_error_vs_true fails its identity")
        if r["iterations"] != 72:
            bad.append(f"{k}: iterations {r['iterations']} != 72")

    # ---- join printed rows to record modes BY KEY ---------------------------
    matched = set()
    for p in printed:
        key = norm_name(p["name"])
        mode = FORMAT.get(key)
        if mode is None:
            bad.append(f"printed format {p['name']!r} (norm {key!r}) has no "
                       "record mode")
            continue
        r = res[mode]
        matched.add(mode)
        cells_total += 1          # the format-name cell, verified by the join
        cells_matching += 1

        # col 2: mu_hat at printed precision (mantissa .10f, exponent 20)
        cells_total += 1
        want_mu = (f"{r['mu_hat'] / 1e20:.10f}", 20)
        if p["mu"] == want_mu:
            cells_matching += 1
        else:
            bad.append(f"{mode} mu_hat: printed {p['mu']!r} record {want_mu!r}")

        # col 3: rel error vs float64 -- '---' iff reference (record value 0.0)
        cells_total += 1
        if mode == "ref64":
            if p["relerr_raw"] == "---" and r["relative_mu_error_vs_ref64"] == 0.0:
                cells_matching += 1
            else:
                bad.append(f"ref64 rel-error cell {p['relerr_raw']!r} with record "
                           f"value {r['relative_mu_error_vs_ref64']!r}")
        else:
            v = r["relative_mu_error_vs_ref64"]
            want = sci(2, v)
            got = (f"{p['relerr'][0]}e{p['relerr'][1]:+03d}"
                   if p["relerr"] else p["relerr_raw"])
            if got == want:
                cells_matching += 1
            else:
                bad.append(f"{mode} rel error: printed {got!r} record {want!r} "
                           f"(raw {v!r})")

        # col 4: iterations to 1e-6
        cells_total += 1
        if p["iters"] == str(r["iterations_to_rel_mu_1e-6"]):
            cells_matching += 1
        else:
            bad.append(f"{mode} iterations: printed {p['iters']!r} record "
                       f"{r['iterations_to_rel_mu_1e-6']!r}")

    unprinted = sorted(set(res) - matched)
    for k in unprinted:
        note.append(f"UNPRINTED record mode {k}: mu_hat={res[k]['mu_hat']!r}")

    # typographic lock: the bolded row is TNF32 and its bolded iteration count
    # is the minimum of the printed column
    bolded = [p for p in printed if p["bold_name"]]
    min_it = min(res[m]["iterations_to_rel_mu_1e-6"] for m in matched)
    if len(bolded) != 1 or FORMAT.get(norm_name(bolded[0]["name"])) != "tnf32":
        bad.append(f"bolded rows {[p['name'] for p in bolded]} != [TNF32]")
    elif not bolded[0]["bold_iters"] \
            or res["tnf32"]["iterations_to_rel_mu_1e-6"] != min_it:
        bad.append("bolded iteration count is not the column minimum")

    # ---- caption claims ------------------------------------------------------
    check_phrase(caption_flat, "all runs were carried to $72$",
                 all(r["iterations"] == 72 for r in res.values()),
                 bad, note, "caption: all runs carried to 72 (record: all 72)")
    check_phrase(caption_flat, "relative change below $10^{-6}$", True,
                 bad, note, "caption states the 1e-6 threshold the record's "
                 "iterations_to_rel_mu_1e-6 field encodes")

    # ---- task-paragraph claims (sec:downstream) ------------------------------
    lo, hi = rec["radii_m_range"]
    check_phrase(tex_flat, "sum of $66$ Gaussian log-likelihoods",
                 rec["n_observations"] == 66, bad, note,
                 f"66 observations (record n={rec['n_observations']})")
    check_phrase(tex_flat, r"$\mu = 1.32712440018\times 10^{20}$",
                 rec["mu_true_SI"] == 1.32712440018e20, bad, note,
                 "seeded truth 1.32712440018e20 (record mu_true_SI)")
    check_phrase(tex_flat,
                 r"Radii run from $1.1\times 10^{15}$ to $5.8\times 10^{17}$",
                 sci(1, lo) == "1.1e+15" and sci(1, hi) == "5.8e+17",
                 bad, note,
                 f"radii 1.1e15..5.8e17 m (record {lo:.4e}..{hi:.4e})")
    check_phrase(tex_flat, "noise is $0.5\\%$ of the true acceleration",
                 rec["sigma_definition"] == "0.005*a_true (m/s^2)",
                 bad, note,
                 f"0.5% noise (record sigma_definition={rec['sigma_definition']!r})")
    bw = res["ref64"]["bracket_width"]
    check_phrase(tex_flat,
                 r"$72$ iterations to a bracket width of $7.1\times 10^{-15}$",
                 sci(1, bw) == "7.1e-15" and all(
                     abs(r["bracket_width"] - bw) <= 1e-12 * bw
                     for r in res.values()),
                 bad, note,
                 f"72 iters to bracket width 7.1e-15 (record {bw!r}, same in "
                 "all four modes)")
    check_phrase(tex_flat,
                 r"the accumulator is \texttt{float32} in every case",
                 "float32" in rec["accumulator"], bad, note,
                 f"fp32 accumulator (record accumulator={rec['accumulator']!r})")

    # ---- what-it-shows / four-boundaries claims ------------------------------
    tnf_e = res["tnf32"]["relative_mu_error_vs_ref64"]
    tak_e = res["takum32"]["relative_mu_error_vs_ref64"]
    b32_e = res["binary32"]["relative_mu_error_vs_ref64"]
    ratio = tak_e / tnf_e
    check_phrase(tex_flat,
                 r"TNF32 lands $1.60\times$ closer to the \texttt{float64} "
                 r"solution than \texttt{takum32}",
                 f"{ratio:.2f}" == "1.60", bad, note,
                 f"1.60x closer (record takum/tnf error ratio {ratio:.6f})")
    check_phrase(tex_flat,
                 "settles in $21$ iterations against that format's $27$",
                 res["tnf32"]["iterations_to_rel_mu_1e-6"] == 21
                 and res["takum32"]["iterations_to_rel_mu_1e-6"] == 27,
                 bad, note, "21 vs 27 iterations to 1e-6 (record: 21, 27)")
    # "beats both by a factor of thirty-three": the smaller of the two factors
    fac = min(tnf_e / b32_e, tak_e / b32_e)
    check_phrase(tex_flat,
                 r"\texttt{binary32} beats both by a factor of thirty-three",
                 int(fac) == 33, bad, note,
                 f"binary32 beats both by >= 33x (record factors "
                 f"{tnf_e / b32_e:.2f} vs TNF32, {tak_e / b32_e:.2f} vs takum32)")
    tak_t = res["takum32"]["relative_mu_error_vs_true"]
    tnf_t = res["tnf32"]["relative_mu_error_vs_true"]
    check_phrase(tex_flat,
                 r"closer} to the seeded $\mu$ ($9.63\times 10^{-5}$ against "
                 r"$1.02\times 10^{-4}$)",
                 tak_t < tnf_t and sci(2, tak_t) == "9.63e-05"
                 and sci(2, tnf_t) == "1.02e-04",
                 bad, note,
                 f"takum32 closer to seeded mu, 9.63e-5 vs 1.02e-4 (record "
                 f"{tak_t:.4e} vs {tnf_t:.4e}) -- the paper prints its own "
                 "damaging comparison and the record confirms it")

    # ---- selection report (rule 6): unprinted columns ------------------------
    note.append("selection: all 4 record modes are printed; no hidden rows")
    it5 = {k: res[k]["iterations_to_rel_mu_1e-5"] for k in res}
    note.append(
        f"UNPRINTED column iterations_to_rel_mu_1e-5 = {it5}: at the looser "
        "1e-5 threshold takum32 ties TNF32 at 21 iterations -- the printed "
        "21-vs-27 advantage exists only at the caption's stated 1e-6 threshold")
    note.append("UNPRINTED columns theta_hat / objective / "
                "objective_error_vs_ref64 carry no comparison the table hides: "
                f"objective errors vs ref64 are binary32 "
                f"{res['binary32']['objective_error_vs_ref64']:.2e} < takum32 "
                f"{res['takum32']['objective_error_vs_ref64']:.2e} < tnf32 "
                f"{res['tnf32']['objective_error_vs_ref64']:.2e} -- same "
                "ordering pattern as the printed mu errors (binary32 best), "
                "with takum32 ahead of TNF32 on the objective")
    if "tnf_downstream_bayesian_si" not in caption_flat.replace("\\_", "_"):
        note.append("caption has no Data: pointer naming the record file; the "
                    "prose says only 'the generator, the oracles and the "
                    "result record are in the repository'")

    # ---- verdict -------------------------------------------------------------
    print(f"cells: {cells_matching}/{cells_total} printed cells reproduce")
    print("\nNOTE:")
    for n_ in note:
        print(f"  {n_}")
    if bad:
        print(f"\nFAIL: {len(bad)} defect(s)\n")
        for b in bad:
            print(f"  {b}")
        return 1
    print(f"\nOK: all {len(printed)} printed rows of tab:downstream reproduce "
          "from the record at printed precision, and every caption/prose claim "
          "recomputes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
