#!/usr/bin/env python3
"""Does every table that prints a SUBSET of its record say so?

Two tables were caught printing fewer rows than their record holds, with no stated
rule, and in both the omitted rows were the interesting ones:

    tab:window      record 11 rows, printed 9   -- c=24 and c=32 absent unmarked
    tab:tailsweep   record 18 rows, printed 8   -- the absent tail held the row
                    where TNF's mean error is 2.48e+35 (two clips of 12,000);
                    the printed sweep stops one step before the failure point

The contrast that defines the rule: `tab:invariant` prints 30 of its record's 180
rows and its caption SAYS WHY ("Only rows in which every sample lies inside the
representable range of both formats are listed"). A selection is editorial
judgement and often right; an UNSTATED selection is indistinguishable from
cherry-picking, even when it is innocent.

This gate walks a REGISTRY of (record, table) pairs whose backing relation has
been established by a reconstruction script, counts rows on both sides, and
requires any shortfall to be disclosed in the caption -- either an explicit
"N of its M rows" or the registry's note of where the rule is stated.

The registry is explicit rather than inferred: matching records to tables by
name or by numeric overlap over-reported by an order of magnitude every time it
was tried here. A pair enters this file when its regenerator lands, not before.
"""
import json
import re
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
TEX = ROOT / "research" / "arxiv_tnf" / "tnf_paper.tex"
MEAS = ROOT / "research" / "arxiv_tnf" / "measurements"

# (record, label, how to count record rows, expected disclosure)
# kind: "list"  -> the record is a JSON array, one object per candidate row
#       "rows"  -> the record is a dict with a "rows" array
# rule: "full"      -> every record row must be printed
#       "stated"    -> a subset is fine; the caption must contain `phrase`
#       "aggregate" -> the table prints per-group summaries, not record rows;
#                      row-count comparison is meaningless and skipped
REGISTRY = [
    dict(rec="crossover_2026-08-13e.json", label="tab:tailsweep", kind="list",
         rule="stated", phrase="of its 18 rows"),
    dict(rec="crossover2_2026-08-13e.json", label="tab:window", kind="list",
         rule="stated", phrase="of its"),
    dict(rec="strict_range_2026-08-13g.json", label="tab:invariant", kind="rows",
         rule="stated", phrase="are listed"),
    dict(rec="workloads_strict_2026-08-13g.json", label="tab:workloads", kind="rows",
         rule="full"),
    dict(rec="inside_window_2026-08-13f.json", label="tab:landing", kind="list",
         rule="full"),
    dict(rec="per_rung_2026-08-13g.json", label="tab:rungthr", kind="rows",
         rule="aggregate"),
    # added when their regenerators landed (W875):
    dict(rec="centering_2026-08-13f.json", label="tab:centring", kind="list",
         rule="full"),
    dict(rec="gpt2_window_2026-08-13e.json", label="tab:gpt2window", kind="list",
         rule="full"),
    dict(rec="breakeven_2026-08-14.json", label="tab:oneoverm", kind="rows",
         rule="aggregate"),  # 5 printed rows are derived from 3 scalars via C/(2cM)
]


def table_env(tex, label):
    for m in re.finditer(r"\\begin\{table\}(.*?)\\end\{table\}", tex, re.S):
        if f"\\label{{{label}}}" in m.group(1):
            return m.group(1)
    return None


def caption_of(env):
    c = env.find("\\caption{")
    if c < 0:
        return ""
    i, depth = c + 9, 1
    while i < len(env) and depth:
        if env[i] == "{":
            depth += 1
        elif env[i] == "}":
            depth -= 1
            if not depth:
                break
        i += 1
    return re.sub(r"\s+", " ", env[c + 9:i])


def printed_row_count(env):
    body = env
    c = body.find("\\caption{")
    if c >= 0:
        cap = caption_of(env)
        body = body.replace("\\caption{" + cap, "", 1) if cap else body
    body = re.sub(r"\\caption\{(?:[^{}]|\{[^{}]*\})*\}", "", body, flags=re.S)
    n = 0
    for raw in body.split(r"\\"):
        cells = [x.strip() for x in raw.split("&")]
        if len(cells) < 2 or "tabular" in cells[0] or "label" in cells[0]:
            continue
        first = re.sub(r"\\hline|[{}\\$]", "", cells[0]).strip()
        # a data row's remaining cells carry at least one number
        if first and any(re.search(r"\d", c) for c in cells[1:]):
            # header rows name columns; they carry words like "family" or "pair"
            # in the first cell AND no digits elsewhere -- already excluded above
            n += 1
    return n


def record_row_count(path, kind):
    d = json.loads(path.read_text())
    # The registry states the shape it EXPECTS; a shape mismatch is a finding
    # about the registry, reported as such rather than crashing mid-walk.
    if kind == "list":
        if not isinstance(d, list):
            raise ValueError(f"{path.name}: registered as list, is {type(d).__name__}")
        return len(d)
    if kind == "rows":
        if not (isinstance(d, dict) and isinstance(d.get("rows"), list)):
            raise ValueError(f"{path.name}: registered as rows-dict, is {type(d).__name__}")
        return len(d["rows"])
    raise ValueError(kind)


def main():
    tex = TEX.read_text()
    fails = []
    for e in REGISTRY:
        env = table_env(tex, e["label"])
        if env is None:
            fails.append(f"{e['label']}: table not found")
            continue
        if e["rule"] == "aggregate":
            continue
        try:
            rec_n = record_row_count(MEAS / e["rec"], e["kind"])
        except ValueError as ex:
            fails.append(f"{e['label']}: {ex}")
            continue
        prn_n = printed_row_count(env)
        cap = caption_of(env)
        if prn_n == 0:
            fails.append(f"{e['label']}: parsed 0 printed rows -- parser, not paper")
            continue
        if e["rule"] == "full":
            if prn_n < rec_n:
                fails.append(f"{e['label']}: prints {prn_n} of {rec_n} record rows "
                             f"and is registered as FULL")
        else:
            if prn_n < rec_n and e["phrase"].lower() not in cap.lower():
                fails.append(f"{e['label']}: prints {prn_n} of {rec_n} rows and the "
                             f"caption does not say so (expected {e['phrase']!r})")
        print(f"  {e['label']:18s} record {rec_n:3d}  printed {prn_n:3d}  "
              f"{'FULL' if prn_n >= rec_n else 'subset, ' + ('disclosed' if e['rule'] == 'stated' and e['phrase'].lower() in cap.lower() else 'SILENT')}")

    BASE = pathlib.Path(__file__).with_name("selection_baseline.txt")
    if "--update-baseline" in sys.argv:
        BASE.write_text("\n".join(sorted(fails)) + ("\n" if fails else ""))
        print(f"baseline written: {len(fails)} known")
        return 0
    known = set(BASE.read_text().splitlines()) if BASE.exists() else set()
    new = [f for f in fails if f not in known]
    if new:
        print(f"\nFAIL: {len(new)} undisclosed selection(s)\n")
        for f in new:
            print(f"  {f}")
        return 1
    print(f"\nOK: every registered subset is disclosed ({len(known)} known exception(s))")
    return 0


if __name__ == "__main__":
    sys.exit(main())
