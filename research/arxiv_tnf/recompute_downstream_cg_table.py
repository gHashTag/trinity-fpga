#!/usr/bin/env python3
"""Regenerate Table `tab:downstream-cg` from
measurements/tnf_downstream_linear_cg_2026-08-14.json.

ADJUDICATION FIRST (rule 1 -- metadata outranks similarity): the record's own
`task` field reads (Russian) "Iterative solution of a 2x2 SPD system by
conjugate gradients in raw scales without normalisation", its
reproduction.command names gen_downstream_linear_cg.py, and the paper's
sec:downstream-cg prose names this exact record file and command.  There is no
competing candidate: tab:downstream (the GPT-2 task) is backed by a different
record and a different generator.  So this record backs exactly one table,
tab:downstream-cg, added by the same Evidence Closure commit.

ROWS ARE MATCHED BY KEY (format name), never by position.  The record key
`float64_reference` prints as "float64 (reference)", `TNF16_(4,8)` prints as
"TNF(4,8)"; the map is explicit and total.

COLUMN IDENTITIES ARE ASSERTED, NOT ASSUMED:
    relative solution error   == ||x_hat - x_true||_2/||x_true||_2  (recomputed
                                 here in float64 from the record's own x_hat and
                                 x_true, asserted to 1e-9 relative)
    external relative residual== ||A64 x_hat - b64||_2/||b64||_2    (recomputed
                                 from the record's A_SI, b_SI, x_hat, 1e-9)
    iterations run            == results[*].iterations_run, exact integer
Printed scientific cells must come back at PRINTED precision: f"{v:.2e}"
against the parsed $m\\times10^{e}$ cell.  No tolerance bands on cells.

CAPTION AND ADJACENT-PROSE CLAIMS ARE DATA, checked conditionally on the phrase
being present in tnf_paper.tex:
    - the displayed A matrix and b vector (display math in sec:downstream-cg)
      at printed precision, plus x_true = (1.2345, -2.3456) exactly
    - "cap of $80$"  -> max_iterations == 80
    - "recorded tolerance $10^{-6}$" -> tolerance_relative_residual == 1e-6
    - "All three low-precision candidates crossed the internal $10^{-6}$
      threshold at iteration 3" -> iterations_to_relative_residual_1e-6 == 3
      for binary16 / TNF16_(4,8) / takum16
    - "float32 accumulator" convention -> record accumulator string
    - x0 = (0,0), the stopping-rule wording, the (E_t,M)=(4,8) rung and its
      not-the-reconciled-(4,11) note
    - the three comparative prose sentences (TNF did not beat takum on solution
      error; TNF had the smaller external residual; binary16 smallest solution
      error of the three) recomputed as ORDERINGS from the record, and their
      quoted numbers at printed precision
    - "a SHA-256 of the canonical record payload (with the digest field
      excluded)" -> recomputed with the generator's own canonicalisation
      (json.dumps(..., ensure_ascii=False, indent=2, sort_keys=True))

VACUOUS-PASS GUARD: exactly 4 printed rows are expected; anything else fails.

SELECTION REPORT: the record holds 4 result rows and the table prints all 4 --
no row is hidden.  Per-row fields the table does NOT print (x_hat,
final_relative_residual, iterations_to_relative_residual_1e-6) are listed in
the NOTE so the unprinted content is on the record.
"""
import hashlib
import json
import math
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
REC = HERE / "measurements" / "tnf_downstream_linear_cg_2026-08-14.json"
PAPER = HERE / "tnf_paper.tex"

# printed format cell (normalised) -> record results key
FORMAT_KEY = {
    "float64 (reference)": "float64_reference",
    "binary16": "binary16",
    "TNF(4,8)": "TNF16_(4,8)",
    "takum16": "takum16",
}
LOWP = ["binary16", "TNF16_(4,8)", "takum16"]


def clean(cell):
    c = re.sub(r"\\(midrule|toprule|bottomrule|hline)", "", cell)
    c = re.sub(r"\\(textbf|texttt|emph|mathrm)\{(.*?)\}", r"\2", c)
    c = re.sub(r"\\[,!;]", " ", c)
    c = c.replace("$", "").strip()
    return re.sub(r"\s+", " ", c)


