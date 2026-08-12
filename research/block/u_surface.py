"""Is u* a property of (block size K, element format), or of the model?

WHAT u IS
---------
A block scale is  s = g^floor(log_g(amax / c)).  The base g is closed by a cost argument and the
scale-field width is closed by b_min = ceil(log2 S(W,K)).  The third parameter, the ALIGNMENT c,
is fixed by every specification and tuned by none.  Reparameterise it base-independently by the
target clamp fraction u under log-uniform block maxima:

        c(u) = max_norm / g^(1 - u)      =>   amax/s in [c, c*g)  and  P(amax/s > max_norm) = u

  u = 0        -> amax/s in [max_norm/g, max_norm): the block maximum NEVER clamps, any base.
  u = u_spec   -> the format's own OCP-style rule  s = g^(floor(log_g amax) - emax), which puts
                  amax/s in [g^emax, g^(emax+1)); solving c = g^emax gives
                        u_spec = 1 - log_g(max_norm / g^emax).
                  For E2M1 (max_norm 6, emax 2) that is 1 - log2(1.5) = 0.41504 -- exactly OCP MX.

u is measured in scale steps (binades when g = 2): raising u by 1 halves s.

THE QUESTION THIS FILE ANSWERS
------------------------------
u* = 0.30-0.35 was measured on two models at K = 32 with E2M1.  A tuned constant fitted on two
models is exactly the shape of the claim this campaign already destroyed once.  So: sweep u at
K in {16,32,64,128} and element format in {E2M1, E3M0, INT4} on two models and ask whether the
u* surface is better described as a function of (K, format) than of the model.

Mechanism under test (stated BEFORE measuring, so it can fail):
  raising u shrinks s, which moves the whole element grid down relative to the block maximum.
  That buys resolution at the BOTTOM of the block (fewer small weights flushed to zero) and pays
  for it at the TOP (the block maximum, and its neighbours, clamp to max_norm).  So u* should
  rise with K -- a wider block puts its typical element further below its maximum -- and fall
  with the element format's own dynamic range max_norm/min_positive, which is what decides how
  far down the grid already reaches.  Both are properties of (K, format), not of the model.

  E2M1  range 6/0.5  = 12    = 3.585 binades      u_spec = 0.41504
  E3M0  range 16/.25 = 64    = 6.000 binades      u_spec = 1.00000  (an M0 format under the OCP
                                                  rule clamps every non-power-of-two block max)
  INT4  range 7/1    = 7     = 2.807 binades      u_spec = 0.19265  (emax analogue below)

INT4 HAS NO EXPONENT FIELD, so "emax" has to be said out loud rather than read off:
  INT4 here is the symmetric signed 4-bit integer grid, magnitudes {0,1,...,7}, max_norm = 7,
  15 distinct signed values -- the same alphabet cardinality as E2M1 and E3M0, and the -8 code
  is left unused, as symmetric weight quantisers do.  Its emax analogue is the binade the top
  code sits in, floor(log2 7) = 2, i.e. the exponent a power-of-two scale field would have to
  pick to make the top code representable; that gives max_norm/2^emax = 1.75 and
  u_spec = 1 - log2(1.75) = 0.19265.  Note that INT4 as usually deployed uses a real-valued
  scale amax/7, which is the u = 0 alignment exactly.  Both readings are reported.

Element quantisation is round-to-nearest with an explicit tie rule.  "even" is generalised as
"of the two codes adjacent to the midpoint take the one whose CODE INDEX is even"; for E2M1 the
code index LSB is the mantissa bit, so this reproduces the trusted harness exactly, for INT4 it
is the ordinary round-half-to-even on integers, and for E3M0 (no mantissa bit) it ties to the
even exponent.  The tie rule is a known nuisance of order 0.09 ppl and is measured, not assumed.

Blocks run along the input dimension of every nn.Linear except the LM head.  When in_features is
not a multiple of K the final partial block gets its own scale, which is what a real
implementation does; the number of partial blocks and the fraction of weights inside them is
printed for every cell.

Usage
    u_surface.py gate    smollm2|qwen            self-tests only, aborts on any failure
    u_surface.py surface smollm2|qwen [options]  the u sweep
"""
import argparse
import hashlib
import json
import math
import os
import sys
import time

