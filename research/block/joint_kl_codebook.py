#!/usr/bin/env python3
"""CAMPAIGN A -- does the KL objective survive a MULTI-MODEL fit?

Two codebooks have now been fitted with six free interior magnitudes and the
same 120-evaluation coordinate descent, both against ONE model (SmolLM2-135M):

  KL-opt      fitted to SmolLM2 logits  -> out of sample LOSES (+1.98% Qwen,
              +8.63% Pythia vs MXFP4); the ranking inverts.
  nSSE-equal  fitted to SmolLM2 weight statistics -> out of sample TIES.

Both failures were single-model fits, so the untested question is whether the KL
objective is worthless or whether the single-model fit was the whole problem.
This fits ONE codebook against the SUM of KL(fp32 || quantised) over THREE
models at once -- SmolLM2-135M, Qwen2.5-0.5B, Pythia-160M -- 2 calibration
windows each, same descent shape (six free interior magnitudes, top pinned to
1.0, step 0.06 halving to 0.004, 120 evaluations per seed, seeds MXFP4 and
Lloyd-Max).

T38 (SCALE_PHASE_THEOREM_2026-08-11.md): the E8M0 scale rounds UP to a power of
two, so a codebook whose top is not a power of two sits at a different headroom
phase and its comparison is confounded. Every codebook here is asserted to have
top exactly 1.0, seeds included, and the descent never touches index 0 or 7.

Measurement path is reused, not reimplemented: quant/perplexity/target_modules/
load_wikitext are executed out of block_tnf.py's source up to its driver marker.

Reference log-probabilities are held in on-disk float32 memmaps (4.1 GB total)
so all three models can stay resident on a 16 GB machine; the reference is
identical for every candidate, so its storage precision cancels out of every
comparison the descent makes.

    EVALS=120 KLWIN=2 python3 joint_kl_codebook.py
"""
import json
import math
import os
import sys
import time

import numpy as np
import torch
import torch.nn.functional as F

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "block_tnf.py")
MARKER = 'print("загружаю модель…", flush=True)'
_s = open(SRC, encoding="utf-8").read()
if MARKER not in _s:
    raise SystemExit("driver marker not found in block_tnf.py")
ns = {}
exec(compile(_s.split(MARKER)[0], SRC, "exec"), ns)

fp_levels = ns["fp_levels"]
quant, perplexity, target_modules, load_wikitext = (
    ns[k] for k in ("quant", "perplexity", "target_modules", "load_wikitext"))
K, SEQLEN = ns["K"], ns["SEQLEN"]
W = os.path.dirname(ns["MODEL"])

torch.set_grad_enabled(False)

EVALS = int(os.environ.get("EVALS", "120"))     # per seed, as the single-model fit
KLWIN = int(os.environ.get("KLWIN", "2"))       # calibration windows per model
CHUNK = int(os.environ.get("CHUNK", "128"))     # rows per KL chunk
FIT_MODELS = os.environ.get("FIT_MODELS", "smollm2,qwen,pythia").split(",")
SCRATCH = os.environ.get(
    "SCRATCH", "/private/tmp/claude-501/-Users-ssdm4-Desktop-PROJECTS-CLAUDE/"
               "4ee033a3-337b-4f3e-a701-150ecdcd58df/scratchpad")
OUT = os.path.join(HERE, "joint_kl_codebook.json")


def normalise(lv):
    v = sorted(float(x) for x in lv)
    return [x / v[-1] for x in v]


def assert_phase0(name, lv):
    assert len(lv) == 8, (name, len(lv))
    assert list(lv) == sorted(lv), name
    assert all(b > a for a, b in zip(lv, lv[1:])), name
    assert float(lv[0]) == 0.0, name
    assert abs(float(lv[-1]) - 1.0) < 1e-12, f"{name}: top={lv[-1]} -> phi != 0"
    assert abs(math.log2(float(lv[-1])) % 1.0) < 1e-12, name


