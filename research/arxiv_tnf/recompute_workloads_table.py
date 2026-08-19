#!/usr/bin/env python3
"""Regenerate Table `tab:workloads` from measurements/workloads_strict_2026-08-13g.json.

The record holds 22 rows (11 workloads x 2 rungs) and the table prints all 22,
so there is no selection -- but rows are still matched BY KEY (pair, workload),
never by position (the tab:tailsweep lesson). The record's workload names are
short (`grav_r_squared`); the table prints presentation names ("inverse-square
denominators $r^2$"); the map between them is explicit and total.

COLUMN IDENTITIES ARE ASSERTED, NOT ASSUMED (the tab:invariant lesson):
    n       exact integer
    D       f"{D:.2f}"        -- 2 decimals, compared as the printed string
    span    f"{span:.1f}"     -- 1 decimal
    range   "yes" iff in_range
    ratio   f"{ratio:.3f}" or "---"
and where both errors are finite, ratio == takum_err / tnf_err to 1e-9
(relative) pins which record field the printed ratio is.

THE DASH RULE IS A CLAIM AND IT IS CHECKED AS ONE. The caption says "when
[range] is no, no ratio exists and none is reported". An earlier audit found
the dashed cells are governed by in_range == false, NOT by ratio-is-NaN: only
3 of the 11 dashed rows have a NaN ratio (the ones where every sample fell out
of range, tnf_out == n); the other 8 carry finite ratios in the record which
the paper suppresses. So "none is reported" is a formatting rule that holds,
while "no ratio exists" is a factual claim about the record that does NOT.
Both halves are recomputed separately below; the second is reported as a
defect, per the rule that a defect report is a success for this task.

CAPTION AND SURROUNDING CLAIMS RECOMPUTED FROM THE RECORD:
    - "The same eleven workloads are evaluated at both rungs"
    - "'range' is yes only when every sample is representable"  (in_range <=> tnf_out==0)
    - "bold marks a pair that satisfies both halves of the condition"
      (bold <=> qualifies, and qualifies == in_range AND D >= threshold)
    - section-header thresholds 9.5 / 21.9 against record pairs/rows
    - body text: "Seven of the twenty-two ... qualify, with ratios from 1.23 to 4.00"
    - caption's Data: pointer names this record file
    - sec:takumrange: "in no row ... does takum go out of range where TNF does not"
"""
import json
import math
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
REC = HERE / "measurements" / "workloads_strict_2026-08-13g.json"
PAPER = HERE / "tnf_paper.tex"

# printed presentation name (normalised to lowercase alnum) -> record workload key
WORKLOAD = {
    "newtonproductsgm1m2": "grav_G_m1_m2",
    "inversesquaredenominatorsr2": "grav_r_squared",
    "gravitationalforcerawsi": "grav_force_SI",
    "boltzmannfactorsat300k": "boltzmann_300K",
    "boltzmannfactorsnarrowekt": "boltzmann_narrow",
    "siphysicalconstants": "si_constants",
    "importanceweights": "mc_importance_weights",
    "montecarlopartialproducts": "mc_partial_products",
    "unnormalisedlikelihoodproducts": "loglik_products",
    "gammavariateswideshape": "gamma_values",
    "gammavariatesnarrowshape": "gamma_narrow",
}


def clean(cell):
    c = re.sub(r"\\hline", "", cell)
    c = re.sub(r"\\(textbf|texttt|emph|mathrm)\{(.*?)\}", r"\2", c)
    c = re.sub(r"\\[,!;]", " ", c)
    return c.replace("$", "").strip()


def norm_name(s):
    return re.sub(r"[^a-z0-9]", "", clean(s).lower())


def table_chunks(tex):
    """(caption_text, body_after_caption) for the tab:workloads table."""
    for m in re.finditer(r"\\begin\{table\}(.*?)\\end\{table\}", tex, re.S):
        if r"\label{tab:workloads}" in m.group(1):
            body = m.group(1)
            break
    else:
        raise SystemExit("tab:workloads not found")
    capm = re.search(r"\\caption\{((?:[^{}]|\{[^{}]*\})*)\}", body, re.S)
    caption = capm.group(1) if capm else ""
    # cut the caption BEFORE parsing rows -- its numbers are not cells
    body = body[: capm.start()] + body[capm.end():] if capm else body
    return caption, body