import numpy as np
import torch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from competitors import _mags          # noqa: E402  (runs published-constant checks at import)

W = ("/private/tmp/claude-501/-Users-ssdm4-Desktop-PROJECTS-CLAUDE/"
     "0e868af8-ab2d-4d00-be03-8fea94ba48e4/scratchpad/weights")
SEQLEN = 2048
PHI = (1.0 + 5.0 ** 0.5) / 2.0
TIES = ("even", "zero", "away")
torch.set_grad_enabled(False)

# ---- established by this campaign; used as instrument checks, not as results ----------------
BASELINE_NW40 = {"smollm2": 14.4874, "qwen": 12.2277}
# SmolLM2, K=32, E2M1, g=2, ties-to-even, 40 windows -- the row this wave has to reproduce
#   the full published row is
#     0 22.7120 | .05 22.1478 | .10 21.3716 | .15 21.1493 | .20 20.9775 | .25 21.0100 |
#     .30 20.7384 | .35 20.6950 | .415(OCP) 23.5224 | .50 27.7307 | .55 31.8413
#   four of them are re-measured here: the no-clamp end, the reported optimum, OCP, and a
#   heavily-clamped point.  Each NW=40 cell costs ~7 min on this (shared, loaded) machine.
ESTABLISHED_NW40 = {
    "smollm2": {0.00: 22.7120, 0.35: 20.6950, 0.41504: 23.5224, 0.50: 27.7307},
    "qwen": {0.30: 14.5532},
}
OCP_CLAMP_PCT_K32 = {"smollm2": 46.57, "qwen": 40.18}

FAILED = []


def check(cond, label, detail=""):
    print(f"    [{'ok ' if cond else 'FAIL'}] {label}" + (f"   {detail}" if detail else ""),
          flush=True)
    if not cond:
        FAILED.append(label)


def abort_if_failed(where):
    if FAILED:
        print(f"\n  SELF-TESTS FAILED at {where} -- no measurement will be reported:", flush=True)
        for f in FAILED:
            print(f"    - {f}", flush=True)
        sys.exit(1)


# ============================================================== element formats
class Fmt:
    def __init__(self, name, mags, emax, note):
        self.name = name
        self.mags = torch.tensor(np.asarray(mags, dtype=np.float64), dtype=torch.float64)
        self.bnd = (self.mags[:-1] + self.mags[1:]) / 2.0        # exact midpoints
        self.lsb = torch.tensor([i & 1 for i in range(len(self.mags))], dtype=torch.bool)
        self.max_norm = float(self.mags[-1])
        self.min_pos = float(self.mags[1])
        self.emax = emax
        self.note = note

    @property
    def u_spec(self):
        """The alignment the format's own OCP-style rule s = 2^(floor(log2 amax) - emax) sits at."""
        return 1.0 - math.log2(self.max_norm / 2.0 ** self.emax)

    @property
    def binades(self):
        return math.log2(self.max_norm / self.min_pos)

    def c_of_u(self, u, g=2.0):
        return self.max_norm / g ** (1.0 - u)

    def __repr__(self):
        return self.name


FMTS = {
    "E2M1": Fmt("E2M1", _mags(2, 1, emax_expected=2, maxnorm_expected=6.0), 2,
                "OCP MX FP4, subnormal included"),
    "E3M0": Fmt("E3M0", _mags(3, 0, emax_expected=4, maxnorm_expected=16.0), 4,
                "4-bit float, 3 exponent bits, no mantissa bit, no Inf/NaN"),
    "INT4": Fmt("INT4", np.arange(8.0), 2,
                "symmetric signed int4, magnitudes 0..7, -8 code unused"),
}


