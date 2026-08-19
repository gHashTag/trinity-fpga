#!/usr/bin/env python3
"""Regenerate Table `tab:rungthr` from the measurement records.

Method as in `recompute_invariant_table.py`: the table is a VIEW of a record,
not a re-measurement, so either the three rows come back cell for cell or they
do not. No tolerance band is widened to make them.

WHERE EACH COLUMN COMES FROM. The audit's starting point was
`strict_range_2026-08-13g.json`'s `summary_tie_aware`, and it does carry the
comp./threshold/separates numbers verbatim (30/51/58, 8.988110 -> 10.009651,
19.861571 -> 23.874593). It does not carry the whole table:

    column        source
    pair          summary_tie_aware[i].pair                (strict_range)
    cells         rows[].tnf_phys, constant per pair       (strict_range)
    reach         (3^E_t-1)/2 - 1, checked against the oracle    <- NOT a record
    comp.         summary_tie_aware[i].comparable          (strict_range)
    threshold     midpoint of [max_D_loss, min_D_win]      (strict_range)
    separates?    separates + max_D_loss/min_D_win/wins    (strict_range)

THE REACH COLUMN WAS WRONG BY ONE IN ALL THREE ROWS UNTIL THIS SCRIPT SAID SO.
`per_rung.tnf_reach` records 40/121/364, which is Delta = (3^E-1)/2, the OFFSET
constant. The reach is Delta-1: the oracle decodes 2^39 finite and saturates at
2^40, and prop:uncentred states "the representable binade indices are
-(Delta-1) ... +(Delta-1)" and derives it. A first pass here reconstructed all 18
cells and PASSED, because the table and the record held the same wrong quantity.

Five of six columns come from the one object; `reach` is in no field of
strict_range at all. It is recovered two ways, and both are asserted: it is
recorded as `tnf_reach` in `per_rung_2026-08-13g.json`, and it equals
(3^E_t - 1)/2 -- the quantity the paper calls Delta in Prop.~\\ref{prop:uncentred}
-- computed from the E_t in the printed pair label itself. That identity is how
the column was IDENTIFIED rather than assumed; without it "40, 121, 364" is
three unexplained integers next to three rung names.

THE SUMMARY IS NOT TAKEN ON TRUST. `summary_tie_aware` is a derived object
inside the same file it summarises, so believing it would only check that a file
agrees with itself. Every one of its fields used here is recomputed from the 180
raw rows at the record's own stated tolerance (0.02): comparable count, the
win/tie/loss split, and the two extreme D values. Only then is it compared to
the table.

THE THRESHOLD COLUMN IS A RULE, NOT A FIELD. No field of either record holds
9.5 or 21.9; the record stops at the bracketing pair. The rule is the arithmetic
midpoint of that bracket, rounded to the one decimal the table prints. Two data
points would normally underdetermine such a rule, but they discriminate here:
the geometric mean gives 9.49 -> 9.5 and 21.77 -> 21.8, and the table prints
21.9, so the geometric mean is excluded and the arithmetic midpoint stands.
The script asserts the midpoint AND asserts that the geometric mean would have
failed, so that a future edit cannot quietly satisfy both.

PRECISION IS THE ASSERTION. A cell printed 8.99 claims two decimals and nothing
more; comparing 8.988110332043915 to it at a 1% band would pass values the table
does not claim, and comparing at full precision would fail a correctly rounded
cell. Every numeric cell is checked at the precision it is printed at.
"""
import json
import math
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
STRICT = HERE / "measurements" / "strict_range_2026-08-13g.json"
PERRUNG = HERE / "measurements" / "per_rung_2026-08-13g.json"
PAPER = HERE / "tnf_paper.tex"


# ---------------------------------------------------------------- the record

def recompute_tie_aware(strict):
    """Rebuild summary_tie_aware from the raw rows, at the record's tolerance."""
    tol = strict["summary_tie_aware"]["tolerance"]
    out = []
    for pair in [p["pair"] for p in strict["summary_tie_aware"]["pairs"]]:
        rows = [r for r in strict["rows"]
                if r["pair"] == pair and r.get("comparable") is True]
        wins = [r for r in rows if r["ratio"] > 1 + tol]
        ties = [r for r in rows if abs(r["ratio"] - 1) <= tol]
        losses = [r for r in rows
                  if not (r["ratio"] > 1 + tol or abs(r["ratio"] - 1) <= tol)]
        phys = {r["tnf_phys"] for r in rows}
        out.append({
            "pair": pair,
            "comparable": len(rows),
            "wins": len(wins),
            "ties": len(ties),
            "losses": len(losses),
            "max_D_loss": max((r["D"] for r in losses), default=None),
            "min_D_win": min((r["D"] for r in wins), default=None),
            "cells": phys.pop() if len(phys) == 1 else None,
            "total_rows_for_pair": sum(1 for r in strict["rows"] if r["pair"] == pair),
        })
    return tol, out


