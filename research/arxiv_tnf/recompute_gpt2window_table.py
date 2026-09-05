#!/usr/bin/env python3
"""Regenerate Table `tab:gpt2window` from measurements/gpt2_window_2026-08-13e.json.

The record holds TWO weight-tensor objects (h.0.attn.c_proj.weight in full, a
1e6-value slice of h.0.mlp.c_fc.weight); the table prints both, six data cells
each, twelve data cells total.  Every other numeral in the table environment is
header material (the 99.9 percentile label, the 4 and 8 of TNF(4,8), five 16s,
two log-base 2s) and is never compared against the record.

RULES APPLIED (each paid for by an earlier regenerator):
  * rows are matched BY KEY -- the tensor name, with `\\_` unescaped and the
    record's `.weight` / `(slice)` suffixes stripped -- never by position;
  * columns are IDENTIFIED, not assumed: the record carries
        ratio_vs_takum    == takum16  / tnf16phys
        ratio_vs_binary16 == binary16 / tnf16phys
    and both identities are ASSERTED to 1e-9 before any cell is judged, which
    pins the TNF column to `tnf16phys` (not `tnf_nominal`);
  * comparison happens AT THE PRECISION THE TABLE PRINTS: `7.02e-4` asserts
    three significant figures, `$-5.3$` asserts one decimal, exactly;
  * the caption's own claims are data: the 20,000-samples-per-tensor count, the
    no-clipping-in-any-format claim, `below 2^12`, and `both lose` are each
    recomputed from the record, over ALL record rows, printed or not;
  * a mismatch is REPORTED with printed value vs record value and the script
    exits nonzero.  tnf_paper.tex is never edited.
"""
import json
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
REC = HERE / "measurements" / "gpt2_window_2026-08-13e.json"
PAPER = HERE / "tnf_paper.tex"

COLS = ("median_log2", "p99_9_log2", "tnf16phys", "takum16", "binary16",
        "ratio_vs_takum")


def table_body_and_caption(tex):
    for m in re.finditer(r"\\begin\{table\}(.*?)\\end\{table\}", tex, re.S):
        if r"\label{tab:gpt2window}" in m.group(1):
            body = m.group(1)
            break
    else:
        raise SystemExit("tab:gpt2window not found in tnf_paper.tex")
    cap = re.search(r"\\caption\{((?:[^{}]|\{[^{}]*\})*)\}", body, re.S)
    caption = cap.group(1) if cap else ""
    # cut the caption BEFORE parsing rows: its numbers are not cells
    body = body.replace(cap.group(0), "") if cap else body
    return body, caption


def clean_cell(c):
    c = re.sub(r"\\mathrm\{e\}\{(-?\d+)\}", r"e\1", c)
    c = re.sub(r"\\(textbf|emph|texttt)\{([^{}]*)\}", r"\2", c)
    c = c.replace("$", "").replace(r"\,", "").replace(r"\hline", "").strip()
    return c


def printed_rows(body):
    rows = []
    for raw in body.split(r"\\"):
        cells = [c.strip() for c in raw.split("&")]
        if len(cells) != 7:
            continue
        if any("tabular" in c or "label" in c for c in cells):
            continue
        name = clean_cell(cells[0]).replace(r"\_", "_")
        if not name.startswith("h.0."):
            continue  # header rows ('tensor', the log_2|w| units line)
        texts = [clean_cell(c) for c in cells[1:7]]
        try:
            vals = [float(t) for t in texts]
        except ValueError:
            continue
        rows.append({"tensor": name, "texts": texts, "vals": vals})
    return rows


def matches_printed(record_value, printed_text):
    """round(record, printed precision) == printed, exactly (from the STRING,
    not from float repr, which folds 1.78e-4 into 0.000178 and loses the
    significant-figure count)."""
    t = printed_text.lower()
    if "e" in t:
        mant = t.split("e")[0].lstrip("+-")
        sig = len(mant.replace(".", ""))
        return float(f"{record_value:.{sig - 1}e}") == float(t)
    dec = len(t.split(".")[1]) if "." in t else 0
    return round(record_value, dec) == float(t)