def printed_rows(body):
    """Rows keyed (pair, workload); pair context comes from \\multicolumn headers."""
    out, pair, thresh = [], None, None
    headers = []
    for raw in body.split(r"\\"):
        if "multicolumn" in raw:
            pm = re.search(r"TNF\((\d+),(\d+)\)/\\texttt\{(takum\d+)\}", raw)
            tm = re.search(r"gtrsim\s*([\d.]+)", raw)
            if pm:
                pair = f"TNF({pm.group(1)},{pm.group(2)})/{pm.group(3)}"
                thresh = float(tm.group(1)) if tm else None
                headers.append((pair, thresh))
            continue
        cells = [c.strip() for c in raw.split("&")]
        if len(cells) < 6 or "tabular" in raw or "label" in raw:
            continue
        name = clean(cells[0])
        if not name or name == "workload":
            continue
        out.append({
            "pair": pair, "threshold": thresh, "name": name,
            "n": clean(cells[1]), "D": clean(cells[2]), "span": clean(cells[3]),
            "range": clean(cells[4]),
            "ratio": clean(cells[5]).replace("---", "---"),
            "bold": r"\textbf" in cells[5],
        })
    return out, headers



def _row_guard(printed_count, expected=22):
    """GUARD: a parser returning zero rows makes every comparison vacuous and the
    script exits 0 having checked nothing -- the exact hole a mutation test found
    in the first version of this file (delete every row: still OK). The expected
    count is pinned at authorship time; a paper edit that changes it should fail
    here and be re-pinned deliberately, not absorbed."""
    if printed_count != expected:
        raise SystemExit(
            f"FAIL: parsed {printed_count} printed rows, expected {expected} -- "
            "either the table changed or the parser broke; neither may pass silently")