def q_elem(y, f, tie):
    """Round |y| onto f's magnitude grid under an explicit tie rule.

    bucketize(right=False) sends an exact midpoint DOWN, (right=True) sends it UP; the two
    indices differ exactly on the ties, which is what makes the tie switch observable at all
    (a previous harness's tie switch was a silent no-op).
    """
    a = y.abs()
    k_lo = torch.bucketize(a, f.bnd, right=False)
    k_hi = torch.bucketize(a, f.bnd, right=True)
    if tie == "zero":
        k = k_lo
    elif tie == "away":
        k = k_hi
    elif tie == "even":
        k = torch.where(f.lsb[k_lo], k_hi, k_lo)
    else:
        raise ValueError(tie)
    return f.mags[k]


# ============================================================== scale rule
def floor_log(x, g):
    """floor(log_g x), fixed up so it is exact at ladder points despite fp log error."""
    j = torch.floor(torch.log(x) / np.log(g))
    for _ in range(2):
        j = torch.where(torch.pow(g, j + 1.0) <= x, j + 1.0, j)
        j = torch.where(torch.pow(g, j) > x, j - 1.0, j)
    return j


def scale_of(amax, f, u, g=2.0):
    """s = g^floor(log_g(amax/c(u))), unbounded exponent field."""
    c = f.c_of_u(u, g)
    return torch.pow(g, floor_log(amax.clamp(min=1e-30) / c, g)), c


def scale_frexp(amax, f, u):
    """Second, INDEPENDENT implementation of the g=2 rule, with no logarithm anywhere.

    frexp gives amax/c = m * 2^e with m in [0.5,1), so floor(log2(amax/c)) = e-1 exactly.
    Gate 5 requires this to agree BITWISE with scale_of on real and synthetic data.
    """
    c = f.c_of_u(u, 2.0)
    _, e = torch.frexp(amax.clamp(min=1e-30) / c)
    return torch.pow(torch.tensor(2.0, dtype=torch.float64), (e - 1).double())


# ============================================================== block quantiser
def linears(m):
    for nm, mod in m.named_modules():
        if isinstance(mod, torch.nn.Linear) and not any(h in nm for h in ("lm_head", "embed_out")):
            yield nm, mod


def quantise_tensor(w, K, f, u, tie, g=2.0):
    """Block-K weight-only quantisation of one [out, in] tensor along the input dimension.

    A trailing partial block (in_features % K != 0) gets its own scale.  Implemented by zero
    padding: zeros never raise a block maximum and quantise back to zero, so the padded columns
    are inert -- gate 9 checks this against an explicit per-block loop.
    """
    out_f, in_f = w.shape
    pad = (-in_f) % K
    b = w.double()
    if pad:
        b = torch.cat([b, torch.zeros(out_f, pad, dtype=torch.float64)], dim=1)
    b = b.reshape(-1, K)
    amax = b.abs().amax(dim=1)
    s, c = scale_of(amax, f, u, g)
    s = s.clamp(min=1e-30)
    y = b / s[:, None]
    rec = torch.sign(b) * q_elem(y, f, tie) * s[:, None]
    ay = y.abs()
    st = dict(nblk=b.shape[0],
              npart=(out_f if pad else 0),
              nelem_real=out_f * in_f,
              nelem_part=out_f * (K - pad if pad else 0),
              nsat=int((amax / s > f.max_norm).sum()),                 # block max clamps
              nel_sat=int((ay > f.max_norm).sum()),                    # any element clamps
              nel_zero=int(((ay > 0) & (ay < f.bnd[0])).sum()),        # flushed to zero
              rmin=float((amax / s).min()), rmax=float((amax / s).max()), c=c)
    out = rec.reshape(out_f, in_f + pad)[:, :in_f]
    return out.to(w.dtype), st


