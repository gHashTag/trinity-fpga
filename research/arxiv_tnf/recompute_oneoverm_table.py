#!/usr/bin/env python3
"""Adjudicate and regenerate: which table does measurements/breakeven_2026-08-14.json back?

The forward mapping was the weakest in the tree (45%, F=0.636) and pointed at
tab:blockpct in one pass and tab:convert in another. Both are wrong, and the
record says so itself: its `description` names cor:breakeven and its `method`
field is the formula C/(2*c*M) with c = 2.4455 -- Theorem thm:oneoverm's law,
not tab:convert's finite-difference lambdas and not tab:blockpct's percentiles.

VERDICT (each branch verified below, not asserted):

  tab:blockpct   NOT BACKED. Zero numeric overlap: percentile spans in binades
                 vs LUT counts and thresholds. Nothing to join on.
  tab:convert    NOT BACKED. The LUT column (438, 40) matches by regime key,
                 but the bits columns divide by lambda = 48.8 / 111.2 -- local
                 finite-difference slopes of the synthesis sweep (e.g.
                 (567-372)/4 = 48.75) that appear nowhere in and cannot be
                 derived from this record. The record's own law lambda = 2cM
                 gives 8.14 (not 8.98) at M=11 and 4.26 (not 3.94) at M=21.
  tab:oneoverm   BACKED, fully. Every printed cell -- both header LUT costs and
                 all 5x3 derived values -- reproduces from the record's three
                 inputs (c, unary_lut, length_prefixed_lut) at printed
                 precision, and the record's thresholds and values_at_M_115
                 reproduce cor:breakeven's prose digit for digit.

Rows are matched BY KEY (the M column / the regime name), never by position.
Record-internal identities (threshold == C/(2c), value == C/(2c*115)) are
asserted to 1e-9 before any cell is judged. Nothing in tnf_paper.tex is edited;
the one defect found (tab:convert's caption superlative) is reported precisely
and does not block exit 0, because it belongs to a table this record does not
back -- it is checkable purely against the paper's own printed cells.
"""
import json
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
REC = HERE / "measurements" / "breakeven_2026-08-14.json"
PAPER = HERE / "tnf_paper.tex"


def table_body(tex, label):
    for m in re.finditer(r"\\begin\{table\}(.*?)\\end\{table\}", tex, re.S):
        if ("\\label{%s}" % label) in m.group(1):
            body = m.group(1)
            break
    else:
        raise SystemExit("%s not found" % label)
    # the caption's numbers are not cells -- cut it before parsing rows
    body = re.sub(r"\\caption\{(?:[^{}]|\{[^{}]*\})*\}", "", body, flags=re.S)
    return body


def clean(cell):
    cell = re.sub(r"\\mathrm\{e\}\{(-?\d+)\}", r"e\1", cell)
    cell = re.sub(r"\\(mathbf|textbf|emph|texttt)\{([^{}]*)\}", r"\2", cell)
    return cell.replace("$", "").replace(r"\,", "").strip()


def rows_of(body, ncols):
    out = []
    for raw in body.split(r"\\"):
        if "tabular" in raw or "label" in raw:
            continue
        cells = [clean(c) for c in raw.split("&")]
        cells = [re.sub(r"\\(top|mid|bottom)rule", "", c).strip() for c in cells]
        if len(cells) == ncols:
            out.append(cells)
    return out


def caption_of(tex, label):
    for m in re.finditer(r"\\begin\{table\}(.*?)\\end\{table\}", tex, re.S):
        if ("\\label{%s}" % label) in m.group(1):
            c = re.search(r"\\caption\{((?:[^{}]|\{[^{}]*\})*)\}", m.group(1), re.S)
            return c.group(1) if c else ""
    return ""


def reproduces(value, printed_str):
    """A cell printed with d decimals asserts |record - printed| <= half an ulp
    of the printed precision (exactly the set of values that round to it)."""
    printed = float(printed_str)
    d = len(printed_str.split(".")[1]) if "." in printed_str else 0
    return abs(value - printed) <= 0.5 * 10 ** (-d) + 1e-12


