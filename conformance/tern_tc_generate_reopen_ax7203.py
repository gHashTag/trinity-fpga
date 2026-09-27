#!/usr/bin/env python3
"""igla-coder's 8-token generation on the AX7203 node, with retransmits and a port reopened on a stop.

Pre-registered in specs/trinet/tern_tc_reopen_ax7203.t27; every number comes from the generated
tern_tc_reopen_params.py. This is a new claim with its own record (TERN_TC_REOPEN.md). The retransmit
run it builds on stays FAIL in TERN_TC_RETRANSMIT.md; its runner, tern_tc_generate_rt_ax7203.py, is
imported unchanged for the parts that do not change (retransmitting(), lossy_cell()), and so are the
generation runner, the harness and the protocol. All of them are pinned by sha256.

One thing differs from the retransmit run: the link. On the board it is tern_tc_reopen.serial_link(),
the harness's SerialLink behind ReopenLink, which closes the port and opens it again when a resync
meets a silent line. In the rehearsal it is ReopenLink over a Stall around the retransmit run's lossy
reference cell, with the two stalls the spec schedules.

    python3 tern_tc_generate_reopen_ax7203.py --self-test
    python3 tern_tc_generate_reopen_ax7203.py --refcell    # the full run, reference cell behind the RTL
                                                          # frame parser, losses and stalls; ~10 min
    python3 tern_tc_generate_reopen_ax7203.py --setkey --port /dev/cu.usbserial-110 --keys ../trinet-keys.txt

Author: Dmitrii Vasilev (@gHashTag)
"""
import argparse
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import tern_tc_generate_ax7203 as g  # noqa: E402
import tern_tc_generate_rt_ax7203 as grt  # noqa: E402
import tern_tc_layer_ax7203 as h  # noqa: E402
import tern_tc_reopen as ro  # noqa: E402
import tern_tc_retransmit as rt  # noqa: E402

PINNED = ("GENERATE_SPEC", "GENERATE_PARAMS", "GENERATE_RUNNER", "HARNESS", "NODE_RTL", "PROTOCOL",
          "RT_SPEC", "RT_PARAMS", "RT_RUNNER", "REOPEN")


def pins_ok(S, spec_file, spec_sha, log=print):
    ok = True
    for rel, want in [(spec_file, spec_sha)] + [(S[k + "_FILE"], S[k + "_SHA256"]) for k in PINNED]:
        got = g.sha256_file(rel)
        if got != want:
            log(f"PIN MISMATCH {rel}: {got[:16]} != {want[:16]}; nothing run")
            ok = False
    return ok


def rehearsal_link(S, log=print):
    """ReopenLink over a Stall around the retransmit run's lossy reference cell; waits not slept."""
    stall = ro.Stall(grt.lossy_cell(S), rx_at=[S["RX_STALL_AT"]], tx_at=[S["TX_STALL_AT"]])
    return ro.stall_link(stall, S["FLUSH_BYTES"], S["REOPEN_WAIT_S"], S["MAX_REOPENS"], log=log), stall


