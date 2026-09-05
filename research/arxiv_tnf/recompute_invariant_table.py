#!/usr/bin/env python3
"""Regenerate Table `tab:invariant` from measurements/strict_range_2026-08-13g.json.

The table had no regenerator: 71 numeric cells with nothing a reader could run
against them. It does not need a re-measurement, because the record already
holds the table -- the table is a FILTERED VIEW of it.

    rows in the record                                        180
    pair == "TNF(4,8)/takum16"                                 60
    ... and comparable == true                                 30   <- the table

Thirty selected rows for thirty printed rows, no leftovers. Columns are
`shape`, `D`, `tnf_err`, `ratio` -- note the THIRD column is the TNF error, not
the takum one, and `ratio == takum_err / tnf_err` holds to 1e-9 on all thirty
rows, which is how the column was identified rather than assumed. The record's
shape names are short (`uniform`, `gauss`); the table prints presentation names
(`log-uniform`, `Gaussian`).

WHY THIS FILE EXISTS RATHER THAN A MATCH-FRACTION CHECK. Scoring this record
against the table by numeric overlap says it covers 100% of the cells -- and so
it does, while holding 563 distinct numbers and covering most of the paper. A
size-corrected score then RANKS IT THIRD and rejects it, because two thirds of
the record belong to other pairs. Both statistics are wrong about this table for
opposite reasons. Reconstruction is not a statistic: either the thirty rows come
back or they do not.

THE TYPOGRAPHIC LOCK. The caption marks wins in bold and exact ties with a
dagger. At the record's own tolerance of 0.02 the thirty rows split 12 / 4 / 14,
and the table prints 12 bold, 4 daggered and 14 plain. A row's FORMATTING is
therefore also checked, which no numeric comparison would have caught -- and it
is what caught a parser here that silently dropped the four daggered rows and
still reported a plausible-looking 26-row agreement.
"""
import json
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
REC = HERE / "measurements" / "strict_range_2026-08-13g.json"
PAPER = HERE / "tnf_paper.tex"
PAIR = "TNF(4,8)/takum16"
TIE = 0.02
SHAPE = {"uniform": "log-uniform", "gauss": "Gaussian",
         "laplace": "Laplace", "bimodal": "bimodal"}


def selected(record):
    rows = [r for r in record["rows"]
            if r["pair"] == PAIR and r.get("comparable") is True]
    return rows


def printed_rows(tex):
    for m in re.finditer(r"\\begin\{table\}(.*?)\\end\{table\}", tex, re.S):
        if r"\label{tab:invariant}" in m.group(1):
            body = m.group(1)
            break
    else:
        raise SystemExit("tab:invariant not found")
    body = re.sub(r"\\caption\{(?:[^{}]|\{[^{}]*\})*\}", "", body, flags=re.S)
    out = []
    for raw in body.split(r"\\"):
        cells = [c.strip() for c in raw.split("&")]
        if len(cells) < 4:
            continue
        shape = re.sub(r"\\hline|[{}\\]", "", cells[0]).strip()
        if not shape:
            continue
        # A daggered cell carries the mark INSIDE it; strip marks before parsing
        # but remember them -- they are part of what is being checked.
        bold = r"\textbf" in raw
        dagger = "dagger" in raw
        vals = []
        for c in cells[1:4]:
            c = re.sub(r"\\textbf\{(.*?)\}", r"\1", c)
            c = re.sub(r"\^?\{?\\d?dagger\}?", "", c)
            c = re.sub(r"\\mathrm\{e\}\{(-?\d+)\}", r"e\1", c)
            c = c.replace("$", "").replace(r"\,", "").strip()
            try:
                vals.append(float(c))
            except ValueError:
                vals.append(None)
        if len(vals) == 3 and all(v is not None for v in vals):
            out.append({"shape": shape, "vals": vals, "bold": bold, "dagger": dagger})
    return out


def at_printed_precision(value, printed):
    """Compare at the precision the table actually shows, not at a fixed tolerance.

    A cell printed as 0.282 asserts three decimals; comparing it to 0.28234 at a
    1% band would pass a value the table does not claim, and comparing at full
    precision would fail every correctly rounded cell.
    """
    s = repr(printed)
    if "e" in s or "E" in s:
        mant = s.split("e")[0].lstrip("-")
        sig = len(mant.replace(".", "").rstrip("0")) or 1
        if value == 0:
            return printed == 0
        from math import floor, log10
        q = round(value, -int(floor(log10(abs(value)))) + (sig - 1))
        return q == printed
    dec = len(s.split(".")[1]) if "." in s else 0
    return round(value, dec) == printed


def main():
    rec = json.loads(REC.read_text())
    rows = selected(rec)
    printed = printed_rows(PAPER.read_text())

    print(f"record rows {len(rec['rows'])}  pair={PAIR} & comparable  ->  {len(rows)}")
    print(f"printed data rows                                        ->  {len(printed)}")
    if len(rows) != len(printed):
        print(f"FAIL: {len(rows)} selected rows against {len(printed)} printed rows")
        return 1

    bad = []
    for r, p in zip(rows, printed):
        want_shape = SHAPE.get(r["shape"], r["shape"])
        if want_shape != p["shape"]:
            bad.append(f"shape: printed {p['shape']!r} record {r['shape']!r}")
            continue
        # The ratio the table prints must be the two errors it also prints.
        if r["tnf_err"] and abs(r["ratio"] - r["takum_err"] / r["tnf_err"]) > 1e-9:
            bad.append(f"{r['shape']}: ratio {r['ratio']} != takum_err/tnf_err")
        for got, exp, name in zip(p["vals"], (r["D"], r["tnf_err"], r["ratio"]),
                                  ("D", "tnf_err", "ratio")):
            if not at_printed_precision(exp, got):
                bad.append(f"{r['shape']} {name}: printed {got} record {exp}")
        want_bold = r["ratio"] > 1 + TIE
        want_dag = abs(r["ratio"] - 1) <= TIE
        if p["bold"] != want_bold:
            bad.append(f"{r['shape']}: bold={p['bold']} but ratio={r['ratio']}")
        if p["dagger"] != want_dag:
            bad.append(f"{r['shape']}: dagger={p['dagger']} but ratio={r['ratio']}")

    w = sum(1 for r in rows if r["ratio"] > 1 + TIE)
    t = sum(1 for r in rows if abs(r["ratio"] - 1) <= TIE)
    print(f"typographic lock: record {w}/{t}/{len(rows)-w-t}  "
          f"table {sum(p['bold'] for p in printed)}/{sum(p['dagger'] for p in printed)}/"
          f"{sum(1 for p in printed if not p['bold'] and not p['dagger'])}"
          "   (wins/ties/losses)")

    # The caption states the sample count; the record carries it.
    tex = PAPER.read_text()
    m = re.search(r"\\label\{tab:invariant\}", tex)
    cap = tex[max(0, m.start() - 2000):m.start()]
    cm = re.search(r"\$(\d+)\$ samples per row", cap)
    if cm and int(cm.group(1)) != rec["n"]:
        bad.append(f"caption says {cm.group(1)} samples per row; record n={rec['n']}")

    if bad:
        print(f"\nFAIL: {len(bad)} mismatch(es)\n")
        for b in bad:
            print(f"  {b}")
        return 1
    print(f"\nOK: {len(printed)} rows, {3*len(printed)} cells, formatting and sample count agree")
    return 0


if __name__ == "__main__":
    sys.exit(main())
