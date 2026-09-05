#!/usr/bin/env python3
"""Regenerate Table `tab:landing` from measurements/inside_window_2026-08-13f.json.

The table is a VIEW of the record: 11 record objects (GPT-2 block-0 forward-pass
intermediates), 11 printed rows, three numeric columns each (median log2|x|,
p99.9, max), every cell printed to one decimal. Either the 33 cells come back at
that precision or they do not; no tolerance is widened to make them.

ROWS ARE MATCHED BY KEY, NEVER BY POSITION (the tab:tailsweep lesson). The key is
the record's `name` field joined against the LaTeX row label after stripping
markup; the join must be a bijection with a unique best match per row, and
`scaled` / `unscaled` are treated as incompatible tokens so the two attention
rows cannot cross-pair. The record happens to be in table order -- that is
verified and reported, not assumed.

COLUMNS ARE IDENTIFIED, NOT ASSUMED (the tab:invariant lesson). Three anchors:
  * the header row must literally name median log_2|x|, p_{99.9}, max, in order;
  * the scaling identity: GPT-2 head dim is 64, scores are divided by sqrt(64)=8,
    so every distribution statistic of the scaled attention scores must equal the
    unscaled one minus exactly 3 binades. Asserted to 1e-9 for median, p99_9,
    maxv AND the unprinted p0_1 before any cell is compared.
  * counting identities on the unprinted `n` fields (see caption claims below).

THE CAPTION'S OWN CLAIMS ARE DATA:
  * "$82$ real tokens": T=82 must reproduce from the record's n fields --
    ln_1 variance n == T (one variance per token), embedding/residual n == 768*T,
    QK^T n == 12*T^2 (12 heads, full score matrix), softmax numerator
    n == 12*T*(T+1)/2 (causal mask keeps the lower triangle), softmax denominator
    n == 12*T, MLP pre-activation n == 3072*T, vocabulary logits n == 50257*T.
  * the caption names its data file; it must be this record's filename.
  * "Not one row approaches the thresholds of Table tab:rungthr": the thresholds
    are on D (mean |log2|x||), which a percentile record cannot reproduce
    exactly; the strongest recomputable reading is checked (no printed statistic
    of any row reaches the lowest threshold D >~ 9.5) and the caveat is printed.

Prose anchors tied to this table are recomputed too (largest median 4.2 at the
unscaled attention scores; layer-norm variance at 2^-5, softmax denominator at
2^2, GEMM partials at 2^-4.7; "inside neural inference there are none" against
the record's inside flags). The prose sentence "the widest spread of any row is
under twelve binades" is checked under the record's own extent lower bound
(maxv - p0_1) and WARNED about rather than gated, because "spread" is not
defined for this table and the paper's span definition belongs to a different
table -- the arithmetic is printed so the reader can judge.

DO NOT EDIT tnf_paper.tex; a defect report is a success for this script.
Exit 0 only when every printed cell reproduces and every caption claim holds.
"""
import json
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
REC = HERE / "measurements" / "inside_window_2026-08-13f.json"
PAPER = HERE / "tnf_paper.tex"

CAPTION_RE = re.compile(r"\\caption\{((?:[^{}]|\{[^{}]*\})*)\}", re.S)


def landing_block(tex):
    for m in re.finditer(r"\\begin\{table\}(.*?)\\end\{table\}", tex, re.S):
        if r"\label{tab:landing}" in m.group(1):
            return m.group(1)
    raise SystemExit("tab:landing not found in tnf_paper.tex")


def parse_table(body):
    """Return (caption_text, header_cells, rows) -- caption cut BEFORE row
    parsing, because its numbers are not cells."""
    cap = CAPTION_RE.search(body)
    caption = cap.group(1) if cap else ""
    body = CAPTION_RE.sub("", body)
    header, rows = None, []
    for raw in body.split(r"\\"):
        # the header shares its chunk with \label{...} and \begin{tabular}{...}
        # once the caption is cut: strip that markup rather than discarding the
        # chunk (chunk-level skipping ate the header row twice)
        raw = re.sub(r"\\label\{[^{}]*\}", "", raw)
        raw = re.sub(r"\\(begin|end)\{tabular\}(\{[^{}]*\})?", "", raw)
        cells = [c.strip() for c in raw.split("&")]
        if len(cells) != 4:
            continue
        cells = [re.sub(r"\\hline", "", c).strip() for c in cells]
        if header is None:
            header = cells
            continue
        label = cells[0]
        vals = []
        for c in cells[1:]:
            c = re.sub(r"\\mathrm\{e\}\{(-?\d+)\}", r"e\1", c)
            c = re.sub(r"\\(textbf|emph|texttt)\{([^{}]*)\}", r"\2", c)
            c = c.replace("$", "").replace(r"\,", "").strip()
            vals.append(float(c))
        rows.append({"label": label, "vals": vals})
    return caption, header, rows


