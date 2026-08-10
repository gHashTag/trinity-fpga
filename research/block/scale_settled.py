"""Settle the phi-vs-2^k scale-ladder margin with nothing left uncontrolled.

WHY THIS EXISTS
---------------
The campaign's block-axis headline is "a phi^j scale ladder beats a 2^k ladder at equal scale
field width". On SmolLM2 the reported margin is 1.145 ppl, which is safe. On Qwen it is 0.0935 --
and merely switching the element tie-break rule moves the 2^k number by 0.0932. A margin the size
of an uncontrolled nuisance parameter is not a result.

Two earlier harnesses were wrong in ways that both flattered one side:

  research/block/scale_frontier.py    scale = g^ceil(log_g(amax/6)), so amax/s <= 6 and the block
                                      maximum NEVER saturates. The OCP MX rule saturates 46.6% of
                                      SmolLM2 blocks. Also breaks element ties toward zero.
  research/block/scale_frontier_spec.py  its tie switch was a no-op (torch.bucketize already puts
                                      an exact midpoint in the lower bin, so its `is_tie` mask was
                                      always empty), and its phi scale used floor(log_phi(amax/6)),
                                      putting amax/s in [6.85, 9.55] -- above max_norm -- so every
                                      single block maximum clamped. It printed phi = 39.56.

So this harness is written from scratch and every one of those failure modes has a self-test that
aborts the run before a number is printed.

THE CONTROL THAT DECIDES THE QUESTION
-------------------------------------
Two things differ between a 2^k ladder and a phi^j ladder, and only one of them is "phi":

  (1) STEP SIZE. phi steps are log2(phi) = 0.6942 binades; 2^k steps are 1.0. A phi ladder is
      1.44x finer. This is the claimed advantage.
  (2) ALIGNMENT. A scale rule s = g^floor(log_g(amax/c)) puts the normalised block maximum
      amax/s in [c, c*g). Whether that interval straddles max_norm = 6 -- i.e. whether the block
      maximum clamps -- is set by c, not by g. OCP MX fixes c = 4 for base 2 (amax/X in [4,8),
      clamps whenever amax's mantissa exceeds 1.5). Nothing fixes c for phi. Pick c = 6/phi for
      phi and c = 4 for 2^k and phi "wins" because it never clamps, which has nothing to do
      with phi.

  (3) SPAN. At equal field width a phi ladder covers LESS dynamic range: 16 levels span
      15*log2(phi) = 10.41 binades against 2^k's 15.00. Equal bits is therefore not equal span.

This harness makes (2) an explicit axis (each base measured at BOTH its no-clamp alignment and at
an alignment matched to OCP's clamp fraction) and reports (3) as both a level count and a
bits-per-weight column, plus a phi ladder widened to 24 levels so its span matches 2^k's.

Element format is E2M1 with the subnormal throughout: magnitudes {0,.5,1,1.5,2,3,4,6}, max_norm 6,
emax 2. Only the scale varies. Weight-only, block 32 along the input dimension, all nn.Linear
except lm_head. wikitext-2 test, 40 windows of 2048 tokens, fp32 forward.

Usage:  scale_settled.py [smollm2|qwen ...] [--sweep]
        --sweep adds the continuous alignment sweep (ties-to-even only).
"""
import hashlib
import json
import os
import sys

import numpy as np
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

W = ("/private/tmp/claude-501/-Users-ssdm4-Desktop-PROJECTS-CLAUDE/"
     "0e868af8-ab2d-4d00-be03-8fea94ba48e4/scratchpad/weights")
SEQLEN, NW, BLK = 2048, 40, 32
PHI = (1.0 + 5.0 ** 0.5) / 2.0
LOG2PHI = np.log2(PHI)
torch.set_grad_enabled(False)

