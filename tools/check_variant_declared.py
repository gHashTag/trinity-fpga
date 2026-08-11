#!/usr/bin/env python3
"""Every compared decoder declares its variant, and the map records it.

Two failures this work made are the same failure. takum16 was reported wrong on
98.7% of its codes because a logarithmic decoder was compared against a linear
reference; lns16 was reported wrong on 253 codes because a scale-128 decoder was
compared against a scale-256 reference. Both decoders were correct. The
disagreement measured the distance between two variants, which is a property of
the pair and says nothing about either implementation.

A conformance test cannot detect this by itself: agreement is the only signal it
has, and both variants are internally consistent. The variant must therefore be
fixed by declaration outside the test. This gate requires two declarations and
that they agree:

  1. the RTL states its variant in a header comment (value formula or scale);
  2. conformance/variant_map.json records, per format, which reference module
     and key it is compared against, and a one-line note naming the variant.

A pair with no checker is a pair that will diverge. This is that checker.
"""
import json, pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
MAP = ROOT / "conformance" / "variant_map.json"
if not MAP.exists():
    print(f"FAIL: {MAP.relative_to(ROOT)} is missing"); sys.exit(1)
entries = json.loads(MAP.read_text())

fails = []
for fmt, e in sorted(entries.items()):
    rtl = ROOT / e["rtl"]
    if not rtl.exists():
        fails.append(f"{fmt}: rtl {e['rtl']} does not exist"); continue
    head = "\n".join(l for l in rtl.read_text().splitlines()[:24] if l.strip().startswith("//"))
    if not head.strip():
        fails.append(f"{fmt}: {e['rtl']} has no header comment to declare a variant"); continue
    # The declaration must be checkable, not merely present: the token the map
    # calls distinguishing must actually appear in the header.
    tok = e.get("declares")
    if not tok:
        fails.append(f"{fmt}: map has no 'declares' token"); continue
    if tok.lower() not in head.lower():
        fails.append(f"{fmt}: header does not contain its declared variant token {tok!r}")
    ref = ROOT / "conformance" / (e["ref_module"] + ".py")
    if not ref.exists():
        fails.append(f"{fmt}: reference module {e['ref_module']}.py does not exist")

# Coverage: a format the paper makes a conformance claim about, but which has
# no entry here, is a format whose variant nothing checks. posit8 was exactly
# that -- its reference declares es=0 and its RTL es=2, scoring 3 of 255
# against the wrong one, and the gate stayed green because posit8 was absent.
TABLE = ROOT / "research" / "arxiv_tnf" / "full_table.json"
if TABLE.exists():
    import unicodedata
    def norm(s): return "".join(c for c in s.lower() if c.isalnum())
    have = {norm(k) for k in entries} | {norm(e["table_name"]) for e in entries.values()
                                          if e.get("table_name")}
    for row in json.loads(TABLE.read_text()):
        claim = row.get("checked", "")
        if "not swept" in claim or "no reference" in claim: continue
        if row.get("ours"): continue            # ours are checked by their own oracles
        if norm(row["format"]) not in have:
            fails.append(f"{row['format']}: claims conformance ({claim}) "
                         f"but has no variant_map entry -- nothing checks which variant")

print(f"variant declarations checked: {len(entries)}")
if fails:
    print(f"\nFAIL: {len(fails)} declaration problem(s)\n")
    for f in fails: print(f"  {f}")
    sys.exit(1)
print("OK: every compared decoder declares its variant and the map agrees")