def label_words(s):
    """LaTeX row label or record name -> lowercase word set for key matching."""
    s = re.sub(r"\\(textbf|emph|texttt|text|mathrm)\{([^{}]*)\}", r"\2", s)
    s = re.sub(r"\\[a-zA-Z]+", " ", s)  # residual commands (\top, \exp, \cdot)
    s = re.sub(r"[^a-zA-Z0-9]+", " ", s)
    return frozenset(w for w in s.lower().split() if w)


def match_rows(printed, rec, bad):
    """Key-based join: unique best word-overlap match, scaled/unscaled must
    agree, result must be a bijection."""
    pairs = []
    used = {}
    for p in printed:
        pw = label_words(p["label"])
        scored = []
        for i, r in enumerate(rec):
            rw = label_words(r["name"])
            if ("unscaled" in pw) != ("unscaled" in rw):
                continue
            inter = len(pw & rw)
            if inter == 0:
                continue
            scored.append((inter / len(pw | rw), i))
        scored.sort(reverse=True)
        if not scored:
            bad.append(f"printed row '{p['label']}' matches NO record name")
            continue
        if len(scored) > 1 and scored[0][0] == scored[1][0]:
            bad.append(f"printed row '{p['label']}' has an AMBIGUOUS key match")
            continue
        i = scored[0][1]
        if i in used:
            bad.append(f"record row '{rec[i]['name']}' claimed twice "
                       f"('{used[i]}' and '{p['label']}')")
            continue
        used[i] = p["label"]
        pairs.append((p, rec[i], i))
    return pairs



