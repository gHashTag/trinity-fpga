"""TASK 3 -- does the alignment gain survive the things that usually kill PTQ gains?

The claim under test: with base g = 2, block 32, E2M1-with-subnormal elements, weight-only,
re-tuning ONLY the alignment constant of s = g^floor(log_g(amax/c)) buys 2.83 ppl on SmolLM2 and
0.51 on Qwen against OCP's alignment, at 4.125 bits/weight.

Reparameterisation (base-independent): u is the clamp fraction under LOG-UNIFORM block maxima,
    c(u, g) = max_norm / g^(1-u)
so amax/s lands in [c, c*g), max_norm sits a fraction (1-u) of the way through that window in log
measure, and Pr[amax/s > max_norm] = u exactly when log(amax) is uniform.  u = 0 is no-clamp for
every base; u = log2(8/6) = 0.415037 reproduces OCP MX (c = 4, g = 2, max_norm = 6, emax = 2).

Four ways the 2.83 could be an artefact of a narrow setup, one per sub-task:
  (a) 40 windows is a small sample                -> subcommand `windows`
  (b) u* was tuned on wikitext-2                  -> subcommand `corpus`
  (c) MX shares the scale encoding with ACTIVATIONS, and u* was tuned on weights alone
                                                  -> subcommand `acts`
  (d) the element tie rule is a live nuisance of the same order as past claims
                                                  -> subcommand `ties`

Every primitive that decides a number (element grid, tie rule, scale rule, ppl) is IMPORTED from
research/block/scale_settled.py, the harness carrying the campaign's 21 self-tests, rather than
re-typed.  What is new here -- the u parameterisation, per-window loss accumulation, and the
activation quantiser -- carries its own gates below, which abort before any number prints.

Usage:  align_harden.py selftest
        align_harden.py windows <tag> [--nw N]
        align_harden.py corpus  <tag> [--nw N]
        align_harden.py ties    <tag> [--nw N]
        align_harden.py acts    <tag> [--nw N]
"""
import hashlib
import json
import os
import sys
import time

import numpy as np
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

import scale_settled as S
from scale_settled import BLK, MAXN, PHI, SEQLEN, check, abort_if_failed, linears, scale

HERE = os.path.dirname(os.path.abspath(__file__))
SCRATCH = ("/private/tmp/claude-501/-Users-ssdm4-Desktop-PROJECTS-CLAUDE/"
           "0e868af8-ab2d-4d00-be03-8fea94ba48e4/scratchpad")
torch.set_grad_enabled(False)

# The clamp fraction of an alignment is 1 - log_g(max_norm/c), NOT log_g(max_norm/c): max_norm
# sits (1-u) of the way through the window, so the mass ABOVE it is u.  Gate N1 caught this
# inverted the first time it ran (it returned c = 4.5, not OCP's 4.0).
U_OCP = 1.0 - float(np.log2(MAXN / 4.0))   # 0.4150375, the alignment every MX-class spec fixes
NLEV_W = 16                             # 4-bit scale field; nclip is printed and must stay 0
NLEV_A = None                           # activations get an unbounded (E8M0-class) field


def u2c(u, g):
    """Alignment constant with target log-uniform clamp fraction u, for base g."""
    return MAXN / g ** (1.0 - u)


