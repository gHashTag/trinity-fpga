#!/usr/bin/env python3
"""Adjudicate and regenerate: what does measurements/tnf_kappa_taxonomy.json back?

Provenance left this UNDECIDED between tab:geoscale, tab:fourfam and
tab:allscales. All three are wrong, and the record says so itself (rule 1): its
generator gen_kappa_and_taxonomy.py opens with "CHECK 1 -- the prefactor of
Theorem thm:scaleradix" and "CHECK 2 -- the taxonomy counts close on the
catalogue size", its `prefactor` field is "one quarter", and its taxonomy block
carries the geometric member list verbatim from tab:taxonomy's caption.

VERDICT (each branch verified below, not asserted):

  tab:geoscale   NOT BACKED. Its measurement cells are perplexities
                 (18.8024 ... 13.7636); the record holds kappa constants,
                 Monte-Carlo error means and integer counts. Zero overlap.
  tab:fourfam    NOT BACKED. Its cells are perplexities and magnitude counts;
                 the only shared number is the degenerate 1.000 (fp32's ratio
                 to itself vs the record's predicted/empirical ratio at (3,8)),
                 which any self-consistent pair prints and identifies nothing.
  tab:allscales  NOT BACKED. Level errors, register/adder counts, LUT/F_max --
                 none derivable from kappa or the taxonomy. Zero overlap.
  tab:taxonomy   BACKED, fully -- the table the provenance pass never fielded.
                 All four class counts, the class keys, and the caption's
                 member list (takum8/16/32/64, tekum8/16/32, "a member list of
                 seven", the earlier draft's 8) reproduce from the record.
  thm:scaleradix + the "prefactor was wrong by a factor of four" paragraph:
                 BACKED. kappa(2), kappa(3), the 1.6825 ratio, the quarter
                 prefactor, the 8e6 draws, and all four printed Monte-Carlo
                 values reproduce at printed precision; the empirical means
                 re-derive BIT-FOR-BIT by re-running the generator's sampler
                 (numpy default_rng, seed 20260814).

Rows are matched BY KEY (class name; (r,M) pairs), never by position. Kappa is
recomputed from its definition (r-1)^2/(r ln r) and asserted against the record
to half an ulp of the record's own 7-decimal storage before any cell is judged.
The printed-row guard pins tab:taxonomy at 4 body rows. Nothing in
tnf_paper.tex is edited.
"""
import json
import math
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
REC = HERE / "measurements" / "tnf_kappa_taxonomy.json"
PAPER = HERE / "tnf_paper.tex"

EXPECTED_TAXONOMY_ROWS = 4          # pinned; an emptied table must FAIL
MC_SEED, MC_DRAWS = 20260814, 8_000_000  # from gen_kappa_and_taxonomy.py


def kappa(r):
    return (r - 1) ** 2 / (r * math.log(r))


def table_body(tex, label):
    for m in re.finditer(r"\\begin\{table\}(.*?)\\end\{table\}", tex, re.S):
        if ("\\label{%s}" % label) in m.group(1):
            body = m.group(1)
            break
    else:
        raise SystemExit("%s not found" % label)
    return re.sub(r"\\caption\{(?:[^{}]|\{[^{}]*\})*\}", "", body, flags=re.S)


def caption_of(tex, label):
    for m in re.finditer(r"\\begin\{table\}(.*?)\\end\{table\}", tex, re.S):
        if ("\\label{%s}" % label) in m.group(1):
            c = re.search(r"\\caption\{((?:[^{}]|\{[^{}]*\})*)\}", m.group(1), re.S)
            return c.group(1) if c else ""
    return ""


def clean(cell):
    cell = re.sub(r"\\(mathbf|textbf|emph|texttt|mathrm)\{([^{}]*)\}", r"\2", cell)
    return cell.replace("$", "").replace(r"\,", "").strip()


def rows_of(body, ncols):
    out = []
    for raw in body.split(r"\\"):
        if "tabular" in raw or "label" in raw:
            continue
        cells = [re.sub(r"\\(top|mid|bottom)rule|\\addlinespace", "",
                        clean(c)).strip() for c in raw.split("&")]
        if len(cells) == ncols:
            out.append(cells)
    return out


