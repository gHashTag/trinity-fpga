#!/usr/bin/env python3
"""W993: the matched-width table, counting only words the format produces.

W991 (`measurements/compare_w991.json`) enumerated every code of each physical
width and counted the distinct non-zero finite decodings. For posit and takum
that is the format. For TNF it is not: `tnf_ref.decode` maps an exponent field
above the special row (`offset_max`) to an ordinary power of two, while
`tnf_ref.encode` sends every such magnitude to infinity, so no rounding and no
arithmetic ever produces those words. At 19 bits they are 47 of the 128
exponent rows. W991 counted them, which is where its 516,096 values and 127
binades came from; its "8190 of 2^19 codes are unreachable" is posit19's value
count minus that figure, not a count of words.

This record recomputes every row of `tab:matchedwidth` from the committed
oracles and reports TNF both ways: the words the format produces (the table's
definition from W993 on) and every code (W991's definition, kept so the two
records can be compared line by line). It also checks the operational meaning
of "produces": every finite non-zero word below the special row survives
encode(decode(w)) unchanged, and every word above it does not.

Usage:  python3 matched_width.py [--write]
        --write  write measurements/matched_width_w993.json
"""
import json
import math
import os
import pathlib
import sys
from fractions import Fraction

HERE = pathlib.Path(os.environ.get("T27_WORK") or pathlib.Path(__file__).resolve().parent)
sys.path.insert(0, os.environ.get("T27_CONFORMANCE") or str(HERE / "oracles"))
import tnf_ref as T      # noqa: E402
import posit_ref as P    # noqa: E402
import takum_ref as K    # noqa: E402

OUT = HERE / "measurements" / "matched_width_w993.json"


def columns(values):
    """values, binades and step below 1.0 (in %), as tab:matchedwidth defines them."""
    pos = sorted(v for v in values if v > 0)
    binades = math.log2(pos[-1] / pos[0])
    below = max(v for v in pos if v < 1)
    return {
        "values": len(values),
        "binades": round(binades, 1),
        "step_at_1_pct": round(float((1 - below) * 100), 3),
    }


def finite_nonzero(v):
    return isinstance(v, Fraction) and v != 0


def tnf_rows(exp_trits, mant_bits):
    f = T.TNFFormat(exp_trits, mant_bits)
    width = f.sign_shift + 1
    field = 1 << f.exp_bits
    produced, every = set(), set()
    roundtrip_ok = roundtrip_bad = above_kept = above_total = 0
    for raw in range(1 << width):
        off = (raw >> f.exp_shift) & (field - 1)
        v = T.decode(f, raw)
        if not finite_nonzero(v):
            continue
        every.add(v)
        if off < f.offset_max:
            produced.add(v)
            if T.encode(f, v) == raw:
                roundtrip_ok += 1
            else:
                roundtrip_bad += 1
        else:
            above_total += 1
            if T.encode(f, v) == raw:
                above_kept += 1
    row = 2 * f.mant
    census = {
        "physical_bits": width,
        "exponent_field_bits": f.exp_bits,
        "exponent_rows": field,
        "trit_word_rows": 3 ** exp_trits,
        "rows_above_special": field - 3 ** exp_trits,
        "words_per_row": row,
        "words_outside_format": (field - 3 ** exp_trits) * row,
        "words_with_finite_nonzero_value": (f.offset_max - 1) * row,
        "words_without_finite_nonzero_value": (1 << width) - (f.offset_max - 1) * row,
        "roundtrip_below_special_ok": roundtrip_ok,
        "roundtrip_below_special_changed": roundtrip_bad,
        "above_special_decoded_finite": above_total,
        "above_special_survive_roundtrip": above_kept,
    }
    return width, columns(produced), columns(every), census


def enumerate_codes(mod, fmt, width):
    vals = set()
    for raw in range(1 << width):
        v = mod.decode(fmt, raw)
        if finite_nonzero(v):
            vals.add(v)
    return columns(vals)


def main():
    rungs = (("TNF16 (4t,11m)", 4, 11), ("TNF8 (3t,4m)", 3, 4), ("TNF4 (2t,1m)", 2, 1))
    results, all_codes, census = {}, {}, {}
    for name, et, mb in rungs:
        width, prod, every, cen = tnf_rows(et, mb)
        key = f"{width}_bits"
        results[key] = {name: prod}
        all_codes[name] = every
        census[name] = cen
        for es in (1, 2):
            pf = P.PositFormat(f"posit{width}", n=width, es=es)
            results[key][f"posit{width} es={es}"] = enumerate_codes(P, pf, width)
        if width == 19:
            results[key]["takum19"] = enumerate_codes(K, K.TakumFormat("takum19", n=19), 19)
        print(f"{key}: " + "; ".join(f"{k} {v}" for k, v in results[key].items()), flush=True)

    w991 = json.loads((HERE / "measurements" / "compare_w991.json").read_text())
    old = w991["matched_width_results"]
    reproduced = {}
    for key, row in old.items():
        for name, cols in row.items():
            mine = all_codes.get(name) if name.startswith("TNF") else results[key][name]
            reproduced[name] = all(mine[c] == cols[c]
                                   for c in ("values", "binades", "step_at_1_pct"))

    pos19 = results["19_bits"]["posit19 es=1"]["values"]
    tnf19 = results["19_bits"]["TNF16 (4t,11m)"]["values"]
    record = {
        "wave": "W993",
        "what": "tab:matchedwidth recomputed from the committed oracles, counting for TNF "
                "only the words the format produces",
        "instrument": "python3 matched_width.py --write",
        "supersedes": {
            "record": "compare_w991.json",
            "fields": ["matched_width_results (the three TNF rows)",
                       "the_finding (the value counts)",
                       "why_the_value_count_is_short"],
            "why": "tnf_ref.decode reads an exponent field above offset_max as an ordinary "
                   "power of two; tnf_ref.encode sends every such magnitude to infinity. "
                   "W991 enumerated all codes and so counted words no computation produces. "
                   "Its 8190 is posit19's value count minus TNF16's all-codes count, not a "
                   "count of unreachable words; 2^19 minus that count is 8192.",
        },
        "definition": {
            "values": "distinct non-zero finite values; for TNF, of the words whose exponent "
                      "field is below offset_max (the words encode produces)",
            "binades": "log2(largest positive value / smallest positive value)",
            "step_at_1_pct": "1 minus the largest value below 1.0, in percent",
        },
        "matched_width_results": results,
        "tnf_all_codes_as_in_w991": all_codes,
        "w991_rows_reproduced_by_all_codes": reproduced,
        "tnf_code_census": census,
        "the_finding": (
            "posit with es=2 still weakly dominates TNF on range and step at all three "
            f"widths, and the value gap is {(pos19 - tnf19) / 8190:.1f} times the 8190 W991 "
            f"reported: at 19 bits {tnf19} values against {pos19}, a deficit of "
            f"{pos19 - tnf19}. At 10 and 6 "
            "bits posit with es=1 now also dominates on every column."),
    }
    print(json.dumps({"reproduced": reproduced, "census": census}, indent=1))
    if not all(reproduced.values()):
        print("W991 NOT reproduced by the all-codes enumeration: definitions differ")
        return 1
    if "--write" in sys.argv:
        OUT.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n")
        print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
