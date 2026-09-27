#!/usr/bin/env python3.12
"""ternary_storage_search_v2 -- the run of specs/numeric/ternary_storage_search_v2.t27.

Every number comes from research/block/ternary_storage_v2_params.py, which
conformance/ternary_storage_v2_from_spec.mjs generates from the spec; the spec says
what each result means and what it does not. This file only executes the protocol:

  0. pins: the params are current, block_tnf.py has the pinned bytes, the model
     and both corpora have the pinned hashes; torch threads are the spec's;
  1. block_tnf.py's own functions, executed from its source (not copied), give
     the level tables; each spec table must equal them; the NVFP4 and MX+
     quantizers pass their unit checks;
  2. rulers on test (BASE, MXFP4, TNF4_7): this Mac must give the first
     attempt's numbers again, within the spec's tolerance, or the run stops;
  3. dev (validation): MXFP4, NVFP4, MXPLUS, E2M2 and the three T27 candidates;
  4. test, once: the dev-chosen T27, NVFP4, MXPLUS, E2M2; the ladder.

    python3.12 research/block/ternary_storage_search_v2.py          first and only run
    python3.12 research/block/ternary_storage_search_v2.py --dry    pins, tables, unit checks
    python3.12 research/block/ternary_storage_search_v2.py --retry  allowed once, only
                                                                    if run 1 finished no arm
"""
import ast, hashlib, json, math, os, platform, subprocess, sys, time
from datetime import datetime, timezone
from statistics import NormalDist

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
from ternary_storage_v2_params import SPEC as S, SPEC_SHA256, SPEC_FILE  # noqa: E402

import numpy as np  # noqa: E402
import torch  # noqa: E402
import transformers  # noqa: E402
from transformers import AutoModelForCausalLM, AutoTokenizer  # noqa: E402

LOG = os.path.join(REPO, S["RESULT_JSON"]).replace(".json", ".log")
RETRY_LOG = LOG.replace(".log", ".retry.log")
_log = None


def utc():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def say(msg):
    line = f"{utc()} {msg}"
    print(line, flush=True)
    _log.write(line + "\n")
    _log.flush()


def stop(msg, result):
    say(f"STOP: {msg}")
    result["status"] = "stopped"
    result["stop_reason"] = msg
    write_json(result)
    sys.exit(1)


def write_json(result):
    if "--dry" in sys.argv:
        return
    with open(os.path.join(REPO, S["RESULT_JSON"]), "w") as f:
        json.dump(result, f, indent=1, sort_keys=True)
        f.write("\n")


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def open_log():
    global _log
    if "--dry" in sys.argv:          # preflight: no model, no run log, no json
        _log = open(os.devnull, "w")
        return "(dry)", False
    retry = "--retry" in sys.argv
    if not retry:
        if os.path.exists(LOG):
            sys.exit(f"{LOG} exists: this search runs once. See the spec's protocol.")
        path = LOG
    else:
        if not os.path.exists(LOG):
            sys.exit("--retry without a first run")
        if os.path.exists(RETRY_LOG):
            sys.exit("the one retry is used")
        if "ARM " in open(LOG).read():
            sys.exit("run 1 finished an arm: no retry allowed")
        path = RETRY_LOG
    _log = open(path, "x")
    return path, retry


def block_tnf_functions():
    """Execute block_tnf.py's own definitions of the pinned functions, nothing else of it."""
    path = os.path.join(REPO, S["BLOCK_TNF_FILE"])
    tree = ast.parse(open(path).read(), path)
    ns = {"os": os, "sys": sys, "math": math, "np": np, "torch": torch,
          "K": S["BLOCK"], "SEQLEN": S["SEQLEN"]}
    found = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in S["BLOCK_TNF_FUNCS"]:
            exec(compile(ast.Module([node], []), path, "exec"), ns)
            found.append(node.name)
    missing = sorted(set(S["BLOCK_TNF_FUNCS"]) - set(found))
    return ns, missing


# --- the two new formats ------------------------------------------------------------------
# Element rounding everywhere: nearest level, a tie to the smaller magnitude (bucketize on the
# midpoints, right=False), the rule block_tnf.quant uses. The tail columns are left as they are.

E2M1_V = torch.tensor([x / 2 for x in S["E2M1"]], dtype=torch.float64)
E2M1_MID = (E2M1_V[:-1] + E2M1_V[1:]) / 2
BM_V = torch.tensor([x / 2 for x in S["MXP_BM_HALF"]], dtype=torch.float64)
BM_MID = (BM_V[:-1] + BM_V[1:]) / 2


