#!/usr/bin/env python3
"""Instrument check WITHOUT checkpoints: quant_signed IS block_tnf.quant.

campaignC_agree.py proves this over real checkpoint tensors, but the four model
directories were deleted from this machine, so that route is unavailable. The
agreement is a property of the two DECISION RULES, not of the data, and the only
place the rules could ever disagree is a value landing EXACTLY on a decision
boundary: quant bucketizes |w| (tie -> toward zero on both signs) while a naive
signed bucketize would round a negative tie toward -inf.

So this check does something the checkpoint route only does by luck: it
CONSTRUCTS tensors that sit exactly on every decision boundary of every book, on
both signs, and demands bit-exact equality there. Real weights hit those points
by accident (189406 times on smollm2 under MXFP4, per campaignB_agree.log); here
every boundary is hit deliberately, every time.

Three families of input, all six symmetric Campaign C books:
  A  boundary-exact  -- block max pinned to 1.0 so E8M0 gives s == 1 and the
                        normalised value y is the literal boundary
  B  random normal   -- the generic case
  C  archived sample -- loguniform_x_<model>.npy, the block-normalised element
                        values kept from the earlier runs

    python3 campaignC_agree_synthetic.py
"""
import os
import sys

import numpy as np
import torch

HERE = os.path.dirname(os.path.abspath(__file__))
_s = open(os.path.join(HERE, "block_tnf.py"), encoding="utf-8").read()
ns = {}
exec(compile(_s.split('print("загружаю модель…", flush=True)')[0],
             "block_tnf.py", "exec"), ns)
quant, K = ns["quant"], ns["K"]

sys.path.insert(0, HERE)
import campaignC_books as C

torch.set_grad_enabled(False)
quant_signed = C.make_quant_signed(K, ns["q_e8m0_t"])


def boundary_block(mags):
    """Rows of K elements whose normalised values are EXACTLY the decision
    boundaries. Element 0 of every row is 1.0, so amax == 1.0 == max|level|,
    hence s = 2**ceil(log2(1)) = 1 and y is the raw value."""
    lv = torch.tensor(sorted(float(x) for x in mags), dtype=torch.float64)
    bnd = ((lv[:-1] + lv[1:]) / 2).tolist()
    # every boundary, both signs, plus every level itself, both signs
    vals = ([+b for b in bnd] + [-b for b in bnd]
            + [+float(x) for x in lv] + [-float(x) for x in lv])
    rows = []
    for start in range(len(vals)):
        r = [1.0] + [vals[(start + j) % len(vals)] for j in range(K - 1)]
        rows.append(r)
    # float64, deliberately: quant promotes to double internally, so a float32
    # store would round most midpoints OFF the boundary and the test would go
    # vacuous for every book whose midpoints are not float32-representable.
    # Verified live by the negative control below.
    w = torch.tensor(rows, dtype=torch.float64)
    # EVERY row, not min(): a single row at 1.0 satisfies min() while any row
    # carrying a value above 1.0 gets s = 2, so its elements stop sitting on a
    # boundary and that row silently degrades to an ordinary random test.
    assert bool((w.abs().amax(dim=1) == 1.0).all()), float(w.abs().amax())
    return w


def check(tag, w, books):
    worst = 0.0
    for name, mags in books:
        sig = C.signed_from_magnitudes(mags)
        assert len(sig) == 15, (name, len(sig))
        a = quant(w, mags)
        b = quant_signed(w, sig)
        worst = max(worst, (a - b).abs().max().item())
    ok = worst == 0.0
    print(f"  {tag:<34} max|quant - quant_signed| = {worst:.3e}   "
          f"{'BIT-EXACT' if ok else 'MISMATCH'}", flush=True)
    return ok


def main():
    bs = C.books()
    print("=== T38 phase check (max|level| == 1.0 asserted in check_phase) ===")
    for name, kind, n, nd in C.check_phase(bs):
        print(f"  {name:<11} {kind}  entries={n:2d}  distinct signed values={nd:2d}")
    sym = [(n, lv) for n, kind, lv in bs if kind == "mag"]
    print(f"\nsymmetric books under test: {', '.join(n for n, _ in sym)}")

    allok = True
    print("\n=== A. boundary-exact tensors (the only place the rules differ) ===")
    for name, mags in sym:
        w = boundary_block(mags)
        # NB: quantised with EVERY book, not just its own, so cross-boundary
        # coincidences are covered too.
        allok &= check(f"built on {name} ({tuple(w.shape)})", w, sym)

    print("\n=== B. random normal tensors ===")
    g = torch.Generator().manual_seed(20260812)
    for i, shape in enumerate([(64, K), (37, 4 * K), (129, 8 * K + 7)]):
        w = torch.randn(shape, generator=g, dtype=torch.float32)
        allok &= check(f"randn{shape}", w, sym)
    # heavy tail + exact zeros + a dead block (all zeros -> s clamps)
    w = torch.randn((64, 4 * K), generator=g) * torch.exp(
        torch.randn((64, 4 * K), generator=g) * 3)
    w[0, :] = 0.0
    w[1, ::3] = 0.0
    allok &= check("heavy-tail + zero rows", w.float(), sym)

    print("\n=== C. archived block-normalised samples ===")
    for m in ["smollm2", "qwen", "pythia", "opt"]:
        p = os.path.join(HERE, f"loguniform_x_{m}.npy")
        if not os.path.exists(p):
            continue
        x = np.load(p)[: 512 * K].astype(np.float32).reshape(-1, K)
        allok &= check(f"{m} sample {x.shape}", torch.from_numpy(x), sym)

    # ---- negative control: the test must be able to FAIL ------------------
    # A naive signed bucketize rounds a negative tie toward -inf instead of
    # toward zero. If that rule also agreed, family A would be proving nothing.
    def quant_naive(w, levels):
        lv = torch.tensor(sorted(float(x) for x in levels), dtype=torch.float64)
        n = (w.shape[1] // K) * K
        head = w[:, :n].reshape(-1, K).double()
        s = ns["q_e8m0_t"]((head.abs().amax(dim=1) / lv.abs().max())
                           .clamp(min=1e-30)).clamp(min=1e-30)
        bnd = (lv[:-1] + lv[1:]) / 2
        rec = lv[torch.bucketize(head / s[:, None], bnd)] * s[:, None]
        out = w.clone()
        out[:, :n] = rec.reshape(-1, n).to(w.dtype)
        return out

    print("\n=== NEGATIVE CONTROL (naive tie -> -inf must DIFFER) ===")
    live = True
    for name, mags in sym:
        w = boundary_block(mags)
        lv = torch.tensor(sorted(float(x) for x in mags), dtype=torch.float64)
        bnd = (lv[:-1] + lv[1:]) / 2
        y = w.reshape(-1, K).abs()
        nb = int((y[..., None] == bnd).any(-1).sum())
        d = (quant(w, mags) - quant_naive(w, C.signed_from_magnitudes(mags))
             ).abs().max().item()
        live &= (nb > 0 and d > 0)
        print(f"  {name:<11} exact-boundary entries={nb:5d}  "
              f"max|quant - naive| = {d:.3e}  "
              f"{'DIFFERS (test is live)' if d > 0 else 'VACUOUS'}")

    print(f"\nAGREEMENT: {'PROVEN' if allok else 'FAILED'}"
          f"   NEGATIVE CONTROL: {'LIVE' if live else 'VACUOUS'}")
    return 0 if (allok and live) else 1


if __name__ == "__main__":
    sys.exit(main())
