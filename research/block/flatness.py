"""Are "flat optima" and "u* does not transfer" one statement or two?

The campaign recorded them as two lessons. They may be one. The claim to test:

    where the u-curve is FLAT relative to that model's own tie-rule floor, the location of the
    minimum is set by noise and cannot transfer; where the curve has a NOTCH deeper than the
    floor, the minimum is real.

If that holds, "u* spans 0.25-0.40 across five families" is not five disagreeing measurements --
it is four models whose optimum is undetermined and one whose optimum is sharp, and the spread is
an artefact of reporting an argmin that three of them do not possess.

The discriminating quantity is the INDISTINGUISHABLE REGION: the set of u whose perplexity lies
within that model's own measured tie floor of the minimum. A wide region means the argmin is not
identified. This costs nothing to compute -- the curves and the floors are already measured.

Data are the stored sweeps; no model is loaded. Written after the scratchpad was cleaned and four
of five checkpoints were lost, which is itself the reason to get everything possible out of the
JSON that survived.
"""
import json
import os

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))

# measured tie-rule floors, per model (align_u_tiefloor_*.json and the campaign record)
FLOOR = {"pythia": 0.5358, "opt": 0.0667, "gpt2": 0.0003, "smollm2": 0.2398, "qwen": 0.0932}
# stored dtype -- the mechanism behind the floor (skill sec 4b: floor ~ 2^-m)
DTYPE = {"pythia": "fp16", "opt": "fp16", "gpt2": "fp32", "smollm2": "bf16", "qwen": "bf16"}


MAXN = 6.0


def load_curve(tag):
    """Return (u, ppl) from whichever stored sweep exists. TWO schemas, both READ from the
    files rather than guessed -- the first version guessed three and matched none.

      align_u_<tag>.json      rows[] = {"u":..., "ppl":...}          (the u sweep)
      scale_settled_<tag>.json sweep[] = [base, c, ppl, clamp%]      (the c sweep)

    The second stores the alignment CONSTANT c, not u. Converting: c = max_norm/g^(1-u), so
    u = 1 - log_g(max_norm/c). Checked against the two anchors the harness itself asserts:
    c=3,g=2 -> u=0 (no-clamp) and c=4,g=2 -> u=0.41504 (OCP)."""
    p1 = os.path.join(HERE, f"align_u_{tag}.json")
    if os.path.exists(p1):
        d = json.load(open(p1))
        rows = [r for r in d.get("rows", []) if isinstance(r, dict) and "u" in r and "ppl" in r]
        if len(rows) >= 5:
            rows.sort(key=lambda r: r["u"])
            return (np.array([float(r["u"]) for r in rows]),
                    np.array([float(r["ppl"]) for r in rows]))
    p2 = os.path.join(HERE, f"scale_settled_{tag}.json")
    if os.path.exists(p2):
        d = json.load(open(p2))
        pts = []
        for rec in d.get("sweep", []):
            if not (isinstance(rec, (list, tuple)) and len(rec) >= 3):
                continue
            base, c, ppl = rec[0], float(rec[1]), float(rec[2])
            if str(base) != "2^k":                    # keep the base the campaign compares on
                continue
            u = 1.0 - np.log2(MAXN / c)               # g = 2
            pts.append((float(u), ppl))
        if len(pts) >= 5:
            pts.sort()
            return np.array([q[0] for q in pts]), np.array([q[1] for q in pts])
    return None, None


print("Is the u* spread an artefact of undetermined optima?\n")
print(f"  {'model':<9}{'dtype':>6}{'floor':>9}{'u*':>7}{'ppl(u*)':>10}"
      f"{'depth':>9}{'depth/floor':>13}{'indist. region':>18}{'verdict':>14}")

rows = []
for tag in ("smollm2", "qwen", "pythia", "opt", "gpt2"):
    u, p = load_curve(tag)
    if u is None:
        print(f"  {tag:<9}{DTYPE.get(tag,'?'):>6}{'':>9}   no stored sweep on disk")
        continue
    i = int(np.argmin(p))
    ustar, pmin = float(u[i]), float(p[i])
    floor = FLOOR[tag]
    # depth = how far the minimum sits below the next-best DISTINCT alignment
    others = np.delete(p, i)
    depth = float(others.min() - pmin)
    # indistinguishable region: every u within one floor of the minimum
    within = u[p <= pmin + floor]
    span = float(within.max() - within.min()) if len(within) else 0.0
    frac = span / float(u.max() - u.min())
    verdict = "SHARP" if depth > floor else "undetermined"
    rows.append((tag, ustar, depth, floor, span, frac, verdict))
    print(f"  {tag:<9}{DTYPE[tag]:>6}{floor:>9.4f}{ustar:>7.2f}{pmin:>10.4f}"
          f"{depth:>9.4f}{depth/floor:>13.2f}{span:>10.2f} ({frac*100:>3.0f}%){verdict:>14}")

print()
sharp = [r for r in rows if r[6] == "SHARP"]
und = [r for r in rows if r[6] != "SHARP"]
print(f"  optima that are SHARP (deeper than their own noise floor): "
      f"{len(sharp)} of {len(rows)}  -> {[r[0] for r in sharp]}")
print(f"  optima that are UNDETERMINED:                              "
      f"{len(und)} of {len(rows)}  -> {[r[0] for r in und]}")
if sharp:
    us = [r[1] for r in sharp]
    print(f"\n  u* among the SHARP models only: {us}  spread {max(us)-min(us):.2f}")
    print(f"  u* among ALL models:            {[r[1] for r in rows]}  "
          f"spread {max(r[1] for r in rows)-min(r[1] for r in rows):.2f}")
    print("\n  If the sharp subset agrees while the full set does not, 'u* does not transfer'")
    print("  and 'the optima are flat' are ONE statement: the spread is the undetermined models")
    print("  reporting an argmin they do not possess. If the sharp subset ALSO disagrees, they")
    print("  are two independent problems and the law is dead for a second, separate reason.")
