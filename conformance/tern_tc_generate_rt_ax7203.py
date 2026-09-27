#!/usr/bin/env python3
"""igla-coder's 8-token generation on the AX7203 node, with lost answers asked for again.

Pre-registered in specs/trinet/tern_tc_retransmit_ax7203.t27; every number comes from the generated
tern_tc_retransmit_params.py. This is a new claim with its own record (TERN_TC_RETRANSMIT.md). The
generation run it builds on, tern_tc_generate_ax7203.py, stays FAIL in TERN_TC_GENERATE.md and is
imported here unchanged: its model loader, forward pass, job builder (BoardDots) and CPU preflight
are the ones pinned by sha256 in both specs.

One thing differs. BoardDots sends each call's jobs with the layer harness's run(), which stops at
the first lost byte. For the length of this run, that one function is replaced by
tern_tc_retransmit.run(), which makes the same checks on every answer and asks again for an answer
that did not arrive or did not verify. Everything the run cannot verify stays a failure: a lie, a
second answer, another node id, a bad status, a job past its attempts, a spent ceiling.

    python3 tern_tc_generate_rt_ax7203.py --self-test
    python3 tern_tc_generate_rt_ax7203.py --refcell    # the full run, reference cell behind the RTL
                                                        # frame parser, pre-registered losses; ~10 min
    python3 tern_tc_generate_rt_ax7203.py --setkey --port /dev/cu.usbserial-110 --keys ../trinet-keys.txt

Author: Dmitrii Vasilev (@gHashTag)
"""
import argparse
import contextlib
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import tern_tc_generate_ax7203 as g  # noqa: E402
import tern_tc_layer_ax7203 as h  # noqa: E402
import tern_tc_retransmit as rt  # noqa: E402


def pins_ok(S, spec_file, spec_sha, log=print):
    ok = True
    for rel, want in ((spec_file, spec_sha),
                      (S["GENERATE_SPEC_FILE"], S["GENERATE_SPEC_SHA256"]),
                      (S["GENERATE_PARAMS_FILE"], S["GENERATE_PARAMS_SHA256"]),
                      (S["GENERATE_RUNNER_FILE"], S["GENERATE_RUNNER_SHA256"]),
                      (S["HARNESS_FILE"], S["HARNESS_SHA256"]),
                      (S["NODE_RTL_FILE"], S["NODE_RTL_SHA256"]),
                      (S["PROTOCOL_FILE"], S["PROTOCOL_SHA256"])):
        got = g.sha256_file(rel)
        if got != want:
            log(f"PIN MISMATCH {rel}: {got[:16]} != {want[:16]}; nothing run")
            ok = False
    return ok


def budget_of(S, keep_events=64):
    return rt.Budget(S["RETRY_BASE"], S["MAX_ATTEMPTS"], S["MAX_RETRANSMITS"], S["MAX_RESYNCS"],
                     S["FLUSH_BYTES"], keep_events=keep_events)


@contextlib.contextmanager
def retransmitting(budget, limit_s, log=print):
    """For the length of the block, BoardDots's h.run() is tern_tc_retransmit.run()."""
    orig = h.run
    t0 = time.monotonic()

    def run(link, jobs, rows_ref, key, window):
        if time.monotonic() - t0 > limit_s:
            raise g.Abort(f"over the pre-registered limit of {limit_s} s")
        # BoardDots sets h.FIRST_JOB_NONCE before each call; the call's first attempts start there
        return rt.run(link, jobs, rows_ref, key, window, h.FIRST_JOB_NONCE, budget, log=log)

    h.run = run
    try:
        yield
    finally:
        h.run = orig


def lossy_cell(S, cell=None):
    """The rehearsal link: the reference cell behind the RTL parser, with the scheduled losses."""
    cell = cell or rt.HuntingCell(key=h.TEST_KEY)
    return rt.RxLoss(rt.TxLoss(cell, S["TX_DROP_AT"]), list(zip(S["RX_HOLE_AT"], S["RX_HOLE_LEN"])))