class Box:
    """One model held in memory with a pristine copy of every quantised weight."""

    def __init__(self, tag, nw):
        from transformers import AutoModelForCausalLM, AutoTokenizer
        import pyarrow.parquet as pq
        self.tag, self.nw = tag, nw
        path = os.path.join(W, tag)
        tok = AutoTokenizer.from_pretrained(path)
        text = "\n\n".join(pq.read_table(os.path.join(W, "wikitext2-test.parquet"))
                           .column("text").to_pylist())
        ids = tok(text, return_tensors="pt").input_ids[0]
        n = (ids.numel() // SEQLEN) * SEQLEN
        self.all_windows = n // SEQLEN
        self.x = ids[:n].reshape(-1, SEQLEN)
        self.m = AutoModelForCausalLM.from_pretrained(path, dtype=torch.float32)
        self.m.eval()
        self.orig = {nm: mod.weight.data.clone() for nm, mod in linears(self.m)}
        self.ntensor = len(self.orig)
        self.nparam = sum(int(v.numel()) for v in self.orig.values())
        self.shapes = sorted({tuple(v.shape) for v in self.orig.values()})

    def restore(self):
        for nm, mod in linears(self.m):
            mod.weight.data = self.orig[nm].clone()

    def quantise(self, K, f, u, tie, g=2.0):
        tot = dict(nblk=0, npart=0, nelem_real=0, nelem_part=0, nsat=0, nel_sat=0, nel_zero=0)
        rmin, rmax, c = 1e30, -1e30, None
        h = hashlib.blake2b(digest_size=16)
        for nm, mod in linears(self.m):
            q, st = quantise_tensor(self.orig[nm], K, f, u, tie, g)
            mod.weight.data = q
            for k in tot:
                tot[k] += st[k]
            rmin, rmax, c = min(rmin, st["rmin"]), max(rmax, st["rmax"]), st["c"]
            h.update(np.ascontiguousarray(q.numpy().reshape(-1)[::64]).tobytes())
        tot.update(rmin=rmin, rmax=rmax, c=c)
        return tot, h.hexdigest()

    def ppl(self, nw=None):
        nw = nw or self.nw
        x = self.x[:nw]
        nll = cnt = 0.0
        for i in range(x.shape[0]):
            cc = x[i:i + 1]
            nll += self.m(cc, labels=cc).loss.double().item() * (SEQLEN - 1)
            cnt += SEQLEN - 1
        return float(np.exp(nll / cnt))


# ============================================================== gates without a model
def gates_global():
    print("\n  GATE 1-9  (formats, scale rule, blocking; no model involved)", flush=True)

    # ---- G1 format tables, printed and asserted against published / stated constants
    print(f"      {'fmt':<6}{'magnitudes':<44}{'max_norm':>9}{'emax':>6}{'binades':>9}"
          f"{'u_spec':>9}{'signed vals':>12}", flush=True)
    for f in FMTS.values():
        sv = len({round(float(v), 12) for v in f.mags} | {-round(float(v), 12) for v in f.mags})
        print(f"      {f.name:<6}{str([float(v) for v in f.mags]):<44}{f.max_norm:9.4f}"
              f"{f.emax:6d}{f.binades:9.4f}{f.u_spec:9.5f}{sv:12d}", flush=True)
        check(sv == 15, f"G1 {f.name} has 15 distinct signed values (equal alphabet cardinality)")
    check([float(v) for v in FMTS["E2M1"].mags] == [0, .5, 1, 1.5, 2, 3, 4, 6],
          "G1 E2M1 == OCP MX FP4 magnitudes incl. subnormal")
    check([float(v) for v in FMTS["E3M0"].mags] == [0, .25, .5, 1, 2, 4, 8, 16],
          "G1 E3M0 == 2^-2..2^4 with a zero")
    check([float(v) for v in FMTS["INT4"].mags] == [0, 1, 2, 3, 4, 5, 6, 7],
          "G1 INT4 == 0..7")
    check(abs(FMTS["E2M1"].u_spec - 0.41504) < 1e-5, "G1 E2M1 u_spec == OCP's 0.41504",
          f"{FMTS['E2M1'].u_spec:.6f}")
    check(abs(FMTS["E3M0"].u_spec - 1.0) < 1e-12, "G1 E3M0 u_spec == 1 (M0 always clamps)")
    check(abs(FMTS["INT4"].u_spec - (1 - math.log2(1.75))) < 1e-12, "G1 INT4 u_spec == 0.19265")

    # ---- G2 quantiser sanity
    for f in FMTS.values():
        gp = f.mags.clone()
        check(all(q_elem(gp, f, t).tolist() == gp.tolist() for t in TIES),
              f"G2 {f.name} exact on its own grid points")
        r = torch.rand(200000, dtype=torch.float64) * (1.6 * f.max_norm) - 0.2 * f.max_norm
        check(all(torch.equal(q_elem(q_elem(r, f, t), f, t), q_elem(r, f, t)) for t in TIES),
              f"G2 {f.name} idempotent")
        big = torch.tensor([f.max_norm * 1.65, f.max_norm + 1e-3, 1e9], dtype=torch.float64)
        check(all(float(q_elem(big, f, t).max()) == f.max_norm for t in TIES),
              f"G2 {f.name} saturates at max_norm")

    # ---- G3 the tie switch is not a no-op, on EVERY format, against a hand table
    hand = {
        "E2M1": {"zero": [0, .5, 1, 1.5, 2, 3, 4], "away": [.5, 1, 1.5, 2, 3, 4, 6],
                 "even": [0, 1, 1, 2, 2, 4, 4]},
        "E3M0": {"zero": [0, .25, .5, 1, 2, 4, 8], "away": [.25, .5, 1, 2, 4, 8, 16],
                 "even": [0, .5, .5, 2, 2, 8, 8]},
        "INT4": {"zero": [0, 1, 2, 3, 4, 5, 6], "away": [1, 2, 3, 4, 5, 6, 7],
                 "even": [0, 2, 2, 4, 4, 6, 6]},
    }
    for f in FMTS.values():
        got = {t: q_elem(f.bnd, f, t).tolist() for t in TIES}
        print(f"      {f.name} midpoints {[float(v) for v in f.bnd]}", flush=True)
        for t in TIES:
            print(f"        ties={t:<5} -> {got[t]}", flush=True)
            check(got[t] == hand[f.name][t], f"G3 {f.name} ties-to-{t} matches hand table")
        check(len({tuple(got[t]) for t in TIES}) == 3, f"G3 {f.name} three tie rules all distinct")

    # ---- G4 the u -> c map
    check(abs(FMTS["E2M1"].c_of_u(0.41504) - 4.0) < 1e-4,
          "G4 E2M1 u=0.41504 gives c=4, the OCP constant",
          f"c = {FMTS['E2M1'].c_of_u(0.41504):.6f}")
    for f in FMTS.values():
        check(abs(f.c_of_u(0.0) - f.max_norm / 2.0) < 1e-12,
              f"G4 {f.name} u=0 gives c = max_norm/2 (no-clamp alignment)")

    # ---- G5 second independent implementation of the scale, bitwise
    a = torch.exp(torch.rand(1000000, dtype=torch.float64) * 40.0 - 20.0)
    for f in FMTS.values():
        for u in (0.0, 0.17, 0.30, 0.41504, 0.75):
            s1, _ = scale_of(a, f, u)
            s2 = scale_frexp(a, f, u)
            check(torch.equal(s1, s2), f"G5 {f.name} u={u}: log-based == frexp-based, bitwise")
    f = FMTS["E2M1"]
    s_ocp, _ = scale_of(a, f, f.u_spec)
    _, ex = torch.frexp(a)
    s_ref = torch.pow(torch.tensor(2.0, dtype=torch.float64), (ex - 1).double() - f.emax)
    check(torch.equal(s_ocp, s_ref), "G5 E2M1 at u_spec == OCP X = 2^(floor(log2 amax) - emax)")

    # ---- G6 the DEFINING property: clamp fraction under log-uniform block maxima == u
    print(f"      clamp fraction under 4e6 log-uniform draws  (target = u, denominator "
          f"4,000,000)", flush=True)
    aa = torch.exp(torch.rand(4000000, dtype=torch.float64) * 60.0 - 30.0)
    print(f"      {'fmt':<6}{'u':>9}{'c':>10}{'window':>22}{'observed clamp':>16}"
          f"{'|obs-u|':>10}", flush=True)
    for f in FMTS.values():
        for u in (0.0, 0.125, 0.25, 0.375, 0.5, 0.625, 0.75):
            s, c = scale_of(aa, f, u)
            r = aa / s
            obs = float((r > f.max_norm).double().mean())
            ok_w = float(r.min()) >= c - 1e-9 and float(r.max()) < 2 * c + 1e-9
            print(f"      {f.name:<6}{u:9.5f}{c:10.4f}  [{c:7.4f},{2 * c:8.4f})"
                  f"{obs:16.5f}{abs(obs - u):10.5f}", flush=True)
            check(abs(obs - u) < 3e-3, f"G6 {f.name} u={u}: clamp fraction == u")
            check(ok_w, f"G6 {f.name} u={u}: amax/s inside [c, 2c)")

    # ---- G8 NEGATIVE CONTROL: the documented broken scale must reproduce its known symptom
    j = floor_log(a / 6.0, PHI)
    r_bad = a / torch.pow(PHI, j)
    print(f"      negative control  floor(log_phi(amax/6)): amax/s in "
          f"[{float(r_bad.min()):.4f}, {float(r_bad.max()):.4f}], clamp "
          f"{100 * float((r_bad > 6.0).double().mean()):.2f}%", flush=True)
    check(float(r_bad.min()) > 6.0, "G8 negative control: the known-broken rule clamps EVERY block")
    s_ok, _ = scale_of(a, FMTS["E2M1"], 0.0)
    check(float((a / s_ok).max()) <= 6.0 + 1e-9, "G8 and our u=0 rule clamps none")

    # ---- G9 ragged blocking equals an explicit per-block loop
    torch.manual_seed(0)
    for in_f, K in ((576, 128), (576, 64), (100, 32), (64, 16)):
        w = torch.randn(7, in_f, dtype=torch.float32)
        f = FMTS["E2M1"]
        got, st = quantise_tensor(w, K, f, 0.3, "even")
        ref = torch.empty_like(w, dtype=torch.float64)
        for r0 in range(w.shape[0]):
            for c0 in range(0, in_f, K):
                seg = w[r0, c0:c0 + K].double()
                s, _ = scale_of(seg.abs().amax().reshape(1), f, 0.3)
                s = float(s.clamp(min=1e-30))
                ref[r0, c0:c0 + K] = torch.sign(seg) * q_elem(seg / s, f, "even") * s
        check(torch.equal(got.double(), ref),
              f"G9 ragged blocking in_f={in_f} K={K} == explicit per-block loop",
              f"partial blocks {st['npart']}")
    abort_if_failed("global gates")
    print("  GATES 1-9 PASSED", flush=True)


# ============================================================== gates that need the model
def gates_model(box):
    tag = box.tag
    print(f"\n  GATE 10-12  ({tag}: {box.ntensor} quantised nn.Linear tensors, "
          f"{box.nparam:,} weights, shapes {box.shapes})", flush=True)
    for K in (16, 32, 64, 128):
        npart = sum(int(v.shape[0]) for v in box.orig.values() if v.shape[1] % K)
        pe = sum(int(v.shape[0] * (v.shape[1] % K)) for v in box.orig.values())
        print(f"      K={K:3d}: partial blocks {npart:,}, weights in a partial block "
              f"{pe:,} / {box.nparam:,} = {100.0 * pe / box.nparam:.2f}%", flush=True)

    # ---- G12 every switch changes the weights.  One representative tensor, not the whole model:
    #      a full-model pass costs 12 float64 sweeps over every weight, and 24 of them on a 0.5B
    #      checkpoint is 16 minutes of pure memory traffic that proves nothing the one tensor does
    #      not.  Distinctness is the claim; the largest tensor is the strictest place to check it.
    nmw = max(box.orig, key=lambda k: box.orig[k].numel())
    w0 = box.orig[nmw]
    fp = {}
    for K in (16, 32, 64, 128):
        for fn in ("E2M1", "E3M0", "INT4"):
            for u in (0.0, 0.25):
                q, _ = quantise_tensor(w0, K, FMTS[fn], u, "even")
                fp[(K, fn, u)] = hashlib.blake2b(
                    np.ascontiguousarray(q.numpy()).tobytes(), digest_size=16).hexdigest()
    check(len(set(fp.values())) == len(fp),
          f"G12 every (K, format, u) gives a distinct quantisation of {nmw} "
          f"{tuple(w0.shape)}", f"{len(set(fp.values()))} distinct of {len(fp)}")
    for tie in TIES[1:]:
        q, _ = quantise_tensor(w0, 32, FMTS["E2M1"], 0.25, tie)
        q0, _ = quantise_tensor(w0, 32, FMTS["E2M1"], 0.25, "even")
        check(not torch.equal(q, q0), f"G12 ties-{tie} differs from ties-even bitwise on {nmw}")

    # ---- G7 window invariant on the REAL weights, printed
    print(f"      observed amax/s on real weights (K=32, denominator = blocks)", flush=True)
    for fn in ("E2M1", "E3M0", "INT4"):
        f = FMTS[fn]
        for u in (0.0, 0.25, 0.5):
            box.restore()
            st, _ = box.quantise(32, f, u, "even")
            ok = st["rmin"] >= st["c"] - 1e-9 and st["rmax"] < 2 * st["c"] + 1e-9
            print(f"      {fn:<6}u={u:5.3f}  c={st['c']:8.4f}  window [{st['c']:8.4f},"
                  f"{2 * st['c']:9.4f})   observed [{st['rmin']:9.5f}, {st['rmax']:9.5f}]"
                  f"   blockmax-clamp {100.0 * st['nsat'] / st['nblk']:6.2f}%  of "
                  f"{st['nblk']:,} blocks", flush=True)
            check(ok, f"G7 {fn} u={u}: real amax/s inside [c, 2c)")

    # ---- G11a OCP block-max clamp rate at K=32 reproduces the campaign
    box.restore()
    st, _ = box.quantise(32, FMTS["E2M1"], FMTS["E2M1"].u_spec, "even")
    pct = 100.0 * st["nsat"] / st["nblk"]
    check(abs(pct - OCP_CLAMP_PCT_K32[tag]) < 0.5, "G11a OCP clamp rate at K=32 reproduces",
          f"{pct:.2f}% vs established {OCP_CLAMP_PCT_K32[tag]:.2f}% over {st['nblk']:,} blocks")

    # ---- G10 fp32 baseline at 40 windows
    box.restore()
    t0 = time.time()
    b40 = box.ppl(40)
    print(f"      fp32 ppl over 40 windows x {SEQLEN} tok = {b40:.4f}  "
          f"({time.time() - t0:.0f}s)", flush=True)
    check(abs(b40 - BASELINE_NW40[tag]) < 5e-4, "G10 fp32 baseline reproduces",
          f"{b40:.4f} vs {BASELINE_NW40[tag]:.4f}")
    abort_if_failed("model gates 7/10/11a/12")

    # ---- G11 reproduce the established u-scan cells at 40 windows
    print(f"      G11 reproducing established NW=40 cells (SmolLM2/Qwen, K=32, E2M1, "
          f"ties=even)", flush=True)
    got = {}
    for u, want in sorted(ESTABLISHED_NW40[tag].items()):
        box.restore()
        st, _ = box.quantise(32, FMTS["E2M1"], u, "even")
        t0 = time.time()
        p = box.ppl(40)
        got[u] = p
        print(f"        u={u:.5f}  ppl={p:.4f}  established={want:.4f}  "
              f"diff={p - want:+.4f}  ({time.time() - t0:.0f}s)", flush=True)
        check(abs(p - want) < 5e-3, f"G11 u={u} reproduces the established number")
    abort_if_failed("model gate 11")
    print(f"  GATES 10-12 PASSED for {tag}", flush=True)
    return dict(baseline40=b40, established=got)


# ============================================================== the surface
def surface(box, Ks, fmts, us, nw, tie="even", tag_extra=""):
    tag = box.tag
    box.restore()
    base = box.ppl(nw)
    print(f"\n  === {tag}: u SURFACE, {nw} windows x {SEQLEN} tok = {nw * SEQLEN:,} tokens, "
          f"ties={tie}, g=2, fp32 = {base:.4f} ===", flush=True)
    print(f"      denominators: {box.ntensor} tensors, {box.nparam:,} weights, "
          f"{box.all_windows} windows available", flush=True)
    rows = []
    for fn in fmts:
        f = FMTS[fn]
        for K in Ks:
            print(f"\n  {tag}  K={K:<4} {fn}  (max_norm {f.max_norm}, emax {f.emax}, "
                  f"{f.binades:.3f} binades, u_spec {f.u_spec:.5f})", flush=True)
            print(f"      {'u':>8}{'c':>9}{'blkclamp%':>11}{'elclamp%':>10}{'el->0%':>9}"
                  f"{'ppl':>10}{'sec':>7}", flush=True)
            for u in us:
                box.restore()
                st, h = box.quantise(K, f, u, tie)
                t0 = time.time()
                p = box.ppl(nw)
                dt = time.time() - t0
                ne = st["nelem_real"]
                row = dict(model=tag, K=K, fmt=fn, u=u, ppl=p, c=st["c"],
                           blk_clamp=100.0 * st["nsat"] / st["nblk"],
                           el_clamp=100.0 * st["nel_sat"] / ne,
                           el_zero=100.0 * st["nel_zero"] / ne,
                           nblk=st["nblk"], npart=st["npart"], nelem=ne,
                           nelem_part=st["nelem_part"], rmin=st["rmin"], rmax=st["rmax"],
                           fp=h, nw=nw, tie=tie)
                rows.append(row)
                print(f"      {u:8.4f}{st['c']:9.4f}{row['blk_clamp']:11.2f}"
                      f"{row['el_clamp']:10.3f}{row['el_zero']:9.2f}{p:10.4f}{dt:7.0f}",
                      flush=True)
                dump(tag + tag_extra, dict(model=tag, nw=nw, tie=tie, baseline=base,
                                           ntensor=box.ntensor, nparam=box.nparam, rows=rows))
    return base, rows


def dump(name, obj):
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           f"u_surface_{name}.json"), "w") as fh:
        json.dump(obj, fh, indent=1)


