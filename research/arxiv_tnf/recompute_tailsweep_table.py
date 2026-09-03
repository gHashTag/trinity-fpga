#!/usr/bin/env python3
"""Regenerate Table `tab:tailsweep` from measurements/crossover_2026-08-13e.json.

The record was one of the orphans: mentioned by nothing in the tree, rebuildable
by nothing, its README twin (`crossover2`) marked current while this one backs a
DIFFERENT table. Numeric provenance put it at tab:tailsweep with 94% forward
coverage; this script replaces that statistic with a reconstruction -- either the
eighteen rows come back or they do not.

COLUMN IDENTITIES ARE ASSERTED, NOT ASSUMED (the tab:invariant lesson, where
assuming column 3 produced 38 phantom mismatches):

    S           round(span, 1)
    col 4       tnf      -- asserted via ratio identities below
    col 5       takum
    col 6       ratio_vs_takum    == takum / tnf      to 1e-9 in the record
    col 7       ratio_vs_binary16 == binary16 / tnf   where binary16 is finite

THE TABLE IS A SELECTION, AND THAT IS REPORTED RATHER THAN FAILED. The record
holds 18 rows; the table prints 8, with no selection rule stated in the caption or
the surrounding prose. Rows are therefore matched BY KEY (family, parameter) --
positional matching mis-paired sigma=1.5 against sigma=1.0 and produced 33 phantom
mismatches. Every PRINTED row must exist in the record and reproduce exactly; the
ten unprinted record rows are listed, because a reader of the table cannot know
they exist.
"""
import json
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
REC = HERE / "measurements" / "crossover_2026-08-13e.json"
PAPER = HERE / "tnf_paper.tex"


def printed_rows(tex):
    for m in re.finditer(r"\\begin\{table\}(.*?)\\end\{table\}", tex, re.S):
        if r"\label{tab:tailsweep}" in m.group(1):
            body = m.group(1)
            break
    else:
        raise SystemExit("tab:tailsweep not found")
    body = re.sub(r"\\caption\{(?:[^{}]|\{[^{}]*\})*\}", "", body, flags=re.S)
    out = []
    for raw in body.split(r"\\"):
        cells = [c.strip() for c in raw.split("&")]
        if len(cells) < 7:
            continue
        if "tabular" in cells[0] or "label" in cells[0]:
            continue
        fam = re.sub(r"\\hline|[{}\\$]", "", cells[0]).strip()
        if not fam or fam == "family":
            continue
        param = re.sub(r"[{}\\$]|hline", "", cells[1]).strip()
        vals = []
        for c in cells[2:7]:
            c = re.sub(r"\\mathrm\{e\}\{(-?\d+)\}", r"e\1", c)
            c = c.replace("$", "").replace(r"\,", "").strip()
            try:
                vals.append(float(c))
            except ValueError:
                vals.append(None)
        out.append({"family": fam, "param": param, "vals": vals})
    return out


def norm_param(p):
    """`$\\sigma=0.5$` prints what the record stores as `sigma=0.5` (or `0.5`)."""
    p = p.replace("\\sigma", "sigma").replace("\\nu", "nu").replace(" ", "")
    return re.sub(r"[^a-z0-9=.+-]", "", p.lower())


def at_printed_precision(value, printed):
    if printed is None:
        return value is None or (isinstance(value, float) and value != value)
    s = repr(printed)
    if "e" in s:
        mant = s.split("e")[0].lstrip("-")
        sig = len(mant.replace(".", "").rstrip("0")) or 1
        from math import floor, log10
        if value == 0:
            return printed == 0
        return round(value, -int(floor(log10(abs(value)))) + sig - 1) == printed
    dec = len(s.split(".")[1]) if "." in s else 0
    return round(value, dec) == printed


def main():
    rec = json.loads(REC.read_text())
    printed = printed_rows(PAPER.read_text())
    print(f"record rows {len(rec)}   printed rows {len(printed)}")

    bad = []

    def fam_key(f):
        f = f.lower().replace("$", "").replace("\\", "")
        f = f.replace("log-normal", "lognormal").replace("student t", "student_t")
        return f.replace(" ", "_")

    def param_num(p):
        m = re.search(r"[-+]?\d*\.?\d+", str(p).replace("\\%", "%"))
        v = float(m.group(0)) if m else None
        if v is not None and "%" in str(p):
            v = v / 100.0
        return v

    index = {(fam_key(r["family"]), param_num(r["param"])): r for r in rec}
    matched = set()
    pairs = []
    for p in printed:
        k = (fam_key(p["family"]), param_num(p["param"]))
        r = index.get(k)
        if r is None:
            bad.append(f"printed row {p['family']} {p['param']} has NO record row")
            continue
        matched.add(k)
        pairs.append((p, r))
    unprinted = [f"{r['family']} {r['param']} (span {r['span']:.1f}, "
                 f"ratio_vs_takum {r['ratio_vs_takum']:.3f})"
                 for k, r in index.items() if k not in matched]

    for p, r in pairs:
        tag = f"{p['family']} {p['param']}"
        s_, tnf, tak, r_tak, r_b16 = p["vals"]
        # ratio identities pin the columns before values are judged
        if r["tnf"] and abs(r["ratio_vs_takum"] - r["takum"] / r["tnf"]) > 1e-9:
            bad.append(f"{tag}: record ratio_vs_takum != takum/tnf")
        b16 = r.get("binary16")
        b16_finite = isinstance(b16, (int, float)) and b16 == b16
        if b16_finite and r["tnf"] and abs(r["ratio_vs_binary16"] - b16 / r["tnf"]) > 1e-9:
            bad.append(f"{tag}: record ratio_vs_binary16 != binary16/tnf")
        for got, exp, name in ((s_, r["span"], "S"), (tnf, r["tnf"], "tnf"),
                               (tak, r["takum"], "takum"),
                               (r_tak, r["ratio_vs_takum"], "ratio_vs_takum"),
                               (r_b16, r["ratio_vs_binary16"] if b16_finite else None,
                                "ratio_vs_binary16")):
            if not at_printed_precision(exp, got):
                bad.append(f"{tag} {name}: printed {got} record {exp}")

    # the caption's own claim is data too
    worst = max(rec, key=lambda r: r["ratio_vs_takum"])
    if worst["ratio_vs_takum"] >= 1.0:
        bad.append(f"caption says 'No row favours TNF' but {worst['family']} "
                   f"{worst['param']} has ratio_vs_takum {worst['ratio_vs_takum']:.3f} >= 1")

    if bad:
        print(f"\nFAIL: {len(bad)} mismatch(es)\n")
        for b in bad:
            print(f"  {b}")
        return 1
    print(f"\nOK: {len(pairs)} printed rows reproduce exactly, ratio identities hold, "
          "and the caption's 'no row favours TNF' recomputes true over ALL 18 "
          "measured rows, printed or not")
    print(f"\nNOTE -- {len(unprinted)} measured rows are not printed, and no selection "
          "rule is stated:")
    for u in unprinted:
        print(f"  {u}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