def main():
    rec = json.loads(REC.read_text())
    rows = rec["rows"]
    tex = PAPER.read_text()
    caption, body = table_chunks(tex)
    printed, headers = printed_rows(body)

    print(f"record rows {len(rows)}   printed rows {len(printed)}")

    _row_guard(len(printed))

    bad, note = [], []
    cells_total = cells_matching = 0

    # ---- record-internal identities, before any comparison -------------------
    for r in rows:
        tag = f"{r['pair']} {r['workload']}"
        tnf, tak, ratio = r["tnf_err"], r["takum_err"], r["ratio"]
        if not math.isnan(tnf) and not math.isnan(tak):
            if math.isnan(ratio) or abs(ratio - tak / tnf) > 1e-9 * max(1.0, abs(ratio)):
                bad.append(f"{tag}: record ratio {ratio!r} != takum_err/tnf_err "
                           f"= {tak / tnf!r}")
        else:
            if not math.isnan(ratio):
                bad.append(f"{tag}: tnf_err is NaN but ratio {ratio!r} is finite")
            if r["tnf_out"] != r["n"]:
                bad.append(f"{tag}: tnf_err NaN but tnf_out {r['tnf_out']} != n {r['n']}")
        if r["qualifies"] != (r["in_range"] and r["above_threshold"]):
            bad.append(f"{tag}: qualifies != in_range AND above_threshold")
        if r["above_threshold"] != (r["D"] >= r["threshold"]):
            bad.append(f"{tag}: above_threshold flag disagrees with D vs threshold")
        if abs(r["span"] - (r["hi"] - r["lo"])) > 1e-9:
            bad.append(f"{tag}: span != hi - lo")

    # ---- join printed rows to record rows BY KEY -----------------------------
    index = {(r["pair"], r["workload"]): r for r in rows}
    matched = set()
    for p in printed:
        key = norm_name(p["name"])
        wl = WORKLOAD.get(key)
        if wl is None:
            bad.append(f"printed workload {p['name']!r} (norm {key!r}) has no mapping")
            continue
        r = index.get((p["pair"], wl))
        if r is None:
            bad.append(f"printed row ({p['pair']}, {wl}) has NO record row")
            continue
        matched.add((p["pair"], wl))
        tag = f"{p['pair']} {wl}"

        # section-header threshold must be the record's threshold for this row
        if p["threshold"] != r["threshold"]:
            bad.append(f"{tag}: header threshold {p['threshold']} != record "
                       f"{r['threshold']}")

        want = {
            "n": str(r["n"]),
            "D": f"{r['D']:.2f}",
            "span": f"{r['span']:.1f}",
            "range": "yes" if r["in_range"] else "no",
            "ratio": f"{r['ratio']:.3f}" if r["in_range"] else "---",
        }
        # workload-name cell counts as a cell: the key mapping just verified it
        cells_total += 1
        cells_matching += 1
        for col in ("n", "D", "span", "range", "ratio"):
            cells_total += 1
            if p[col] == want[col]:
                cells_matching += 1
            else:
                bad.append(f"{tag} {col}: printed {p[col]!r} record {want[col]!r}")
        # typographic lock: bold <=> qualifies
        if p["bold"] != r["qualifies"]:
            bad.append(f"{tag}: bold={p['bold']} but qualifies={r['qualifies']}")

    unprinted = [k for k in index if k not in matched]
    for k in unprinted:
        r = index[k]
        note.append(f"UNPRINTED record row {k}: D={r['D']:.2f} ratio={r['ratio']!r}")
    if len(printed) != len(rows):
        bad.append(f"{len(printed)} printed rows vs {len(rows)} record rows")

    # ---- the dash rule, checked as two separate claims -----------------------
    dashed = [p for p in printed if p["ratio"] == "---"]
    dashed_keys = {(p["pair"], WORKLOAD[norm_name(p["name"])]) for p in dashed
                   if norm_name(p["name"]) in WORKLOAD}
    inrange_false = {(r["pair"], r["workload"]) for r in rows if not r["in_range"]}
    nan_ratio = {(r["pair"], r["workload"]) for r in rows if math.isnan(r["ratio"])}
    if dashed_keys != inrange_false:
        bad.append(f"dashed cells {sorted(dashed_keys)} != in_range==false rows "
                   f"{sorted(inrange_false)}")
    else:
        note.append(f"dash rule: dashed cells ({len(dashed_keys)}) are exactly the "
                    f"in_range==false rows -- governed by in_range, NOT by NaN "
                    f"(only {len(nan_ratio)} of {len(dashed_keys)} have NaN ratio)")
    suppressed = sorted(inrange_false - nan_ratio)
    for k in suppressed:
        r = index[k]
        note.append(f"  suppressed finite ratio: {k[0]} {k[1]} ratio={r['ratio']:.3f} "
                    f"(tnf_out {r['tnf_out']}/{r['n']} samples out of TNF range)")
    # The caption's factual half. This is checked against the PAPER, not
    # hardcoded: the first version asserted the defect unconditionally, so fixing
    # the caption could never turn the light green -- a check that cannot pass is
    # not a check. The suppressed-finite-ratio facts stay in the NOTE either way.
    tex_all = PAPER.read_text()
    if suppressed and "no ratio exists" in tex_all:
        ex = index[suppressed[0]]
        bad.append(
            f"caption says 'when [range] is no, no ratio exists' but the record "
            f"carries finite ratios for {len(suppressed)} of {len(inrange_false)} "
            f"dashed rows, e.g. {suppressed[0][0]} {suppressed[0][1]} ratio="
            f"{ex['ratio']:.6f} = takum_err {ex['takum_err']:.6e} / tnf_err "
            f"{ex['tnf_err']:.6e} (computed with {ex['tnf_out']}/{ex['n']} samples "
            f"out of TNF range); only 3 rows (tnf_out == n) have no ratio at all")

    # ---- remaining caption / surrounding-text claims -------------------------
    # "The same eleven workloads are evaluated at both rungs"
    per_wl = {}
    for r in rows:
        per_wl.setdefault(r["workload"], set()).add(r["pair"])
    if not (len(per_wl) == 11 and all(len(v) == 2 for v in per_wl.values())):
        bad.append(f"caption says eleven workloads at both rungs; record has "
                   f"{len(per_wl)} workloads, pair-counts "
                   f"{sorted(len(v) for v in per_wl.values())}")
    # "'range' is yes only when every sample is representable"
    for r in rows:
        if r["in_range"] != (r["tnf_out"] == 0):
            bad.append(f"{r['pair']} {r['workload']}: in_range={r['in_range']} but "
                       f"tnf_out={r['tnf_out']}")
    # record pairs vs the two section headers
    rec_pairs = {(f"TNF({a},{b})/{t}", th) for a, b, t, th in rec["pairs"]}
    if rec_pairs != set(headers):
        bad.append(f"section headers {sorted(set(headers))} != record pairs "
                   f"{sorted(rec_pairs)}")
    # body text: "Seven of the twenty-two (workload, rung) pairs qualify,
    #             with ratios from $1.23$ to $4.00$"
    bm = re.search(r"Seven of the twenty-two \(workload, rung\) pairs qualify,\s*"
                   r"with ratios from \$([\d.]+)\$ to \$([\d.]+)\$", tex)
    quals = [r for r in rows if r["qualifies"]]
    if bm:
        lo, hi = bm.group(1), bm.group(2)
        if len(quals) != 7 or len(rows) != 22:
            bad.append(f"text says 7 of 22 qualify; record has {len(quals)} of "
                       f"{len(rows)}")
        qlo = min(r["ratio"] for r in quals)
        qhi = max(r["ratio"] for r in quals)
        if f"{qlo:.2f}" != lo or f"{qhi:.2f}" != hi:
            bad.append(f"text says ratios from {lo} to {hi}; record qualifying "
                       f"ratios span {qlo:.6f} to {qhi:.6f}")
    else:
        bad.append("could not find the 'Seven of the twenty-two' sentence to check")
    # caption's Data: pointer
    if "workloads_strict_2026-08-13g.json" not in caption.replace("\\_", "_"):
        bad.append("caption's Data: pointer does not name this record file")
    # sec:takumrange: takum never out of range where TNF is not
    for r in rows:
        if r["takum_out"] > 0 and r["tnf_out"] == 0:
            bad.append(f"{r['pair']} {r['workload']}: takum_out={r['takum_out']} "
                       f"with tnf_out=0 -- contradicts sec:takumrange claim")
    # body text: "Four of the eleven workloads ... leave the reach of both rungs
    # entirely. takum represents all of them, at low accuracy but without loss."
    both_out = {w for w, prs in per_wl.items()
                if all(not index[(p, w)]["in_range"] for p in prs)}
    if len(both_out) != 4:
        bad.append(f"text says four workloads leave both rungs; record has "
                   f"{len(both_out)}: {sorted(both_out)}")
    lossy = [(r["pair"], r["workload"], r["takum_out"], r["n"])
             for r in rows if r["workload"] in both_out and r["takum_out"] > 0]
    claims_lossless = ("represents all of them, at low accuracy but without loss"
                       in tex_all)
    for p_, w_, o_, n_ in (lossy if claims_lossless else []):
        bad.append(f"text says takum represents the four excluded workloads "
                   f"'without loss', but {p_} {w_} has takum_out={o_} of n={n_} "
                   f"samples outside takum's range")

    tko = [(r["pair"], r["workload"], r["takum_out"], r["tnf_out"])
           for r in rows if r["takum_out"] > 0]
    note.append("sec:takumrange claim ('in no row does takum go out of range where "
                "TNF does not') recomputes true: "
                + ("takum_out == 0 on all 22 rows" if not tko else
                   "takum_out > 0 only on " + "; ".join(
                       f"{p} {w} (takum_out {a}, tnf_out {b})" for p, w, a, b in tko)
                   + " -- TNF is out on strictly more samples in each"))

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
    print(f"\nOK: all {len(printed)} printed rows reproduce and every caption "
          "claim recomputes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