def self_test(S, GS, model):
    ok = True

    def check(cond, msg):
        nonlocal ok
        print(f"  [{'ok ' if cond else 'FAIL'}] {msg}")
        ok &= bool(cond)

    check(g.pins_ok(GS, S["GENERATE_SPEC_FILE"], S["GENERATE_SPEC_SHA256"], log=lambda s: print("  " + s)),
          "the generation run's pins hold (runner, harness, model, tc_infer.c)")
    print("  tern_tc_reopen.self_test with the spec's constants:")
    t0 = time.time()
    check(ro.self_test(retry_base=S["RETRY_BASE"], max_attempts=S["MAX_ATTEMPTS"],
                       max_retransmits=S["MAX_RETRANSMITS"], max_resyncs=S["MAX_RESYNCS"],
                       flush_bytes=S["FLUSH_BYTES"], wait_s=S["REOPEN_WAIT_S"], max_reopens=S["MAX_REOPENS"]),
          f"reopen self-test ({time.time() - t0:.1f} s)")
    check(h.run.__module__ == "tern_tc_layer_ax7203", "h.run is the harness's own outside a run")

    # One real call through BoardDots (layer 0 q/k/v of token 0), as the retransmit self-test does,
    # now over links that stall until reopened.
    ly = model.layers[0]
    xn = g.rms_norm(model.embed[GS["START_TOKEN"]].astype(g.F32), ly["norm1"])
    q, _s = g.quantize(xn)
    groups = [("L0/wq", ly["wq"], q), ("L0/wk", ly["wk"], q), ("L0/wv", ly["wv"], q)]
    want = g.CpuDots().dots(groups, "")
    R, Q = S["RESP_LEN"], S["REQ_LEN"]
    cases = [
        ("clean link", ro.Stall(rt.HuntingCell(key=h.TEST_KEY)), 0),
        ("11 bytes of answer 3000, then silence", ro.Stall(rt.HuntingCell(key=h.TEST_KEY), rx_at=[3000 * R + 11]), 1),
        ("request 2000 cut after 5 bytes, then nothing reaches the cell",
         ro.Stall(rt.HuntingCell(key=h.TEST_KEY), tx_at=[2000 * Q + 5]), 1),
        ("a hole at answer 1000 and a stall at answer 5000",
         ro.Stall(rt.RxLoss(rt.HuntingCell(key=h.TEST_KEY), [(1000 * R + 1, 56)]), rx_at=[5000 * R + 11]), 1),
    ]
    for what, stall, reopens in cases:
        quiet = []
        b = grt.budget_of(S, keep_events=S["KEEP_EVENTS"])
        link = ro.stall_link(stall, S["FLUSH_BYTES"], S["REOPEN_WAIT_S"], S["MAX_REOPENS"], log=quiet.append)
        bd = g.BoardDots(model, link, h.TEST_KEY, S["WINDOW"], S["FIRST_JOB_NONCE"],
                         bool(GS["SKIP_ZERO_X_CHUNKS"]), log=quiet.append)
        with grt.retransmitting(b, S["LIMIT_S"], log=quiet.append):
            got = bd.dots(groups, "L0/qkv")
        same = all(np.array_equal(x, y) for x, y in zip(got, want))
        check(same and bd.tot["accepted"] == bd.tot["jobs"] and link.reopens == reopens
              and link.flushes == b.resyncs and link.waited == [S["REOPEN_WAIT_S"] * 2 ** k for k in range(reopens)]
              and len(b.events) == b.soft["lost"] + b.resyncs,
              f"BoardDots, {what}: {bd.tot['accepted']}/{bd.tot['jobs']} receipts, "
              f"{bd.tot['exact']}/{bd.tot['rows']} rows, {b.retransmits} retransmitted, {b.resyncs} resyncs, "
              f"{link.reopens} reopens (waits {link.waited}), {len(b.events)} events all kept; sums equal the CPU's")
    # negative control for the event count: a small cap must show as events missing
    b = grt.budget_of(S, keep_events=4)
    link = ro.stall_link(ro.Stall(rt.HuntingCell(key=h.TEST_KEY), rx_at=[3000 * R + 11]), S["FLUSH_BYTES"],
                         S["REOPEN_WAIT_S"], S["MAX_REOPENS"], log=lambda s: None)
    bd = g.BoardDots(model, link, h.TEST_KEY, S["WINDOW"], S["FIRST_JOB_NONCE"],
                     bool(GS["SKIP_ZERO_X_CHUNKS"]), log=lambda s: None)
    with grt.retransmitting(b, S["LIMIT_S"], log=lambda s: None):
        bd.dots(groups, "L0/qkv")
    check(len(b.events) == 4 < b.soft["lost"] + b.resyncs,
          f"with a cap of 4 the same stall keeps {len(b.events)} of {b.soft['lost'] + b.resyncs} events, "
          f"so the all-kept check above can fail")
    check(h.run.__module__ == "tern_tc_layer_ax7203", "h.run restored after the runs")

    # A stall no reopen clears ends the run, and a lie after a reopen is still a lie.
    small = groups[1:2]                                     # wk: 64 rows
    stall = ro.Dead(rt.HuntingCell(key=h.TEST_KEY), rx_at=[500 * R + 11])
    link = ro.stall_link(stall, S["FLUSH_BYTES"], S["REOPEN_WAIT_S"], S["MAX_REOPENS"], log=lambda s: None)
    bf = g.BoardDots(model, link, h.TEST_KEY, S["WINDOW"], S["FIRST_JOB_NONCE"], True, log=lambda s: None)
    try:
        with grt.retransmitting(grt.budget_of(S), S["LIMIT_S"], log=lambda s: None):
            bf.dots(small, "dead")
        check(False, "a stall no reopen clears did not stop the run")
    except (g.Abort, ro.ReopenExhausted) as e:
        check(link.reopens >= 1, f"a stall no reopen clears stops the run after {link.reopens} reopens "
                                 f"({type(e).__name__}: {str(e)[:48]})")
    for fault in ("lie", "impersonate"):
        stall = ro.Stall(rt.HuntingCell(key=h.TEST_KEY, fault=fault, fault_at=1000), rx_at=[500 * R + 11])
        link = ro.stall_link(stall, S["FLUSH_BYTES"], S["REOPEN_WAIT_S"], S["MAX_REOPENS"], log=lambda s: None)
        bf = g.BoardDots(model, link, h.TEST_KEY, S["WINDOW"], S["FIRST_JOB_NONCE"], True, log=lambda s: None)
        try:
            with grt.retransmitting(grt.budget_of(S), S["LIMIT_S"], log=lambda s: None):
                bf.dots(small, "fault")
            check(False, f"fault '{fault}' at job 1000, after a reopen, was not caught")
        except g.Abort as e:
            check(link.reopens == 1, f"fault '{fault}' at job 1000, after a reopen at answer 500, stops the run "
                                     f"({str(e)[:44]})")
    return ok