def _row_guard(printed_count, expected=2):
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
    body, caption = table_body_and_caption(PAPER.read_text())
    printed = printed_rows(body)
    print(f"record rows {len(rec)}   printed rows {len(printed)}   "
          f"data cells {6 * len(printed)}")
    _row_guard(len(printed))

    bad = []

    # ---- key-based join: printed tensor name is a prefix of the record's ----
    def rec_key(r):
        return r["tensor"].replace(".weight", "").replace("(slice)", "").strip()

    index = {rec_key(r): r for r in rec}
    matched = set()
    pairs = []
    for p in printed:
        hits = [k for k in index if k == p["tensor"] or k.startswith(p["tensor"])]
        if len(hits) != 1:
            bad.append(f"printed row {p['tensor']}: {len(hits)} record rows match")
            continue
        matched.add(hits[0])
        pairs.append((p, index[hits[0]]))
    unprinted = [(k, index[k]) for k in index if k not in matched]

    # ---- column identities asserted BEFORE any value is judged (1e-9) ----
    for k, r in index.items():
        e = r["err"]
        if abs(r["ratio_vs_takum"] - e["takum16"] / e["tnf16phys"]) > 1e-9:
            bad.append(f"{k}: record ratio_vs_takum != takum16/tnf16phys")
        if abs(r["ratio_vs_binary16"] - e["binary16"] / e["tnf16phys"]) > 1e-9:
            bad.append(f"{k}: record ratio_vs_binary16 != binary16/tnf16phys")

    # ---- the twelve data cells, at printed precision ----
    n_ok = 0
    for p, r in pairs:
        record_vals = [r["stats"]["median"], r["stats"]["p99_9"],
                       r["err"]["tnf16phys"], r["err"]["takum16"],
                       r["err"]["binary16"], r["ratio_vs_takum"]]
        for col, text, rv in zip(COLS, p["texts"], record_vals):
            if matches_printed(rv, text):
                n_ok += 1
            else:
                bad.append(f"{p['tensor']} {col}: printed {text}, "
                           f"record {rv!r} (prints as "
                           f"{'%.*e' % (len(text.split('e')[0].replace('.', '').lstrip('+-')) - 1, rv) if 'e' in text else round(rv, len(text.split('.')[1]) if '.' in text else 0)})")
    print(f"cells reproducing at printed precision: {n_ok} / {6 * len(pairs)}")

    # ---- the caption's own claims are data ----
    m = re.search(r"\$(\d+)\{,\}(\d+)\$\s*sampled", caption)
    if not m:
        bad.append("caption: sample-count claim not found where expected")
    else:
        claimed = int(m.group(1) + m.group(2))
        for k, r in index.items():
            if r["sampled"] != claimed:
                bad.append(f"caption says {claimed} sampled per tensor; "
                           f"{k} record has sampled={r['sampled']}")
    if "no clipping" in caption:
        for k, r in index.items():
            for fmt, n in r["clips"].items():
                if n != 0:
                    bad.append(f"caption says no clipping in any format; "
                               f"{k} {fmt} clips {n} of {r['sampled']}")
    else:
        bad.append("caption: no-clipping claim not found where expected")
    if re.search(r"below \$2\^\{12\}\$", caption):
        for k, r in index.items():  # the whole record, not only printed rows
            if not r["stats"]["p99_9"] < 12.0:
                bad.append(f"caption says both sit below 2^12; {k} p99.9 "
                           f"log2|w| = {r['stats']['p99_9']}")
    else:
        bad.append("caption: below-2^12 claim not found where expected")
    if "both lose" in caption:
        for k, r in index.items():
            if not (r["ratio_vs_takum"] < 1.0 and r["ratio_vs_binary16"] < 1.0):
                bad.append(f"caption says both lose; {k} ratios "
                           f"{r['ratio_vs_takum']:.3f} / "
                           f"{r['ratio_vs_binary16']:.3f}")
    else:
        bad.append("caption: both-lose claim not found where expected")

    if unprinted:
        print(f"\nNOTE -- {len(unprinted)} record row(s) not printed:")
        for k, r in unprinted:
            print(f"  {k}  (ratio_vs_takum {r['ratio_vs_takum']:.3f})")
    else:
        print("\nNOTE -- every record row is printed; the table is the whole "
              "record, not a selection")

    if bad:
        print(f"\nFAIL: {len(bad)} mismatch(es)\n")
        for b in bad:
            print(f"  {b}")
        return 1
    print(f"\nOK: all {6 * len(pairs)} printed data cells reproduce at printed "
          "precision, both ratio identities hold to 1e-9, and the caption's "
          "sample-count / no-clipping / below-2^12 / both-lose claims recompute "
          "true over the whole record")
    return 0


if __name__ == "__main__":
    sys.exit(main())
