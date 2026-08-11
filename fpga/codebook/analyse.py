#!/usr/bin/env python3
"""Turn the raw arm results into the numbers the question asks for."""
import json, os
HERE = os.path.dirname(os.path.abspath(__file__))
R = {}
for f in ("results.json", "results_mcm.json", "results_extra.json"):
    p = os.path.join(HERE, f)
    if os.path.exists(p):
        R.update(json.load(open(p)))

def g(n, k="lut"):
    return R[n][k] if n in R and k in R[n] else None
def f(n):
    return R[n].get("fmed") if n in R else None
def sp(n):
    return 100 * R[n].get("fspread", 0) if n in R else None

print("=" * 78)
print("1. THE DECODE PATH ALONE, net of a bare wire of the same width")
print("=" * 78)
print(f"{'arm':10s} {'W':>3s} {'LUT':>5s} {'FF':>4s} {'wire LUT':>9s} {'wire FF':>8s} "
      f"{'net LUT':>8s} {'net FF':>7s} {'Fmed':>8s} {'spread':>7s}")
for arm, w, base in (("d_mxfp4", 5, "d_wire5"), ("d_cb6", 8, "d_wire8"),
                     ("d_cb8", 10, "d_wire10"), ("d_cb10", 12, "d_wire12")):
    if arm not in R or base not in R: continue
    print(f"{arm:10s} {w:3d} {g(arm):5d} {g(arm,'ff'):4d} {g(base):9d} {g(base,'ff'):8d} "
          f"{g(arm)-g(base):8d} {g(arm,'ff')-g(base,'ff'):7d} {f(arm):8.2f} {sp(arm):6.1f}%")

print()
print("=" * 78)
print("2. ONE DECODER FEEDING ONE MAC LANE  (8-bit activation, 32-bit accumulator)")
print("=" * 78)
H = g("ln_h32")
print(f"harness reference ln_h32 = {H} LUT, {g('ln_h32','ff')} FF\n")
print(f"{'arm':11s} {'form':22s} {'LUT':>5s} {'net':>5s} {'FF':>4s} {'DSP':>3s} "
      f"{'Fmed':>7s} {'spread':>7s}")
rows = [("ln_raw5",  "raw 5b weight, no code"), ("ln_raw8", "raw 8b weight, no code"),
        ("ln_raw12", "raw 12b weight, no code"),
        ("ln_mxfp4", "E2M1 decode+multiply"), ("mn_mxfp4", "E2M1 specialised"),
        ("ln_cb6",   "CB B=6 decode+multiply"), ("mn_cb6", "CB B=6 specialised"),
        ("ln_cb10",  "CB B=10 decode+multiply"), ("mn_cb10", "CB B=10 specialised")]
for a, d in rows:
    if a not in R: continue
    print(f"{a:11s} {d:22s} {g(a):5d} {g(a)-H:5d} {g(a,'ff'):4d} {g(a,'dsp'):3d} "
          f"{f(a):7.2f} {sp(a):6.1f}%")

print()
print("  same-formulation ratios, LUT-only fabric (net of harness):")
for lab, mx, cb in (("decode+multiply, B=6 ", "ln_mxfp4", "ln_cb6"),
                    ("specialised,     B=6 ", "mn_mxfp4", "mn_cb6"),
                    ("decode+multiply, B=10", "ln_mxfp4", "ln_cb10"),
                    ("specialised,     B=10", "mn_mxfp4", "mn_cb10")):
    if mx in R and cb in R:
        print(f"    {lab}: codebook {g(cb)-H:4d} / E2M1 {g(mx)-H:4d} = {(g(cb)-H)/(g(mx)-H):.2f}x"
              f"   (+{g(cb)-g(mx)} LUT on a {g(mx)}-LUT lane = +{100*(g(cb)-g(mx))/g(mx):.0f}% of the whole build)")

print()
print("  with DSP48 allowed (hard multiplier -- what a real accelerator has):")
print(f"  {'arm':10s} {'LUT':>5s} {'FF':>4s} {'DSP':>3s} {'Fmed':>7s} {'spread':>7s}")
for a in ("ld_raw5", "ld_raw12", "ld_mxfp4", "ld_cb6", "ld_cb10"):
    if a in R:
        print(f"  {a:10s} {g(a):5d} {g(a,'ff'):4d} {g(a,'dsp'):3d} {f(a):7.2f} {sp(a):6.1f}%")