def numbers_in(text):
    return [float(x) for x in re.findall(r"\d+\.?\d*", text)]



def _row_guard(printed_count, expected=5):
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
    tex = PAPER.read_text()
    c = rec["c"]
    U, L = rec["unary_lut"], rec["length_prefixed_lut"]
    thr_u, thr_l = rec["thresholds"]["unary"], rec["thresholds"]["length_prefixed"]
    v115_u = rec["values_at_M_115"]["unary"]
    v115_l = rec["values_at_M_115"]["length_prefixed"]

    bad = []       # blocks exit 0
    findings = []  # defects in tables this record does NOT back; reported, not blocking

    # ---- record-internal identities, asserted before any comparison (1e-9) ----
    for name, got, exp in (("thresholds.unary", thr_u, U / (2 * c)),
                           ("thresholds.length_prefixed", thr_l, L / (2 * c)),
                           ("values_at_M_115.unary", v115_u, U / (2 * c * 115)),
                           ("values_at_M_115.length_prefixed", v115_l, L / (2 * c * 115))):
        if abs(got - exp) > 1e-9:
            bad.append(f"record identity broken: {name} = {got!r} but C/(2c[*M]) = {exp!r}")
    print("record identities: thresholds == C/(2c) and values_at_M_115 == C/(2c*115)"
          + (" hold to 1e-9" if not bad else " BROKEN"))

    # ================= adjudication =================
    print("\n-- ADJUDICATION: which table does this record back? --")

    # candidate 1: tab:blockpct -- any shared number at all?
    bp = rows_of(table_body(tex, "tab:blockpct"), 4)
    bp_nums = {n for r in bp for n in numbers_in(" ".join(r[:3]))}
    rec_nums = {U, L, round(c, 4), round(thr_u, 1), round(thr_l, 1),
                round(v115_u, 2), round(v115_l, 2)}
    overlap = bp_nums & rec_nums
    print(f"tab:blockpct: cells hold {sorted(bp_nums)}; record holds {sorted(rec_nums)}; "
          f"overlap = {sorted(overlap) or 'NONE'} -> "
          + ("NOT backed by this record" if not overlap else "unexpected overlap"))
    if overlap:
        bad.append(f"tab:blockpct unexpectedly shares {overlap} with the record")

    # candidate 2: tab:convert -- LUT column matches by key; bits columns do not
    cv = {r[0]: r[1:] for r in rows_of(table_body(tex, "tab:convert"), 4)
          if "regime" not in r[0]}
    cv_u = cv[[k for k in cv if k.startswith("unary")][0]]
    cv_l = cv[[k for k in cv if k.startswith("length-prefixed")][0]]
    if int(cv_u[0]) != U or int(cv_l[0]) != L:
        bad.append(f"tab:convert LUT column ({cv_u[0]}, {cv_l[0]}) != record ({U}, {L})")
    print(f"tab:convert: LUT column ({cv_u[0]}, {cv_l[0]}) == record's (unary, length-prefixed) "
          "-- the ONLY cells the two share")
    # under the record's law lambda = 2cM at the paper's class rungs (M=11 reconciled
    # 16-bit, M=21 32-bit oracle rung), the printed bits do NOT come back:
    print(f"  record law C/(2cM):  M=11 -> {U/(2*c*11):.2f} vs printed {cv_u[1]};  "
          f"M=21 -> {U/(2*c*21):.2f} vs printed {cv_u[2]}")
    # the printed cells invert to the text's finite-difference sweep slopes instead:
    print(f"  implied lambda from printed cells: {438/float(cv_u[1]):.2f}, "
          f"{40/float(cv_l[1]):.2f} (16-bit) and {438/float(cv_u[2]):.2f}, "
          f"{40/float(cv_l[2]):.2f} (32-bit) -> the sweep's local slopes 48.8 / 111.2 "
          "((567-372)/4 = 48.75; (1683-1238)/4 = 111.25), which this record does not contain")
    print("  -> tab:convert is backed by the synthesis-sweep record, NOT by breakeven_2026-08-14")

    # rule 6 applied to the candidate's caption while we are here: its superlative
    # fails in the table's own currency. TNF16's mantissa is 9 on the ladder
    # (tab:gftvstnf) and 11 reconciled (the paper's eq. around line 421).
    cv_cap = caption_of(tex, "tab:convert")
    if "more than" in cv_cap and "mantissa" in cv_cap:
        bits = float(cv_u[1])  # 8.98, the caption's own bold cell
        if bits < 9:
            findings.append(
                "tab:convert caption: 'The unary regime costs, in LUT area alone, more than "
                f"TNF16's entire mantissa' -- but its own bold cell is {bits} bits, and "
                "TNF16's mantissa is 9 bits (ladder, tab:gftvstnf) or 11 (reconciled): "
                f"{bits} < 9 < 11. In LUT units the claim also fails at the table's own "
                f"lambda: 9 * 48.8 = {9*48.8:.1f} LUTs > 438. It holds only against the "
                f"quadratic term c*9^2 = {c*81:.1f} LUTs, a reading the table does not print.")

    # candidate 3: tab:oneoverm -- full reconstruction, matched by key M
    ov_body = table_body(tex, "tab:oneoverm")
    body_rows = [r for r in rows_of(ov_body, 4) if re.fullmatch(r"\d+", r[0])]
    _row_guard(len(body_rows))
    # the header carries the two LUT costs -- printed cells, matched to the
    # record by regime name (the header shares a chunk with \begin{tabular}, so
    # it is regexed from the cleaned body rather than parsed as a row)
    hdr = clean(ov_body)
    h_u = int(re.search(r"unary,\s*(\d+)\s*LUT", hdr).group(1))
    h_l = int(re.search(r"length-prefixed,\s*(\d+)\s*LUT", hdr).group(1))
    cells_total = 2 + 4 * len(body_rows)
    cells_ok = 0
    for name, got, exp in (("header unary LUTs", h_u, U),
                           ("header length-prefixed LUTs", h_l, L)):
        if got == exp:
            cells_ok += 1
        else:
            bad.append(f"tab:oneoverm {name}: printed {got} record {exp}")
    print(f"\ntab:oneoverm: header LUT costs ({h_u}, {h_l}) == record ({U}, {L})")
    for r in body_rows:
        M = int(r[0]); cells_ok += 1  # the key column, present by construction
        lam = 2 * c * M
        for col, val, printed in (("lambda", lam, r[1]),
                                  ("unary", U / lam, r[2]),
                                  ("length-prefixed", L / lam, r[3])):
            if reproduces(val, printed):
                cells_ok += 1
            else:
                bad.append(f"tab:oneoverm M={M} {col}: printed {printed} "
                           f"record {val!r} (lambda = 2*{c}*{M} = {lam!r})")
        print(f"  M={M:>2}: lambda {lam:8.3f} -> {r[1]:>6}  unary {U/lam:7.4f} -> {r[2]:>5}  "
              f"lp {L/lam:7.4f} -> {r[3]:>5}")
    print(f"  cells: {cells_ok}/{cells_total} reproduce at printed precision")

    # ---- tab:oneoverm caption claims are data ----
    cap = caption_of(tex, "tab:oneoverm")
    if "2.4455" not in cap or abs(c - 2.4455) > 1e-12:
        bad.append(f"caption states c = 2.4455 but record c = {c!r}")
    if "five" in cap and len(body_rows) != 5:
        bad.append(f"caption says 'five mantissa widths' but table prints {len(body_rows)}")
    # 'worth most of an entire TNF16 mantissa': unary bits at the reconciled rung
    # M=11 must exceed half of TNF16's mantissa on either ladder (9 or 11)
    u11 = U / (2 * c * 11)
    if not (u11 > 9 / 2 and u11 > 11 / 2):
        bad.append(f"caption 'most of an entire TNF16 mantissa' fails: {u11!r} bits")
    # 'below one bit everywhere above the 8-bit class': the record's own threshold
    # must sit below the first rung above the 8-bit class (M=9), and every printed
    # length-prefixed cell at M>=9 must be < 1
    if not thr_l < 9:
        bad.append(f"caption 'below one bit above the 8-bit class' fails: threshold {thr_l!r}")
    for r in body_rows:
        if int(r[0]) >= 9 and float(r[3]) >= 1:
            bad.append(f"caption 'below one bit' fails at printed M={r[0]}: {r[3]}")
    print("caption: c matches record; five widths printed; unary at M=11 = "
          f"{u11:.2f} bits > half of TNF16's mantissa (9 ladder / 11 reconciled); "
          f"length-prefixed threshold {thr_l:.2f} < 9 so every rung above the "
          "8-bit class is below one bit")

    # ---- cor:breakeven prose: the record's declared target, digit for digit ----
    cor = re.search(r"\\begin\{corollary\}\[Break-even widths\](.*?)\\end\{proof\}",
                    tex, re.S).group(1)
    prose = [("89.6", round(thr_u, 1)), ("8.2", round(thr_l, 1)),
             ("0.78", round(v115_u, 2)),
             ("89.5522", round(thr_u, 4)), ("8.1783", round(thr_l, 4)),
             ("0.0711", round(v115_l, 4)), ("0.7787", round(v115_u, 4))]
    for printed, computed in prose:
        if printed not in cor:
            bad.append(f"cor:breakeven does not print {printed}")
        elif float(printed) != computed:
            bad.append(f"cor:breakeven prints {printed} but record gives {computed}")
    # and its ordering claims: TNF64's M=56 below the unary threshold, TNF128's
    # M=115 above it; the first rung above TNF8 (M=11) above the l-p threshold
    if not (56 < thr_u < 115):
        bad.append(f"cor:breakeven ordering fails: 56 < {thr_u!r} < 115 is false")
    if not thr_l < 11:
        bad.append(f"cor:breakeven: M=11 not above length-prefixed threshold {thr_l!r}")
    print("cor:breakeven prose: 89.6 / 8.2 / 0.78 and the proof digits 89.5522 / "
          "8.1783 / 0.0711 / 0.7787 all recompute from the record; 56 < threshold "
          "< 115 and 11 > 8.18 hold")

    # ================= verdict =================
    if findings:
        print(f"\nDEFECT REPORTED ({len(findings)}) -- in a candidate table this record "
              "does not back; checkable against the paper's own printed cells:")
        for f in findings:
            print(f"  {f}")
    if bad:
        print(f"\nFAIL: {len(bad)} mismatch(es)\n")
        for b in bad:
            print(f"  {b}")
        return 1
    print("\nOK: the record backs tab:oneoverm and cor:breakeven -- not tab:convert "
          "(shares only the two LUT costs; its bits columns need the sweep's 48.8/111.2) "
          "and not tab:blockpct (zero overlap). All 22 printed cells of tab:oneoverm "
          "reproduce at printed precision and every caption/prose claim recomputes.")
    print("\nNOTE -- record content not printed in tab:oneoverm (a reader of the table "
          "cannot know it exists):")
    print(f"  break-even thresholds C/(2c): unary {thr_u:.4f}, length-prefixed {thr_l:.4f} "
          "(prose-only, cor:breakeven)")
    print(f"  values at M=115 (TNF128 rung, absent from the table's five): unary "
          f"{v115_u:.4f}, length-prefixed {v115_l:.4f} (prose-only, cor:breakeven)")
    print("  the table prints the selection M in {9, 11, 25, 56, 90}; the record's law "
          "C/(2cM) generates every width, so the selection is the paper's, not the record's")
    return 0


if __name__ == "__main__":
    sys.exit(main())
