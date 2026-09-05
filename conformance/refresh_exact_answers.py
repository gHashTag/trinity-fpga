#!/usr/bin/env python3
"""Recompute the answers in every `*_exact.json` pack from the oracle it names.

The 38 division and square-root packs have NO generator. `generate_vectors.py`
does not produce them -- the string `div_exact` appears in it zero times -- and
a search of this repository and of t27 finds only consumers. They exist because
they are committed.

That cost a correction its second half. When `takum_ref.py` was fixed on
2026-08-18 ("wrong on every negative code"), running the generator refreshed
add, mul and sub; the four takum division packs kept answers from the broken
decode for four more days, until an audit named the counts and they were
rebuilt by hand.

This is that hand-rebuild, committed, so the next oracle correction is one
command rather than an archaeology exercise.

WHAT IT DOES NOT DO: it does not choose operands. The pairs in these packs were
selected by something no longer in the tree, and their selection rule is not
recoverable -- 251 vectors over 251 distinct `a` values with `b` varying is a
search whose seed nobody wrote down. Reproducing the packs byte for byte is
therefore impossible; refreshing their ANSWERS for the operands they already
carry is not, because each pack states its own recipe in its `oracle` field.
Keeping the operand set fixed is also what makes this safe to run: a rebuild
that quietly re-selects its operands is a different pack wearing the same name.
"""
import argparse
import importlib
import json
import pathlib
import re
import sys

# Formats a pack names one way and its oracle names another. Copied from
# research/audit_pack_vs_oracle.py deliberately: two spellings of the same
# table would be one more place for them to drift apart.
ALIASES = {
    "fp32_e8m23":    ("ieee_ref", "binary32"),
    "fp128_e15m112": ("ieee_ref", "binary128"),
    "bf16":          ("bf16_ref", "bfloat16"),
}

HERE = pathlib.Path(__file__).resolve().parent
VECTORS = HERE / "vectors"
sys.path.insert(0, str(HERE))


def indent_of(text):
    """The pack's own formatting, so a refresh is a diff of answers only.

    One pack in this corpus is pretty-printed and the rest are single-line.
    Rewriting with a fixed style turned 159 real changes into a 1,117-line
    deletion the first time this was done by hand -- a diff nobody can review
    is a change nobody can check.
    """
    m = re.search(r'\n(\s+)"', text)
    return len(m.group(1)) if m else None


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true",
                    help="report what would change and exit 1 if anything would; "
                         "write nothing")
    args = ap.parse_args()

    import exact_ops

    packs = sorted(VECTORS.glob("*_exact.json"))
    total_changed = 0
    stale = []
    skipped = []
    for p in packs:
        text = p.read_text()
        doc = json.loads(text)
        oracle = doc.get("oracle", "")
        m = re.match(r"([A-Za-z0-9_]+)\.py", oracle)
        if not m:
            skipped.append((p.name, f"oracle field does not name a module: {oracle!r}"))
            continue
        try:
            mod = importlib.import_module(m.group(1))
        except Exception as e:
            skipped.append((p.name, f"import {type(e).__name__}: {e}"))
            continue
        fname = doc.get("format")
        fmt = mod.FORMATS.get(fname)
        if fmt is None and fname in ALIASES:
            # Three packs name a format their oracle spells differently. The
            # same table lives in research/audit_pack_vs_oracle.py, and using
            # ITS spelling rather than a second guess is what keeps the
            # refresher and the auditor talking about the same thing.
            alias_mod, alias_fmt = ALIASES[fname]
            try:
                mod = importlib.import_module(alias_mod)
                fmt = mod.FORMATS[alias_fmt]
            except Exception as e:
                skipped.append((p.name, f"alias {alias_mod}.{alias_fmt}: "
                                        f"{type(e).__name__}: {e}"))
                continue
        if fmt is None:
            skipped.append((p.name, f"oracle has no format {fname!r}"))
            continue
        op = doc.get("operation")
        if op == "div":
            fn = exact_ops.make_div(mod)
        elif op == "sqrt":
            fn = exact_ops.make_sqrt(mod)
        else:
            skipped.append((p.name, f"operation {op!r} is not div or sqrt"))
            continue

        hexw = (fmt.width + 3) // 4
        changed = 0
        for v in doc["vectors"]:
            a = int(v["a"], 16)
            b = int(v["b"], 16)
            new = f"0x{fn(fmt, a, b):0{hexw}x}"
            if new != v["expected"]:
                v["expected"] = new
                changed += 1
        if changed:
            stale.append((p.name, changed, len(doc["vectors"])))
            total_changed += changed
            if not args.check:
                ind = indent_of(text)
                out = json.dumps(doc, indent=ind) if ind else json.dumps(doc)
                if text.endswith("\n"):
                    out += "\n"
                p.write_text(out)

    print(f"packs examined: {len(packs)}   skipped: {len(skipped)}")
    for n, why in skipped:
        print(f"  SKIP {n}: {why}")
    if not stale:
        print("OK: every pack's answers already match the oracle it names")
        return 0
    verb = "would change" if args.check else "refreshed"
    print(f"\n{len(stale)} pack(s) {verb}, {total_changed} answer(s):")
    for n, c, t in stale:
        print(f"  {n}: {c} of {t}")
    if args.check:
        print("\nThese packs no longer agree with their own oracle. Run without "
              "--check to refresh them.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