def floats_in(text):
    """Measurement cells only: numbers WITH a decimal point. Structural integer
    columns (bit widths, register counts, (r,M) keys) collide with the record's
    small integers by construction and identify nothing; every measured cell in
    all three candidate tables is printed with a decimal point."""
    return {float(x) for x in re.findall(r"\d+\.\d+", text)}


def rerun_sampler(r, m, n=MC_DRAWS, seed=MC_SEED):
    """gen_kappa_and_taxonomy.py's sampler, verbatim."""
    import numpy as np
    rng = np.random.default_rng(seed)
    s = r ** rng.random(n)                       # log-uniform on [1, r)
    step = (r - 1) * 2.0 ** -m
    q = np.round((s - 1) / step) * step + 1.0
    return float(np.mean(np.abs(q - s) / s))


def main():
    rec = json.loads(REC.read_text())
    tex = PAPER.read_text()
    # prose phrases are matched against whitespace-normalised source, so a LaTeX
    # line break inside a phrase ("one\nrequires probes...") cannot hide it
    tex = re.sub(r"\s+", " ", tex)
    bad = []
    cells_ok = cells_total = 0

    def cell(desc, ok):
        nonlocal cells_ok, cells_total
        cells_total += 1
        if ok:
            cells_ok += 1
        else:
            bad.append(desc)
        return ok

    # ---- rule 1: the record's own metadata, before any similarity argument ----
    tax = rec["taxonomy"]
    print("record metadata: prefactor=%r, status=%r, draws=%d, "
          "closes_on_catalogue=%r" % (rec["prefactor"], rec["prefactor_status"],
                                      rec["monte_carlo_draws"],
                                      tax["closes_on_catalogue"]))
    print("generator gen_kappa_and_taxonomy.py: CHECK 1 = thm:scaleradix "
          "prefactor, CHECK 2 = taxonomy closure -- neither is a perplexity or "
          "an FPGA number\n")

    # ---- record-internal identities, asserted before any cell is judged ----
    k2, k3 = kappa(2), kappa(3)
    if abs(rec["kappa"]["2"] - k2) > 5e-8 or abs(rec["kappa"]["3"] - k3) > 5e-8:
        bad.append("record kappa fields do not reproduce (r-1)^2/(r ln r) to "
                   "half an ulp of their 7-decimal storage")
    if rec["kappa"]["ratio_3_over_2"] != round(k3 / k2, 4):
        bad.append(f"record ratio_3_over_2 {rec['kappa']['ratio_3_over_2']!r} != "
                   f"round(kappa(3)/kappa(2), 4) = {round(k3 / k2, 4)!r}")
    rows = {(r["r"], r["M"]): r for r in rec["rows"]}
    if set(rows) != {(2, 8), (2, 11), (3, 8), (3, 11)}:
        raise SystemExit(f"FAIL: record rows keyed {sorted(rows)}, "
                         "expected the four (r,M) crossings")
    for (r, m), row in sorted(rows.items()):
        pred = 0.25 * kappa(r) * 2.0 ** -m
        if row["predicted_quarter_kappa"] != float(f"{pred:.4e}"):
            bad.append(f"row ({r},{m}): stored prediction "
                       f"{row['predicted_quarter_kappa']!r} != (1/4)kappa({r})"
                       f"2^-{m} at the record's 5-significant-digit storage")
        emp = rerun_sampler(r, m)
        if row["empirical"] != float(f"{emp:.4e}"):
            bad.append(f"row ({r},{m}): stored empirical {row['empirical']!r} "
                       f"does not re-derive from the generator's sampler "
                       f"(re-run gives {emp:.4e})")
        if row["ratio"] != round(pred / emp, 4):
            bad.append(f"row ({r},{m}): stored ratio {row['ratio']!r} != "
                       f"round(pred/emp, 4) = {round(pred / emp, 4)!r}")
        print(f"  ({r},{m:2d}): sampler re-run {emp:.4e} == stored "
              f"{row['empirical']:.4e}; (1/4)kappa*2^-M = {pred:.4e}; "
              f"ratio {row['ratio']}")
    print("record identities: kappa, predictions, ratios hold; all four "
          "empirical means re-derive bit-for-bit (numpy default_rng, "
          f"seed {MC_SEED}, {MC_DRAWS} draws)")
    cls = tax["classes"]
    closure = (tax["no_exponent"] + tax["too_narrow"] + tax["too_wide_to_probe"]
               + tax["classified"])
    if closure != tax["catalogue"] or sum(cls.values()) != tax["classified"] \
            or cls["geometric"] != len(tax["geometric_members"]):
        bad.append("taxonomy closure broken inside the record itself")
    n_takum = sum(m.startswith("takum") for m in tax["geometric_members"])
    n_tekum = sum(m.startswith("tekum") for m in tax["geometric_members"])
    print(f"taxonomy closure: {tax['no_exponent']}+{tax['too_narrow']}+"
          f"{tax['too_wide_to_probe']}+{tax['classified']} = {closure} = "
          f"catalogue {tax['catalogue']}; classes sum {sum(cls.values())}; "
          f"geometric = {n_takum} takum + {n_tekum} tekum")
    if bad:
        print("\nFAIL: record-internal identities broken\n" + "\n".join(bad))
        return 1

    # ================= adjudication: the three fielded candidates =================
    print("\n-- ADJUDICATION: the provenance candidates --")
    rec_floats = ({round(k2, 7), round(k3, 7), round(k2, 5), round(k3, 5),
                   rec["kappa"]["ratio_3_over_2"]}
                  | {r["empirical"] for r in rec["rows"]}
                  | {r["predicted_quarter_kappa"] for r in rec["rows"]}
                  | {r["ratio"] for r in rec["rows"]})
    for label, min_floats in (("tab:geoscale", 6), ("tab:fourfam", 8),
                              ("tab:allscales", 10)):
        cand = floats_in(table_body(tex, label))
        if len(cand) < min_floats:   # guard: an unparsed candidate proves nothing
            raise SystemExit(f"FAIL: parsed only {len(cand)} measurement cells "
                             f"from {label}; adjudication would be vacuous")
        overlap = cand & rec_floats
        degenerate = overlap <= {1.0}
        print(f"{label}: {len(cand)} measurement cells, e.g. "
              f"{sorted(cand)[:4]} ... ; overlap with record = "
              f"{sorted(overlap) or 'NONE'}"
              + (" (only the degenerate 1.000: fp32's ratio to itself vs the "
                 "record's pred/emp ratio at (3,8) -- any self-consistent pair "
                 "prints it; it identifies nothing)" if overlap and degenerate
                 else ""))
        if not degenerate:
            bad.append(f"{label} unexpectedly shares {sorted(overlap)} with the record")
    print("-> none of the three candidates contains a single number this "
          "record can produce; all three are NOT backed by it")

    # ================= reconstruction 1: tab:taxonomy =================
    print("\n-- tab:taxonomy: full reconstruction, matched by class key --")
    body_rows = [r for r in rows_of(table_body(tex, "tab:taxonomy"), 4)
                 if r[0] in cls]
    if len(body_rows) != EXPECTED_TAXONOMY_ROWS:
        raise SystemExit(f"FAIL: parsed {len(body_rows)} printed taxonomy rows, "
                         f"expected {EXPECTED_TAXONOMY_ROWS} -- either the table "
                         "changed or the parser broke; neither may pass silently")
    for r in body_rows:
        form, count = r[0], int(r[2])
        cell(f"tab:taxonomy key {form!r} present in record classes", form in cls)
        cell(f"tab:taxonomy {form} count: printed {count}, record {cls[form]}",
             count == cls[form])
        note = ""
        if form == "geometric":
            m = re.search(r"takum\s*\\times\s*(\d+),\s*tekum\s*\\times\s*(\d+)",
                          r[3])
            cell("tab:taxonomy geometric members cell 'takum x4, tekum x3' vs "
                 "record member list", bool(m) and int(m.group(1)) == n_takum
                 and int(m.group(2)) == n_tekum)
            cells_total += 1  # the second number of the split
            cells_ok += bool(m) and int(m.group(2)) == n_tekum
            note = f"  <- {n_takum} takum + {n_tekum} tekum in the record"
        print(f"  {form:<10} count {count} == record {cls[form]}{note}")

    cap = caption_of(tex, "tab:taxonomy")
    cell("caption 'member list of seven' == record list length",
         "member list of seven" in cap and len(tax["geometric_members"]) == 7)
    cell("caption names takum8/16/32/64",
         "takum8/16/32/64" in cap and
         [m for m in tax["geometric_members"] if m.startswith("takum")]
         == ["takum8", "takum16", "takum32", "takum64"])
    cell("caption names tekum8/16/32",
         "tekum8/16/32" in cap and
         [m for m in tax["geometric_members"] if m.startswith("tekum")]
         == ["tekum8", "tekum16", "tekum32"])
    cell("caption: earlier draft's geometric 8 'disagreed by exactly that one "
         "entry' -- 8 = record's 7 + 1 and 84 = catalogue + 1",
         "read $8$ in an earlier draft" in cap
         and 8 == cls["geometric"] + 1)
    print("caption: member list of seven == record list; takum8/16/32/64 and "
          "tekum8/16/32 verbatim; the earlier draft's 8 is the record's 7+1")

    # ---- adjacent prose (sec:taxonomy), conditional on each phrase (rule 5) ----
    cell("prose 'Of the 83 entries, 11 are integer'",
         "Of the 83 entries, 11 are integer" in tex
         and tax["catalogue"] == 83 and tax["no_exponent"] == 11)
    cell("prose 'the remaining 72' == 83 - 11",
         "the remaining 72, 18 span fewer" in tex
         and tax["catalogue"] - tax["no_exponent"] == 72
         and tax["too_narrow"] == 18)
    cell("prose 'one requires probes wider than we generated'",
         "one requires probes wider than we generated" in tex
         and tax["too_wide_to_probe"] == 1)
    cell("prose 'That leaves $53$ classified' and 'sum to $53$'",
         "That leaves $53$ classified" in tex and "sum to $53$" in tex
         and tax["classified"] == 53 and sum(cls.values()) == 53)
    cell("prose 'the total closes on $83$' == record closes_on_catalogue",
         "the total closes on $83$" in tex and tax["closes_on_catalogue"]
         and closure == 83)
    print("sec:taxonomy prose: 83 / 11 / 72 / 18 / one / 53 / 53 / closes-on-83 "
          "all recompute from the record")

    # ================= reconstruction 2: thm:scaleradix + prefactor prose =================
    print("\n-- thm:scaleradix and the quarter-prefactor paragraph --")
    cell("theorem prints kappa(2) = 0.72135 (record to 5 places)",
         r"\kappa(2) = 0.72135" in tex and round(k2, 5) == 0.72135)
    cell("theorem prints kappa(3) = 1.21365 (record to 5 places)",
         r"\kappa(3) = 1.21365" in tex and round(k3, 5) == 1.21365)
    cell("theorem/corollary print kappa(3)/kappa(2) = 1.6825 == record ratio",
         r"\kappa(3)/\kappa(2) = 1.6825" in tex
         and rec["kappa"]["ratio_3_over_2"] == 1.6825)
    cell("cor:scaleradix proof digits 0.721347.../1.213652... truncate the record",
         r"\kappa(2)=0.721347\ldots" in tex and r"\kappa(3)=1.213652\ldots" in tex
         and f"{k2:.8f}".startswith("0.721347")
         and f"{k3:.8f}".startswith("1.213652"))
    cell("prose: quarter prefactor '\\tfrac14\\kappa' == record 'one quarter'",
         r"\tfrac14\kappa(r)\,2^{-M}" in tex and rec["prefactor"] == "one quarter")
    cell("prose: '$8\\times10^{6}$ log-uniform draws' == record draw count",
         r"$8\times10^{6}$ log-uniform draws" in tex
         and rec["monte_carlo_draws"] == 8_000_000)
    cell("prose: 7.0471e-4 at (2,8) == record empirical",
         r"returns $7.0471\times10^{-4}$" in tex and "$(r,M)=(2,8)$" in tex
         and rows[(2, 8)]["empirical"] == 7.0471e-4)
    cell("prose: predicted 7.0444e-4 == record row (2,8)",
         r"\tfrac14\kappa(2)2^{-8} = 7.0444\times10^{-4}" in tex
         and rows[(2, 8)]["predicted_quarter_kappa"] == 7.0444e-4)
    cell("prose: 1.4822e-4 at (3,11) == record empirical",
         r"$1.4822\times10^{-4}$ at $(3,11)$" in tex
         and rows[(3, 11)]["empirical"] == 1.4822e-4)
    cell("prose: predicted 1.4815e-4 == record row (3,11)",
         "1.4815\\times10^{-4}$" in tex
         and rows[(3, 11)]["predicted_quarter_kappa"] == 1.4815e-4)
    cell("prose: '[measured --- software]' == record prefactor_status",
         "[measured --- software]" in tex
         and rec["prefactor_status"] == "[measured -- software]")
    # 'confirmed to four figures': at 8e6 draws the Monte-Carlo standard error of
    # the mean is ~2.5e-4 relative, so the claim is that the pred/emp ratio is
    # unity to within noise at the fourth figure: |ratio - 1| <= 5e-4 (2 SE).
    dev = {k: abs(rows[k]["ratio"] - 1.0) for k in ((2, 8), (3, 11))}
    cell("prose 'confirmed to four figures': |pred/emp - 1| <= 5e-4 (2 MC "
         "standard errors) at both printed crossings",
         "confirmed to four figures" in tex and all(d <= 5e-4 for d in dev.values()))
    print(f"kappa digits, ratio, quarter prefactor, 8e6 draws, and both printed "
          f"(empirical, predicted) pairs reproduce; 'four figures' holds as "
          f"|ratio-1| = {dev[(2, 8)]:.1e} and {dev[(3, 11)]:.1e}, both <= 5e-4 "
          f"(~2 Monte-Carlo standard errors at 8e6 draws)")

    print(f"\ncells/claims: {cells_ok}/{cells_total} reproduce at printed precision")

    # ================= rule 6: the selection =================
    print("\nNOTE -- record content not printed anywhere in the paper:")
    for key in ((2, 11), (3, 8)):
        row = rows[key]
        # check the significand digits as the paper would print them
        sig = f"{row['empirical']:.4e}".split("e")[0]   # e.g. '8.8088'
        printed = sig in tex
        status = "PRINTED (unexpected)" if printed else "unprinted"
        print(f"  row (r={key[0]}, M={key[1]}): empirical {row['empirical']:.4e}, "
              f"ratio {row['ratio']} -- {status}")
        if printed:
            bad.append(f"selection: row {key} thought unprinted but its "
                       f"significand {sig} appears in the paper")
    print("  the hidden half of the 2x2 confirms rather than damages: ratios "
          "0.9996 and 1.0000, the same agreement the printed half shows. The "
          "paper prints only the diagonal (2,8) and (3,11); the record ran the "
          "full crossing.")

    # ================= verdict =================
    if bad:
        print(f"\nFAIL: {len(bad)} mismatch(es)\n")
        for b in bad:
            print(f"  {b}")
        return 1
    print("\nOK: the record backs tab:taxonomy (every count, key and the "
          "caption's member list) and the thm:scaleradix quarter-prefactor "
          "prose (every printed constant and Monte-Carlo value, with the "
          "empirical means re-derived bit-for-bit). It backs NONE of the three "
          "provenance candidates: tab:geoscale, tab:fourfam and tab:allscales "
          "share no non-degenerate number with it. fig:canon-taxonomy's caption "
          "('the counts they resolve the catalogue into') describes the same "
          "counts and is backed transitively.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
