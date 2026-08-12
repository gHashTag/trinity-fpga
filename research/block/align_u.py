#!/usr/bin/env python3
"""Does the alignment optimum u* replicate across five model families?

WHY THIS EXISTS
---------------
A block scale s = g^floor(log_g(amax/c)) has an alignment constant c that every published
specification FIXES and none tunes.  Reparameterised base-independently as

    c = max_norm / g^(1-u)

u is the clamp fraction the rule would produce if block maxima were log-uniform: the window
amax/s in [c, g*c) has log_g-width 1, max_norm sits at log_g(max_norm/c) = 1-u from the bottom,
so the top u of the window clamps.  u = 0 never clamps for ANY base; u = 0.4150375 with
g = 2, max_norm = 6 gives c = 4, which is exactly OCP MX (X = 2^(floor(log2 amax) - emax),
emax = 2).

Scanning u on SmolLM2 and Qwen said the optimum sits near u* = 0.30-0.35 and beats the OCP
alignment by 2.83 / 0.51 ppl at identical 4.125 bits/weight.  Two models is exactly how this
campaign previously manufactured a law that the third model destroyed.  This script measures
the same scan on pythia, opt and gpt2 -- and re-measures SmolLM2 as a replication gate against
the trusted harness's own stored JSON.

WHAT IS NEW HERE, AND THEREFORE WHAT NEEDS ITS OWN SELF-TEST
-----------------------------------------------------------
scale_settled.py is imported, not reimplemented: the E2M1 grid, the tie rules, floor_log and
the scale rule all come from it, so its 21 self-tests still guard this measurement.  Three
things are genuinely new and each has a gate that aborts before any number prints:

  1. the u -> c reparameterisation                      (U1, U2)
  2. Conv1D support -- GPT-2 stores [in, out], not      (U6)
     [out, in], so the block axis is dim 0 not dim 1
  3. per-family module targeting and seqlen             (U7, U8, U9)

U8 is the gate the task named explicitly: a filter that matches nothing must ABORT, not
silently report the fp32 number five times.  U9 checks the complementary failure: that the
weights REALLY changed at every scan point.

Usage:  align_u.py [pythia opt gpt2 ...]  [--replicate] [--ties]
        --replicate  runs the SmolLM2 gate against scale_settled_smollm2.json first
        --ties       adds the tie-rule nuisance floor at u* and at OCP
"""
import hashlib
import json
import os
import sys
import time

import numpy as np
import torch

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import scale_settled as S          # noqa: E402  (guarded by __main__, safe to import)

from transformers import AutoModelForCausalLM, AutoTokenizer   # noqa: E402
from transformers.pytorch_utils import Conv1D                  # noqa: E402

torch.set_grad_enabled(False)
W = S.W
BLK, NW, MAXN = S.BLK, S.NW, S.MAXN
NLEV = 16          # 4-bit scale field, the operating point of the finding
TIE = "even"

# ---- per family: seqlen, expected target-module count (from config, NOT from the model),
#      and the fp32 perplexity this campaign already published for that model.
#      pythia/opt come from research/block/campaignC_measure.py RULERS (40 windows x 2048).
#      smollm2/qwen come from scale_settled.BASELINE.
#      gpt2 has no campaign baseline: max_position_embeddings is 1024, so it cannot be run at
#      2048 and no earlier number exists to reproduce.  Its gate is a plausibility band plus
#      the published-literature band for GPT-2 small on wikitext-2 at seqlen 1024.
FAM = {
    "smollm2": dict(seqlen=2048, nlayer=30, per_layer=7, fp32=14.4874, kind="linear"),
    "qwen":    dict(seqlen=2048, nlayer=24, per_layer=7, fp32=12.2277, kind="linear"),
    "pythia":  dict(seqlen=2048, nlayer=12, per_layer=4, fp32=25.9561, kind="linear"),
    "opt":     dict(seqlen=2048, nlayer=12, per_layer=6, fp32=27.5678, kind="linear"),
    "gpt2":    dict(seqlen=1024, nlayer=12, per_layer=4, fp32=None,    kind="conv1d",
                    band=(20.0, 45.0)),
}

