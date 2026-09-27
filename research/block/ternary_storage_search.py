#!/usr/bin/env python3.12
"""ternary_storage_search -- the run of specs/numeric/ternary_storage_search.t27.

Every number comes from research/block/ternary_storage_params.py, which
conformance/ternary_storage_from_spec.mjs generates from the spec; the spec says
what a pass means and what it does not. This file only executes the protocol:

  0. pins: the params are current, block_tnf.py has the pinned bytes, the model
     and both corpora have the pinned hashes;
  1. block_tnf.py's own functions, executed from its source (not copied), give
     the level tables; each spec table must equal them;
  2. rulers on test (BASE, MXFP4 rule B, TNF4_7 rule B, MXFP4 rule A);
  3. dev (validation): BASE, MXFP4, E2M2 and the three T27 candidates, rule B;
  4. test, once: the dev winner under rule B and rule A, E2M2 under rule B.

    python3.12 research/block/ternary_storage_search.py            first and only run
    python3.12 research/block/ternary_storage_search.py --dry      pins and tables only
    python3.12 research/block/ternary_storage_search.py --retry    allowed once, only
                                                                   if run 1 finished no arm
"""
import ast, hashlib, json, math, os, subprocess, sys, time
from datetime import datetime, timezone
from statistics import NormalDist

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
from ternary_storage_params import SPEC as S, SPEC_SHA256, SPEC_FILE  # noqa: E402

import numpy as np  # noqa: E402
import torch  # noqa: E402
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
    if "--dry" in sys.argv:          # preflight: pins and tables only, no model, no run log
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