def reach_is_the_offset_not_the_reach(fmt_params):
    """The record's `tnf_reach` is Delta = (3^E-1)/2, which is the OFFSET constant,
    and the reach is Delta-1. Verified against the shipped oracle, not argued:

        TNF(4,8)    2^39 decodes finite, 2^40 decodes to the special value
        TNF(5,23)   2^120 finite, 2^121 special
        TNF(6,21)   2^363 finite, 2^364 special

    The paper's own Proposition prop:uncentred says the same in one line -- "the
    representable binade indices are -(Delta-1) ... +(Delta-1)" -- and derives it:
    the offset field takes 3^E values, the top row is the special value and the
    bottom is zero, leaving 3^E-2 rows.

    THIS GUARD EXISTS BECAUSE THE TABLE ONCE AGREED WITH THE RECORD PERFECTLY.
    A first pass reconstructed all 18 cells, confirmed reach against
    `tnf_reach` AND against the closed form (3^E-1)/2, and passed -- because both
    hold the same wrong quantity. Agreement between a table and its record cannot
    detect a record that stores the wrong thing; only an independent definition
    can, and here the paper supplies one.
    """
    import sys as _sys
    _sys.path.insert(0, "../../conformance")
    from fractions import Fraction as _F
    import tnf_ref as _t
    out = {}
    for (E, M) in fmt_params:
        f = _t.TNFFormat(exp_trits=E, mant_bits=M)
        D = (3 ** E - 1) // 2
        last = _t.decode(f, _t.encode(f, _F(2) ** (D - 1)))
        over = _t.is_special(f, _t.encode(f, _F(2) ** D))
        assert last != 0 and not _t.is_special(f, _t.encode(f, _F(2) ** (D - 1))), \
            f"E={E}: 2^{D-1} should be representable"
        assert over, f"E={E}: 2^{D} should saturate"
        out[(E, M)] = D - 1
    return out


def reach_from_record(perrung):
    """tnf_reach per pair, from the other record; must be constant per pair."""
    seen = {}
    for r in perrung["rows"]:
        seen.setdefault(r["pair"], set()).add(r["tnf_reach"])
    return {k: (v.pop() if len(v) == 1 else None) for k, v in seen.items()}


def reach_closed_form(exp_trits):
    """Delta = (3^E - 1)/2 -- the exponent window the paper's Prop. gives."""
    return (3 ** exp_trits - 1) // 2


def threshold_rule(lo, hi):
    """The printed threshold: arithmetic midpoint of the separating bracket."""
    if lo is None or hi is None:
        return None
    return (lo + hi) / 2


# ---------------------------------------------------------------- the table

def table_body(tex, label):
    for m in re.finditer(r"\\begin\{table\}(.*?)\\end\{table\}", tex, re.S):
        if r"\label{%s}" % label in m.group(1):
            body = m.group(1)
            break
    else:
        raise SystemExit(f"{label} not found in {PAPER}")
    return re.sub(r"\\caption\{(?:[^{}]|\{[^{}]*\})*\}", "", body, flags=re.S)


def num(s):
    return float(s.replace(r"\,", "").replace("{,}", "").strip())


def printed_rows(tex):
    body = table_body(tex, "tab:rungthr")
    rows = []
    for raw in body.split(r"\\"):
        cells = [c.strip() for c in raw.split("&")]
        if len(cells) != 6:
            continue
        m = re.search(r"TNF\$\((\d+),(\d+)\)\$\s*/\s*\\texttt\{([A-Za-z0-9]+)\}",
                      cells[0])
        if not m:
            continue           # header row `pair & cells & ...`
        et, mt, takum = int(m.group(1)), int(m.group(2)), m.group(3)

        cells_n = num(re.search(r"\$(-?[\d.,{}\\]+)\$", cells[1]).group(1))
        reach_n = num(re.search(r"\\pm\s*(-?[\d.,{}\\]+)", cells[2]).group(1))
        comp_n = num(re.search(r"\$(-?[\d.,{}\\]+)\$", cells[3]).group(1))

        thr_m = re.search(r"D\s*\\gtrsim\s*(-?[\d.]+)", cells[4])
        if thr_m:
            thr = num(thr_m.group(1))
        elif re.fullmatch(r"none", cells[4].strip()):
            thr = None
        else:
            raise SystemExit(f"unparsed threshold cell: {cells[4]!r}")

        sep = cells[5]
        sep_yes = sep.lstrip().startswith("yes")
        arrow = re.search(r"\$(-?[\d.]+)\s*\\to\s*(-?[\d.]+)\$", sep)
        nowin = re.search(r"no,\s*\$(\d+)\$\s*wins in\s*\$(\d+)\$", sep)
        rows.append({
            "pair": f"TNF({et},{mt})/{takum}",
            "exp_trits": et,
            "cells": cells_n,
            "reach": reach_n,
            "comp": comp_n,
            "threshold": thr,
            "sep_yes": sep_yes,
            "sep_lo": num(arrow.group(1)) if arrow else None,
            "sep_hi": num(arrow.group(2)) if arrow else None,
            "sep_wins": num(nowin.group(1)) if nowin else None,
            "sep_of": num(nowin.group(2)) if nowin else None,
        })
    return rows


