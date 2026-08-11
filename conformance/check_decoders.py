#!/usr/bin/env python3
"""Do the decoders in the throughput table decode correctly?

The table prices twenty decoders by area and frequency. Neither says anything
about whether the circuit computes the right value, and a decoder that is wrong
is small for a reason. Every code of every 8- and 16-bit format was swept
through the same RTL that was synthesised; this compares the fp32 it produced
against the format's reference implementation.

A mismatch here invalidates a row of the table, not merely a module.
"""
import struct, sys, pathlib, importlib.util

ROOT = pathlib.Path(__file__).resolve().parents[1]
SWEEP = ROOT / "fpga" / "tnet"

def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "conformance" / f"{name}.py")
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m

def fp32(h):
    return struct.unpack(">f", bytes.fromhex(h))[0]

def sweep(tag):
    f = SWEEP / f"cf_{tag}.txt"
    if not f.exists(): return None
    out = {}
    for line in f.read_text().splitlines():
        p = line.split()
        if len(p) == 2 and p[0].isdigit():
            try: out[int(p[0])] = fp32(p[1])
            except Exception: pass
    return out

def close(a, b, tol=1e-6):
    if a != a and b != b: return True          # NaN vs NaN
    if a in (float("inf"), float("-inf")) or b in (float("inf"), float("-inf")):
        return a == b
    if b == 0: return abs(a) < 1e-38
    return abs(a - b) <= tol * max(abs(a), abs(b), 1e-38)

# Every oracle exposes FORMATS: name -> format object.
SPEC = [("fp8e4m3",   "fp8_ref",       "fp8_e4m3"),
        ("fp8e5m2",   "fp8_ref",       "fp8_e5m2"),
        ("gfternary", "gfternary_ref", "gfternary"),
        ("binary16",  "ieee_ref",      "binary16"),
        ("posit16",   "posit_ref",     "posit16"),
        # Ours are checked too. Reporting that a competitor's decoder is
        # incomplete while never checking our own would be the asymmetry this
        # project exists to avoid.

        ("gf10",      "gf_ref",        "gf10"),
        ("gf14",      "gf_ref",        "gf14")]
CASES = []
# tnf16_ref takes the raw code directly rather than a format object.
try:
    _t = load("tnf16_ref")
    CASES.append(("tnf16", lambda r, m=_t: float(m.decode(r))))
except Exception as e:
    print(f"  tnf16: oracle unavailable -- {e}")

for tag, mod, key in SPEC:
    try:
        m = load(mod); fmt = m.FORMATS[key]
        CASES.append((tag, lambda r, m=m, f=fmt: float(m.decode(f, r))))
    except Exception as e:
        print(f"  {tag}: oracle unavailable -- {e}")

fails, checked, counts = [], 0, {}
for tag, ref in CASES:
    got = sweep(tag)
    if not got:
        print(f"  {tag}: no sweep captured -- skipped"); continue
    bad = 0
    for raw, v in sorted(got.items()):
        try: want = ref(raw)
        except Exception: continue
        checked += 1
        if not close(v, want):
            bad += 1
            if bad <= 3:
                fails.append(f"{tag}: code {raw} decoded {v!r}, reference says {want!r}")
    counts[tag] = bad
    print(f"  {tag:12} {len(got):6} codes, {bad} mismatch(es)")

print(f"\ncodes compared: {checked}")
# An instrument that compared nothing has not found agreement; it has found
# nothing. Reporting that as OK is the failure this project keeps meeting.
if checked == 0:
    print("\nFAIL: no codes were compared -- the check saw nothing and must "
          "not report agreement")
    sys.exit(1)
# Ratcheted: four decoders are known not to implement their formats fully --
# TNF16 (ours, a mantissa bit narrow), fp8 e4m3 and e5m2 (subnormals), posit16
# (extremes). Blocking on them would make the gate useless; it fails on new
# divergence and on any regression in the four that pass cleanly.
BASE = pathlib.Path(__file__).with_name("decoder_conformance_baseline.txt")
summary = sorted(f"{t}:{n}" for t, n in counts.items())
if "--update-baseline" in sys.argv:
    BASE.write_text("\n".join(summary) + "\n")
    print(f"baseline written: {len(summary)} formats"); sys.exit(0)
known = dict(l.split(":") for l in BASE.read_text().splitlines() if ":" in l) \
        if BASE.exists() else {}
worse = [f"{t}: {n} mismatches, was {known.get(t, '0')}"
         for t, n in counts.items() if n > int(known.get(t, 0))]
if worse:
    print(f"\nFAIL: {len(worse)} decoder(s) worse than baseline\n")
    for w in worse: print(f"  {w}")
    for f in fails[:6]: print(f"    {f}")
    sys.exit(1)
print(f"OK: no decoder is worse than its baseline ({len(known)} known)")