U_GRID = [0.0, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.4150375, 0.45, 0.50, 0.55]
U_OCP = 1.0 - float(np.log2(MAXN / 4.0))     # 0.4150375...


# ------------------------------------------------------------------ the reparameterisation
def c_of_u(u, g=2.0, max_norm=MAXN):
    """Alignment constant at target clamp fraction u.  Base-independent by construction."""
    return max_norm / g ** (1.0 - u)


# ------------------------------------------------------------------ model plumbing
def targets(m):
    """(name, module, transposed) for every quantisable projection, head excluded.

    transposed=True means the stored weight is [in, out] (HF Conv1D, used by GPT-2) and the
    block axis -- the INPUT axis, as in every MX-style block quantiser -- is dim 0.
    """
    out = []
    for nm, mod in m.named_modules():
        if any(h in nm for h in ("lm_head", "embed_out")):
            continue
        if isinstance(mod, torch.nn.Linear):
            out.append((nm, mod, False))
        elif isinstance(mod, Conv1D):
            out.append((nm, mod, True))
    return out


def quantise_tensor_u(w, transposed, u, g=2.0, nlev=NLEV, tie=TIE):
    """Block-BLK weight-only quantisation of one projection at alignment u.  Returns (wq, st)."""
    wt = w.t().contiguous() if transposed else w        # -> [out, in]
    assert wt.shape[1] % BLK == 0, f"in_features {wt.shape[1]} not a multiple of {BLK}"
    b = wt.double().reshape(-1, BLK)
    amax = b.abs().amax(dim=1)
    s, nclip = S.scale(amax, g, c_of_u(u, g), nlev)
    s = s.clamp(min=1e-30)
    ratio = amax / s
    rec = torch.sign(b) * S.q_elem(b / s[:, None], tie) * s[:, None]
    q = rec.reshape(wt.shape).to(w.dtype)
    st = dict(nblk=b.shape[0], nclip=nclip, nsat=int((ratio > MAXN).sum()),
              rmin=float(ratio.min()), rmax=float(ratio.max()), nelem=b.numel())
    return (q.t().contiguous() if transposed else q), st


def quantise_model_u(tg, orig, u, g=2.0, nlev=NLEV, tie=TIE):
    tot = dict(nblk=0, nclip=0, nsat=0, nelem=0)
    rmin, rmax = 1e30, -1e30
    h = hashlib.blake2b(digest_size=16)
    for nm, mod, tr in tg:
        q, st = quantise_tensor_u(orig[nm], tr, u, g, nlev, tie)
        mod.weight.copy_(q)
        for k in tot:
            tot[k] += st[k]
        rmin, rmax = min(rmin, st["rmin"]), max(rmax, st["rmax"])
        h.update(np.ascontiguousarray(q.detach().numpy()).tobytes())
    tot["rmin"], tot["rmax"] = rmin, rmax
    return tot, h.hexdigest()


def whash(tg, orig):
    h = hashlib.blake2b(digest_size=16)
    for nm, mod, tr in tg:
        h.update(np.ascontiguousarray(orig[nm].detach().numpy()).tobytes())
    return h.hexdigest()


