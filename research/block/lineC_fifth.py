#!/usr/bin/env python3
"""Line C: four checkpoints from families this campaign has never measured.

Everything the block campaign still asserts is WITHIN a checkpoint. The four
checkpoints it owns have each been used for selection at least once, and they
are four variations on one decoder-only theme, so they are closer to one
replicate than to four. This file measures the pre-registered arms on four
checkpoints chosen for ARCHITECTURAL DISTANCE, under the protocol in
PREREGISTRATION_FIFTH_2026-08-12.md, which was written and committed before any
model here was loaded.

NOTHING ON THE MEASUREMENT PATH IS REIMPLEMENTED. quant / perplexity /
target_modules / load_wikitext / q_e8m0_t are executed out of block_tnf.py's
source up to its driver marker; the codebooks are campaignA_books; the signed
quantiser is campaignC_books.make_quant_signed.

TWO THINGS ARE GENUINELY NEW, SO EACH GETS A GATE THAT ABORTS BEFORE A NUMBER
PRINTS.

G1  Conv1D targeting.  GPT-2 stores its projections as transformers Conv1D with
    shape [in, out], not nn.Linear [out, in]. block_tnf.target_modules matches
    isinstance(nn.Linear) only, so on GPT-2 it returns lm_head alone -- which is
    then excluded -- and EVERY arm would silently report the fp32 number. That
    is the failure align_u.py's U8 gate was built for, and it is the single most
    likely way this file could produce twelve identical columns and call them a
    result. So: targets() carries a per-tensor block AXIS, Conv1D is transposed
    into [out, in] before quantisation and back after, and the selector is
    asserted to agree tensor-for-tensor with block_tnf.target_modules on every
    checkpoint that has no Conv1D.

G2  A new checkpoint has no published ruler, so "the ruler reproduces" cannot be
    checked on it. The gate is therefore run on the FOUR OLD checkpoints with
    this file's own code path (MODE=ruler): if this harness cannot reproduce
    14.4874 / 21.9397 and the other three pairs, it is not the campaign's
    instrument and nothing it says about a new checkpoint counts.

Plus the standing checks: the signed quantiser is bit-exact against
block_tnf.quant in THIS process, every arm is asserted to actually CHANGE the
weights, and the fraction of parameters the block rule reaches is recorded per
model rather than assumed.

    MODE=ruler python3 lineC_fifth.py                # gate on the old four
    MDIR=gpt2 python3 lineC_fifth.py                 # measure one new checkpoint
"""
import json
import os
import sys
import time

import numpy as np
import torch

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "block_tnf.py")
MARKER = 'print("загружаю модель…", flush=True)'
_s = open(SRC, encoding="utf-8").read()
if MARKER not in _s:
    raise SystemExit("driver marker not found in block_tnf.py")
ns = {}
exec(compile(_s.split(MARKER)[0], SRC, "exec"), ns)
quant, perplexity, target_modules, load_wikitext = (
    ns[k] for k in ("quant", "perplexity", "target_modules", "load_wikitext"))
K = ns["K"]

sys.path.insert(0, HERE)
import campaignA_books as A          # noqa: E402
import campaignC_books as C          # noqa: E402

from transformers.pytorch_utils import Conv1D    # noqa: E402

torch.set_grad_enabled(False)
if os.environ.get("THREADS"):
    torch.set_num_threads(int(os.environ["THREADS"]))

W = os.environ.get("W", "/private/tmp/claude-501/-Users-ssdm4-Desktop-PROJECTS-"
                        "CLAUDE/0e868af8-ab2d-4d00-be03-8fea94ba48e4/scratchpad/"
                        "weights")

# The four this campaign already owns -- here ONLY as the ruler gate.
OLD = {
    "smollm2": dict(src=os.path.join(W, "smollm2"), seqlen=2048, nwin=40,
                    ruler={"fp32": 14.4874, "MXFP4": 21.9397}),
    "qwen":    dict(src=os.path.join(W, "qwen"), seqlen=2048, nwin=20,
                    ruler={"fp32": 12.6999, "MXFP4": 15.4374}),
    "pythia":  dict(src=os.path.join(W, "pythia"), seqlen=2048, nwin=40,
                    ruler={"fp32": 25.9561, "MXFP4": 47.6504}),
    "opt":     dict(src=os.path.join(W, "opt"), seqlen=2048, nwin=40,
                    ruler={"fp32": 27.5678, "MXFP4": 30.7871}),
}
# The four pre-registered new ones. gpt2's context is 1024 by construction
# (learned positional table, n_positions = 1024), so 2048 is not available to
# it at any price; 80 windows of 1024 cover the SAME 81,920-token span that
# 40 x 2048 covers everywhere else. Declared in the pre-registration, not here.
NEW = {
    "gpt2":   dict(src=os.path.join(W, "gpt2"), seqlen=1024, nwin=80, ruler=None),
    "gptneo": dict(src="EleutherAI/gpt-neo-125m", seqlen=2048, nwin=40, ruler=None),
    "bloom":  dict(src="bigscience/bloom-560m", seqlen=2048, nwin=40, ruler=None),
    "mamba":  dict(src="state-spaces/mamba-130m-hf", seqlen=2048, nwin=40, ruler=None),
}
SPEC = dict(OLD, **NEW)