# ---------------------------------------------------------------- per-window loss
def losses(m, ids, nw):
    """Per-window mean NLL, so ppl over any window prefix is exp(mean(L[:K])).

    Weighting matches scale_settled.ppl exactly: every window contributes SEQLEN-1 tokens, so the
    aggregate is a plain mean of the per-window losses.  Gate N3 checks this against S.ppl.
    """
    n = (ids.numel() // SEQLEN) * SEQLEN
    x = ids[:n].reshape(-1, SEQLEN)[:nw]
    out = np.empty(x.shape[0], dtype=np.float64)
    for i in range(x.shape[0]):
        c = x[i:i + 1]
        out[i] = m(c, labels=c).loss.double().item()
    return out


def ppl_of(L, k=None):
    return float(np.exp(L[:k].mean() if k else L.mean()))


# ---------------------------------------------------------------- activation quantiser
class ActQ:
    """MX-style activation quantisation on the input of every quantised Linear.

    Blocks of 32 along the reduction (last) axis, same scale rule and same E2M1 element grid as the
    weights -- this is what "MX shares the scale encoding between weights and activations" means.
    Records the observed amax/s window and clamp rate so gate 3 (print the range) holds for
    activations too.
    """

    def __init__(self, g, c, tie, nlev=NLEV_A):
        self.g, self.c, self.tie, self.nlev = g, c, tie, nlev
        self.n = self.nsat = 0
        self.rmin, self.rmax = 1e30, -1e30
        self.handles = []

    def _q(self, x):
        sh = x.shape
        assert sh[-1] % BLK == 0, f"activation last dim {sh[-1]} not a multiple of {BLK}"
        b = x.double().reshape(-1, BLK)
        amax = b.abs().amax(dim=1)
        s, _ = scale(amax, self.g, self.c, self.nlev)
        s = s.clamp(min=1e-30)
        nz = amax > 0
        if bool(nz.any()):
            r = (amax[nz] / s[nz])
            self.rmin = min(self.rmin, float(r.min()))
            self.rmax = max(self.rmax, float(r.max()))
            self.nsat += int((r > MAXN).sum())
            self.n += int(nz.sum())
        q = torch.sign(b) * S.q_elem(b / s[:, None], self.tie) * s[:, None]
        return q.reshape(sh).to(x.dtype)

    def attach(self, m):
        for nm, mod in linears(m):
            self.handles.append(mod.register_forward_pre_hook(
                lambda mod, args, self=self: (self._q(args[0]),) + tuple(args[1:])))
        return len(self.handles)


# ---------------------------------------------------------------- corpora
def wikitext(tok):
    import pyarrow.parquet as pq
    t = pq.read_table(os.path.join(S.W, "wikitext2-test.parquet")).column("text").to_pylist()
    return tok("\n\n".join(t), return_tensors="pt").input_ids[0]


# SECOND CORPUS.  PTB and C4 both require a download, and downloading is not something this
# session has the user's permission to do (the PTB mirror
# https://raw.githubusercontent.com/wojzaremba/lstm/master/data/ptb.test.txt was verified
# reachable, HTTP 200, 449,945 bytes, but not fetched).  So the held-out corpus is built from text
# already on this machine: 215 English Markdown files from trinity-fpga/docs/, exact-duplicate
# files dropped, files >2% Cyrillic dropped, deterministic shuffle seed 20260812, 1,851,862 bytes,
# sha256 a8ba7437...4304f, manifest beside the file.  Technical prose + code blocks + tables is a
# LARGER distribution shift from wikitext-2 than PTB would be, which is what the check needs.
DOCS_PATH = os.path.join(SCRATCH, "docs_en.txt")


def docs_en(tok):
    with open(DOCS_PATH, encoding="utf-8") as f:
        return tok(f.read(), return_tensors="pt").input_ids[0]


# STANDARD SECOND CORPUS, added 2026-08-12 wave 2.  Penn Treebank test split, the Mikolov
# preprocessing every PTQ paper reports (lower-cased, <unk>, numbers as N), fetched from the
# canonical Zaremba mirror
#   https://raw.githubusercontent.com/wojzaremba/lstm/master/data/ptb.test.txt
#   449,945 bytes, 3,761 lines, 78,669 whitespace tokens,
#   sha256 dd65dff31e70846b2a6030a87482edcd5d199130cdcfa1f3dccbb033728deee0
# The whole file is tokenised as one string, exactly as wikitext-2 is here.
PTB_PATH = os.path.join(SCRATCH, "ptb.test.txt")


def ptb(tok):
    with open(PTB_PATH, encoding="utf-8") as f:
        return tok(f.read(), return_tensors="pt").input_ids[0]


CORPORA = {"wikitext2": wikitext, "docs_en": docs_en, "ptb": ptb}


# ================================================================== gates for the NEW code
def selftests():
    print("\n  GATES FOR THE NEW CODE (the u map, the loss accumulator, the activation path)",
          flush=True)

    # N1 -- the u parameterisation reproduces the specs it claims to reproduce, exactly.
    check(abs(u2c(U_OCP, 2.0) - 4.0) < 1e-12, "N1 u=log2(6/4), g=2 gives OCP's c=4 exactly",
          f"c = {u2c(U_OCP, 2.0):.15f}")
    check(abs(u2c(0.0, 2.0) - 3.0) < 1e-12 and abs(u2c(0.0, PHI) - MAXN / PHI) < 1e-12,
          "N1 u=0 is max_norm/g for both bases (the no-clamp alignment)")
    check(abs(u2c(1.0, 2.0) - MAXN) < 1e-12, "N1 u=1 puts max_norm at the window floor")

    # N2 -- GATE 3: the clamp fraction is MEASURED against a log-uniform generator and PRINTED,
    #       for both bases, not assumed from the algebra.
    a = torch.exp(torch.rand(4000000, dtype=torch.float64) * 60.0 - 30.0)
    print(f"      {'base':<6}{'u':>9}{'c':>10}{'amax/s window':>22}"
          f"{'observed window':>26}{'clamp% obs':>12}{'clamp% =u':>11}", flush=True)
    for g, gn in ((2.0, "2^k"), (PHI, "phi")):
        for u in (0.0, 0.15, 0.30, 0.35, U_OCP, 0.55):
            c = u2c(u, g)
            s, _ = scale(a, g, c, None)
            r = a / s
            obs = 100.0 * float((r > MAXN).double().mean())
            print(f"      {gn:<6}{u:9.5f}{c:10.5f}  [{c:6.4f},{c * g:7.4f})"
                  f"   [{float(r.min()):9.5f},{float(r.max()):9.5f})"
                  f"{obs:12.3f}{100 * u:11.3f}", flush=True)
            check(float(r.min()) >= c - 1e-9 and float(r.max()) < c * g,
                  f"N2 {gn} u={u:.5f} lands in [{c:.4f},{c * g:.4f})")
            check(abs(obs - 100 * u) < 0.15, f"N2 {gn} u={u:.5f} clamp fraction == u",
                  f"{obs:.3f}% vs {100 * u:.3f}%  (4e6 samples)")
            if u == 0.0:
                check(float(r.max()) <= MAXN + 1e-9, f"N2 {gn} u=0 really never clamps")

    # N3 -- NEGATIVE CONTROL: the alignment that broke scale_frontier_spec.py.  That harness used
    #       c = max_norm with base phi, i.e. amax/s in [6, 6*phi) -- above max_norm -- so EVERY
    #       block maximum clamped and it printed phi = 39.56.  u = 1 is exactly that bug.
    s, _ = scale(a, PHI, MAXN, None)
    frac = float(((a / s) > MAXN).double().mean())
    check(frac > 0.999, "N3 negative control: u=1 (c=max_norm) clamps ~every block",
          f"{100 * frac:.3f}% of 4,000,000 log-uniform blocks -- the scale_frontier_spec.py bug")
    abort_if_failed()
    print("      gates passed\n", flush=True)


def selftests_model(tag, fresh, ids):
    print(f"  GATES ({tag}, real weights and a real forward pass)", flush=True)
    m = fresh()

    # N4 -- the loss accumulator agrees with the trusted scale_settled.ppl on real data, and the
    #       40-window fp32 baseline reproduces the campaign value (gate 1).
    t0 = time.time()
    L = losses(m, ids, 40)
    sec_per_window = (time.time() - t0) / 40.0
    p_new = ppl_of(L)
    nw_save, S.NW = S.NW, 8                     # 8-window cross-check keeps the gate affordable
    p_old = S.ppl(m, ids)
    S.NW = nw_save
    check(abs(ppl_of(L, 8) - p_old) < 1e-9, "N4 per-window accumulator == scale_settled.ppl",
          f"{ppl_of(L, 8):.10f} vs {p_old:.10f}  (8 windows, independent code path)")
    check(abs(p_new - S.BASELINE[tag]) < 5e-4, "N4 fp32 baseline reproduces the campaign value",
          f"{p_new:.4f} vs {S.BASELINE[tag]:.4f}  (40 windows)")
    print(f"      forward cost {sec_per_window:.2f} s/window on this machine "
          f"(torch {torch.__version__}, {torch.get_num_threads()} threads)", flush=True)

    # N5 -- the OCP clamp rate on the REAL weights reproduces the established measurement, and the
    #       4-bit scale field never clips (so 4.125 b/w is the honest cost).
    st, _ = S.quantise_model(m, 2.0, u2c(U_OCP, 2.0), NLEV_W, "even")
    pct = 100.0 * st["nsat"] / st["nblk"]
    check(abs(pct - S.OCP_CLAMP_PCT[tag]) < 0.5, "N5 OCP block-max clamp rate reproduces",
          f"{pct:.2f}% vs established {S.OCP_CLAMP_PCT[tag]:.2f}%  over {st['nblk']:,} blocks")
    check(st["nclip"] == 0, "N5 4-bit scale field never clips",
          f"{st['nclip']} of {st['nblk']:,} blocks")
    print(f"      real-weight amax/s window at OCP: [{st['rmin']:.5f}, {st['rmax']:.5f})",
          flush=True)
    del m
    abort_if_failed()
    print("      gates passed\n", flush=True)


# ================================================================== plumbing
def load(tag, corpus="wikitext2"):
    path = os.path.join(S.W, tag)
    tok = AutoTokenizer.from_pretrained(path)
    ids = CORPORA[corpus](tok)

    def fresh():
        m = AutoModelForCausalLM.from_pretrained(path, dtype=torch.float32)
        m.eval()
        return m
    return fresh, ids


CACHE = {}      # (corpus, weight-hash) -> (longest per-window loss array computed, stats)


def run_cfg(fresh, ids, nw, g, u, tie, nlev=NLEV_W, act_u=None, act_tie=None, corpus="wikitext2"):
    """One measurement, memoised on the quantised-weight hash.

    The cache is keyed by the BLAKE2b digest of the quantised weights (from scale_settled), so two
    configurations that produce bitwise-identical models are never both evaluated -- and a stage
    that needs 40 windows reuses the first 40 of a 120-window array a previous stage computed.
    """
    t0 = time.time()
    m = fresh()
    if u is None:
        st, h = dict(nblk=0, nsat=0, nclip=0, rmin=0.0, rmax=0.0), "fp32"
    else:
        st, h = S.quantise_model(m, g, u2c(u, g), nlev, tie)
    aq = None
    if act_u is not None:
        aq = ActQ(g, u2c(act_u, g), act_tie or tie)
        h = h + f"|act{g}:{act_u:.6f}:{act_tie or tie}"
    key = (corpus, h)
    if key in CACHE and len(CACHE[key][0]) >= nw:
        del m
        L, st0 = CACHE[key]
        st0 = dict(st0)
        st0["sec"] = 0.0
        st0["cached"] = True
        return L[:nw], st0
    if aq is not None:
        st["act_layers"] = aq.attach(m)
    L = losses(m, ids, nw)
    if aq is not None:
        st["act_n"], st["act_sat"] = aq.n, aq.nsat
        st["act_rmin"], st["act_rmax"] = aq.rmin, aq.rmax
    del m
    st["sec"] = time.time() - t0
    CACHE[key] = (L, st)
    return L, st


def boot_gain(La, Lb, n=20000, seed=0):
    """Paired bootstrap over WINDOWS of ppl(A) - ppl(B). Windows are the resampling unit because
    they are the independent replicates; tokens inside a window are not."""
    rng = np.random.default_rng(seed)
    k = len(La)
    idx = rng.integers(0, k, size=(n, k))
    d = np.exp(La[idx].mean(1)) - np.exp(Lb[idx].mean(1))
    return float(np.percentile(d, 2.5)), float(np.percentile(d, 97.5))


def summarise(name, res, base_L, nw, extra=None):
    """res: dict label -> (L, st).  Prints ppl, prefix curve, disjoint-40 spread."""
    print(f"\n  === {name}: {nw} windows x {SEQLEN} tokens "
          f"(denominator: {nw} windows, {nw * (SEQLEN - 1):,} scored tokens) ===", flush=True)
    ks = [k for k in (10, 20, 40, 80, 100, 128, nw) if k <= nw]
    ks = sorted(set(ks))
    print(f"  {'config':<34}{'ppl@' + str(nw):>11}" + "".join(f"{'@' + str(k):>10}" for k in ks)
          + f"{'clamp%':>9}{'sec':>8}", flush=True)
    for label, (L, st) in res.items():
        cl = (100.0 * st["nsat"] / st["nblk"]) if st["nblk"] else 0.0
        print(f"  {label:<34}{ppl_of(L):11.4f}"
              + "".join(f"{ppl_of(L, k):10.4f}" for k in ks)
              + f"{cl:9.2f}{st.get('sec', 0):8.1f}", flush=True)
    # disjoint 40-window subsamples: the honest "how much does the window sample move a number"
    nsub = nw // 40
    if nsub >= 2:
        print(f"\n  WINDOW-SAMPLE NOISE FLOOR: same config, {nsub} DISJOINT 40-window samples",
              flush=True)
        print(f"  {'config':<34}" + "".join(f"{'w' + str(i * 40) + '-' + str(i * 40 + 39):>12}"
                                            for i in range(nsub)) + f"{'spread':>10}", flush=True)
        for label, (L, st) in res.items():
            v = [float(np.exp(L[i * 40:(i + 1) * 40].mean())) for i in range(nsub)]
            print(f"  {label:<34}" + "".join(f"{x:12.4f}" for x in v)
                  + f"{max(v) - min(v):10.4f}", flush=True)
    return ks


U_BEST = {"smollm2": 0.35, "qwen": 0.30}     # the 40-window argmax this wave has to defend


def stage_scan(tag, fresh, ids, nw, corpus, out, save):
    """(a) MORE DATA / (b) ANOTHER CORPUS: u-scan, ties=even, base 2. Ordered so the headline
    pair (OCP, tuned) lands first and a killed run still leaves the result."""
    ub = U_BEST[tag]
    # Long runs buy statistical power on the headline pair; short runs buy curve shape.  Both
    # always contain fp32, OCP and the 40-window argmax, so the claim is testable either way.
    us = ([None, U_OCP, ub, 0.30 if ub != 0.30 else 0.35] if nw >= 80 else
          [None, U_OCP, ub, 0.30 if ub != 0.30 else 0.35, 0.25, 0.20, 0.0])
    res = {}
    for u in us:
        lab = ("fp32 (no quantisation)" if u is None else
               f"u={u:.5f}" + ("  <- OCP MXFP4 spec" if u == U_OCP else "")
               + ("  <- 40w argmax" if u == ub else ""))
        L, st = run_cfg(fresh, ids, nw, 2.0, u, "even", corpus=corpus)
        res[lab] = (L, st)
        print(f"    done {lab}  ppl={ppl_of(L):.4f}  {st.get('sec', 0):.0f}s", flush=True)
        out.setdefault(f"scan_{corpus}", {})[lab] = dict(u=u, ppl=ppl_of(L), L=L.tolist(),
                                               nsat=st["nsat"], nblk=st["nblk"],
                                               nclip=st["nclip"])
        save()
    summarise(f"{tag} / {corpus} / u-scan, base 2, ties=even", res, None, nw)
    ocp_lab = [k for k in res if "OCP" in k][0]
    Lo = res[ocp_lab][0]
    print(f"\n  GAIN vs OCP (positive = tuned u better), paired bootstrap over the {nw} "
          f"windows, 20,000 resamples:", flush=True)
    for lab, (L, st) in res.items():
        if "fp32" in lab or lab == ocp_lab:
            continue
        lo, hi = boot_gain(Lo, L)
        sig = "excludes 0" if lo > 0 or hi < 0 else "INCLUDES 0"
        print(f"    {lab:<34} gain {ppl_of(Lo) - ppl_of(L):+8.4f}   95% CI "
              f"[{lo:+.4f}, {hi:+.4f}]  {sig}", flush=True)
        out.setdefault(f"gain_{corpus}", {})[lab] = dict(gain=ppl_of(Lo) - ppl_of(L),
                                                          ci=[lo, hi], nw=nw)
    # how the gain itself moves with window count -- the noise floor of the CLAIM, not of a ppl
    print(f"\n  GAIN vs WINDOW COUNT (is 40 windows enough to see it?):", flush=True)
    best = min((k for k in res if "fp32" not in k), key=lambda k: ppl_of(res[k][0]))
    print(f"    {'windows':<10}{'ppl OCP':>11}{'ppl ' + best[:9]:>13}{'gain':>10}", flush=True)
    for k in [10, 20, 40, 60, 80, 100, nw]:
        if k > nw:
            continue
        a, b = ppl_of(Lo, k), ppl_of(res[best][0], k)
        print(f"    {k:<10}{a:11.4f}{b:13.4f}{a - b:10.4f}", flush=True)
        out.setdefault(f"gain_vs_nw_{corpus}", {})[str(k)] = a - b
    save()


def stage_ties(tag, fresh, ids, nw, corpus, out, save):
    """(d) TIE RULE: is the gain larger than the element tie-break spread?  ties=even rows come
    free from the scan's cache."""
    ub = U_BEST[tag]
    res = {}
    for u, un in ((ub, f"u={ub:.2f} tuned"), (U_OCP, f"u={U_OCP:.5f} OCP")):
        for tie in S.TIES:
            L, st = run_cfg(fresh, ids, nw, 2.0, u, tie, corpus=corpus)
            res[f"{un}  ties={tie}"] = (L, st)
            print(f"    done {un} ties={tie}  ppl={ppl_of(L):.4f}"
                  f"{'  (cached)' if st.get('cached') else ''}", flush=True)
            out.setdefault("ties", {})[f"{un}|{tie}"] = dict(u=u, tie=tie, ppl=ppl_of(L))
            save()
    summarise(f"{tag} / tie-rule spread at both alignments", res, None, nw)
    sp = {}
    for un in (f"u={ub:.2f} tuned", f"u={U_OCP:.5f} OCP"):
        v = [ppl_of(res[f"{un}  ties={t}"][0]) for t in S.TIES]
        sp[un] = max(v) - min(v)
        print(f"    {un}: tie spread {sp[un]:.4f}  across {S.TIES}", flush=True)
    worst = min(ppl_of(res[f"u={U_OCP:.5f} OCP  ties={t}"][0]) for t in S.TIES)
    bestt = max(ppl_of(res[f"u={ub:.2f} tuned  ties={t}"][0]) for t in S.TIES)
    print(f"\n    WORST CASE FOR THE CLAIM: OCP at its best tie rule {worst:.4f} vs tuned u at "
          f"its worst tie rule {bestt:.4f}  ->  gain {worst - bestt:+.4f}", flush=True)
    out["tie_spread"] = sp
    out["tie_worst_case_gain"] = worst - bestt
    save()


def stage_acts(tag, fresh, ids, nw, corpus, out, save):
    """(c) ACTIVATIONS: MX shares the scale encoding between weights and activations.  Does an
    alignment tuned on weights hurt activations?"""
    ub = U_BEST[tag]
    combos = [(None, None, "fp32 (no quantisation)"),
              (None, U_OCP, f"W fp32,  A OCP u={U_OCP:.4f}"),
              (None, ub, f"W fp32,  A tuned u={ub:.2f}"),
              (U_OCP, U_OCP, "W OCP,   A OCP        (MX spec, shared)"),
              (ub, ub, f"W u={ub:.2f}, A u={ub:.2f}     (shared, tuned)"),
              (ub, U_OCP, f"W u={ub:.2f}, A OCP        (split)")]
    res = {}
    for wu, au, lab in combos:
        L, st = run_cfg(fresh, ids, nw, 2.0, wu, "even", act_u=au, corpus=corpus)
        res[lab] = (L, st)
        extra = ""
        if au is not None and not st.get("cached"):
            extra = (f"   act amax/s [{st['act_rmin']:.4f},{st['act_rmax']:.4f})  "
                     f"act clamp {100.0 * st['act_sat'] / max(st['act_n'], 1):.2f}% of "
                     f"{st['act_n']:,} nonzero blocks over {st['act_layers']} layers")
        print(f"    done {lab}  ppl={ppl_of(L):.4f}{extra}", flush=True)
        out.setdefault("acts", {})[lab] = dict(wu=wu, au=au, ppl=ppl_of(L),
                                               act_n=st.get("act_n"), act_sat=st.get("act_sat"),
                                               act_rmin=st.get("act_rmin"),
                                               act_rmax=st.get("act_rmax"))
        save()
    summarise(f"{tag} / activation sharing (activations E8M0-unbounded field)", res, None, nw)
    save()


def stage_actscan(tag, fresh, ids, nw, corpus, out, save):
    """(c) stronger form: WHERE is the activation optimum?  stage_acts only shows that the
    weight-tuned alignment does not hurt activations; this locates the activation argmin, so the
    two optima can be compared instead of assumed to coincide.  Weights stay fp32 so the only
    quantiser in the path is the activation one."""
    ub = U_BEST[tag]
    res = {}
    for au in [None, 0.0, 0.15, 0.25, ub, 0.35, U_OCP, 0.50]:
        lab = ("W fp32, A fp32" if au is None else
               f"W fp32, A u={au:.5f}" + ("  <- OCP" if au == U_OCP else "")
               + ("  <- weight-opt" if au == ub else ""))
        if lab in res:
            continue
        L, st = run_cfg(fresh, ids, nw, 2.0, None, "even", act_u=au, corpus=corpus)
        res[lab] = (L, st)
        cl = (100.0 * st["act_sat"] / max(st.get("act_n") or 1, 1)) if au is not None else 0.0
        print(f"    done {lab}  ppl={ppl_of(L):.4f}  act clamp {cl:.2f}%", flush=True)
        out.setdefault("actscan", {})[lab] = dict(au=au, ppl=ppl_of(L), act_clamp_pct=cl,
                                                  act_n=st.get("act_n"), act_sat=st.get("act_sat"))
        save()
    summarise(f"{tag} / ACTIVATION-only u-scan (weights fp32)", res, None, nw)
    q = {k: ppl_of(v[0]) for k, v in res.items() if "A fp32" not in k}
    best = min(q, key=q.get)
    print(f"\n    activation argmin: {best.strip()}  ppl {q[best]:.4f}   "
          f"weight-optimal u = {ub}   OCP u = {U_OCP:.5f}", flush=True)
    out["actscan_argmin"] = best
    save()


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    opt = {a.split("=")[0].lstrip("-"): a.split("=")[1] for a in sys.argv[1:] if "=" in a}
    tag = args[0] if args else "smollm2"
    nw = int(opt.get("nw", 120))
    nw_small = int(opt.get("nws", 40))
    stages = opt.get("stages", "scan,ties,acts,corpus").split(",")
    if "threads" in opt:
        torch.set_num_threads(int(opt["threads"]))

    S.selftests_global()
    selftests()
    if args and args[0] == "selftest":
        for t in args[1:] or ["smollm2", "qwen"]:
            f_, i_ = load(t)
            selftests_model(t, f_, i_)
        print("ALL GATES PASSED", flush=True)
        sys.exit(0)

    fresh, ids = load(tag, "wikitext2")
    selftests_model(tag, fresh, ids)
    nw = min(nw, ids.numel() // SEQLEN)

    out = dict(tag=tag, seqlen=SEQLEN, block=BLK, nlev_w=NLEV_W, u_ocp=U_OCP, nw=nw,
               nw_small=nw_small, torch=torch.__version__, threads=torch.get_num_threads(),
               u_best_40w=U_BEST[tag], baseline=S.BASELINE[tag], stages=stages)
    OUTP = os.path.join(HERE, opt.get("out", f"align_harden_{tag}.json"))

    def save():
        with open(OUTP, "w") as f:
            json.dump(out, f)

    for stg in stages:
        t0 = time.time()
        print(f"\n{'=' * 100}\nSTAGE {stg}  ({tag})\n{'=' * 100}", flush=True)
        if stg == "scan":
            stage_scan(tag, fresh, ids, nw, "wikitext2", out, save)
        elif stg == "ties":
            stage_ties(tag, fresh, ids, nw_small, "wikitext2", out, save)
        elif stg == "acts":
            stage_acts(tag, fresh, ids, nw_small, "wikitext2", out, save)
        elif stg == "actscan":
            stage_actscan(tag, fresh, ids, int(opt.get("nwa", nw_small)), "wikitext2", out, save)
        elif stg.startswith("corpus"):
            c2 = stg.split(":", 1)[1] if ":" in stg else "docs_en"
            f2, i2 = load(tag, c2)
            n2 = min(int(opt.get("nw2", nw_small)), i2.numel() // SEQLEN)
            print(f"  held-out corpus {c2}: {i2.numel():,} tokens -> {n2} windows used "
                  f"(denominator {n2})", flush=True)
            out[f"{c2}_tokens"] = int(i2.numel())
            stage_scan(tag, f2, i2, n2, c2, out, save)
        print(f"  STAGE {stg} took {(time.time() - t0) / 60:.1f} min", flush=True)
    print(f"\n  wrote {OUTP}", flush=True)
