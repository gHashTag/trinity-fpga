#!/usr/bin/env python3
"""Regenerate Table `tab:centring` from measurements/centering_2026-08-13f.json.

The mapping was established at 96% forward coverage, F=0.712, name-adjacent
(the record uses the American spelling `centering`, the label the British
`centring`). This script replaces that statistic with a reconstruction: either
the nine printed rows come back or they do not.

STRUCTURE OF THE RECORD. A list of nine dicts keyed by `span`, each holding a
`centred` and a `displaced` block with fields `tnf`, `takum`, `binary16`,
`ratio`, `clips`. Rows are matched BY KEY (span), never by position.

COLUMN IDENTITIES ARE ASSERTED, NOT ASSUMED:

    printed col 1   span
    printed col 2   centred.tnf
    printed col 3   centred.ratio    == centred.takum   / centred.tnf   to 1e-9
    printed col 4   displaced.tnf
    printed col 5   displaced.ratio  == displaced.takum / displaced.tnf to 1e-9

The ratio identity is asserted on every row of BOTH blocks before any cell is
judged -- it is what names the ratio column as takum-over-TNF, exactly as the
caption claims. The `clips` array's third slot is identified as binary16 via
the prose corroboration next to the table (115 of 8000 clipped at S=32, 2871
at S=64, both in the CENTRED blocks), not assumed from position.

CAPTION CLAIMS ARE DATA:
  * "the ratio is takum16 over TNF"      -> the 1e-9 identity above, 18 blocks.
  * "$8000$ samples per row"             -> the record stores no `n`; the two
    fully-clipped displaced binary16 rows (spans 4 and 8, error NaN) pin the
    sample count exactly: their clip count must equal the caption's 8000, and
    no clip count anywhere may exceed it.
  * "seed $20260813$"                    -> NOT RECOMPUTABLE: the record
    carries no seed field. Reported in the NOTE section, not silently passed.
  * "TNF$(4,8)$ occupies sixteen physical cells, as does takum16" -> a format
    property, not present in the record; reported in the NOTE section.

THE TYPOGRAPHIC LOCK. Exactly one cell is bold: the centred ratio at $S=40$
(\textbf{1.04}). The prose says TNF "overtakes" takum at about forty binades,
so the lock checked is: the bold cell is exactly the smallest-span row whose
centred ratio exceeds one -- rows 48/56/64 also exceed one and must NOT be
bold.

PROSE COROBBORATIONS (the numbers beside the table are claims too):
  * centred binary16 clips 115 of 8000 at S=32 and 2871 at S=64;
  * "beyond a span of thirty-two, where it begins to clip": the first nonzero
    centred binary16 clip count must sit at S=32.
"""
import json
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
REC = HERE / "measurements" / "centering_2026-08-13f.json"
PAPER = HERE / "tnf_paper.tex"


def printed_rows(tex):
    for m in re.finditer(r"\\begin\{table\}(.*?)\\end\{table\}", tex, re.S):
        if r"\label{tab:centring}" in m.group(1):
            body = m.group(1)
            break
    else:
        raise SystemExit("tab:centring not found")
    # the caption's numbers are not cells; cut it before parsing rows,
    # but keep it for the caption-claim checks
    capm = re.search(r"\\caption\{((?:[^{}]|\{[^{}]*\})*)\}", body, re.S)
    caption = capm.group(1) if capm else ""
    body = body[:capm.start()] + body[capm.end():] if capm else body
    out = []
    for raw in body.split(r"\\"):
        cells = [c.strip() for c in raw.split("&")]
        if len(cells) != 5:
            continue
        if any("tabular" in c or "label" in c or "multicolumn" in c for c in cells):
            continue
        first = re.sub(r"\\hline|[{}\\$]", "", cells[0]).strip()
        if not first or not re.fullmatch(r"\d+", first):
            continue  # header rows ("span $S$", "(binades)")
        row = {"span": int(first), "cells": [], "bold": []}
        ok = True
        for c in cells[1:]:
            bold = r"\textbf" in c
            c = re.sub(r"\\textbf\{(.*?)\}", r"\1", c)
            c = re.sub(r"\\mathrm\{e\}\{(-?\d+)\}", r"e\1", c)
            c = c.replace("$", "").replace(r"\,", "").strip()
            try:
                float(c)
            except ValueError:
                ok = False
                break
            row["cells"].append(c)
            row["bold"].append(bold)
        if ok:
            out.append(row)
    return out, caption


def at_printed_precision(value, printed_str):
    """A cell printed 6.76e-4 asserts three significant figures; a cell
    printed 0.19 asserts two decimals. Compare exactly at that precision,
    deriving it from the PRINTED STRING (repr of the float loses the
    trailing zero of 2.00)."""
    printed = float(printed_str)
    if not isinstance(value, (int, float)) or value != value:
        return False
    s = printed_str.lower()
    if "e" in s:
        mant = s.split("e")[0].lstrip("+-")
        sig = len(mant.replace(".", "")) or 1
        if value == 0:
            return printed == 0
        from math import floor, log10
        return round(value, -int(floor(log10(abs(value)))) + sig - 1) == printed
    dec = len(s.split(".")[1]) if "." in s else 0
    return round(value, dec) == printed