def main():
    from tern_tc_reopen_params import SPEC as S, SPEC_FILE, SPEC_SHA256
    from tern_tc_generate_params import SPEC as GS
    a = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    a.add_argument("--self-test", action="store_true")
    a.add_argument("--refcell", action="store_true",
                   help="the full run against the reference cell with the pre-registered losses and stalls")
    a.add_argument("--port", default="/dev/cu.usbserial-110")
    a.add_argument("--keys", default="../trinet-keys.txt")
    a.add_argument("--node", default="node0")
    a.add_argument("--setkey", action="store_true")
    args = a.parse_args()
    if not pins_ok(S, SPEC_FILE, SPEC_SHA256):
        return 2
    print(f"spec {SPEC_FILE} sha256 {SPEC_SHA256[:16]}; reopen {S['REOPEN_SHA256'][:16]}, protocol "
          f"{S['PROTOCOL_SHA256'][:16]}, harness {S['HARNESS_SHA256'][:16]}, node RTL {S['NODE_RTL_SHA256'][:16]} "
          f"(pins checked)")
    model = g.TC02(GS["MODEL"])
    print(f"model {GS['MODEL']}: {model.n_layer} layers, d {model.d}, ff {model.ff}, vocab {model.vocab}")
    if args.self_test:
        ok = self_test(S, GS, model)
        print(f"self-test tern_tc_generate_reopen_ax7203: {'PASS' if ok else 'FAIL'}")
        return 0 if ok else 1
    if not g.pins_ok(GS, S["GENERATE_SPEC_FILE"], S["GENERATE_SPEC_SHA256"]):
        return 2
    if not g.preflight(GS, model):
        print("the CPU path no longer matches the pre-registration; nothing sent to the board")
        return 2
    if args.refcell:
        key = h.TEST_KEY
        link, _stall = rehearsal_link(S)
        what = "reference-cell receipts "           # a Python model of the node, not the board
        print(f"rehearsal losses: answer stream {list(zip(S['RX_HOLE_AT'], S['RX_HOLE_LEN']))}, "
              f"request stream {S['TX_DROP_AT']}; stalls: answer stream at {S['RX_STALL_AT']}, "
              f"request stream at {S['TX_STALL_AT']}")
    else:
        key = h.load_key(args.keys, args.node)
        link = ro.serial_link(args.port, S["BAUD"], S["REOPEN_WAIT_S"], S["MAX_REOPENS"], S["FLUSH_BYTES"])
        if args.setkey and h.install_key(link, key) is None:
            print("setkey failed before the first job (a retry is allowed once, both logs kept)")
            return 3
        what = "receipts verified (tag) "
    budget = grt.budget_of(S, keep_events=S["KEEP_EVENTS"])
    board = g.BoardDots(model, link, key, S["WINDOW"], S["FIRST_JOB_NONCE"], bool(GS["SKIP_ZERO_X_CHUNKS"]))
    t0 = time.time()
    try:
        with grt.retransmitting(budget, S["LIMIT_S"]):
            ids = g.Generator(model, board, "int").greedy(GS["START_TOKEN"], S["N_TOKENS"], GS["STOP_TOKEN"])
        err = None
    except (g.Abort, ro.ReopenExhausted) as e:
        ids, err = None, f"{type(e).__name__}: {e}" if isinstance(e, ro.ReopenExhausted) else str(e)
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
    print(f"link                    : {link.summary()}, waits {link.waited} s")
    for e in budget.events:
        print(f"  event  {e}")
    for e in link.events:
        print(f"  link   {e}")
    recorded = budget.soft["lost"] + budget.resyncs
    print(f"events kept             : {len(budget.events)} (cap {budget.keep_events}); lost {budget.soft['lost']} "
          f"+ resyncs {budget.resyncs} = {recorded}"
          + ("; CAP REACHED, later events are not in this log" if len(budget.events) >= budget.keep_events else ""))
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
            and budget.retransmits <= S["MAX_RETRANSMITS"] and budget.resyncs <= S["MAX_RESYNCS"]
            and link.reopens <= S["MAX_REOPENS"])
    if full and args.refcell:
        seen = (budget.retransmits >= S["REHEARSAL_LOSSES"] and budget.resyncs >= 1
                and link.reopens == S["REHEARSAL_STALLS"] and _stall.cleared == S["REHEARSAL_STALLS"])
        if seen:
            print(f"RESULT: REHEARSAL OK - {len(ids)} tokens through the reference cell with "
                  f"{S['REHEARSAL_LOSSES']} scheduled losses recovered and {S['REHEARSAL_STALLS']} stalls "
                  f"cleared by one reopen each; the board was not used.")
            return 0
        print("RESULT: FAIL - the scheduled losses or stalls were not seen as such "
              "(fewer retransmits, no resync, or reopens != stalls).")
        return 1
    if full:
        print(f"RESULT: PASS - {len(ids)} tokens generated with every ternary dot product computed on the")
        print("        AX7203 and every credited receipt verified under the key; ids equal the CPU integer")
        print(f"        path; {budget.retransmits} jobs asked again, {budget.resyncs} resyncs, "
              f"{link.reopens} reopens.")
        if link.reopens == 0:
            print("        No stop happened, so this run does not test whether a reopen clears one.")
        return 0
    print("RESULT: FAIL - ids, counts, ceilings or time differ from the pre-registration.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