def sci_key(s):
    """Canonicalise a printed scientific cell to (mantissa_str, exp_int)."""
    m = re.match(r"^([\d.]+)\\times10\^\{(-?\d+)\}$", s.replace(" ", ""))
    if m:
        return (m.group(1), int(m.group(2)))
    m = re.match(r"^([\d.]+)e(-?\d+)$", s)
    if m:
        return (m.group(1), int(m.group(2)))
    return None


def rec_sci_key(v):
    mant, exp = f"{v:.2e}".split("e")
    return (mant, int(exp))


def table_body(tex, label):
    for m in re.finditer(r"\\begin\{table\}(.*?)\\end\{table\}", tex, re.S):
        if rf"\label{{{label}}}" in m.group(1):
            body = m.group(1)
            capm = re.search(r"\\caption\{((?:[^{}]|\{[^{}]*\})*)\}", body, re.S)
            caption = capm.group(1) if capm else ""
            body = body[:capm.start()] + body[capm.end():] if capm else body
            return caption, body
    raise SystemExit(f"FAIL: {label} not found in tnf_paper.tex")


def printed_rows(body):
    out = []
    for raw in body.split(r"\\"):
        cells = [c.strip() for c in raw.split("&")]
        if len(cells) != 4 or "tabular" in raw or "toprule" in cells[0]:
            continue
        name = clean(cells[0])
        if not name or name == "format":
            continue
        out.append({
            "format": name,
            "solerr": clean(cells[1]),
            "resid": clean(cells[2]),
            "iters": clean(cells[3]),
        })
    return out


