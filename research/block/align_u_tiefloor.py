"""Tie-rule nuisance floor at the u values the verdict hinges on.

A power-of-two scale keeps binary float32 weights exactly on the E2M1 binary midpoints, so the
element tie rule is a live nuisance: it moved Qwen's 2^k arm by 0.0932, the size of a claimed
margin.  Every arm on every u-curve here is a 2^k scale, so the floor applies to every point.
Nothing on a u-curve may be called an optimum until it clears this.
"""
import json, os, sys
sys.path.insert(0, "/Users/ssdm4/Desktop/PROJECTS/CLAUDE/trinity-fpga/research/block")
import scale_settled as S, align_u as A

tag = sys.argv[1]; us = [float(x) for x in sys.argv[2:]]
f = A.FAM[tag]
m, ids = A.load(tag)
tg = A.targets(m); A.guard_targets(tag, tg, f["nlayer"]*f["per_layer"])
orig = {nm: mod.weight.data.clone() for nm, mod, _ in tg}
base = A.ppl_at(m, ids, f["seqlen"], A.NW)
if f["fp32"] is not None:
    S.check(abs(base-f["fp32"]) < 5e-4, f"{tag} fp32 reproduces", f"{base:.4f} vs {f['fp32']:.4f}")
    S.abort_if_failed()
print(f"\n=== {tag} tie-rule floor: fp32 {base:.4f}, {len(tg)} projections, "
      f"{A.NW}x{f['seqlen']} ===", flush=True)
print(f"{'u':>8}{'obs clamp%':>12}" + "".join(f"{'ties='+t:>12}" for t in S.TIES)
      + f"{'spread':>10}", flush=True)
rows = []
for u in us:
    vals = []
    for t in S.TIES:
        st, h = A.quantise_model_u(tg, orig, u, tie=t)
        vals.append(A.ppl_at(m, ids, f["seqlen"], A.NW))
    for nm, mod, _ in tg: mod.weight.copy_(orig[nm])
    sp = max(vals)-min(vals)
    print(f"{u:8.4f}{100.0*st['nsat']/st['nblk']:12.2f}"
          + "".join(f"{v:12.4f}" for v in vals) + f"{sp:10.4f}", flush=True)
    rows.append(dict(u=u, obs_clamp=100.0*st['nsat']/st['nblk'],
                     ppl=dict(zip(S.TIES, vals)), spread=sp))
floor = max(r["spread"] for r in rows)
print(f"\nNUISANCE FLOOR ({tag}) = {floor:.4f} ppl  over u in {us}", flush=True)
json.dump(dict(tag=tag, baseline=base, rows=rows, floor=floor),
          open(f"/Users/ssdm4/Desktop/PROJECTS/CLAUDE/trinity-fpga/research/block/align_u_tiefloor_{tag}.json","w"), indent=1)