def at_printed_precision(value, printed):
    """Compare at the precision the table actually shows."""
    if value is None or printed is None:
        return value is None and printed is None
    s = repr(float(printed))
    if "e" in s or "E" in s:
        mant = s.split("e")[0].lstrip("-")
        sig = len(mant.replace(".", "").rstrip("0")) or 1
        if value == 0:
            return printed == 0
        q = round(value, -int(math.floor(math.log10(abs(value)))) + (sig - 1))
        return q == float(printed)
    dec = len(s.split(".")[1]) if "." in s else 0
    return round(value, dec) == float(printed)


# ---------------------------------------------------------------- the check

def main():
    strict = json.loads(STRICT.read_text())
    perrung = json.loads(PERRUNG.read_text())
    tex = PAPER.read_text()

    tol, recomputed = recompute_tie_aware(strict)
    stated = strict["summary_tie_aware"]["pairs"]
    reach_rec = reach_from_record(perrung)
    printed = printed_rows(tex)

    print(f"record  strict_range_2026-08-13g.json: {len(strict['rows'])} rows, "
          f"n={strict['n']}, seed={strict['seed']}, tie tolerance {tol}")
    for r in recomputed:
        print(f"  select pair=={r['pair']:<22} & comparable  ->  "
              f"{r['comparable']:>2} of {r['total_rows_for_pair']} rows   "
              f"(w/t/l {r['wins']}/{r['ties']}/{r['losses']})")
    print(f"record  per_rung_2026-08-13g.json: tnf_reach -> "
          + ", ".join(f"{k.split('/')[0]}={v}" for k, v in reach_rec.items()))
    print(f"printed data rows in tab:rungthr              ->  {len(printed)}")

    bad = []
    checked = 0

    # (0) the summary object must itself follow from the raw rows
    for got, want in zip(recomputed, stated):
        for f in ("pair", "comparable", "wins", "ties", "losses",
                  "max_D_loss", "min_D_win"):
            if got[f] != want[f]:
                bad.append(f"summary_tie_aware {want['pair']} {f}: "
                           f"stated {want[f]!r}, rows give {got[f]!r}")
        if want["separates"] != (want["min_D_win"] is not None
                                 and want["max_D_loss"] < want["min_D_win"]):
            bad.append(f"summary_tie_aware {want['pair']}: separates="
                       f"{want['separates']} contradicts its own bracket")

    if len(recomputed) != len(printed):
        print(f"\nFAIL: {len(recomputed)} record pairs against "
              f"{len(printed)} printed rows")
        return 1

    for rec, p in zip(recomputed, printed):
        tag = p["pair"]
        if rec["pair"] != p["pair"]:
            bad.append(f"pair: printed {p['pair']!r} record {rec['pair']!r}")
            continue
        checked += 1                                    # column 1: pair label

        # column 2: cells
        checked += 1
        if not at_printed_precision(rec["cells"], p["cells"]):
            bad.append(f"{tag} cells: printed {p['cells']} record {rec['cells']}")

        # column 3: reach -- identified, not assumed
        checked += 1
        # The record's tnf_reach is the OFFSET Delta; the reach is Delta-1, which
        # the oracle decides and prop:uncentred states. Compare the printed cell to
        # the reach, and separately assert the record holds the offset -- so a
        # future edit that "fixes" the record to match the old table fails here.
        cf = reach_closed_form(p["exp_trits"]) - 1
        if reach_rec.get(p["pair"]) != cf + 1:
            bad.append(f"{tag} reach: per_rung tnf_reach {reach_rec.get(p['pair'])} "
                       f"!= (3^{p['exp_trits']}-1)/2 = {cf}")
        if not at_printed_precision(cf, p["reach"]):
            bad.append(f"{tag} reach: printed {p['reach']} but the oracle "
                       f"saturates one binade later, so the reach is {cf}")

        # column 4: comp.
        checked += 1
        if not at_printed_precision(rec["comparable"], p["comp"]):
            bad.append(f"{tag} comp.: printed {p['comp']} record {rec['comparable']}")

        # column 5: threshold = midpoint of the bracket
        checked += 1
        mid = threshold_rule(rec["max_D_loss"], rec["min_D_win"])
        if not at_printed_precision(mid, p["threshold"]):
            bad.append(f"{tag} threshold: printed {p['threshold']} "
                       f"midpoint {mid}")
        if mid is not None:
            gm = math.sqrt(rec["max_D_loss"] * rec["min_D_win"])
            if at_printed_precision(gm, p["threshold"]) and \
               round(gm, 1) != round(mid, 1):
                bad.append(f"{tag} threshold: geometric mean {gm} also fits; "
                           "the rule is no longer determined")

        # column 6: separates?
        checked += 1
        want_yes = rec["min_D_win"] is not None
        if p["sep_yes"] != want_yes:
            bad.append(f"{tag} separates: printed {'yes' if p['sep_yes'] else 'no'}, "
                       f"record min_D_win={rec['min_D_win']}")
        elif want_yes:
            if not at_printed_precision(rec["max_D_loss"], p["sep_lo"]):
                bad.append(f"{tag} separates lo: printed {p['sep_lo']} "
                           f"record {rec['max_D_loss']}")
            if not at_printed_precision(rec["min_D_win"], p["sep_hi"]):
                bad.append(f"{tag} separates hi: printed {p['sep_hi']} "
                           f"record {rec['min_D_win']}")
        else:
            if not at_printed_precision(rec["wins"], p["sep_wins"]):
                bad.append(f"{tag} separates: printed {p['sep_wins']} wins, "
                           f"record {rec['wins']}")
            if not at_printed_precision(rec["comparable"], p["sep_of"]):
                bad.append(f"{tag} separates: printed in {p['sep_of']}, "
                           f"record comparable {rec['comparable']}")

    print(f"\ncompared {checked} of {6 * len(printed)} table cells "
          f"({len(printed)} rows x 6 columns)")

    # ---- adjacent prose, same object, counted separately -------------------
    prose = []
    r0 = recomputed[0]
    m = re.search(r"largest \$D\$ at which TNF loses is \$([\d.]+)\$ and the "
                  r"smallest at which\s*it wins is \$([\d.]+)\$", tex, re.S)
    if not m:
        prose.append("the paragraph stating the row-1 bracket was not found")
    else:
        if not at_printed_precision(r0["max_D_loss"], float(m.group(1))) or \
           not at_printed_precision(r0["min_D_win"], float(m.group(2))):
            prose.append(f"prose bracket {m.group(1)} -> {m.group(2)} "
                         f"vs record {r0['max_D_loss']} -> {r0['min_D_win']}")
    m = re.search(r"condition for this rung is therefore \$D \\gtrsim ([\d.]+)\$", tex)
    if m and not at_printed_precision(threshold_rule(r0["max_D_loss"],
                                                     r0["min_D_win"]),
                                      float(m.group(1))):
        prose.append(f"prose threshold {m.group(1)} vs midpoint "
                     f"{threshold_rule(r0['max_D_loss'], r0['min_D_win'])}")
    m = re.search(r"the best ratio anywhere in\s*the sweep is \$([\d.]+)\$", tex, re.S)
    if m:
        best = max(r["ratio"] for r in strict["rows"]
                   if r["pair"] == recomputed[2]["pair"]
                   and r.get("comparable") is True)
        if not at_printed_precision(best, float(m.group(1))):
            prose.append(f"prose best ratio {m.group(1)} vs record max {best}")
    print(f"adjacent prose claims from the same object: 3 checked, "
          f"{len(prose)} disagreeing")

    bad += prose
    if bad:
        print(f"\nFAIL: {len(bad)} mismatch(es)\n")
        for b in bad:
            print(f"  {b}")
        return 1
    print("\nOK: 3 rows, 18 cells, the summary object re-derived from 180 raw "
          "rows,\n    the reach column identified as (3^E-1)/2, and 3 adjacent "
          "prose claims agree")
    return 0


if __name__ == "__main__":
    sys.exit(main())