def self_test(S, GS, model):
    ok = True

    def check(cond, msg):
        nonlocal ok
        print(f"  [{'ok ' if cond else 'FAIL'}] {msg}")
        ok &= bool(cond)

    check(g.pins_ok(GS, S["GENERATE_SPEC_FILE"], S["GENERATE_SPEC_SHA256"], log=lambda s: print("  " + s)),
          "the generation run's pins hold (runner, harness, model, tc_infer.c)")
    print("  tern_tc_retransmit.self_test with the spec's constants:")
    t0 = time.time()
    check(rt.self_test(retry_base=S["RETRY_BASE"], max_attempts=S["MAX_ATTEMPTS"],
                       max_retransmits=S["MAX_RETRANSMITS"], max_resyncs=S["MAX_RESYNCS"],
                       flush_bytes=S["FLUSH_BYTES"]),
          f"protocol self-test ({time.time() - t0:.1f} s)")
    check(h.run.__module__ == "tern_tc_layer_ax7203", "h.run is the harness's own outside a run")

    # One real call through BoardDots (layer 0 q/k/v of token 0), as the generation self-test does,
    # now over links that lose bytes.
    ly = model.layers[0]
    xn = g.rms_norm(model.embed[GS["START_TOKEN"]].astype(g.F32), ly["norm1"])
    q, _s = g.quantize(xn)
    groups = [("L0/wq", ly["wq"], q), ("L0/wk", ly["wk"], q), ("L0/wv", ly["wv"], q)]
    want = g.CpuDots().dots(groups, "")
    R = S["RESP_LEN"]
    links = [
        ("clean link", rt.HuntingCell(key=h.TEST_KEY), 0),
        ("the generation hole at answer 1000", rt.RxLoss(rt.HuntingCell(key=h.TEST_KEY), [(1000 * R + 1, 56)]), 3),
        ("a lost w byte in request 2000", rt.TxLoss(rt.HuntingCell(key=h.TEST_KEY), [2000 * S["REQ_LEN"] + 10]), 1),
        ("the call's last answer lost", None, 1),
    ]
    for what, link, min_rt in links:
        b = budget_of(S)
        quiet = []
        if link is None:
            probe = g.BoardDots(model, rt.HuntingCell(key=h.TEST_KEY), h.TEST_KEY, S["WINDOW"],
                                S["FIRST_JOB_NONCE"], bool(GS["SKIP_ZERO_X_CHUNKS"]), log=quiet.append)
            with retransmitting(budget_of(S), S["LIMIT_S"], log=quiet.append):
                probe.dots(groups, "probe")
            n_jobs = probe.tot["jobs"]
            link = rt.RxLoss(rt.HuntingCell(key=h.TEST_KEY), [((n_jobs - 1) * R, R)])
        bd = g.BoardDots(model, link, h.TEST_KEY, S["WINDOW"], S["FIRST_JOB_NONCE"],
                         bool(GS["SKIP_ZERO_X_CHUNKS"]), log=quiet.append)
        with retransmitting(b, S["LIMIT_S"], log=quiet.append):
            got = bd.dots(groups, "L0/qkv")
        same = all(np.array_equal(x, y) for x, y in zip(got, want))
        check(same and bd.tot["accepted"] == bd.tot["jobs"] and b.retransmits >= min_rt
              and (min_rt > 0 or b.retransmits == 0),
              f"BoardDots, {what}: {bd.tot['accepted']}/{bd.tot['jobs']} receipts, "
              f"{bd.tot['exact']}/{bd.tot['rows']} rows, {b.retransmits} retransmitted, "
              f"{b.resyncs} resyncs; sums equal the CPU's")
    check(h.run.__module__ == "tern_tc_layer_ax7203", "h.run restored after the runs")

    small = groups[1:2]                                     # wk: 64 rows
    for fault in ("lie", "impersonate", "wrong_key"):
        link = rt.RxLoss(rt.HuntingCell(key=h.TEST_KEY, fault=fault, fault_at=1000), [(500 * R + 3, 40)])
        bf = g.BoardDots(model, link, h.TEST_KEY, S["WINDOW"], S["FIRST_JOB_NONCE"], True, log=lambda s: None)
        try:
            with retransmitting(budget_of(S), S["LIMIT_S"], log=lambda s: None):
                bf.dots(small, "fault")
            check(False, f"fault '{fault}' at job 1000 behind a hole at answer 500 was not caught")
        except g.Abort as e:
            check(True, f"fault '{fault}' at job 1000, behind a hole at answer 500, stops the run ({str(e)[:50]})")
    try:
        with retransmitting(budget_of(S), -1.0, log=lambda s: None):
            g.BoardDots(model, rt.HuntingCell(key=h.TEST_KEY), h.TEST_KEY, S["WINDOW"], S["FIRST_JOB_NONCE"],
                        True, log=lambda s: None).dots(small, "late")
        check(False, "a call after the time limit was not refused")
    except g.Abort as e:
        check("limit" in str(e), "a call after the time limit is refused")
    return ok