# ==============================================================
if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["gate", "surface", "formats"])
    ap.add_argument("tag", nargs="?", default="smollm2")
    ap.add_argument("--nw", type=int, default=10)
    ap.add_argument("--K", default="16,32,64,128")
    ap.add_argument("--fmt", default="E2M1,E3M0,INT4")
    ap.add_argument("--u", default="0,0.125,0.25,0.375,0.5,0.625,0.75")
    ap.add_argument("--threads", type=int, default=1)
    ap.add_argument("--tie", default="even", choices=list(TIES))
    ap.add_argument("--out", default="")
    ap.add_argument("--skip-global", action="store_true")
    a = ap.parse_args()
    torch.set_num_threads(a.threads)

    if a.mode == "formats":
        gates_global()
        sys.exit(0)

    if not a.skip_global:
        gates_global()
    box = Box(a.tag, a.nw)
    if a.mode == "gate":
        g = gates_model(box)
        dump(a.tag + "_gate", g)
    else:
        Ks = [int(v) for v in a.K.split(",")]
        fmts = a.fmt.split(",")
        us = [float(v) for v in a.u.split(",")]
        base, rows = surface(box, Ks, fmts, us, a.nw, tie=a.tie, tag_extra=a.out)
        print("\n  DONE", flush=True)