if "ld_mxfp4" in R and "ld_cb6" in R:
    print(f"    B=6  costs {g('ld_cb6')-g('ld_mxfp4'):+d} LUT and "
          f"{g('ld_cb6','dsp')-g('ld_mxfp4','dsp'):+d} DSP against E2M1 "
          f"= {100*(g('ld_cb6')-g('ld_mxfp4'))/g('ld_mxfp4'):+.1f}% of the lane")
    print(f"    B=10 costs {g('ld_cb10')-g('ld_mxfp4'):+d} LUT and "
          f"{g('ld_cb10','dsp')-g('ld_mxfp4','dsp'):+d} DSP against E2M1 "
          f"= {100*(g('ld_cb10')-g('ld_mxfp4'))/g('ld_mxfp4'):+.1f}%")

print()
print("=" * 78)
print("3. A WHOLE 32-ELEMENT BLOCK -- is the table shared or replicated?")
print("=" * 78)
S = g("b_scale")
print(f"E8M0 alignment alone, in its harness: {S} LUT, {g('b_scale','ff')} FF, "
      f"{f('b_scale'):.2f} MHz -- identical for both formats")
print(f"{'arm':10s} {'LUT':>6s} {'per weight':>11s} {'vs E2M1':>8s} {'Fmed':>7s} {'spread':>7s}")
for a in ("b_raw5", "b_raw12", "b_mxfp4", "b_cb6", "b_cb10"):
    if a not in R: continue
    per = (g(a) - S) / 32
    rel = per / ((g("b_mxfp4") - S) / 32) if "b_mxfp4" in R else 0
    print(f"{a:10s} {g(a):6d} {per:11.1f} {rel:7.2f}x {f(a):7.2f} {sp(a):6.1f}%")
if "b_mxfp4" in R and "b_raw5" in R:
    d = g("b_mxfp4") - g("b_raw5")
    print(f"\n  E2M1 block minus the same block with an unconstrained 5-bit weight:"
          f" {d} LUT for 32 decoders = {d/32:.1f} LUT each.")
    print(f"  One decoder measured alone was {g('d_mxfp4')-g('d_wire5')} LUT and inside one lane"
          f" {g('ln_mxfp4')-g('ln_raw5')} LUT.")
    print(f"  If the table were SHARED across the block the difference would be one decoder,"
          f" not thirty-two.")
if "b_scale" in R and "b_mxfp4" in R:
    print(f"\n  the shared E8M0 alignment is at most {S} LUT (its harness included), i.e. at most"
          f" {S/32:.1f} LUT per weight,")
    print(f"  against {(g('b_mxfp4')-S)/32:.0f}-{(g('b_cb10')-S)/32:.0f} LUT per weight for the lanes."
          f"  THAT is what amortises.")

print()
print("=" * 78)
print("4. DOES FREQUENCY SEPARATE THEM? -- gap against the seed spread")
print("=" * 78)
print("   A ranking on a metric with spread s asserts an ordering only between rows")
print("   further apart than s (MEDIAN_SWEEP_2026-08-10.md).")
print(f"   {'comparison':34s} {'gap':>7s} {'worst spread':>13s}  verdict")
for lab, a, b in (("decoder alone, E2M1 vs CB B=6", "d_mxfp4", "d_cb6"),
                  ("decoder alone, E2M1 vs CB B=10", "d_mxfp4", "d_cb10"),
                  ("lane LUT-only, E2M1 vs CB B=6", "ln_mxfp4", "ln_cb6"),
                  ("lane LUT-only, E2M1 vs CB B=10", "ln_mxfp4", "ln_cb10"),
                  ("lane on DSP,   E2M1 vs CB B=6", "ld_mxfp4", "ld_cb6"),
                  ("lane on DSP,   E2M1 vs CB B=10", "ld_mxfp4", "ld_cb10"),
                  ("32-block,      E2M1 vs CB B=6", "b_mxfp4", "b_cb6"),
                  ("32-block,      E2M1 vs CB B=10", "b_mxfp4", "b_cb10")):
    if a not in R or b not in R: continue
    ga = 100 * abs(f(a) - f(b)) / max(f(a), f(b))
    s = max(sp(a), sp(b))
    print(f"   {lab:34s} {ga:6.1f}% {s:12.1f}%  "
          f"{'RESOLVED' if ga > s else 'not resolved -- report as a tie'}")