def main():
    from tern_tc_retransmit_params import SPEC as S, SPEC_FILE, SPEC_SHA256
    from tern_tc_generate_params import SPEC as GS
    a = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    a.add_argument("--self-test", action="store_true")
    a.add_argument("--refcell", action="store_true",
                   help="the full run against the reference cell with the pre-registered losses (rehearsal)")
    a.add_argument("--port", default="/dev/cu.usbserial-110")
    a.add_argument("--keys", default="../trinet-keys.txt")
    a.add_argument("--node", default="node0")
    a.add_argument("--setkey", action="store_true")
    args = a.parse_args()
    if not pins_ok(S, SPEC_FILE, SPEC_SHA256):
        return 2
    print(f"spec {SPEC_FILE} sha256 {SPEC_SHA256[:16]}; protocol {S['PROTOCOL_SHA256'][:16]}, "
          f"harness {S['HARNESS_SHA256'][:16]}, node RTL {S['NODE_RTL_SHA256'][:16]} (pins checked)")
    model = g.TC02(GS["MODEL"])
    print(f"model {GS['MODEL']}: {model.n_layer} layers, d {model.d}, ff {model.ff}, vocab {model.vocab}")
    if args.self_test:
        ok = self_test(S, GS, model)
        print(f"self-test tern_tc_generate_rt_ax7203: {'PASS' if ok else 'FAIL'}")
        return 0 if ok else 1
    if not g.pins_ok(GS, S["GENERATE_SPEC_FILE"], S["GENERATE_SPEC_SHA256"]):
        return 2
    if not g.preflight(GS, model):
        print("the CPU path no longer matches the pre-registration; nothing sent to the board")
        return 2
    if args.refcell:
        key, link = h.TEST_KEY, lossy_cell(S)
        what = "reference-cell receipts "           # a Python model of the node, not the board
        print(f"rehearsal losses: answer stream {list(zip(S['RX_HOLE_AT'], S['RX_HOLE_LEN']))}, "
              f"request stream {S['TX_DROP_AT']}")
    else:
        key = h.load_key(args.keys, args.node)
        link = h.SerialLink(args.port, S["BAUD"])
        if args.setkey and h.install_key(link, key) is None:
            print("setkey failed before the first job (a retry is allowed once, both logs kept)")
            return 3
        what = "receipts verified (tag) "
    budget = budget_of(S)
    board = g.BoardDots(model, link, key, S["WINDOW"], S["FIRST_JOB_NONCE"], bool(GS["SKIP_ZERO_X_CHUNKS"]))
    t0 = time.time()
    try:
        with retransmitting(budget, S["LIMIT_S"]):
            ids = g.Generator(model, board, "int").greedy(GS["START_TOKEN"], S["N_TOKENS"], GS["STOP_TOKEN"])
        err = None
    except g.Abort as e:
        ids, err = None, str(e)
    el = time.time() - t0
    t = board.tot
    print("-" * 66)
    print(f"calls                   : {t['calls']} of {GS['CALLS_EXPECTED']} (4 per layer per token)")
    print(f"jobs                    : {t['jobs']} of {S['JOBS_EXPECTED']} "
          f"(+ {t['skipped']} chunks skipped: activation digit plane all zero)")
    print(f"requests written        : {t['jobs'] + budget.retransmits} "
          f"({budget.retransmits} of them retransmits under nonces from {S['RETRY_BASE']:#x})")
    print(f"{what}: {t['accepted']}/{t['jobs']}"
          + (f" under node {board.node:#010x}" if board.node is not None else ""))
    print(f"rows bit-exact          : {t['exact']}/{t['rows']}  (int8 activations from the model's own forward pass)")
    print(f"transport               : {budget.summary()}")
    for e in budget.events:
        print(f"  event  {e}")
    print(f"elapsed                 : {el:.1f} s of {S['LIMIT_S']} "
          f"({t['accepted'] / max(t['seconds'], 1e-9):.0f} answers/s in run())")
    print(f"longest host pause      : {1000 * t['max_pause']:.1f} ms")
    print("-" * 66)
    if err:
        print(f"RESULT: FAIL - {err}. No token from this run is cited.")
        return 1
    print("ids " + ("refcell" if args.refcell else "board  ") + ": " + " ".join(map(str, ids)))
    print("CPU_INT_IDS: " + " ".join(map(str, GS["CPU_INT_IDS"])))
    full = (ids == GS["CPU_INT_IDS"] and t["accepted"] == t["jobs"] == S["JOBS_EXPECTED"]
            and t["exact"] == t["rows"] == GS["ROWS_EXPECTED"] and el <= S["LIMIT_S"]
            and budget.retransmits <= S["MAX_RETRANSMITS"] and budget.resyncs <= S["MAX_RESYNCS"])
    if full and args.refcell:
        losses_ok = budget.retransmits >= S["REHEARSAL_LOSSES"] and budget.resyncs >= 1
        if losses_ok:
            print(f"RESULT: REHEARSAL OK - {len(ids)} tokens through the reference cell with "
                  f"{S['REHEARSAL_LOSSES']} scheduled losses recovered; the board was not used.")
            return 0
        print("RESULT: FAIL - the scheduled losses were not all seen as losses (fewer retransmits or no resync).")
        return 1
    if full:
        print(f"RESULT: PASS - {len(ids)} tokens generated with every ternary dot product computed on the")
        print("        AX7203 and every credited receipt verified under the key; ids equal the CPU integer")
        print(f"        path; {budget.retransmits} jobs asked again, {budget.resyncs} resyncs.")
        return 0
    print("RESULT: FAIL - ids, counts, ceilings or time differ from the pre-registration.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