MXFP4 = normalise(fp_levels(2, 1))
LLOYD = normalise([0.0, 0.10334, 0.21079, 0.32491, 0.44963,
                   0.59031, 0.75635, 0.96567])
KLOPT = [0.0, 0.07701, 0.18828, 0.31396, 0.46561, 0.6113, 0.79074, 1.0]
NSSE = [0.0, 0.09083, 0.18167, 0.28750, 0.40833, 0.55250, 0.73417, 1.0]
for nm, lv in (("MXFP4", MXFP4), ("Lloyd-Max", LLOYD),
               ("KL-opt", KLOPT), ("nSSE-equal", NSSE)):
    assert_phase0(nm, lv)
print("all seed/reference codebooks: top = 1.0 exactly (headroom phase phi=0)",
      flush=True)


class Sub:
    """One model, its calibration windows, and its reference log-probabilities."""

    def __init__(self, mdir):
        from transformers import AutoModelForCausalLM, AutoTokenizer
        path = os.path.join(W, mdir)
        self.name = mdir
        t0 = time.time()
        tok = AutoTokenizer.from_pretrained(path)
        self.model = AutoModelForCausalLM.from_pretrained(path,
                                                          dtype=torch.float32)
        self.model.eval()
        ids = tok(load_wikitext(), return_tensors="pt").input_ids
        flat = ids.reshape(-1)
        nwin = flat.numel() // SEQLEN
        self.win = flat[:nwin * SEQLEN].view(-1, SEQLEN)[:KLWIN]
        self.lins = target_modules(self.model)
        if not self.lins:
            raise SystemExit(f"{mdir}: zero target modules")
        self.orig = {n: m.weight.detach().clone() for n, m in self.lins}
        self.V = int(self.model(self.win[0:1]).logits.shape[-1])
        # reference log-probs -> float32 memmap on disk
        self.ref_path = os.path.join(SCRATCH, f"ref_{mdir}.f32")
        self.ref = np.memmap(self.ref_path, dtype=np.float32, mode="w+",
                             shape=(KLWIN * SEQLEN, self.V))
        self.apply(None)
        for i in range(KLWIN):
            lg = self.model(self.win[i:i + 1]).logits[0]
            for a in range(0, SEQLEN, CHUNK):
                b = min(a + CHUNK, SEQLEN)
                self.ref[i * SEQLEN + a: i * SEQLEN + b] = \
                    F.log_softmax(lg[a:b].double(), dim=-1).float().numpy()
            del lg
        self.ref.flush()
        npar = sum(v.numel() for v in self.orig.values())
        print(f"  {mdir:<8} {len(self.lins):3d} linear tensors, "
              f"{npar/1e6:6.1f}M weights, vocab {self.V}, "
              f"ref {self.ref.nbytes/1e9:.2f} GB  [{time.time()-t0:.0f}s]",
              flush=True)

    def apply(self, lv):
        for n, m in self.lins:
            m.weight.copy_(self.orig[n] if lv is None else quant(self.orig[n], lv))

    def kl(self, lv):
        """mean_positions KL(p_ref || p_quantised), float64, chunked."""
        self.apply(lv)
        tot, cnt = 0.0, 0
        for i in range(KLWIN):
            lg = self.model(self.win[i:i + 1]).logits[0]
            for a in range(0, SEQLEN, CHUNK):
                b = min(a + CHUNK, SEQLEN)
                lpr = torch.from_numpy(
                    np.asarray(self.ref[i * SEQLEN + a: i * SEQLEN + b])).double()
                lpq = F.log_softmax(lg[a:b].double(), dim=-1)
                tot += float((lpr.exp() * (lpr - lpq)).sum())
                cnt += b - a
                del lpr, lpq
            del lg
        return tot / cnt