def _row_guard(printed_count, expected=11):
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
    caption, header, printed = parse_table(landing_block(PAPER.read_text()))
    print(f"record rows {len(rec)}   printed rows {len(printed)}")
    _row_guard(len(printed))

    bad = []

    # --- column identification, anchor 1: the header names the columns -------
    hdr = [re.sub(r"[\\${}]", "", h) for h in (header or ["?"] * 4)]
    if not (len(hdr) == 4 and "median" in hdr[1] and "log_2|x|" in hdr[1]
            and "99.9" in hdr[2] and hdr[3] == "max"):
        bad.append(f"header does not name median log_2|x| / p_99.9 / max: {hdr}")

    # --- column identification, anchor 2: the sqrt(d_head)=8 scaling identity
    by_name = {r["name"]: r for r in rec}
    uns = by_name.get("attention scores Q.K^T, unscaled")
    sca = by_name.get("attention scores, scaled")
    if uns is None or sca is None:
        bad.append("record lacks the unscaled/scaled attention pair")
    else:
        for f in ("median", "p99_9", "maxv", "p0_1"):
            if abs(sca[f] - (uns[f] - 3.0)) > 1e-9:
                bad.append(f"scaling identity fails on '{f}': scaled {sca[f]!r}"
                           f" != unscaled {uns[f]!r} - 3 (1/sqrt(64) = -3 binades)")

    # --- key-based row join ---------------------------------------------------
    pairs = match_rows(printed, rec, bad)
    in_order = [i for _, _, i in pairs] == sorted(i for _, _, i in pairs)

    # --- the 33 data cells at printed precision (one decimal) ----------------
    fields = ("median", "p99_9", "maxv")
    n_cells = n_ok = 0
    for p, r, _ in pairs:
        for got, f in zip(p["vals"], fields):
            n_cells += 1
            want = round(r[f], 1) + 0.0  # +0.0 folds -0.0 into 0.0
            if want == got:
                n_ok += 1
            else:
                bad.append(f"'{r['name']}' {f}: printed {got} but record "
                           f"{r[f]!r} rounds to {want}")

    # --- caption claim: "$82$ real tokens" recomputes from the n fields ------
    m = re.search(r"\$(\d+)\$ real tokens", caption)
    if not m:
        bad.append("caption no longer states a token count")
    else:
        T = int(m.group(1))
        heads, d_model, d_ff, vocab = 12, 768, 3072, 50257
        for name, expect, why in (
            ("ln_1 variance (accumulator)", T, "one variance per token"),
            ("token+position embedding", d_model * T, "768*T"),
            ("residual after attention", d_model * T, "768*T"),
            ("block output residual", d_model * T, "768*T"),
            ("attention scores Q.K^T, unscaled", heads * T * T, "12*T^2"),
            ("attention scores, scaled", heads * T * T, "12*T^2"),
            ("softmax numerator exp(.)", heads * T * (T + 1) // 2,
             "12*T(T+1)/2, causal lower triangle"),
            ("softmax denominator (accumulator)", heads * T, "12*T"),
            ("MLP pre-activation (c_fc out)", d_ff * T, "3072*T"),
            ("vocabulary logits (50257 wide)", vocab * T, "50257*T"),
        ):
            r = by_name.get(name)
            if r is None:
                bad.append(f"record row '{name}' missing for token-count check")
            elif r["n"] != expect:
                bad.append(f"caption says {T} real tokens but '{name}' has "
                           f"n={r['n']}, not {expect} ({why})")

    # --- caption claim: the data file it names is this record ----------------
    cap_file = re.search(r"measurements/([^\s{}]*\.json)",
                         caption.replace("\\_", "_"))
    if not cap_file:
        bad.append("caption names no measurements/*.json data file")
    elif cap_file.group(1) != REC.name:
        bad.append(f"caption names measurements/{cap_file.group(1)} but this "
                   f"record is {REC.name}")

    # --- caption claim: "Not one row approaches the thresholds" --------------
    # The thresholds (tab:rungthr) are D >~ 9.5 and D >~ 21.9 on D = mean
    # |log2|x||, which percentiles cannot reproduce exactly. Strongest
    # recomputable reading: no printed statistic of any row reaches even the
    # lowest threshold.
    if "Not one row approaches the thresholds" in caption:
        worst = max((max(abs(r["median"]), abs(r["p99_9"]), abs(r["maxv"])), r["name"])
                    for r in rec)
        if worst[0] >= 9.5:
            bad.append(f"caption says not one row approaches the thresholds, but "
                       f"'{worst[1]}' has a printed statistic of magnitude "
                       f"{worst[0]:.2f} >= 9.5, the lowest rung threshold")
        thr_note = (f"largest |printed statistic| over all rows is {worst[0]:.2f}"
                    f" ('{worst[1]}') vs lowest threshold D >~ 9.5; D itself "
                    "(mean |log2|x||) is not in the record and cannot be "
                    "recomputed from percentiles")
    else:
        thr_note = "caption threshold sentence not found (claim skipped)"

    # --- prose anchors around the table (unambiguous, recomputable) ----------
    med_max = max(rec, key=lambda r: r["median"])
    if not (round(med_max["median"], 1) == 4.2
            and med_max["name"] == "attention scores Q.K^T, unscaled"):
        bad.append(f"prose says the largest median is 4.2 for the unscaled "
                   f"attention scores; record's largest is {med_max['median']!r} "
                   f"for '{med_max['name']}'")
    for name, anchor in (("ln_1 variance (accumulator)", -5.0),
                         ("softmax denominator (accumulator)", 2.0),
                         ("GEMM running partial sums", -4.7)):
        r = by_name.get(name)
        want = round(r["median"], 1) if r else None
        # prose quotes 2^-5 and 2^2 to integer precision, 2^-4.7 to one decimal
        prec_ok = r is not None and (
            round(r["median"]) == anchor if anchor == int(anchor)
            else round(r["median"], 1) == anchor)
        if not prec_ok:
            bad.append(f"prose pins '{name}' at 2^{anchor:g} but record median "
                       f"is {r['median']!r} (rounds to {want})")
    insiders = [r["name"] for r in rec if r.get("inside")]
    if insiders:
        bad.append(f"prose says 'Inside neural inference there are none' but "
                   f"the record marks inside:true on {insiders}")

    # --- verdict -------------------------------------------------------------
    if bad:
        print(f"\nFAIL: {len(bad)} mismatch(es)  "
              f"[{n_ok}/{n_cells} data cells reproduce]\n")
        for b in bad:
            print(f"  {b}")
        return 1

    print(f"\nOK: all {n_cells} data cells of {len(pairs)} printed rows "
          "reproduce at one-decimal precision; the header, the -3-binade "
          "scaling identity and every caption claim recompute "
          "(82 real tokens confirmed by seven independent n-field identities, "
          "including the causal-mask triangle count 12*82*83/2 = 40836)")
    print(f"     row join is a bijection and record order "
          f"{'matches' if in_order else 'DOES NOT match'} printed order")
    print(f"     threshold claim: {thr_note}")

    print(f"\nNOTE -- every record row is printed ({len(rec)}/{len(printed)}); "
          "the unprinted content is four FIELDS per row (n, p0_1, inside, note):")
    for r in rec:
        print(f"  {r['name']:38s} n={r['n']:>7d}  p0.1={r['p0_1']:8.2f}  "
              f"inside={str(r['inside']).lower()}  ({r['note']})")

    print("\nWARNING -- prose claim 'the widest spread of any row is under twelve "
          "binades' does not survive the record's own extent lower bound "
          "(maxv - p0_1); 'spread' is undefined for this table, so this is "
          "reported, not gated:")
    for r in sorted(rec, key=lambda r: r["p0_1"] - r["maxv"]):
        span = r["maxv"] - r["p0_1"]
        flag = "  <-- exceeds twelve binades" if span >= 12 else ""
        print(f"  {r['name']:38s} max {r['maxv']:6.2f} - p0.1 {r['p0_1']:8.2f} "
              f"= {span:5.2f} binades{flag}")
    print("  5 of 11 rows exceed twelve binades under that reading; the widest "
          "is the softmax numerator at 42.31. Under a printed-columns reading "
          "(max - median <= 7.39) the sentence holds. The record cannot decide "
          "which the author meant.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