def nvfp4(w, parts=None):
    """E2M1 per 16, E4M3 block scale, FP32 per-tensor scale g = 448 * 6 / amax(tensor)."""
    nb = S["NV_BLOCK"]
    n = (w.shape[1] // nb) * nb
    if n == 0:
        return w
    head = w[:, :n].reshape(-1, nb).double()
    amax_t = head.abs().max()
    if amax_t == 0:
        return w.clone()
    g = (torch.tensor(float(S["NV_G_NUM"]), dtype=torch.float32) / amax_t.float()).double()
    want = (head.abs().amax(dim=1) / (S["E2M1_MAX_HALF"] / 2) * g).clamp(max=S["E4M3_MAX"])
    sb = want.float().to(torch.float8_e4m3fn).double()          # round to nearest even
    dec = sb / g
    ok = sb > 0
    y = torch.zeros_like(head)
    y[ok] = head[ok].abs() / dec[ok, None]
    q = E2M1_V[torch.bucketize(y, E2M1_MID)]
    rec = torch.where(ok[:, None], torch.sign(head) * q * dec[:, None], torch.zeros_like(head))
    if parts is not None:
        parts.update(g=g, sb=sb, q=q, ok=ok)
    out = w.clone()
    out[:, :n] = rec.reshape(-1, n).to(w.dtype)
    return out


def mxplus(w, parts=None):
    """MX+ over MXFP4 (arXiv 2510.14557, re-implemented from its description): OCP scale per 32;
    the block's largest element gets 3 mantissa bits at the top exponent; the rest are E2M1."""
    k = S["BLOCK"]
    n = (w.shape[1] // k) * k
    if n == 0:
        return w
    head = w[:, :n].reshape(-1, k).double()
    a = head.abs()
    amax, bm = a.max(dim=1)                                      # first index on a tie
    ok = amax > 0
    e = torch.zeros_like(amax)
    e[ok] = torch.floor(torch.log2(amax[ok])) - S["MXP_EMAX"]
    x = torch.pow(2.0, e)
    y = a / x[:, None]
    q = E2M1_V[torch.bucketize(y, E2M1_MID)]
    rows = torch.arange(head.shape[0])
    qbm = BM_V[torch.bucketize(y[rows, bm], BM_MID)]
    q[rows, bm] = qbm
    rec = torch.where(ok[:, None], torch.sign(head) * q * x[:, None], torch.zeros_like(head))
    if parts is not None:
        parts.update(x=x, q=q, bm=bm, ok=ok, y=y)
    out = w.clone()
    out[:, :n] = rec.reshape(-1, n).to(w.dtype)
    return out


def unit_checks():
    """Hand-worked cases and grid properties; returns a list of failures."""
    bad = []
    # NVFP4 by hand: amax(tensor) = 6 -> g = 448; a block with amax 6 -> scale 448 -> decode 1.
    w = torch.zeros(1, 16, dtype=torch.float32)
    w[0, :4] = torch.tensor([6.0, 2.7, 2.5, -0.3])
    got = nvfp4(w)[0, :4].tolist()
    if got != [6.0, 3.0, 2.0, -0.5]:
        bad.append(f"nvfp4 hand case {got} != [6, 3, 2 (tie down), -0.5]")
    # MX+ by hand: amax 5 -> X = 2^(2 - 2) = 1; BM 5 on the 4..7.5 grid; 1.2 -> 1; 7 (not BM) -> 6.
    w = torch.zeros(1, 32, dtype=torch.float32)
    w[0, :3] = torch.tensor([1.2, -5.0, 0.26])
    got = mxplus(w)[0, :3].tolist()
    if got != [1.0, -5.0, 0.5]:
        bad.append(f"mxplus hand case {got} != [1, -5, 0.5]")
    w = torch.zeros(1, 32, dtype=torch.float32)
    w[0, :3] = torch.tensor([7.9, 7.0, 6.9])
    got = mxplus(w)[0, :3].tolist()
    if got != [7.5, 6.0, 6.0]:
        bad.append(f"mxplus saturation case {got} != [7.5, 6, 6]")
    # properties on random weights with a heavy tail
    g = torch.Generator().manual_seed(7213)
    w = (torch.randn(64, 576, generator=g) * torch.exp(torch.randn(64, 576, generator=g))).float()
    p = {}
    nvfp4(w, p)
    sb = p["sb"]
    if not torch.equal(sb.float().to(torch.float8_e4m3fn).double(), sb):
        bad.append("nvfp4: a block scale is not an exact E4M3 value")
    if float(sb.max()) > S["E4M3_MAX"] or float(sb.min()) < 0:
        bad.append("nvfp4: a block scale is outside [0, 448]")
    if not bool(torch.isin(p["q"], E2M1_V).all()):
        bad.append("nvfp4: an element is off the E2M1 grid")
    if abs(float(p["g"]) * float(w.abs().max()) - S["NV_G_NUM"]) > 1e-3:
        bad.append("nvfp4: g * amax(tensor) != 2688")
    p = {}
    mxplus(w, p)
    q, bm = p["q"], p["bm"]
    rows = torch.arange(q.shape[0])
    if not bool(torch.isin(q[rows, bm], BM_V).all()):
        bad.append("mxplus: a block-max element is off the 4..7.5 grid")
    mask = torch.ones_like(q, dtype=torch.bool)
    mask[rows, bm] = False
    if not bool(torch.isin(q[mask], E2M1_V).all()):
        bad.append("mxplus: a non-block-max element is off the E2M1 grid")
    ybm = p["y"][rows, bm]
    if not bool(((ybm >= 4) & (ybm < 8)).all()):
        bad.append("mxplus: the block max does not sit in [4, 8) of its scale")
    if not torch.equal(torch.log2(p["x"]), torch.round(torch.log2(p["x"]))):
        bad.append("mxplus: a scale is not a power of two")
    return bad


def main():
    log_path, retry = open_log()
    torch.set_grad_enabled(False)
    torch.set_num_threads(S["TORCH_THREADS"])
    versions = {"python": platform.python_version(), "torch": torch.__version__,
                "transformers": transformers.__version__, "numpy": np.__version__}
    result = {"spec": SPEC_FILE, "spec_sha256": SPEC_SHA256, "log": os.path.relpath(log_path, REPO)
              if log_path != "(dry)" else log_path, "retry": retry, "started": utc(),
              "status": "running", "versions": versions, "arms": []}
    say(f"ternary_storage_search_v2: spec {SPEC_FILE} sha256 {SPEC_SHA256[:16]}, log {result['log']}")
    say(f"versions {versions}; torch threads {torch.get_num_threads()}")
    if torch.get_num_threads() != S["TORCH_THREADS"]:
        stop(f"torch threads {torch.get_num_threads()} != {S['TORCH_THREADS']}", result)

    # 0. pins ------------------------------------------------------------------------------
    gen = subprocess.run(["node", "conformance/ternary_storage_v2_from_spec.mjs", "--check"],
                         cwd=REPO, capture_output=True, text=True)
    say("generator --check: " + " | ".join(gen.stdout.strip().splitlines()[-1:]))
    if gen.returncode != 0:
        stop("params drifted from the spec (generator --check failed)", result)
    got = sha256_file(os.path.join(REPO, S["BLOCK_TNF_FILE"]))
    if got != S["BLOCK_TNF_SHA256"]:
        stop(f"{S['BLOCK_TNF_FILE']} sha256 {got}", result)
    got = sha256_file(os.path.join(REPO, S["V1_LOG"]))
    if got != S["V1_LOG_SHA256"]:
        stop(f"{S['V1_LOG']} sha256 {got}", result)
    cache = os.path.expanduser(S["CACHE_DIR"])
    mdir = os.path.join(cache, S["MODEL_DIR"])
    got = sha256_file(os.path.join(mdir, "model.safetensors"))
    if got != S["MODEL_SHA256"]:
        stop(f"model sha256 {got}", result)
    texts = {}
    for split, name, want in (("test", S["TEST_JSON"], S["TEST_TEXT_SHA256"]),
                              ("dev", S["DEV_JSON"], S["DEV_TEXT_SHA256"])):
        t = "\n\n".join(json.load(open(os.path.join(cache, name))))
        got = hashlib.sha256(t.encode()).hexdigest()
        if got != want:
            stop(f"{split} text sha256 {got}", result)
        texts[split] = t
    say("pins: block_tnf.py, the first attempt's log, model, test and dev text match the spec")

    # 1. tables and unit checks ---------------------------------------------------------
    ns, missing = block_tnf_functions()
    if missing:
        stop(f"block_tnf.py lacks {missing}", result)
    fp_levels, tnf_levels, quant = ns["fp_levels"], ns["tnf_levels"], ns["quant"]
    q_e8m0_t, target_modules, perplexity = ns["q_e8m0_t"], ns["target_modules"], ns["perplexity"]

    def same(levels, table):
        top = table[-1]
        return len(levels) == len(table) and all(abs(a * top - b) < 1e-9 for a, b in zip(levels, table))

    for name, lv in (("E2M1", fp_levels(2, 1)), ("TNF4_7", tnf_levels(4, 1)), ("E2M2", fp_levels(2, 2))):
        if not same(lv, S[name]):
            stop(f"spec table {name} != block_tnf's {[x * S[name][-1] for x in lv]}", result)
    off = S["T27_N_OFFSET_NUM"] / S["T27_N_OFFSET_DEN"]
    qn = [NormalDist().inv_cdf(float(p)) for p in np.linspace(0.5, off, S["T27_MAGS"] + 1)[1:]]
    if [0] + [round(S["T27_N"][-1] * x / qn[-1]) for x in qn] != S["T27_N"]:
        stop("T27_N does not recompute from NormalDist", result)
    say("tables: E2M1, TNF4_7, E2M2 equal block_tnf's; T27_N recomputed, equal")
    bad = unit_checks()
    if bad:
        stop("unit checks: " + "; ".join(bad), result)
    say("unit checks: NVFP4 and MX+ hand cases and grid properties pass")
    if "--dry" in sys.argv:
        say("dry run: pins, tables and unit checks pass; no model loaded, nothing written")
        return

    def levels(name):                                            # rule B: top level is 1
        table = [float(x) for x in S[name]]
        return [x / table[-1] for x in table]

    # model and corpora ---------------------------------------------------------------------
    t0 = time.time()
    tok = AutoTokenizer.from_pretrained(mdir)
    model = AutoModelForCausalLM.from_pretrained(mdir, dtype=torch.float32).eval()
    ids = {k: tok(v, return_tensors="pt").input_ids for k, v in texts.items()}
    orig = {n: m.weight.detach().clone() for n, m in target_modules(model)}
    tails = sum(int(w.shape[1] % S["BLOCK"] != 0) for w in orig.values())
    say(f"loaded in {time.time() - t0:.1f} s; target modules {len(orig)} ({tails} with tail columns); "
        f"windows test {ids['test'].numel() // S['SEQLEN']}, dev {ids['dev'].numel() // S['SEQLEN']}")

    t27_k = [10 ** 9, -10 ** 9]

    def arm(phase, split, name):
        t = time.time()
        ks = None
        if name == "BASE":
            for n, m in target_modules(model):
                m.weight.copy_(orig[n])
        elif name == "NVFP4":
            for n, m in target_modules(model):
                m.weight.copy_(nvfp4(orig[n]))
        elif name == "MXPLUS":
            for n, m in target_modules(model):
                m.weight.copy_(mxplus(orig[n]))
        else:
            lv = levels(name)
            lo, hi, zero = 10 ** 9, -10 ** 9, 0
            for n, m in target_modules(model):
                w = orig[n]
                m.weight.copy_(quant(w, lv))
                nn_ = (w.shape[1] // S["BLOCK"]) * S["BLOCK"]
                a = w[:, :nn_].reshape(-1, S["BLOCK"]).double().abs().amax(dim=1)
                ok = a > 0
                zero += int((~ok).sum())
                k = torch.log2(q_e8m0_t(a[ok].clamp(min=1e-30))).round().long()
                lo, hi = min(lo, int(k.min())), max(hi, int(k.max()))
            ks = [lo, hi, zero]
            if name in S["T27_CANDIDATES"]:
                t27_k[0], t27_k[1] = min(t27_k[0], lo), max(t27_k[1], hi)
        p = perplexity(model, ids[split], S["NWIN"])
        row = {"phase": phase, "split": split, "arm": name, "ppl": p, "ppl_e4": round(p * 1e4),
               "scale_k_min_max_zero_blocks": ks, "seconds": round(time.time() - t, 1), "at": utc()}
        result["arms"].append(row)
        write_json(result)
        say(f"ARM {phase:5s} {split:4s} {name:7s} ppl {p:.4f}  k {ks}  {row['seconds']} s")
        return p

    # 2. rulers -----------------------------------------------------------------------------
    tol = S["RULER_TOL_E4"] / 1e4
    rul = {}
    for name, key in (("BASE", "RULER_BASE_E4"), ("E2M1", "RULER_MXFP4_B_E4"), ("TNF4_7", "RULER_TNF4_7_B_E4")):
        p = arm("ruler", "test", name)
        rul[name] = p
        miss = abs(p - S[key] / 1e4)
        say(f"ruler {name}: {p:.4f} against the first attempt's {S[key] / 1e4:.4f} on this Mac, "
            f"|diff| {miss:.4f} {'within' if miss <= tol else 'OUTSIDE'} {tol}")
        if miss > tol:
            stop(f"ruler {name} missed by {miss:.4f}", result)
    result["rulers_reproduced"] = True

    # 3. dev --------------------------------------------------------------------------------
    dev = {n: arm("dev", "dev", n) for n in ["E2M1", "NVFP4", "MXPLUS", "E2M2"] + S["T27_CANDIDATES"]}
    star = min(S["T27_CANDIDATES"], key=lambda n: (dev[n], S["T27_CANDIDATES"].index(n)))
    result["t27_star"] = star
    say(f"dev choice: T27_STAR = {star} ({dev[star]:.4f}); dev MXFP4 {dev['E2M1']:.4f}, "
        f"NVFP4 {dev['NVFP4']:.4f}, MXPLUS {dev['MXPLUS']:.4f}, E2M2 {dev['E2M2']:.4f}")

    # 4. test, once -------------------------------------------------------------------------
    test = {"T27_STAR": arm("test", "test", star)}
    for n in ("NVFP4", "MXPLUS", "E2M2"):
        test[n] = arm("test", "test", n)
    test["MXFP4"] = rul["E2M1"]

    def ladder(t27, c, cname):
        r = 1000 * t27 / c
        if r <= S["BEAT_PERMILLE"]:
            return "T27 better", r
        if r <= S["TIE_PERMILLE"]:
            return "tie", r
        return f"{cname} better", r

    dev_as = {"NVFP4": "NVFP4", "MXPLUS": "MXPLUS", "MXFP4": "E2M1"}
    verdicts = {}
    for c in S["LADDER_COMPARATORS"]:
        v, r = ladder(test["T27_STAR"], test[c], c)
        dv, dr = ladder(dev[star], dev[dev_as[c]], c)
        trits = {"NVFP4": S["TRITS_NVFP4"], "MXPLUS": S["TRITS_MXPLUS"], "MXFP4": S["TRITS_MXFP4"]}[c]
        verdicts[c] = {"test": v, "test_permille": r, "dev": dv, "dev_permille": dr,
                       "trits_t27": S["TRITS_T27"], "trits_c": trits}
        say(f"LADDER vs {c:6s} test {test['T27_STAR']:.4f} / {test[c]:.4f} = {r:.1f} permille -> {v}"
            f"   (dev {dr:.1f} -> {dv}; per 32 weights {S['TRITS_T27']} trits against {trits})")
    fits = max(abs(t27_k[0]), abs(t27_k[1])) <= S["T27_SCALE_KMAX"]
    preds = {"PRED_NVFP4_BEATS_MXFP4": test["NVFP4"] < test["MXFP4"],
             "PRED_E2M2_AT_LEAST_T27": test["E2M2"] <= test["T27_STAR"],
             "PRED_SCALE_FITS": fits,
             "GUESS_T27_VS_NVFP4": verdicts["NVFP4"]["test"] == S["GUESS_T27_VS_NVFP4"]}
    result.update({"status": "done", "finished": utc(), "test": test, "dev": dev,
                   "verdicts": verdicts, "primary": S["PRIMARY"],
                   "primary_verdict": verdicts[S["PRIMARY"]]["test"], "predictions": preds,
                   "t27_scale_k_range": t27_k})
    write_json(result)
    say(f"PRIMARY ({S['PRIMARY']}): {verdicts[S['PRIMARY']]['test']}")
    for k, v in preds.items():
        say(f"{k}: {'held' if v else 'FAILED'}")
    say(f"T27 scale exponents seen {t27_k[0]}..{t27_k[1]} (5 trits hold |k| <= {S['T27_SCALE_KMAX']})")
    for n, m in target_modules(model):
        m.weight.copy_(orig[n])


if __name__ == "__main__":
    main()