def main():
    out = {"EVALS_per_seed": EVALS, "KLWIN": KLWIN, "fit_models": FIT_MODELS,
           "seeds": {"MXFP4": MXFP4, "Lloyd-Max": LLOYD}}
    print(f"\nloading {len(FIT_MODELS)} models "
          f"({KLWIN} calibration windows each)…", flush=True)
    subs = [Sub(m) for m in FIT_MODELS]

    nev = {"n": 0}

    def joint(lv):
        assert_phase0("candidate", lv)
        per = [s.kl(lv) for s in subs]
        nev["n"] += 1
        return float(sum(per)), per

    def objective(lv):
        return joint(lv)[0]

    # ---- where the incumbents sit on this objective -----------------------
    print("\nincumbents on the joint objective "
          "(sum over models of KL(fp32 || quantised)):", flush=True)
    ref_obj = {}
    for name, lv in (("MXFP4", MXFP4), ("Lloyd-Max", LLOYD),
                     ("KL-opt (SmolLM2-only fit)", KLOPT),
                     ("nSSE-equal (SmolLM2-only fit)", NSSE)):
        t0 = time.time()
        tot, per = joint(lv)
        ref_obj[name] = {"joint": tot,
                         "per_model": dict(zip(FIT_MODELS, per))}
        print(f"  {name:<32} {tot:.6f}   "
              + "  ".join(f"{m}={v:.6f}" for m, v in zip(FIT_MODELS, per))
              + f"   [{time.time()-t0:.0f}s/eval]", flush=True)
    out["incumbent_objective"] = ref_obj
    json.dump(out, open(OUT, "w"), indent=1)

    # ---- the search: identical shape to the single-model fit --------------
    print(f"\ncoordinate descent, {EVALS} evaluations per seed, "
          f"step 0.06 halving to 0.004, interior points only", flush=True)
    best, traj = None, {}
    for seed_name, seed in (("MXFP4", MXFP4), ("Lloyd-Max", LLOYD)):
        lv = normalise(seed)
        cur = start = objective(lv)
        evals, step = 0, 0.06
        t0 = time.time()
        while evals < EVALS and step > 0.004:
            improved = False
            for i in range(1, len(lv) - 1):          # interior points only
                for d in (+step, -step):
                    cand = list(lv)
                    cand[i] = cand[i] + d
                    lo, hi = cand[i - 1] + 1e-3, cand[i + 1] - 1e-3
                    if not (lo < cand[i] < hi):
                        continue
                    v = objective(cand)
                    evals += 1
                    if v < cur - 1e-7:
                        lv, cur, improved = cand, v, True
                    if evals >= EVALS:
                        break
                if evals >= EVALS:
                    break
            if not improved:
                step /= 2
        _, per = joint(lv)
        print(f"  from {seed_name:<10} {evals:4d} evals  {start:.6f} -> "
              f"{cur:.6f} ({100*(1-cur/start):+.3f}%)  "
              f"{[round(x,5) for x in lv]}  [{(time.time()-t0)/60:.1f} min]",
              flush=True)
        traj[seed_name] = {"start": start, "end": cur, "evals": evals,
                           "levels": [float(x) for x in lv],
                           "per_model": dict(zip(FIT_MODELS, per))}
        out["trajectory"] = traj
        json.dump(out, open(OUT, "w"), indent=1)
        if best is None or cur < best[0]:
            best = (cur, lv, seed_name)

    kl_best, lv_best, origin = best
    assert_phase0("joint fit", lv_best)
    out["joint_fit"] = {"levels": [float(x) for x in lv_best],
                        "objective": kl_best, "origin": origin,
                        "total_objective_evaluations": nev["n"]}
    print(f"\nJOINT-KL codebook (from {origin}): "
          f"{[round(x,5) for x in lv_best]}")
    print(f"  joint objective {kl_best:.6f} vs MXFP4 "
          f"{ref_obj['MXFP4']['joint']:.6f} "
          f"({100*(kl_best/ref_obj['MXFP4']['joint']-1):+.2f}%)")
    for s in subs:
        s.apply(None)
    json.dump(out, open(OUT, "w"), indent=1)
    print(f"\nwrote {OUT}")
    print("NOTE: the objective is the fitting signal, NOT the verdict. "
          "The verdict is 40/20/40-window perplexity + a held-out model.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