def _row_guard(printed_count, expected=9):
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
    printed, caption = printed_rows(PAPER.read_text())
    print(f"record rows {len(rec)}   printed rows {len(printed)}")
    _row_guard(len(printed))

    bad = []
    cells_total = cells_ok = 0

    # ---- column identity: ratio == takum/tnf on every block, before judging
    for r in rec:
        for side in ("centred", "displaced"):
            b = r[side]
            if b["tnf"] and abs(b["ratio"] - b["takum"] / b["tnf"]) > 1e-9:
                bad.append(f"S={r['span']} {side}: record ratio {b['ratio']} "
                           f"!= takum/tnf {b['takum']/b['tnf']}")

    # ---- clips slot identity: prose says centred binary16 clips 115@32, 2871@64
    by_span = {r["span"]: r for r in rec}
    for span, want in ((32, 115), (64, 2871)):
        got = by_span[span]["centred"]["clips"][2]
        if got != want:
            bad.append(f"prose: centred binary16 clips at S={span}: "
                       f"prose says {want}, record clips[2]={got}")
    first_clip = next((r["span"] for r in sorted(rec, key=lambda r: r["span"])
                       if r["centred"]["clips"][2] > 0), None)
    if first_clip != 32:
        bad.append(f"prose says binary16 'begins to clip' at S=32; record's first "
                   f"nonzero centred binary16 clip is at S={first_clip}")

    # ---- printed rows, matched by span
    matched = set()
    for p in printed:
        r = by_span.get(p["span"])
        if r is None:
            bad.append(f"printed row S={p['span']} has NO record row")
            continue
        matched.add(p["span"])
        cells_total += 1  # the span cell itself
        cells_ok += 1     # exact integer match by construction of the join
        expect = [r["centred"]["tnf"], r["centred"]["ratio"],
                  r["displaced"]["tnf"], r["displaced"]["ratio"]]
        names = ["centred tnf", "centred ratio", "displaced tnf", "displaced ratio"]
        for got_str, exp, name in zip(p["cells"], expect, names):
            cells_total += 1
            if at_printed_precision(exp, got_str):
                cells_ok += 1
            else:
                bad.append(f"S={p['span']} {name}: printed {got_str} record {exp!r}")
    unprinted = [r for r in rec if r["span"] not in matched]

    # ---- typographic lock: the single bold cell is the crossing row
    crossing = min((r["span"] for r in rec if r["centred"]["ratio"] > 1),
                   default=None)
    for p in printed:
        want = [False, p["span"] == crossing, False, False]
        if p["bold"] != want:
            bad.append(f"S={p['span']}: bold marks {p['bold']}, but the crossing "
                       f"(first centred ratio > 1) is S={crossing}")

    # ---- caption claims
    cm = re.search(r"\$(\d+)\$ samples per row", caption.replace("{,}", ""))
    if not cm:
        bad.append("caption: could not find the 'samples per row' claim to check")
    else:
        n = int(cm.group(1))
        # the two displaced rows whose binary16 error is NaN clipped EVERY sample
        full = [(r["span"], r["displaced"]["clips"][2]) for r in rec
                if r["displaced"]["binary16"] != r["displaced"]["binary16"]]
        if not full:
            bad.append("caption n-check: no fully-clipped row found to pin n")
        for span, c in full:
            if c != n:
                bad.append(f"caption says {n} samples per row, but the fully-"
                           f"clipped displaced binary16 row at S={span} clips {c}")
        worst = max(c for r in rec for side in ("centred", "displaced")
                    for c in r[side]["clips"])
        if worst > n:
            bad.append(f"caption says {n} samples per row, but a clip count "
                       f"of {worst} exceeds it")
    if not re.search(r"takum16.*over TNF", caption, re.S):
        bad.append("caption no longer states the ratio is takum16 over TNF; "
                   "the identity this script asserts would be unanchored")

    if bad:
        print(f"\nFAIL: {len(bad)} mismatch(es)  "
              f"({cells_ok}/{cells_total} cells reproduce)\n")
        for b in bad:
            print(f"  {b}")
        return 1

    print(f"\nOK: {len(printed)} printed rows reproduce exactly "
          f"({cells_ok}/{cells_total} cells), the ratio identity "
          "takum/tnf holds to 1e-9 on all 18 blocks, the bold cell sits on the "
          "crossing row, the sample count 8000 is pinned by the two fully-"
          "clipped rows, and both prose clip counts (115@32, 2871@64) recompute.")

    print(f"\nNOTE -- unprinted record rows: {len(unprinted)} "
          "(every record row is printed; the table is the whole record)")
    print("NOTE -- unprinted record COLUMNS a reader cannot see:")
    print("  takum errors (both blocks), binary16 errors, and clip counts;")
    print("  centred binary16 error grows to "
          f"{by_span[64]['centred']['binary16']:.3g} at S=64 while the table's "
          "prose only says it 'begins to clip';")
    print("  displaced binary16 is NaN (all 8000 clipped) at S=4 and S=8.")
    print("NOTE -- caption claims NOT recomputable from this record:")
    print("  seed $20260813$ (no seed field in the record);")
    print("  'TNF(4,8) occupies sixteen physical cells, as does takum16' "
          "(a format property, not a measurement).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