def ppl_at(m, ids, seqlen, nw=NW):
    """Perplexity over nw non-overlapping windows.  Gate U4 proves this equals scale_settled.ppl
    bitwise when seqlen == 2048."""
    n = (ids.numel() // seqlen) * seqlen
    x = ids[:n].reshape(-1, seqlen)[:nw]
    if x.shape[0] < nw:
        raise SystemExit(f"only {x.shape[0]} windows of {seqlen} available, need {nw}")
    nll = cnt = 0.0
    for i in range(x.shape[0]):
        c = x[i:i + 1]
        nll += m(c, labels=c).loss.double().item() * (seqlen - 1)
        cnt += seqlen - 1
    return float(np.exp(nll / cnt))


def load(tag):
    path = os.path.join(W, tag)
    tok = AutoTokenizer.from_pretrained(path)
    import pyarrow.parquet as pq
    text = "\n\n".join(pq.read_table(os.path.join(W, "wikitext2-test.parquet"))
                       .column("text").to_pylist())
    ids = tok(text, return_tensors="pt").input_ids[0]
    m = AutoModelForCausalLM.from_pretrained(path, dtype=torch.float32)
    m.eval()
    return m, ids


# ================================================================== new self-tests
def selftests_u():
    print("\n  SELF-TESTS (the u reparameterisation; no model involved)", flush=True)

    # U1 -- the two anchors the reparameterisation MUST hit exactly
    S.check(abs(c_of_u(0.0) - 3.0) < 1e-12, "U1 u=0 -> c=3 (2^k no-clamp)",
            f"c={c_of_u(0.0):.12f}")
    S.check(abs(c_of_u(U_OCP) - 4.0) < 1e-12, "U1 u=0.4150375 -> c=4 (exactly OCP MX)",
            f"u_ocp={U_OCP:.7f}  c={c_of_u(U_OCP):.12f}")
    S.check(abs(c_of_u(0.0, S.PHI) - MAXN / S.PHI) < 1e-12,
            "U1 u=0 -> phi's own no-clamp c=6/phi", f"c={c_of_u(0.0, S.PHI):.6f}")

    # U2 -- u IS the clamp fraction under log-uniform block maxima, for EVERY base.
    #       This is the whole point of the parameterisation; if it were base-dependent the
    #       cross-base comparison would be confounded again.
    #
    #       The draw must span an INTEGER number of g-steps.  A first version drew
    #       exp(U(-20,20)) -- 57.71 binades -- whose fractional part is NOT uniform, and the
    #       residual 0.71 of a binade biased the observed clamp rate by 0.29 points (54.71
    #       against 55.00) with a Monte-Carlo sd of only 0.035.  That is the instrument being
    #       wrong, not the tolerance being tight; scale_settled's T4 printed the same bias
    #       (41.42 against 41.50) without asserting on it.
    print(f"      {'base':<6}{'u':>8}{'c':>9}{'predicted clamp%':>19}{'observed clamp%':>18}"
          f"{'amax/s window':>24}", flush=True)
    for g, gn in ((2.0, "2^k"), (S.PHI, "phi")):
        a = torch.pow(g, torch.rand(2000000, dtype=torch.float64) * 60.0 - 30.0)
        for u in (0.0, 0.20, U_OCP, 0.55):
            c = c_of_u(u, g)
            s, _ = S.scale(a, g, c, None)
            r = a / s
            obs = 100.0 * float((r > MAXN).double().mean())
            print(f"      {gn:<6}{u:8.4f}{c:9.4f}{100 * u:19.2f}{obs:18.2f}"
                  f"   [{float(r.min()):7.4f},{float(r.max()):7.4f})", flush=True)
            S.check(abs(obs - 100 * u) < 0.15, f"U2 {gn} u={u:.4f}: clamp% == u",
                    f"{obs:.2f} vs {100 * u:.2f}")
            S.check(float(r.min()) >= c - 1e-9 and float(r.max()) < c * g,
                    f"U2 {gn} u={u:.4f}: amax/s inside [{c:.4f},{c * g:.4f})")
    # OCP's published clamp rate is log2(8/6) = 41.504% -- the same number, from the spec side
    S.check(abs(100 * U_OCP - 100 * np.log2(8 / 6)) < 1e-9,
            "U2 u_OCP == log2(8/6), the OCP spec's own clamp fraction",
            f"{100 * U_OCP:.5f}% vs {100 * np.log2(8 / 6):.5f}%")
    S.abort_if_failed()


def selftests_impl(tag="smollm2"):
    """U4-U7: this file's quantiser is the trusted one, on real weights, bitwise."""
    print(f"\n  SELF-TESTS (implementation agreement, real {tag} weights)", flush=True)
    m, ids = load(tag)
    tg = targets(m)
    S.check(len(tg) > 0, "U7 target filter is non-empty")

    # U5 -- at u=u_OCP the new path must be BITWISE the trusted harness's c=4 path.
    #       Deliberately a NON-SQUARE projection: on a square weight the two candidate block
    #       axes are indistinguishable, so U6's negative control would prove nothing.
    cand = [(nm, mod) for nm, mod, tr in tg if mod.weight.shape[0] != mod.weight.shape[1]]
    S.check(len(cand) > 0, "U5 a non-square projection exists to test the axis on")
    S.abort_if_failed()
    nm0, mod0 = cand[0]
    w0 = mod0.weight.data.clone()
    q_new, st_new = quantise_tensor_u(w0, False, U_OCP)
    q_old, st_old = S.quantise_tensor(w0, 2.0, 4.0, NLEV, TIE)
    S.check(torch.equal(q_new, q_old), f"U5 {nm0}: align_u(u_OCP) == scale_settled(c=4) bitwise")
    S.check(st_new["nsat"] == st_old["nsat"] and st_new["nblk"] == st_old["nblk"],
            "U5 block statistics agree too",
            f"nsat {st_new['nsat']}/{st_new['nblk']}")
    # and at u=0 it must be the trusted harness's c=3 path
    S.check(torch.equal(quantise_tensor_u(w0, False, 0.0)[0],
                        S.quantise_tensor(w0, 2.0, 3.0, NLEV, TIE)[0]),
            "U5 align_u(u=0) == scale_settled(c=3) bitwise")

    # U6 -- THE CONV1D PATH.  GPT-2 stores [in, out]; quantising it must give exactly the
    #       transpose of quantising the [out, in] tensor.  Without this, GPT-2 would be
    #       blocked along the OUTPUT axis and every GPT-2 number would be a different
    #       experiment wearing the same label.
    w_conv = w0.t().contiguous()                       # pretend it is a Conv1D weight
    q_conv, st_conv = quantise_tensor_u(w_conv, True, U_OCP)
    S.check(torch.equal(q_conv, q_old.t().contiguous()),
            "U6 Conv1D path == transpose of the Linear path, bitwise")
    S.check(st_conv["nsat"] == st_old["nsat"] and st_conv["nblk"] == st_old["nblk"],
            "U6 Conv1D path saturates the same blocks as the Linear path",
            f"{st_conv['nsat']}/{st_conv['nblk']} both ways")
    # NEGATIVE CONTROL.  Block COUNT cannot detect the error -- it is numel/BLK whichever axis
    # is used -- so the control has to be the tensor itself, on a non-square weight where the
    # two axes really are different groupings.
    q_bad, st_bad = quantise_tensor_u(w_conv, False, U_OCP)
    S.check(not torch.equal(q_bad, q_conv),
            "U6 NEGATIVE CONTROL: blocking the OUTPUT axis gives a different tensor",
            f"shape {tuple(w_conv.shape)}, saturated blocks wrong-axis {st_bad['nsat']} vs "
            f"right-axis {st_conv['nsat']} of {st_conv['nblk']}")

    # U4 -- my perplexity == scale_settled's, bitwise, at seqlen 2048
    p_new = ppl_at(m, ids, 2048, 4)
    S.NW_SAVE = S.NW
    S.NW = 4
    p_old = S.ppl(m, ids)
    S.NW = S.NW_SAVE
    S.check(p_new == p_old, "U4 ppl_at == scale_settled.ppl bitwise (4 windows)",
            f"{p_new!r} vs {p_old!r}")

    # U7 -- a filter that matches nothing must ABORT.  Tested, not assumed.
    class Empty(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.norm = torch.nn.LayerNorm(8)
    S.check(len(targets(Empty())) == 0, "U7 a model with no projections yields 0 targets")
    try:
        guard_targets("nonesuch", [], 1)
        S.check(False, "U7 empty target list ABORTS")
    except SystemExit:
        S.check(True, "U7 empty target list ABORTS")
    del m
    S.abort_if_failed()


def guard_targets(tag, tg, expect):
    """ABORT unless the target set is exactly what the config predicts."""
    if len(tg) == 0:
        raise SystemExit(f"[{tag}] target filter matched NOTHING -- aborting (a run that "
                         f"quantises nothing reports the fp32 number)")
    if len(tg) != expect:
        raise SystemExit(f"[{tag}] target filter matched {len(tg)}, config predicts {expect} "
                         f"-- aborting")
    return True


# ================================================================== the scan
def scan(tag, ties=False):
    f = FAM[tag]
    seqlen = f["seqlen"]
    t0 = time.time()
    m, ids = load(tag)
    tg = targets(m)
    expect = f["nlayer"] * f["per_layer"]
    guard_targets(tag, tg, expect)
    orig = {nm: mod.weight.data.clone() for nm, mod, _ in tg}
    nq = sum(int(orig[nm].numel()) for nm, _, _ in tg)
    ntot = sum(int(p.numel()) for p in m.parameters())
    kinds = sorted({("Conv1D" if tr else "Linear") for _, _, tr in tg})
    print(f"\n  === {tag}: {len(tg)}/{expect} target projections ({'+'.join(kinds)}), "
          f"{nq:,} of {ntot:,} model params quantised ({100.0 * nq / ntot:.1f}%), "
          f"seqlen {seqlen}, {NW} windows, block {BLK}, E2M1+subnormal, "
          f"{NLEV}-level (4-bit) scale field, ties-to-{TIE} ===", flush=True)
    print(f"      first/last target: {tg[0][0]} ... {tg[-1][0]}", flush=True)

    h_fp32 = whash(tg, orig)
    base = ppl_at(m, ids, seqlen, NW)
    if f["fp32"] is not None:
        S.check(abs(base - f["fp32"]) < 5e-4, f"G1 {tag} fp32 baseline reproduces campaign value",
                f"{base:.4f} vs published {f['fp32']:.4f}")
    else:
        lo, hi = f["band"]
        S.check(lo < base < hi, f"G1 {tag} fp32 baseline inside plausibility band",
                f"{base:.4f} in ({lo}, {hi}) -- NO campaign value exists to reproduce")
    S.abort_if_failed()
    print(f"      fp32 = {base:.4f}   ({time.time() - t0:.0f}s)", flush=True)

    print(f"\n  {'u':>9}{'c':>9}{'pred clamp%':>13}{'obs clamp%':>12}{'fieldclip':>11}"
          f"{'ppl':>11}{'vs fp32':>10}", flush=True)
    rows = []
    seen = {h_fp32: "fp32"}
    for u in U_GRID:
        t1 = time.time()
        st, h = quantise_model_u(tg, orig, u)
        # U9 -- the weights REALLY changed, and this u is not a duplicate of an earlier one
        if h == h_fp32:
            raise SystemExit(f"[{tag}] u={u}: quantised weights hash equals fp32 -- "
                             f"nothing was quantised, aborting")
        dup = seen.get(h)
        seen[h] = f"u={u}"
        p = ppl_at(m, ids, seqlen, NW)
        clamp = 100.0 * st["nsat"] / st["nblk"]
        tag_dup = f"   [bitwise dup of {dup}]" if dup else ""
        print(f"  {u:9.4f}{c_of_u(u):9.4f}{100 * u:13.2f}{clamp:12.2f}{st['nclip']:11d}"
              f"{p:11.4f}{p / base:10.3f}x{tag_dup}"
              f"   ({time.time() - t1:.0f}s)", flush=True)
        rows.append(dict(u=u, c=c_of_u(u), pred_clamp=100 * u, obs_clamp=clamp,
                         nclip=st["nclip"], nblk=st["nblk"], nelem=st["nelem"], ppl=p,
                         hash=h, dup=dup))
    for nm, mod, _ in tg:
        mod.weight.copy_(orig[nm])

    best = min(rows, key=lambda r: r["ppl"])
    ocp = [r for r in rows if abs(r["u"] - U_OCP) < 1e-9][0]
    print(f"\n    u*        = {best['u']:.4f}   ppl {best['ppl']:.4f}", flush=True)
    print(f"    OCP u     = {ocp['u']:.4f}   ppl {ocp['ppl']:.4f}", flush=True)
    print(f"    GAIN from retuning c alone = {ocp['ppl'] - best['ppl']:+.4f} ppl "
          f"at identical {4 + 4 / BLK:.3f} bits/weight", flush=True)

    out = dict(tag=tag, seqlen=seqlen, windows=NW, block=BLK, nlev=NLEV, tie=TIE,
               ntarget=len(tg), nparam_quantised=nq, nparam_total=ntot,
               baseline=base, published_fp32=f["fp32"], rows=rows,
               u_star=best["u"], ppl_star=best["ppl"], u_ocp=U_OCP, ppl_ocp=ocp["ppl"],
               gain=ocp["ppl"] - best["ppl"])

    if ties:
        print(f"\n  TIE-RULE NUISANCE FLOOR (the margin must exceed this to mean anything):",
              flush=True)
        nz = {}
        for u, lab in ((best["u"], "u*"), (U_OCP, "OCP")):
            vals = []
            for t in S.TIES:
                quantise_model_u(tg, orig, u, tie=t)
                vals.append(ppl_at(m, ids, seqlen, NW))
            for nm, mod, _ in tg:
                mod.weight.copy_(orig[nm])
            print(f"    {lab:<4} u={u:.4f}  " + "  ".join(
                f"{t}={v:.4f}" for t, v in zip(S.TIES, vals))
                + f"   spread {max(vals) - min(vals):.4f}", flush=True)
            nz[lab] = dict(vals=dict(zip(S.TIES, vals)), spread=max(vals) - min(vals))
        out["tie_floor"] = nz

    with open(os.path.join(HERE, f"align_u_{tag}.json"), "w") as fh:
        json.dump(out, fh, indent=1)
    del m
    return out


def replicate_smollm2():
    """GATE: the stored trusted-harness JSON must be reproduced by this file, to 4 decimals,
    at the two u values where the two parameterisations provably coincide."""
    p = os.path.join(HERE, "scale_settled_smollm2.json")
    d = json.load(open(p))
    ref_u0 = d["rows"]["2^k    4-bit field, noclamp"][0]     # ties=even, c=3   == u=0
    ref_ocp = d["rows"]["2^k    4-bit field, OCP   "][0]     # ties=even, c=4   == u=u_OCP
    print(f"\n  REPLICATION GATE against {os.path.basename(p)} (independent earlier run)",
          flush=True)
    m, ids = load("smollm2")
    tg = targets(m)
    guard_targets("smollm2", tg, FAM["smollm2"]["nlayer"] * FAM["smollm2"]["per_layer"])
    orig = {nm: mod.weight.data.clone() for nm, mod, _ in tg}
    for u, ref, lab in ((0.0, ref_u0, "u=0 (c=3)"), (U_OCP, ref_ocp, "u=u_OCP (c=4)")):
        quantise_model_u(tg, orig, u)
        got = ppl_at(m, ids, 2048, NW)
        S.check(abs(got - ref) < 5e-4, f"G2 smollm2 {lab} reproduces stored run",
                f"{got:.6f} vs stored {ref:.6f}")
    del m
    S.abort_if_failed()


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    S.selftests_global()
    selftests_u()
    selftests_impl("smollm2")
    if "--replicate" in sys.argv:
        replicate_smollm2()
    res = {}
    for tag in (args or ["pythia", "opt", "gpt2"]):
        res[tag] = scan(tag, ties="--ties" in sys.argv)
    print("\n\n  ================ SUMMARY ================", flush=True)
    print(f"  {'model':<10}{'fp32':>9}{'u*':>8}{'ppl(u*)':>10}{'ppl(OCP)':>10}{'gain':>9}",
          flush=True)
    for tag, o in res.items():
        print(f"  {tag:<10}{o['baseline']:9.4f}{o['u_star']:8.2f}{o['ppl_star']:10.4f}"
              f"{o['ppl_ocp']:10.4f}{o['gain']:+9.4f}", flush=True)