def main():
    rec = json.loads(REC.read_text())
    tex = PAPER.read_text()

    # ---- rule 1: the record's own metadata, stated up front ------------------
    print("record metadata:")
    print(f"  task        : {rec['task']}")
    print(f"  command     : {rec['reproduction']['command']}")
    print(f"  seed        : {rec['seed']}   git_head: {rec['reproduction']['git_head'][:12]}")
    print(f"  rung        : (E_t,M)=({rec['reproduction']['tnf_parameters']['E_t']},"
          f"{rec['reproduction']['tnf_parameters']['M']})  "
          f"note: {rec['reproduction']['tnf_parameters']['note']}")
    print("adjudication: backs tab:downstream-cg (sec:downstream-cg names this "
          "record file and generator; no other table candidate exists)\n")

    caption, body = table_body(tex, "tab:downstream-cg")
    printed = printed_rows(body)
    print(f"record result rows {len(rec['results'])}   printed rows {len(printed)}")

    # ---- vacuous-pass guard --------------------------------------------------
    if len(printed) != 4:
        raise SystemExit(f"FAIL: parsed {len(printed)} printed rows, expected 4 -- "
                         "either the table changed or the parser broke; neither "
                         "may pass silently")

    bad, note = [], []
    cells_total = cells_matching = 0
    res = rec["results"]
    A = rec["A_SI"]
    b = rec["b_SI"]
    xt = rec["x_true"]

    # ---- record-internal column identities (1e-9), before any cell check -----
    nb = math.hypot(b[0], b[1])
    nxt = math.hypot(xt[0], xt[1])
    for key, r in res.items():
        xh = r["x_hat"]
        solerr = math.hypot(xh[0] - xt[0], xh[1] - xt[1]) / nxt
        rr = [A[i][0] * xh[0] + A[i][1] * xh[1] - b[i] for i in range(2)]
        resid = math.hypot(rr[0], rr[1]) / nb
        for name, got, want in (("relative_solution_error", r["relative_solution_error"], solerr),
                                ("relative_residual_64", r["relative_residual_64"], resid)):
            if abs(got - want) > 1e-9 * max(1.0, abs(want)):
                bad.append(f"{key}: record {name} {got!r} != recomputed {want!r} "
                           "-- column identity broken")
    note.append("column identities hold: solution error and external residual "
                "recompute from the record's own x_hat/A_SI/b_SI/x_true to 1e-9")

    # ---- join printed rows to record rows BY KEY -----------------------------
    matched = set()
    for p in printed:
        key = FORMAT_KEY.get(p["format"])
        if key is None:
            bad.append(f"printed format {p['format']!r} has no record mapping")
            continue
        if key not in res:
            bad.append(f"printed row {p['format']!r} -> {key!r} has NO record row")
            continue
        matched.add(key)
        r = res[key]
        cells_total += 1  # format-name cell: the key mapping verified it
        cells_matching += 1
        for col, field in (("solerr", "relative_solution_error"),
                           ("resid", "relative_residual_64")):
            cells_total += 1
            got, want = sci_key(p[col]), rec_sci_key(r[field])
            if got == want:
                cells_matching += 1
            else:
                bad.append(f"{p['format']} {col}: printed {p[col]!r} ({got}) but "
                           f"record {r[field]!r} prints as {want}")
        cells_total += 1
        if p["iters"] == str(r["iterations_run"]):
            cells_matching += 1
        else:
            bad.append(f"{p['format']} iterations: printed {p['iters']!r} but "
                       f"record iterations_run = {r['iterations_run']}")

    # ---- selection report ----------------------------------------------------
    unprinted = sorted(set(res) - matched)
    if unprinted:
        for k in unprinted:
            note.append(f"UNPRINTED record row {k}: "
                        f"solerr={res[k]['relative_solution_error']:.3e}")
        bad.append(f"record holds {len(res)} rows, table prints {len(matched)}")
    else:
        note.append("selection: all 4 record rows are printed; nothing is hidden")
    for k, r in sorted(res.items()):
        note.append(f"  unprinted fields of {k}: x_hat={r['x_hat']}, "
                    f"final_relative_residual={r['final_relative_residual']}, "
                    f"iters_to_1e-6={r['iterations_to_relative_residual_1e-6']}")

    # ---- caption / adjacent-prose claims, conditional on the phrase ----------
    # displayed A and b (prose display math), at printed precision
    am = re.search(r"A=\\begin\{bmatrix\}([\d.]+)&([\d.]+)\\\\([\d.]+)&([\d.]+)"
                   r"\\end\{bmatrix\}", tex)
    bm = re.search(r"b=\\begin\{bmatrix\}([\d.]+)\\\\([\d.]+)\\end\{bmatrix\}", tex)
    if am:
        pa = [[am.group(1), am.group(2)], [am.group(3), am.group(4)]]
        for i in range(2):
            for j in range(2):
                if float(pa[i][j]) != A[i][j]:
                    bad.append(f"displayed A[{i}][{j}] = {pa[i][j]} != record "
                               f"{A[i][j]!r}")
    else:
        bad.append("could not find the displayed A matrix in sec:downstream-cg")
    if bm:
        for i, ps in enumerate([bm.group(1), bm.group(2)]):
            digits = len(ps.replace(".", "").lstrip("0"))
            if f"{b[i]:.{digits}g}" != ps:
                bad.append(f"displayed b[{i}] = {ps} != record {b[i]!r} at its "
                           f"printed {digits} significant digits")
            elif float(ps) != b[i]:
                note.append(f"displayed b[{i}] = {ps} matches the record at its "
                            f"printed {digits} sig. digits; full record value is "
                            f"{b[i]!r} (display is a decimal rounding, not the "
                            "exact double)")
    else:
        bad.append("could not find the displayed b vector in sec:downstream-cg")
    # b really is A @ x_true in float64 (prose: "The exact solution used to
    # generate $b$ was $(1.2345,-2.3456)$")
    if "The exact solution used to generate" in tex:
        if xt != [1.2345, -2.3456]:
            bad.append(f"prose says x_true = (1.2345, -2.3456); record {xt}")
        for i in range(2):
            gen = A[i][0] * xt[0] + A[i][1] * xt[1]
            # The generator formed b with numpy's matmul, whose BLAS reduction
            # order (or FMA) may differ from elementwise a*x0 + a*x1 by an ulp;
            # that is an evaluation-order artefact, not a record defect.  The
            # identity is asserted to 2 ulps and any inexactness is noted.
            if abs(gen - b[i]) > 2 * math.ulp(b[i]):
                bad.append(f"b[{i}] {b[i]!r} != (A @ x_true)[{i}] = {gen!r} "
                           "beyond 2 ulps")
            elif gen != b[i]:
                note.append(f"b[{i}] = A @ x_true holds to "
                            f"{abs(gen - b[i]) / math.ulp(b[i]):.0f} ulp "
                            f"(record {b[i]!r}, elementwise {gen!r}) -- numpy "
                            "matmul reduction order, not a defect")

    # cap and tolerance
    if re.search(r"cap of \$80\$", tex) and rec["max_iterations"] != 80:
        bad.append(f"paper says cap of 80; record max_iterations = "
                   f"{rec['max_iterations']}")
    if re.search(r"recorded tolerance \$10\^\{-6\}\$", tex) \
            and rec["tolerance_relative_residual"] != 1e-6:
        bad.append(f"paper says recorded tolerance 1e-6; record "
                   f"{rec['tolerance_relative_residual']!r}")

    # caption: all three low-precision candidates crossed 1e-6 at iteration 3
    if re.search(r"crossed\s+the\s+internal\s+\$10\^\{-6\}\$\s+threshold\s+at\s+"
                 r"iteration\s+3", caption):
        for k in LOWP:
            it = res[k]["iterations_to_relative_residual_1e-6"]
            if it != 3:
                bad.append(f"caption says all three crossed 1e-6 at iteration 3; "
                           f"{k} crossed at {it}")
    else:
        note.append("caption iteration-3 phrase not found verbatim; skipped")

    # float32 accumulator convention
    if "float32" in tex and "accumulator" in tex:
        acc = rec["accumulator"]
        if not (acc.startswith("float32") and "float64 only for reference" in acc):
            bad.append(f"paper asserts float32 accumulator for candidates / "
                       f"float64 reference; record accumulator = {acc!r}")

    # x0 = (0,0)
    if re.search(r"x_0\s*=\s*\(0,0\)", tex.replace(" ", "")) \
            or re.search(r"\\texttt\{x0\}|x_0", tex):
        if rec["reproduction"]["x0"] != [0.0, 0.0]:
            bad.append(f"paper says x0 = (0,0); record {rec['reproduction']['x0']}")

    # stopping rule: caption wording vs record wording, and consistency with
    # the recorded outcomes (all four stopped before the cap with stored
    # residual exactly zero)
    srule = rec["reproduction"]["stopping_rule"]
    for frag in ("residual reaches exactly zero", "finite and non-zero",
                 "max_iterations"):
        if frag not in srule:
            bad.append(f"record stopping_rule lacks {frag!r}: {srule!r}")
    if all(r["final_relative_residual"] == 0.0 and r["iterations_run"] < 80
           for r in res.values()):
        note.append("stopping rule consistent with outcomes: every run stopped "
                    "before the cap with stored residual exactly 0.0, so the "
                    "iterations column records where each solver stalled, as "
                    "the caption says")
    else:
        bad.append("caption's stall reading assumes stored residual hit exactly "
                   "zero before the cap; the record contradicts that for some row")

    # rung note
    if "not the reconciled TNF16 rung $(4,11)$" in tex or "(4,11)" in tex:
        tp = rec["reproduction"]["tnf_parameters"]
        if (tp["E_t"], tp["M"]) != (4, 8) or "(4,11)" not in tp["note"]:
            bad.append(f"caption pins rung (4,8) / not-(4,11); record "
                       f"tnf_parameters = {tp!r}")

    # the three comparative prose sentences, as orderings AND quoted digits
    tnf_e = res["TNF16_(4,8)"]["relative_solution_error"]
    tak_e = res["takum16"]["relative_solution_error"]
    bin_e = res["binary16"]["relative_solution_error"]
    tnf_r = res["TNF16_(4,8)"]["relative_residual_64"]
    tak_r = res["takum16"]["relative_residual_64"]
    if "did not beat" in tex:
        if not tnf_e > tak_e:
            bad.append(f"prose: TNF did not beat takum on solution error, but "
                       f"record has TNF {tnf_e!r} <= takum {tak_e!r}")
        m = re.search(r"did not beat \\texttt\{takum16\} on solution error:\s*"
                      r"\$([\d.]+)\\times10\^\{(-?\d+)\}\$ against "
                      r"\$([\d.]+)\\times10\^\{(-?\d+)\}\$", tex)
        if m and ((m.group(1), int(m.group(2))) != rec_sci_key(tnf_e)
                  or (m.group(3), int(m.group(4))) != rec_sci_key(tak_e)):
            bad.append("prose quotes for the TNF-vs-takum solution errors do not "
                       "reproduce at printed precision")
    if re.search(r"smaller\s+externally\s+recomputed\s+residual", tex):
        if not tnf_r < tak_r:
            bad.append(f"prose: TNF had the smaller external residual, but record "
                       f"has TNF {tnf_r!r} >= takum {tak_r!r}")
        m = re.search(r"smaller externally\s+recomputed residual, "
                      r"\$([\d.]+)\\times10\^\{(-?\d+)\}\$ against\s*"
                      r"\$([\d.]+)\\times10\^\{(-?\d+)\}\$", tex)
        if m and ((m.group(1), int(m.group(2))) != rec_sci_key(tnf_r)
                  or (m.group(3), int(m.group(4))) != rec_sci_key(tak_r)):
            bad.append("prose quotes for the residual comparison do not reproduce "
                       "at printed precision")
    if re.search(r"smallest\s+solution\s+error\s+of\s+the\s+three", tex):
        if not (bin_e < tnf_e and bin_e < tak_e):
            bad.append(f"prose: binary16 smallest solution error of the three; "
                       f"record binary16 {bin_e!r} vs TNF {tnf_e!r} takum {tak_e!r}")
        m = re.search(r"smallest solution error of the three[^$]*\$([\d.]+)"
                      r"\\times10\^\{(-?\d+)\}\$", tex)
        if m and (m.group(1), int(m.group(2))) != rec_sci_key(bin_e):
            bad.append("prose quote for binary16's solution error does not "
                       "reproduce at printed precision")

    # prose names this record file and generator command
    flat = tex.replace("\\allowbreak", "").replace("\\_", "_") \
              .replace("\\texttt{", "").replace("}", "").replace("\\ ", " ")
    if "tnf_downstream_linear_cg_2026-08-14.json" not in flat:
        bad.append("prose does not name this record file")
    if "gen_downstream_linear_cg.py" not in flat:
        bad.append("prose does not name the generator")

    # digest of the canonical payload, generator's own canonicalisation
    # whitespace-tolerant: the phrase wraps across a source line in the tex
    if re.search(r"with\s+the\s+digest\s+field\s+excluded", tex):
        payload = {k: v for k, v in rec.items()
                   if k != "artefact_sha256_of_canonical_payload"}
        digest = hashlib.sha256(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
            .encode("utf-8")).hexdigest()
        if digest != rec["artefact_sha256_of_canonical_payload"]:
            bad.append(f"recomputed canonical-payload sha256 {digest} != recorded "
                       f"{rec['artefact_sha256_of_canonical_payload']}")
        else:
            note.append("canonical-payload sha256 recomputes exactly "
                        f"({digest[:16]}...), digest field excluded, generator's "
                        "canonicalisation")
    else:
        note.append("digest phrase not found in tex; sha256 check skipped")

    # ---- verdict -------------------------------------------------------------
    print(f"cells: {cells_matching}/{cells_total} printed cells reproduce")
    print("\nNOTE:")
    for n_ in note:
        print(f"  {n_}")
    if bad:
        print(f"\nFAIL: {len(bad)} defect(s)\n")
        for b_ in bad:
            print(f"  {b_}")
        return 1
    print("\nOK: all 4 printed rows reproduce at printed precision, every caption "
          "and prose claim recomputes from the record, and the payload digest "
          "verifies")
    return 0


if __name__ == "__main__":
    sys.exit(main())