# ---- E2M1 with subnormal. MBIT is the mantissa LSB of each code: e=00 -> {0,.5},
#      e=01 -> {1,1.5}, e=10 -> {2,3}, e=11 -> {4,6}.  "even" in the IEEE sense = MBIT 0.
MAG = torch.tensor([0.0, 0.5, 1.0, 1.5, 2.0, 3.0, 4.0, 6.0], dtype=torch.float64)
MBIT = torch.tensor([0, 1, 0, 1, 0, 1, 0, 1], dtype=torch.bool)
BND = (MAG[:-1] + MAG[1:]) / 2.0        # the 7 exact midpoints
MAXN = 6.0
EMAX = 2
TIES = ("even", "zero", "away")

BASELINE = {"smollm2": 14.4874, "qwen": 12.2277}
# established this campaign, used as instrument checks
OCP_CLAMP_PCT = {"smollm2": 46.57, "qwen": 40.18}

FAILED = []


def check(cond, label, detail=""):
    print(f"    [{'ok ' if cond else 'FAIL'}] {label}" + (f"   {detail}" if detail else ""),
          flush=True)
    if not cond:
        FAILED.append(label)


def abort_if_failed():
    if FAILED:
        print("\n  SELF-TESTS FAILED -- no measurement will be reported:", flush=True)
        for f in FAILED:
            print(f"    - {f}", flush=True)
        sys.exit(1)


# ------------------------------------------------------------------ element quantiser
def q_elem(y, tie):
    """Quantise |y| onto the E2M1 magnitude grid under an explicit tie rule.

    torch.bucketize(right=False) resolves an exact midpoint DOWNWARD (toward zero) and
    (right=True) resolves it UPWARD (away from zero); the difference of the two indices is the
    exact-tie mask.  Values above the top midpoint 5.0 land on index 7 = max_norm, which is the
    saturation the OCP scale rule makes common.
    """
    a = y.abs()
    k_zero = torch.bucketize(a, BND, right=False)
    k_away = torch.bucketize(a, BND, right=True)
    if tie == "zero":
        k = k_zero
    elif tie == "away":
        k = k_away
    elif tie == "even":
        k = torch.where(MBIT[k_zero], k_away, k_zero)   # of the pair, take the MBIT==0 code
    else:
        raise ValueError(tie)
    return MAG[k]


# ------------------------------------------------------------------ scale rules
def floor_log(x, g):
    """floor(log_g x), fixed up so it is exact at the ladder points despite fp log error."""
    j = torch.floor(torch.log(x) / np.log(g))
    for _ in range(2):
        j = torch.where(torch.pow(g, j + 1.0) <= x, j + 1.0, j)
        j = torch.where(torch.pow(g, j) > x, j - 1.0, j)
    return j


def scale(amax, g, c, nlev=None):
    """s = g^floor(log_g(amax/c)) so that amax/s lies in [c, c*g).

    g = 2, c = 4 is exactly the OCP MX rule X = 2^(floor(log2 amax) - emax) with emax = 2.
    If nlev is given the exponent is confined to a finite field of nlev levels, anchored at the
    tensor's own minimum -- what a real format with a narrow scale field does.
    Returns (s, n_field_clamped).
    """
    a = amax.clamp(min=1e-30)
    j = floor_log(a / c, g)
    nclip = 0
    if nlev is not None:
        jlo = j.min()
        jc = torch.clamp(j - jlo, 0, nlev - 1) + jlo
        nclip = int((jc != j).sum())
        j = jc
    return torch.pow(g, j), nclip


# ------------------------------------------------------------------ model plumbing
def linears(m):
    for nm, mod in m.named_modules():
        if isinstance(mod, torch.nn.Linear) and not any(h in nm for h in ("lm_head", "embed_out")):
            yield nm, mod


def quantise_tensor(w, g, c, nlev, tie):
    """Block-32 weight-only quantisation of one [out, in] tensor. Returns (w_q, stats)."""
    assert w.shape[1] % BLK == 0, f"in_features {w.shape[1]} not a multiple of {BLK}"
    b = w.double().reshape(-1, BLK)
    amax = b.abs().amax(dim=1)
    s, nclip = scale(amax, g, c, nlev)
    s = s.clamp(min=1e-30)
    ratio = amax / s
    rec = torch.sign(b) * q_elem(b / s[:, None], tie) * s[:, None]
    st = dict(nblk=b.shape[0], nclip=nclip,
              nsat=int((ratio > MAXN).sum()),          # block maximum clamps to max_norm
              rmin=float(ratio.min()), rmax=float(ratio.max()))
    return rec.reshape(w.shape).to(w.dtype), st


