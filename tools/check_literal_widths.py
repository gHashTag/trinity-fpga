#!/usr/bin/env python3
"""No sized literal is wider than it declares, and no casez arm is unreachable.

posit32's leading-zero count had one casez pattern written 32 bits wide in a
31-bit case. Verilog truncates from the left, which turned the lzc=11 arm into a
byte-for-byte copy of the lzc=10 arm above it: unreachable, so every code with
exactly eleven leading zeros fell through to the default. It cost 48 wrong
values out of 40,000 and looked like a regime-arithmetic bug for two iterations.

iverilog said so, every single run:

    warning: Extra digits given for sized binary constant.

The harness redirected compiler output to a log nobody read. A warning nobody
reads is not a warning; this gate turns that class into an exit code.

Over-wide hex literals whose lost bits are all zero are ignored -- 23'h000000 is
idiomatic and harmless. Binary patterns are never ignored: in a casez the lost
character changes which values match, whatever it was.
"""
import pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
LIT = re.compile(r"(\d+)'([bh])([01?_zxA-Fa-f]+)", re.I)
# Failing scope is the path the paper measures: fpga/tnet/** and the decoders
# in fpga/openxc7-synth. Everything else is counted and printed, never dropped
# silently -- a bounded gate that does not say what it bounded reads as
# "covered everything".
def measured(f):
    r = str(f.relative_to(ROOT))
    return r.startswith("fpga/tnet/") or (r.startswith("fpga/openxc7-synth/")
                                          and "/tb/" not in r and "_decode" in r)

fails, elsewhere, checked = [], [], 0

for f in sorted((ROOT / "fpga").rglob("*.v")):
    for i, line in enumerate(f.read_text().splitlines(), 1):
        for m in LIT.finditer(line):
            w, base, body = int(m.group(1)), m.group(2).lower(), m.group(3).replace("_", "")
            checked += 1
            bits = body if base == "b" else "".join(
                "????" if ch in "?zZxX" else f"{int(ch,16):04b}" for ch in body)
            if len(bits) <= w:
                continue
            lost = bits[:len(bits) - w]
            if base == "h" and set(lost) <= {"0"}:
                continue
            msg = (f"{f.relative_to(ROOT)}:{i}  declares {w} bits, "
                   f"writes {len(bits)}, silently drops {lost!r}   {m.group(0)[:44]}")
            (fails if measured(f) else elsewhere).append(msg)

# Unreachable casez arms: two patterns that match exactly the same values, the
# later one dead. This is what the width bug produced, so check the effect too.
CASE = re.compile(r"(\d+)'b([01?]+)\s*:")
# Scope is one case block, not one file: the same 2'b00 arm appearing in two
# separate case statements is normal, and treating a file as one scope reported
# 2,616 shadowed arms where the repository holds none.
for f in sorted((ROOT / "fpga").rglob("*.v")):
    seen, inside = {}, False
    for i, line in enumerate(f.read_text().splitlines(), 1):
        if re.search(r"\bcase[zx]?\b", line): seen, inside = {}, True; continue
        if "endcase" in line: inside = False; continue
        if not inside: continue
        m = CASE.search(line)
        if not m: continue
        w, pat = int(m.group(1)), m.group(2)
        key = pat[-w:] if len(pat) > w else pat.rjust(w, "0")
        if key in seen:
            msg = (f"{f.relative_to(ROOT)}:{i}  case arm is unreachable: "
                   f"same pattern as line {seen[key]} after width truncation")
            (fails if measured(f) else elsewhere).append(msg)
        else:
            seen[key] = i

print(f"sized literals checked: {checked}")
if elsewhere:
    print(f"outside the measured path, NOT gated: {len(elsewhere)} "
          f"(tf3 test benches -- real, and tracked, but not this paper's path)")
    for x in elsewhere[:3]: print(f"    {x}")
if fails:
    print(f"\nFAIL: {len(fails)} literal-width or reachability problem(s)\n")
    for x in fails[:20]: print(f"  {x}")
    if len(fails) > 20: print(f"  ... and {len(fails)-20} more")
    sys.exit(1)
print("OK: every sized literal fits and no case arm is shadowed")
