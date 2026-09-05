#!/usr/bin/env python3
"""Campaign B analysis: what asymmetry costs in silicon.

Nothing here computes a new number. It subtracts the harness, VERIFIES the
subtrahend against an independent method, and applies the project's tie rule.
"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import logic_count as L

R = json.load(open(os.path.join(HERE, "results_asym.json")))
OLD = json.load(open(os.path.join(HERE, "results.json")))
SA = json.load(open(os.path.join(HERE, "asym_decode_logic.json")))

def rng(n):
    f = R[n]["f"]
    return min(f), max(f), R[n]["fmed"]

print("=" * 78)
print("0. FLOW IDENTITY: reproduce the published BEL-occupancy numbers")
print("=" * 78)
# The published doc quotes BEL occupancy for its lane rows. Reproducing them
# proves this is the same flow before any logic-counted number is quoted.
chk = [("MXFP4 lane LUT-only, net BEL", R["an_mxfp4"]["lut"] - R["an_h32"]["lut"], 228),
       ("cb6   lane LUT-only, net BEL", OLD["ln_cb6"]["lut"] - OLD["ln_h32"]["lut"], 295),
       ("MXFP4 lane DSP, total BEL",    R["ap_mxfp4"]["lut"], 102),
       ("cb6   lane DSP, total BEL",    OLD["ld_cb6"]["lut"], 105)]
ok = True
for nm, got, pub in chk:
    ok &= got == pub
    print(f"  {nm:32s} got {got:4d}  published {pub:4d}  {'MATCH' if got==pub else 'MISMATCH'}")
print(f"  FLOW IDENTITY: {'PASS' if ok else 'FAIL'}")

print()
print("=" * 78)
print("1. DECODER, LOGIC CELLS -- two independent methods must agree")
print("=" * 78)
# Harness subtraction: the baseline must match the number of bits that actually
# survive to the fold, which is ff-64. Subtracting a 6-bit wire from a design
# whose 6th bit is provably constant would over-subtract.
WIRE = {5: "ad_wire5", 6: "ad_wire6"}
ARMS = [("ad_mxfp4",  "mxfp4_decode",  "E2M1 sym", "struct", "1/12", 5),
        ("ad_mx12fl", "mx_u12_flat",   "E2M1 sym", "flat",   "1/12", 5),
        ("ad_mx24st", "mx_u24_struct", "E2M1 sym", "struct", "1/24", 6),
        ("ad_mx24fl", "mx_u24_flat",   "E2M1 sym", "flat",   "1/24", 6),
        ("ad_asymmx", "asym_mx",       "NEAR0 ASYM", "flat", "1/24", 6),
        ("ad_asymsr", "asym_srt",      "NEAR0 ASYM", "flat", "1/24", 6)]
print(f"  {'decoder':14s} {'book':11s} {'enc':7s} {'grid':5s} {'W':>2s} {'live':>4s} "
      f"{'LUT':>4s} {'CY4':>4s} {'FF':>3s}  {'standalone':>10s}  agree")
agree = True
rows = {}
for n, mod, book, enc, grid, W in ARMS:
    live = R[n]["live_bits"]
    base = WIRE[R[n]["logic_ff"] - 64]
    sub_lut = R[n]["logic_lut"] - R[base]["logic_lut"]
    sub_cy  = R[n]["logic_carry"] - R[base]["logic_carry"]
    st = SA[mod]
    a = (sub_lut == st["lut"] and sub_cy == st["carry"])
    agree &= a
    rows[mod] = (sub_lut, sub_cy)
    print(f"  {mod:14s} {book:11s} {enc:7s} {grid:5s} {W:2d} {live:4d} "
          f"{sub_lut:4d} {sub_cy:4d} {0:3d}  {st['lut']:4d}+{st['carry']}CY4  "
          f"{'yes' if a else 'NO'}")
print(f"  SUBTRAHEND VERIFIED (harness-subtracted == standalone): {'PASS' if agree else 'FAIL'}")

print()
print("  Decomposition, one variable at a time:")
b = rows["mxfp4_decode"]
print(f"    published incumbent  E2M1 struct 1/12 : {b[0]:2d} LUT + {b[1]} CARRY4")
print(f"    + flat table instead of sign+shift    : {rows['mx_u12_flat'][0]:2d} LUT + {rows['mx_u12_flat'][1]} CARRY4"
      f"   ({rows['mx_u12_flat'][0]-b[0]:+d} LUT, {rows['mx_u12_flat'][1]-b[1]:+d} CARRY4)")
print(f"    + 1/24 grid, still structural         : {rows['mx_u24_struct'][0]:2d} LUT + {rows['mx_u24_struct'][1]} CARRY4"
      f"   ({rows['mx_u24_struct'][0]-b[0]:+d} LUT vs incumbent)")
print(f"    + 1/24 grid, flat  [matched control]  : {rows['mx_u24_flat'][0]:2d} LUT + {rows['mx_u24_flat'][1]} CARRY4")
print(f"    + ASYMMETRIC book  [challenger]       : {rows['asym_mx'][0]:2d} LUT + {rows['asym_mx'][1]} CARRY4"
      f"   ({rows['asym_mx'][0]-rows['mx_u24_flat'][0]:+d} LUT vs matched control,"
      f" {rows['asym_mx'][0]-b[0]:+d} LUT / {rows['asym_mx'][1]-b[1]:+d} CARRY4 vs incumbent)")
print(f"    code assignment (MX layout vs sorted) : "
      f"{rows['asym_mx'][0]} vs {rows['asym_srt'][0]} LUT -- free")

print()
print("=" * 78)
print("2. ONE MAC LANE, LOGIC CELLS, harness subtracted")
print("=" * 78)
for tag, t, lbl in (("an", "an_h32", "LUT-ONLY FABRIC (-nodsp)"),
                    ("ap", "ap_h32", "WITH A DSP48")):
    h = R[t]["logic_lut"]
    print(f"\n  {lbl}   harness baseline = {h} LUT")
    print(f"    {'lane':22s} {'LUT':>5s} {'CY4':>4s} {'DSP':>4s}   {'decode delta':>13s}")
    LS = [("raw5", "raw 5b weight, no decode", None),
          ("raw6", "raw 6b weight, no decode", None),
          ("mxfp4", "MXFP4 struct [publ.]", "raw5"),
          ("mx12fl", "E2M1-flat/12 [BEST SYM]", "raw5"),
          ("mx24fl", "E2M1-flat/24 (LSB dead)", "raw6"),
          ("asymmx", "MX-asym-NEAR0 [CHALL.]", "raw6")]
    for nm, lbl2, ref in LS:
        k = f"{tag}_{nm}"
        net = R[k]["logic_lut"] - h
        d = ""
        if ref:
            d = (f"+{R[k]['logic_lut']-R[f'{tag}_{ref}']['logic_lut']:d} LUT "
                 f"{R[k]['logic_carry']-R[f'{tag}_{ref}']['logic_carry']:+d} CY4")
        print(f"    {lbl2:25s} {net:5d} {R[k]['logic_carry']:4d} {R[k]['logic_dsp']:4d}   {d:>13s}")
    A = R[f"{tag}_asymmx"]["logic_lut"] - h
    for ref, lbl3 in (("mx12fl", "BEST SYMMETRIC lane (E2M1 flat, 5b)"),
                      ("mxfp4",  "PUBLISHED INCUMBENT lane (E2M1 struct)")):
        r_ = R[f"{tag}_{ref}"]
        n_ = r_["logic_lut"] - h
        print(f"    ASYM vs {lbl3:40s}: {A} vs {n_} LUT "
              f"({100*(A-n_)/n_:+.1f}%), CARRY4 "
              f"{R[f'{tag}_asymmx']['logic_carry']} vs {r_['logic_carry']}, "
              f"DSP {R[f'{tag}_asymmx']['logic_dsp']} vs {r_['logic_dsp']}")
    if tag == "an":
        print(f"    mechanism: MAC width {R['an_raw6']['logic_lut']-h} (6b) vs "
              f"{R['an_raw5']['logic_lut']-h} (5b) = "
              f"{R['an_raw6']['logic_lut']-R['an_raw5']['logic_lut']:+d} LUT; "
              f"decode {R['an_asymmx']['logic_lut']-R['an_raw6']['logic_lut']} (asym) vs "
              f"{R['an_mx12fl']['logic_lut']-R['an_raw5']['logic_lut']} (best sym) = "
              f"{(R['an_asymmx']['logic_lut']-R['an_raw6']['logic_lut'])-(R['an_mx12fl']['logic_lut']-R['an_raw5']['logic_lut']):+d} LUT")

print()
print("=" * 78)
print("3. Fmax -- UNCONSTRAINED post-route critical-path estimate")
print("   (bench.xdc's create_clock is NOT consumed by nextpnr; confirmed again)")
print("   Tie rule: overlapping seed ranges assert no ordering.")
print("=" * 78)
CMP = [("decode vs publ.",  "ad_asymmx", "ad_mxfp4"),
       ("decode vs bestsym","ad_asymmx", "ad_mx12fl"),
       ("LUTlane vs publ.", "an_asymmx", "an_mxfp4"),
       ("LUTlane vs bestsym","an_asymmx","an_mx12fl"),
       ("DSPlane vs publ.", "ap_asymmx", "ap_mxfp4"),
       ("DSPlane vs bestsym","ap_asymmx","ap_mx12fl")]
for lbl, x, y in CMP:
    ax, bx, mx = rng(x); ay, by, my = rng(y)
    tie = not (ax > by or ay > bx)
    print(f"  {lbl:16s} asym {mx:7.2f} [{ax:7.2f},{bx:7.2f}]   "
          f"ref {my:7.2f} [{ay:7.2f},{by:7.2f}]   "
          f"{'TIE (ranges overlap)' if tie else 'SEPARATED'}")