NINE = ["NEAR0", "NEAR0N", "MIDN", "MID", "G12", "G23", "G34", "G68", "MID2"]
ARMS = ["MXFP4"] + [f"MX-asym-{g}" for g in NINE] + ["NF4"]


def targets(model):
    """(name, module, axis) for every quantisable tensor, lm_head excluded.

    axis is the CONTRACTION axis, i.e. the one blocks of 32 run along:
    nn.Linear stores [out, in] so it is 1; transformers Conv1D stores
    [in, out] so it is 0.
    """
    out = []
    for n, m in model.named_modules():
        if "lm_head" in n:
            continue
        if isinstance(m, torch.nn.Linear):
            out.append((n, m, 1))
        elif isinstance(m, Conv1D):
            out.append((n, m, 0))
    return out


def qblock(f, w, lv, axis):
    """Apply a block quantiser whose block axis is dim 1 to a tensor whose
    contraction axis is `axis`."""
    if axis == 1:
        return f(w, lv)
    return f(w.t().contiguous(), lv).t().contiguous()


def elems(w, axis):
    """Elements the block rule actually reaches: the ragged tail of a row that
    is not a multiple of 32 is left in fp32 by block_tnf.quant, on purpose."""
    n_ax = w.shape[1] if axis == 1 else w.shape[0]
    other = w.shape[0] if axis == 1 else w.shape[1]
    return (n_ax // K) * K * other, w.numel()


def wikitext():
    import pyarrow.parquet as pq
    t = pq.read_table(os.path.join(W, "wikitext2-test.parquet"))
    return "\n\n".join(t.column("text").to_pylist())


def main():
    from transformers import AutoModelForCausalLM, AutoTokenizer

    mode = os.environ.get("MODE", "measure")
    mdirs = ([m for m in OLD] if mode == "ruler"
             else [os.environ["MDIR"]])

    quant_signed = C.make_quant_signed(K, ns["q_e8m0_t"])
    BOOKS = {n: (k, [float(x) for x in lv]) for n, k, lv in A.all_books()}
    list(A.check(A.all_books()))          # T38 on both tails, 16-codeword count
    for a in ARMS:
        assert a in BOOKS, a

    txt = wikitext()
    rc = 0
    for mdir in mdirs:
        sp = SPEC[mdir]
        ns["SEQLEN"] = SEQLEN = sp["seqlen"]     # perplexity() reads this global
        NWIN = sp["nwin"]
        print(f"\n{'='*78}\n{mdir}   src={sp['src']}   SEQLEN={SEQLEN}  "
              f"NWIN={NWIN}  MODE={mode}\n{'='*78}", flush=True)

        tok = AutoTokenizer.from_pretrained(sp["src"])
        model = AutoModelForCausalLM.from_pretrained(sp["src"], dtype=torch.float32)
        model.eval()
        ids = tok(txt, return_tensors="pt").input_ids
        flat = ids.reshape(-1)
        ntot = flat.numel() // SEQLEN
        if ntot < NWIN:
            print(f"ABORT: {ntot} windows available, {NWIN} required")
            return 5
        win = flat[:ntot * SEQLEN].view(-1, SEQLEN)
        print(f"tokens={flat.numel()}  windows_available={ntot}", flush=True)

        # ---- G1: targeting -------------------------------------------------
        tg = targets(model)
        if not tg:
            print("ABORT: the target filter matched NOTHING.")
            return 6
        n_conv = sum(1 for _, _, ax in tg if ax == 0)
        if n_conv == 0:
            base = [n for n, _ in target_modules(model)]
            assert base == [n for n, _, _ in tg], (
                "extended selector disagrees with block_tnf.target_modules")
            same = "identical to block_tnf.target_modules"
        else:
            same = f"{n_conv} Conv1D tensors transposed to [out, in]"
        nq = nt = 0
        for _, m, ax in tg:
            a, b = elems(m.weight, ax)
            nq += a
            nt += b
        ptot = sum(p.numel() for p in model.parameters())
        frac = nq / ptot
        print(f"G1 targets: {len(tg)} tensors, {same}\n"
              f"   {nq:,} of {nt:,} target elements blocked "
              f"({100*nq/nt:.3f}% -- the rest is the ragged tail left in fp32)\n"
              f"   {100*frac:.1f}% of the checkpoint's {ptot/1e6:.1f}M parameters",
              flush=True)
        if frac < 0.20:
            print("ABORT: the block rule reaches under 20% of the model.")
            return 7

        orig = {n: m.weight.detach().clone() for n, m, _ in tg}

        def apply(entry):
            if entry is None:
                for n, m, _ in tg:
                    m.weight.copy_(orig[n])
                return 0.0
            kind, lv = entry
            f = quant if kind == "mag" else quant_signed
            worst = 0.0
            for n, m, ax in tg:
                q = qblock(f, orig[n], lv, ax)
                worst = max(worst, float((q - orig[n]).abs().max()))
                m.weight.copy_(q)
            return worst

        def per_window():
            return np.array([float(np.log(perplexity(model, win[i], 1)))
                             for i in range(NWIN)], dtype=np.float64)

        # ---- G3: the signed quantiser is still block_tnf.quant, here -------
        worst = 0.0
        for name in ("MXFP4", "NF4-sym"):
            mags = BOOKS[name][1]
            sig = C.signed_from_magnitudes(mags)
            assert len(sig) == 15, (name, len(sig))
            for _, m, ax in tg:
                w = m.weight.detach()
                worst = max(worst, float(
                    (qblock(quant, w, mags, ax)
                     - qblock(quant_signed, w, sig, ax)).abs().max()))
        print(f"G3 instrument max|quant - quant_signed| = {worst:.3e}  "
              f"{'BIT-EXACT' if worst == 0.0 else 'MISMATCH'}", flush=True)
        if worst != 0.0:
            return 3

        dst = os.path.join(HERE, f"lineC_{mdir}.json")
        out = {"model": mdir, "src": sp["src"], "seqlen": SEQLEN, "nwin": NWIN,
               "block": K, "scale": "E8M0", "lm_head": "excluded",
               "n_target_tensors": len(tg), "n_conv1d": n_conv,
               "elem_blocked": nq, "elem_target": nt, "param_total": ptot,
               "frac_params_quantised": frac,
               "instrument_bit_exact": worst == 0.0,
               "per_window_nll": {}, "ppl": {}, "arm_max_abs_delta": {},
               "books": {a: BOOKS[a][1] for a in ARMS}}

        # ---- fp32 + the ruler ---------------------------------------------
        t0 = time.time()
        apply(None)
        nll = per_window()
        p32 = float(np.exp(nll.mean()))
        out["per_window_nll"]["fp32"] = list(map(float, nll))
        out["ppl"]["fp32"] = p32
        print(f"   fp32{'':<14}{p32:>10.4f}   ({time.time()-t0:.0f}s)", flush=True)

        want = ["MXFP4"] if mode == "ruler" else ARMS
        ruler_ok = True
        for a in want:
            t0 = time.time()
            d = apply(BOOKS[a])
            # G4: an arm that changed nothing is a silent fp32 column.
            if d <= 0.0:
                print(f"ABORT: arm {a} left every weight unchanged.")
                return 8
            v = per_window()
            pv = float(np.exp(v.mean()))
            out["per_window_nll"][a] = list(map(float, v))
            out["ppl"][a] = pv
            out["arm_max_abs_delta"][a] = d
            tag = ""
            if sp["ruler"] and a in sp["ruler"]:
                rel = abs(pv - sp["ruler"][a]) / sp["ruler"][a]
                ok = rel < 5e-4
                ruler_ok &= ok
                tag = (f"   published {sp['ruler'][a]:.4f}  rel {rel:.2e}  "
                       f"{'OK' if ok else 'MISMATCH'}")
            print(f"   {a:<18}{pv:>10.4f}   ({time.time()-t0:.0f}s){tag}",
                  flush=True)
            json.dump(out, open(dst, "w"), indent=1)

        if sp["ruler"]:
            rel = abs(p32 - sp["ruler"]["fp32"]) / sp["ruler"]["fp32"]
            ok = rel < 5e-4
            ruler_ok &= ok
            print(f"   RULER fp32 published {sp['ruler']['fp32']:.4f}  "
                  f"rel {rel:.2e}  {'OK' if ok else 'MISMATCH'}", flush=True)
            out["ruler_reproduces"] = bool(ruler_ok)
            if not ruler_ok:
                print("RULER BROKEN -- this harness is not the campaign's "
                      "instrument. Refusing to measure anything new.")
                rc = 2
        else:
            # No published ruler exists for a checkpoint nobody has measured.
            # What CAN be asserted: 4-bit weights must cost perplexity.
            out["ruler_reproduces"] = None
            out["mxfp4_costs_ppl"] = bool(out["ppl"]["MXFP4"] > p32)
            if not out["mxfp4_costs_ppl"]:
                print("ABORT: MXFP4 did not raise perplexity over fp32.")
                return 9
            print(f"   NEW RULERS RECORDED: fp32 {p32:.4f}  "
                  f"MXFP4 {out['ppl']['MXFP4']:.4f}", flush=True)

        apply(None)
        json.dump(out, open(dst, "w"), indent=1)
        print(f"wrote {dst}", flush=True)
        del model, orig
    return rc


if __name__ == "__main__":
    sys.exit(main())