def main():
    log_path, retry = open_log()
    torch.set_grad_enabled(False)
    result = {"spec": SPEC_FILE, "spec_sha256": SPEC_SHA256, "log": os.path.relpath(log_path, REPO),
              "retry": retry, "started": utc(), "status": "running", "arms": []}
    say(f"ternary_storage_search: spec {SPEC_FILE} sha256 {SPEC_SHA256[:16]}, log {result['log']}")

    # 0. pins ------------------------------------------------------------------------------
    gen = subprocess.run(["node", "conformance/ternary_storage_from_spec.mjs", "--check"],
                         cwd=REPO, capture_output=True, text=True)
    say("generator --check: " + " | ".join(gen.stdout.strip().splitlines()[-1:]))
    if gen.returncode != 0:
        stop("params drifted from the spec (generator --check failed)", result)
    got = sha256_file(os.path.join(REPO, S["BLOCK_TNF_FILE"]))
    if got != S["BLOCK_TNF_SHA256"]:
        stop(f"{S['BLOCK_TNF_FILE']} sha256 {got}", result)
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
    say("pins: block_tnf.py, model, test and dev text match the spec")

    # 1. level tables from block_tnf's own functions ------------------------------------
    ns, missing = block_tnf_functions()
    if missing:
        stop(f"block_tnf.py lacks {missing}", result)
    fp_levels, tnf_levels, quant = ns["fp_levels"], ns["tnf_levels"], ns["quant"]
    q_e8m0_t, target_modules, perplexity = ns["q_e8m0_t"], ns["target_modules"], ns["perplexity"]

    def same(levels, table):
        top = table[-1]
        return len(levels) == len(table) and all(abs(a * top - b) < 1e-9 for a, b in zip(levels, table))

    e2m1, tnf4, e2m2 = fp_levels(2, 1), tnf_levels(4, 1), fp_levels(2, 2)
    for name, lv in (("E2M1", e2m1), ("TNF4_7", tnf4), ("E2M2", e2m2)):
        if not same(lv, S[name]):
            stop(f"spec table {name} != block_tnf's {[x * S[name][-1] for x in lv]}", result)
    identity = sorted(set(tnf4) | {e2m1[S["E2M1_ONLY"]]}) == e2m1
    say(f"tables: E2M1, TNF4_7, E2M2 equal block_tnf's; TNF4_7 + the 1/12 code == E2M1 as float64: {identity}")
    if not identity:
        stop("TNF4_7 plus one code is not E2M1 bit for bit", result)
    off = S["T27_N_OFFSET_NUM"] / S["T27_N_OFFSET_DEN"]
    q = [NormalDist().inv_cdf(float(p)) for p in np.linspace(0.5, off, S["T27_MAGS"] + 1)[1:]]
    t27n = [0] + [round(S["T27_N"][-1] * x / q[-1]) for x in q]
    if t27n != S["T27_N"]:
        stop(f"T27_N recomputed as {t27n}", result)
    say("tables: T27_N recomputed from NormalDist, equal")
    result["tnf4_plus_one_code_is_e2m1"] = identity
    if "--dry" in sys.argv:
        say("dry run: pins and tables pass; no model loaded, nothing written")
        return

    def levels(name, rule):
        table = [float(x) for x in S[name]]
        return [x / table[-1] for x in table] if rule == "B" else table

    # model and corpora ---------------------------------------------------------------------
    t0 = time.time()
    tok = AutoTokenizer.from_pretrained(mdir)
    model = AutoModelForCausalLM.from_pretrained(mdir, dtype=torch.float32).eval()
    ids = {k: tok(v, return_tensors="pt").input_ids for k, v in texts.items()}
    orig = {n: m.weight.detach().clone() for n, m in target_modules(model)}
    say(f"loaded in {time.time() - t0:.1f} s; torch threads {torch.get_num_threads()}; "
        f"target modules {len(orig)}; windows test {ids['test'].numel() // S['SEQLEN']}, "
        f"dev {ids['dev'].numel() // S['SEQLEN']}")

    kmin, kmax = [10 ** 9], [-10 ** 9]

    def arm(phase, split, name, rule):
        t = time.time()
        if name == "BASE":
            for n, m in target_modules(model):
                m.weight.copy_(orig[n])
            ks = None
        else:
            lv = levels(name, rule)
            top = torch.tensor(sorted(lv), dtype=torch.float64)[-1]
            lo, hi, zero = 10 ** 9, -10 ** 9, 0
            for n, m in target_modules(model):
                w = orig[n]
                m.weight.copy_(quant(w, lv))
                nn_ = (w.shape[1] // S["BLOCK"]) * S["BLOCK"]
                a = w[:, :nn_].reshape(-1, S["BLOCK"]).double().abs().amax(dim=1)
                ok = a > 0
                zero += int((~ok).sum())
                k = torch.log2(q_e8m0_t((a[ok] / top).clamp(min=1e-30))).round().long()
                lo, hi = min(lo, int(k.min())), max(hi, int(k.max()))
            kmin[0], kmax[0] = min(kmin[0], lo), max(kmax[0], hi)
            ks = [lo, hi, zero]
        p = perplexity(model, ids[split], S["NWIN"])
        row = {"phase": phase, "split": split, "arm": name, "rule": rule, "ppl": p,
               "ppl_e4": round(p * 1e4), "scale_k_min_max_zero_blocks": ks,
               "seconds": round(time.time() - t, 1), "at": utc()}
        result["arms"].append(row)
        write_json(result)
        say(f"ARM {phase:5s} {split:4s} {name:7s} rule {rule or '-'}  ppl {p:.4f}  "
            f"k {ks}  {row['seconds']} s")
        return p

    # 2. rulers -----------------------------------------------------------------------------
    tol = S["RULER_TOL_E4"] / 1e4
    rulers = [("BASE", None, S["RULER_BASE_E4"], True), ("E2M1", "B", S["RULER_MXFP4_B_E4"], True),
              ("TNF4_7", "B", S["RULER_TNF4_7_B_E4"], True), ("E2M1", "A", S["RULER_MXFP4_A_E4"], False)]
    got = {}
    rule_a_ok = True
    for name, rule, want, hard in rulers:
        p = arm("ruler", "test", name, rule)
        got[(name, rule)] = p
        miss = abs(p - want / 1e4)
        say(f"ruler {name} {rule or '-'}: {p:.4f} against main {want / 1e4:.4f}, "
            f"|diff| {miss:.4f} {'within' if miss <= tol else 'OUTSIDE'} {tol}")
        if miss > tol:
            if hard:
                stop(f"ruler {name} rule {rule} missed by {miss:.4f}", result)
            rule_a_ok = False
    result["rule_a_reproduced"] = rule_a_ok

    # 3. dev --------------------------------------------------------------------------------
    arm("dev", "dev", "BASE", None)
    dev = {n: arm("dev", "dev", n, "B") for n in ["E2M1", "E2M2"] + S["T27_CANDIDATES"]}
    star = min(S["T27_CANDIDATES"], key=lambda n: (dev[n], S["T27_CANDIDATES"].index(n)))
    result["t27_star"] = star
    say(f"dev choice: T27_STAR = {star} ({dev[star]:.4f}); dev MXFP4 {dev['E2M1']:.4f}, E2M2 {dev['E2M2']:.4f}")

    # 4. test, once -------------------------------------------------------------------------
    t_b = arm("test", "test", star, "B")
    t_a = arm("test", "test", star, "A")
    e2 = arm("test", "test", "E2M2", "B")
    mx = got[("E2M1", "B")]

    win = S["WIN_PCT"] / 100
    claim_b = t_b <= win * mx
    claim_a = t_a <= win * mx
    claim = claim_b and (claim_a or not rule_a_ok)
    pred_e2m2 = e2 <= t_b
    fits = max(abs(kmin[0]), abs(kmax[0])) <= S["T27_SCALE_KMAX"]
    share = (mx - t_b) / (mx - e2) if mx != e2 else float("nan")
    result.update({
        "status": "done", "finished": utc(),
        "test_mxfp4_b": mx, "test_t27_star_b": t_b, "test_t27_star_a": t_a, "test_e2m2_b": e2,
        "claim_rule_b": claim_b, "claim_rule_a": claim_a, "claim": claim,
        "pred_e2m2_at_least_t27": pred_e2m2, "pred_scale_fits": fits,
        "scale_k_range_all_arms": [kmin[0], kmax[0]],
        "gain_share_of_mxfp4_to_e2m2": share, "bit_share": S["BIT_SHARE_E3"] / 1000,
    })
    write_json(result)
    say(f"TEST  MXFP4 B {mx:.4f} | {star} B {t_b:.4f} ({t_b / mx * 100:.1f}%)  "
        f"A {t_a:.4f} ({t_a / mx * 100:.1f}%) | E2M2 B {e2:.4f}")
    say(f"CLAIM (<= {S['WIN_PCT']}% of MXFP4 under B and A): {'HOLDS' if claim else 'DOES NOT HOLD'}"
        f"{'' if rule_a_ok else ' (rule A not reproduced: rule B only, per the spec)'}")
    say(f"PRED_E2M2_AT_LEAST_T27: {'held' if pred_e2m2 else 'FAILED'}; "
        f"PRED_SCALE_FITS (|k| <= {S['T27_SCALE_KMAX']}, seen {kmin[0]}..{kmax[0]}): {'held' if fits else 'FAILED'}")
    say(f"descriptive: {star} takes {share * 100:.1f}% of the MXFP4 -> E2M2 gain for "
        f"{S['BIT_SHARE_E3'] / 10:.1f}% of the extra bit")
    for n, m in target_modules(model):
        m.weight.copy_(orig[n])


if __name__ == "__main__":
    main()