def quantise_model(m, g, c, nlev, tie):
    tot = dict(nblk=0, nclip=0, nsat=0)
    rmin, rmax = 1e30, -1e30
    h = hashlib.blake2b(digest_size=16)
    for nm, mod in linears(m):
        q, st = quantise_tensor(mod.weight.data, g, c, nlev, tie)
        mod.weight.data = q
        for k in tot:
            tot[k] += st[k]
        rmin, rmax = min(rmin, st["rmin"]), max(rmax, st["rmax"])
        h.update(np.ascontiguousarray(q.numpy()).tobytes())
    tot["rmin"], tot["rmax"] = rmin, rmax
    return tot, h.hexdigest()


def ppl(m, ids):
    n = (ids.numel() // SEQLEN) * SEQLEN
    x = ids[:n].reshape(-1, SEQLEN)[:NW]
    nll = cnt = 0.0
    for i in range(x.shape[0]):
        c = x[i:i + 1]
        nll += m(c, labels=c).loss.double().item() * (SEQLEN - 1)
        cnt += SEQLEN - 1
    return float(np.exp(nll / cnt))


# ================================================================== SELF-TESTS (global)
def selftests_global():
    print("\n  SELF-TESTS (format and rules; no model involved)", flush=True)

    # T1 -- the grid itself
    check(MAG.tolist() == [0.0, 0.5, 1.0, 1.5, 2.0, 3.0, 4.0, 6.0], "T1 E2M1 grid w/ subnormal",
          str(MAG.tolist()))
    check(float(MAG[-1]) == MAXN and EMAX == 2, "T1 max_norm 6, emax 2")

    # T2 -- THE TIE SWITCH IS NOT A NO-OP.  Hand table, computed from the E2M1 code layout.
    #   Only two codes neighbour any midpoint, so at a single midpoint at most TWO of the three
    #   rules can differ; the correct test is that the three 7-vectors are pairwise different AND
    #   that each equals its hand-computed value.
    mids = torch.tensor([0.25, 0.75, 1.25, 1.75, 2.5, 3.5, 5.0], dtype=torch.float64)
    hand = {"zero": [0.0, 0.5, 1.0, 1.5, 2.0, 3.0, 4.0],
            "away": [0.5, 1.0, 1.5, 2.0, 3.0, 4.0, 6.0],
            "even": [0.0, 1.0, 1.0, 2.0, 2.0, 4.0, 4.0]}
    got = {t: q_elem(mids, t).tolist() for t in TIES}
    print(f"      midpoint      {'  '.join(f'{float(v):>4}' for v in mids)}", flush=True)
    for t in TIES:
        print(f"      ties={t:<5}     {'  '.join(f'{v:>4}' for v in got[t])}", flush=True)
    for t in TIES:
        check(got[t] == hand[t], f"T2 ties-to-{t} matches hand table")
    for a, b in (("even", "zero"), ("even", "away"), ("zero", "away")):
        check(got[a] != got[b], f"T2 ties-to-{a} differs from ties-to-{b} on the 7 midpoints")
    check(len({tuple(got[t]) for t in TIES}) == 3, "T2 all three tie rules distinct")

    # T3 -- quantiser sanity: exact on grid points, idempotent, saturating
    gp = MAG.clone()
    check(all(q_elem(gp, t).tolist() == gp.tolist() for t in TIES), "T3 exact on grid points")
    r = torch.rand(200000, dtype=torch.float64) * 9.0 - 1.0
    check(all(torch.equal(q_elem(q_elem(r, t), t), q_elem(r, t)) for t in TIES),
          "T3 idempotent")
    check(all(float(q_elem(torch.tensor([9.9, 6.1, 1e9], dtype=torch.float64), t).max()) == MAXN
              for t in TIES), "T3 saturates at max_norm")

    # T4 -- the OCP scale rule, against an independent instrument (frexp, no logs)
    a = torch.exp(torch.rand(1000000, dtype=torch.float64) * 40.0 - 20.0)
    s_ocp, _ = scale(a, 2.0, 4.0, None)
    mant, ex = torch.frexp(a)                       # a = mant * 2^ex, mant in [0.5,1)
    s_ref = torch.pow(2.0, (ex - 1).double() - EMAX)   # floor(log2 a) = ex-1
    check(torch.equal(s_ocp, s_ref), "T4 c=4,g=2 rule == OCP X = 2^(floor(log2 amax)-emax)")
    ratio = a / s_ocp
    check(float(ratio.min()) >= 4.0 and float(ratio.max()) < 8.0,
          "T4 OCP puts amax/X in [4,8)", f"observed [{float(ratio.min()):.4f}, "
                                         f"{float(ratio.max()):.4f})")
    print(f"      OCP clamp rate on log-uniform amax: "
          f"{100.0 * float((ratio > MAXN).double().mean()):.2f}%  "
          f"(analytic log2(8/6) = {100 * np.log2(8 / 6):.2f}%)", flush=True)

    # T5 -- every alignment lands where it claims to.  PRINTED, not assumed.
    print(f"      {'rule':<26}{'amax/s window':>22}{'observed':>24}{'clamp%':>9}", flush=True)
    for nm, g, c in ALIGNMENTS:
        s, _ = scale(a, g, c, None)
        rr = a / s
        ok = float(rr.min()) >= c - 1e-9 and float(rr.max()) < c * g
        print(f"      {nm:<26}[{c:6.4f}, {c * g:6.4f}){'':>4}"
              f"[{float(rr.min()):8.4f}, {float(rr.max()):8.4f})"
              f"{100.0 * float((rr > MAXN).double().mean()):9.2f}", flush=True)
        check(ok, f"T5 {nm} lands in [{c:.4f}, {c * g:.4f})")
        if "no-clamp" in nm:
            check(float(rr.max()) <= MAXN + 1e-9, f"T5 {nm} really never clamps")

    # T6 -- span arithmetic: equal bits is NOT equal span
    check(abs(15 * LOG2PHI - 10.4132) < 1e-3, "T6 16 phi levels span 15*log2(phi) binades",
          f"{15 * LOG2PHI:.4f} vs 2^k's 15.0000")
    check(int(np.ceil(16 / LOG2PHI)) == 24, "T6 ceil(16/log2 phi) = 24 steps -> 5-bit field")
    check(24 - 1 >= 15 / LOG2PHI, "T6 24 phi levels cover >= 15 binades",
          f"23*log2(phi) = {23 * LOG2PHI:.4f} binades")
    abort_if_failed()


# ================================================================== SELF-TESTS (per model)
def selftests_model(tag, model, ids, base):
    print(f"\n  SELF-TESTS ({tag}, real weights and real forward pass)", flush=True)
    m = model()
    wref = None
    nb = ne = nmid = 0
    for nm, mod in linears(m):
        w = mod.weight.data.double()
        if wref is None:
            wref = (nm, w.clone())
        b = w.reshape(-1, BLK)
        s, _ = scale(b.abs().amax(dim=1), 2.0, 4.0, None)
        y = (b / s[:, None]).abs()
        nmid += int((torch.bucketize(y, BND, right=False)
                     != torch.bucketize(y, BND, right=True)).sum())
        ne += y.numel()
        nb += b.shape[0]
    # T7 -- exact midpoints really are common, so the tie rule really is a live nuisance
    print(f"      {nb:,} blocks, {ne:,} elements; exact E2M1 midpoints "
          f"{100.0 * nmid / ne:.3f}% of elements", flush=True)
    check(nmid > 0, "T7 exact midpoints exist in the real weights")

    # T8 -- the three tie rules give BITWISE DIFFERENT tensors (the bug that faked a null result)
    nmw, w0 = wref
    outs = {t: quantise_tensor(w0, 2.0, 4.0, None, t)[0] for t in TIES}
    for a, b in (("even", "zero"), ("even", "away"), ("zero", "away")):
        check(not torch.equal(outs[a], outs[b]),
              f"T8 {nmw}: ties-{a} != ties-{b} bitwise")

    # T9 -- OCP saturation rate reproduces the established measurement
    st, _ = quantise_model(m, 2.0, 4.0, None, "even")
    pct = 100.0 * st["nsat"] / st["nblk"]
    check(abs(pct - OCP_CLAMP_PCT[tag]) < 0.5, "T9 OCP block-max clamp rate reproduces campaign",
          f"{pct:.2f}% vs established {OCP_CLAMP_PCT[tag]:.2f}%")
    del m

    # T10 -- fp32 baseline reproduces
    check(abs(base - BASELINE[tag]) < 5e-4, "T10 fp32 baseline reproduces",
          f"{base:.4f} vs {BASELINE[tag]:.4f}")
    abort_if_failed()


# ================================================================== configurations
#  name, base g, alignment constant c
ALIGNMENTS = [
    ("2^k  OCP align c=4", 2.0, 4.0),
    ("2^k  no-clamp c=3", 2.0, 3.0),
    ("phi  no-clamp c=6/phi", PHI, MAXN / PHI),
    # same clamp fraction as OCP: max_norm sits log2(6/4)/log2(2) = 0.585 of the way through the
    # window in log measure, so c = 6 / phi^0.585.
    ("phi  OCP-matched align", PHI, MAXN / PHI ** (np.log2(MAXN / 4.0))),
]

#  label, g, c, nlev (None = unbounded field), scale field bits
def build_configs():
    c2ocp, c2free = 4.0, 3.0
    cphif, cphio = MAXN / PHI, MAXN / PHI ** (np.log2(MAXN / 4.0))
    return [
        ("MXFP4  E8M0 OCP           ", 2.0, c2ocp, None, 8),
        ("2^k    4-bit field, OCP   ", 2.0, c2ocp, 16, 4),
        ("2^k    4-bit field, noclamp", 2.0, c2free, 16, 4),
        ("phi^j  4-bit field, noclamp", PHI, cphif, 16, 4),
        ("phi^j  4-bit field, OCP-mat", PHI, cphio, 16, 4),
        ("phi^j  5-bit/24lv, noclamp ", PHI, cphif, 24, 5),
        ("phi^j  5-bit/24lv, OCP-mat ", PHI, cphio, 24, 5),
    ]


def run_model(tag, sweep):
    path = os.path.join(W, tag)
    tok = AutoTokenizer.from_pretrained(path)
    import pyarrow.parquet as pq
    text = "\n\n".join(pq.read_table(os.path.join(W, "wikitext2-test.parquet"))
                       .column("text").to_pylist())
    ids = tok(text, return_tensors="pt").input_ids[0]

    def fresh():
        m = AutoModelForCausalLM.from_pretrained(path, dtype=torch.float32)
        m.eval()
        return m

    base = ppl(fresh(), ids)
    selftests_model(tag, fresh, ids, base)

    cache = {}      # weight-hash -> ppl, so bitwise-identical configurations are not re-run

    def measure(g, c, nlev, tie):
        m = fresh()
        st, h = quantise_model(m, g, c, nlev, tie)
        if h in cache:
            del m
            return cache[h], st, h, True
        p = ppl(m, ids)
        del m
        cache[h] = p
        return p, st, h, False

    print(f"\n  === {tag}: fp32 = {base:.4f}   ({NW} windows x {SEQLEN} tok, block {BLK}, "
          f"E2M1 elements) ===", flush=True)
    print(f"  {'scheme':<28}{'b/w':>7}{'span':>7}"
          f"{'ties=even':>11}{'ties=zero':>11}{'ties=away':>11}"
          f"{'clamp%':>8}{'fieldclip':>10}", flush=True)
    rows = {}
    hashes = {}
    for label, g, c, nlev, sb in build_configs():
        vals, sts, hs = [], [], []
        for tie in TIES:
            p, st, h, hit = measure(g, c, nlev, tie)
            vals.append(p)
            sts.append(st)
            hs.append(h)
        rows[label] = vals
        hashes[label] = hs
        span = (nlev - 1) * np.log2(g) if nlev else float("inf")
        bw = 4.0 + sb / BLK
        print(f"  {label:<28}{bw:7.4f}{span:7.2f}"
              + "".join(f"{v:>11.4f}" for v in vals)
              + f"{100.0 * sts[0]['nsat'] / sts[0]['nblk']:8.2f}{sts[0]['nclip']:10d}", flush=True)

    print("\n  phi minus 2^k, LIKE ALIGNMENT AGAINST LIKE, every cell:", flush=True)
    pairs = [("phi^j  4-bit field, noclamp", "2^k    4-bit field, noclamp",
              "no-clamp alignment, 4-bit field, EQUAL BITS"),
             ("phi^j  4-bit field, OCP-mat", "2^k    4-bit field, OCP   ",
              "OCP-matched alignment, 4-bit field, EQUAL BITS"),
             ("phi^j  5-bit/24lv, noclamp ", "2^k    4-bit field, noclamp",
              "no-clamp alignment, EQUAL SPAN (phi 5 bits vs 2^k 4 bits)"),
             ("phi^j  5-bit/24lv, OCP-mat ", "2^k    4-bit field, OCP   ",
              "OCP-matched alignment, EQUAL SPAN")]
    for pn, qn, why in pairs:
        d = [rows[pn][i] - rows[qn][i] for i in range(3)]
        print(f"    {why}", flush=True)
        for i, t in enumerate(TIES):
            print(f"        ties={t:<5} phi {rows[pn][i]:8.4f}  2^k {rows[qn][i]:8.4f}  "
                  f"diff {d[i]:+8.4f}  {'phi wins' if d[i] < 0 else '2^k wins'}", flush=True)

    print("\n  CROSS-ALIGNMENT (what the earlier harness actually compared):", flush=True)
    for i, t in enumerate(TIES):
        d = rows["phi^j  4-bit field, noclamp"][i] - rows["2^k    4-bit field, OCP   "][i]
        print(f"        ties={t:<5} phi(no-clamp) - 2^k(OCP) = {d:+8.4f}", flush=True)

    print("\n  TIE-RULE SENSITIVITY (max spread across the three rules, per scheme):", flush=True)
    for label, v in rows.items():
        print(f"        {label} spread {max(v) - min(v):.4f}", flush=True)

    out = dict(tag=tag, baseline=base, windows=NW, seqlen=SEQLEN, block=BLK,
               rows={k: v for k, v in rows.items()}, hashes=hashes)

    if sweep:
        print("\n  ALIGNMENT SWEEP (ties=even, 4-bit field): is the winner alignment-invariant?",
              flush=True)
        print(f"  {'base':<6}{'c':>9}{'amax/s window':>20}{'clamp%':>9}{'ppl':>11}", flush=True)
        sw = []
        for g, cs in ((2.0, [3.0, 3.4, 3.8, 4.0, 4.4, 4.8, 5.2, 5.6]),
                      (PHI, [3.7082, 3.95, 4.2, 4.55, 4.9, 5.25, 5.6, 5.95])):
            for c in cs:
                p, st, h, hit = measure(g, c, 16, "even")
                print(f"  {'2^k' if g == 2.0 else 'phi':<6}{c:9.4f}"
                      f"  [{c:5.3f},{c * g:6.3f})"
                      f"{100.0 * st['nsat'] / st['nblk']:9.2f}{p:11.4f}", flush=True)
                sw.append((("2^k" if g == 2.0 else "phi"), c, p,
                           100.0 * st["nsat"] / st["nblk"]))
        b2 = min(r[2] for r in sw if r[0] == "2^k")
        bp = min(r[2] for r in sw if r[0] == "phi")
        print(f"    best 2^k over alignment {b2:.4f}   best phi over alignment {bp:.4f}   "
              f"diff {bp - b2:+.4f}  ({'phi wins' if bp < b2 else '2^k wins'})", flush=True)
        out["sweep"] = sw

    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           f"scale_settled_{tag}.json"), "w") as f:
        json.dump(out, f, indent=1)
    return out


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    sweep = "--sweep" in sys.argv
    selftests_global()
    for tag in (args or ["smollm2", "qwen"]):
        run_model(tag, sweep)
