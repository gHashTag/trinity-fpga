#!/usr/bin/env python3
"""Cross-artefact parameter gate.

Every existing check verifies an artefact against itself: the oracle round-trips,
the RTL simulates, the catalogue validates. All three passed while the oracle and
the RTL implemented DIFFERENT formats under the name TNF16 -- Et=6, M=9 in a
20-bit word against Et=4, M=8 in a 16-bit one.

No within-artefact test can catch that. This one compares the declared
PARAMETERS across artefacts, which is the only place the divergence shows.

Exit 1 on any disagreement, and on any format whose declared parameters do not
fit its declared storage.
"""
import re, sys, math, pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
CAT = ROOT.parent / "t27" / "specs" / "numeric" / "formats_catalog.t27"
RTL = ROOT / "fpga" / "tnet" / "bnf_decode.v"

fails = []

# --- 1. catalogue: do declared parameters fit declared storage? -------------
cat = {}
if CAT.exists():
    for m in re.finditer(r'id=(\w+)\s+name="([^"]+)"\s+bits=(\d+)\s+s=1\s+e=(\d+)\s+m=(\d+)', CAT.read_text()):
        fid, name, N, e, mm = m.group(1), m.group(2), int(m.group(3)), int(m.group(4)), int(m.group(5))
        tern = fid.startswith(("gft", "tnf"))
        cat[fid] = dict(name=name, N=N, e=e, m=mm, ternary=tern)
        # Parametric families declare no width (Q-format, minifloat, Unum I,
        # tapered FP) and GFTernary is a 2-bit alphabet rather than a float --
        # the fit test does not apply to either.
        if N < 2 or fid == "gfternary":
            continue
        codes = (3 ** e if tern else 2 ** e) * (2 ** mm)
        if codes > (1 << (N - 1)):
            need = math.ceil(math.log2(codes)) + 1
            fails.append(f"[catalogue] {name}: e={e}{' trits' if tern else ' bits'}, m={mm} "
                         f"needs {need} bits but declares {N}")

# --- 2. RTL: what parameters does the decoder actually implement? -----------
rtl = {}
if RTL.exists():
    src = RTL.read_text()
    for mod in re.finditer(r'module (\w+)_decode \(input wire \[(\d+):0\] x.*?endmodule', src, re.S):
        nm, hi = mod.group(1), int(mod.group(2))
        body = mod.group(0)
        f = re.search(r'wire \[(\d+):0\] (?:e|off) = x\[(\d+):(\d+)\]', body)
        g = re.search(r'wire \[(\d+):0\] m = x\[(\d+):(\d+)\]', body)
        if not (f and g): continue
        efield = int(f.group(2)) - int(f.group(3)) + 1
        mbits = int(g.group(2)) - int(g.group(3)) + 1
        tern = "трита" in body or "trits" in body or nm.startswith("tnf")
        # a ternary field of E bits holds floor(E*log2(3)... ) -> read the trit count
        t = re.search(r'(\d+)\s*(?:трита|trits)', body)
        trits = int(t.group(1)) if t else None
        rtl[nm] = dict(width=hi + 1, efield=efield, m=mbits, ternary=tern, trits=trits)

# --- 3. do they agree? ------------------------------------------------------
# The rename to TNF changed display names but not catalogue ids, which are
# still gft*. Map RTL module names onto catalogue ids explicitly rather than
# letting the lookup miss silently -- a gate that quietly finds nothing is the
# failure mode this file exists to prevent.
ALIAS = {f"tnf{n}": f"gft{n}" for n in (4, 8, 16, 32, 64, 128, 256, 512, 1024)}
for nm, r in rtl.items():
    c = cat.get(nm) or cat.get(ALIAS.get(nm, ""))
    if not c:
        print(f"  note: RTL decoder {nm} has no catalogue row -- not compared")
        continue
    if r["ternary"] and r["trits"] is not None:
        if r["trits"] != c["e"]:
            fails.append(f"[divergence] {nm}: RTL implements Et={r['trits']}, "
                         f"catalogue declares e={c['e']}")
    if r["m"] != c["m"]:
        fails.append(f"[divergence] {nm}: RTL mantissa {r['m']} bits, "
                     f"catalogue declares m={c['m']}")
    if r["width"] != c["N"]:
        fails.append(f"[divergence] {nm}: RTL word {r['width']} bits, "
                     f"catalogue declares bits={c['N']}")

# --- 4. does a ternary field claim the capacity of its binary sibling? -------
for nm, r in rtl.items():
    if not (r["ternary"] and r["trits"]): continue
    sib = nm.replace("tnf", "bnf")
    s = rtl.get(sib)
    if not s: continue
    tcap, bcap = 3 ** r["trits"], 2 ** s["efield"]
    if tcap != bcap:
        fails.append(f"[capacity] {nm} field holds {tcap} exponents, {sib} holds {bcap} "
                     f"({100*(1-tcap/bcap):.1f}% less) -- an area comparison between them "
                     f"is not at equal capability")

# --- 5. implementation orphans -------------------------------------------
# A module that synthesises and measures but has no catalogue row is checked by
# nothing: specification gates do not see it, and instrument checks only confirm
# it does what it does. Its numbers reach a report with the same weight as
# verified ones.
for nm, r in rtl.items():
    cid = nm if nm in cat else ALIAS.get(nm, "")
    c = cat.get(cid)
    if not c:
        continue
    if r["ternary"] and r["trits"] is not None:
        match = [k for k, v in cat.items()
                 if v["ternary"] and v["e"] == r["trits"] and v["m"] == r["m"]
                 and v["N"] == r["width"]]
        if not match:
            fails.append(f"[orphan] {nm} implements Et={r['trits']}, M={r['m']} in "
                         f"{r['width']} bits, which matches no catalogue row -- "
                         f"synthesised and measured but specified nowhere")

# --- 6. ratchet ------------------------------------------------------------
# The tree currently carries known divergences whose fix is an owner decision
# (rename by actual storage, or respecify the ladder packed). Blocking every PR
# on that debt would make the gate useless until someone pays it. So the known
# set is recorded as a baseline and the gate fails only on NEW disagreements --
# and on baseline entries that have disappeared, so the file cannot rot into a
# permanent excuse.
BASE = pathlib.Path(__file__).with_name("artefact_agreement_baseline.txt")
print(f"catalogue rows parsed: {len(cat)}   RTL decoders parsed: {len(rtl)}")

if "--update-baseline" in sys.argv:
    BASE.write_text("\n".join(sorted(fails)) + ("\n" if fails else ""))
    print(f"baseline written: {len(fails)} known disagreement(s)")
    sys.exit(0)

known = set()
if BASE.exists():
    known = {l for l in BASE.read_text().splitlines() if l.strip()}
cur = set(fails)
new, fixed = sorted(cur - known), sorted(known - cur)

if fixed:
    print(f"\n{len(fixed)} baseline entry/entries no longer reproduce -- "
          f"run with --update-baseline to shrink the ratchet:")
    for f in fixed: print(f"  [fixed] {f}")
if new:
    print(f"\nFAIL: {len(new)} NEW disagreement(s) beyond the baseline\n")
    for f in new: print(f"  {f}")
    sys.exit(1)
if fixed:
    sys.exit(1)
print(f"OK: no new disagreements ({len(known)} known, see "
      f"{BASE.name} and research/frontier/WITHDRAWAL_1*.md)")
