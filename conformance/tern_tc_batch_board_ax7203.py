#!/usr/bin/env python3
"""tern_tc_batch_board_ax7203.py -- the batched wire protocol on the real UART, when the owner flashes it.

The board arm the RTL plan's pre-registration demanded: tern_tc_batch_runner.py's
run() -- the whole two-pass workload, mixed 19/24-byte answers, one shared
Budget -- over the port itself, behind the reopen link the reopen run proved.
Nothing here changes the runner, the model, the harness or the RTL; every one of
them is pinned by sha256 out of tern_tc_batch_params.py, and the link constants
come from the reopen spec the batch spec itself pins
(specs/trinet/tern_tc_reopen_t27_ax7203.t27).

The run's shape is pre-registered in conformance/TERN_TC_BATCH_RTL_PLAN.md and
concretised here, before any board is touched:

  * workload -- the rehearsal pair's pass sizes by default (wq 16 rows x 320
    wide, down 16 x 864); --full runs the spec's own L2 shapes (320 x 320,
    320 x 864), whose frame counts the spec pins (SETX 60/162, DOT6 3200/8640).
  * frame counts per pass pre-computed from the pass dimensions and asserted
    against what the run actually sent.
  * ceilings from the specs, not from the model's projections: retransmits
    <= BATCH_RETRANSMITS_MAX (13), resyncs <= 32 (runner policy, as in
    tern_tc_retransmit), reopens <= MAX_REOPENS (4, reopen spec), wall <=
    LIMIT_S. 235 s is the model's link arithmetic and stays unclaimed: the
    board run's wall is its own number, the ceiling is the pre-registration's.
  * success is every row bit-exact against the int8 oracle, transport counters
    within ceilings; anything else is RESULT: FAIL with the first bad row.

    python3 tern_tc_batch_board_ax7203.py --self-test
    python3 tern_tc_batch_board_ax7203.py --refcell    # same main path, Stall/RxLoss around
                                                      # HuntingBatchCell, one scheduled reopen
    python3 tern_tc_batch_board_ax7203.py --setkey --port /dev/cu.usbserial-110 \
        --keys ../trinet-keys.txt --node node0

Author: Dmitrii Vasilev (@gHashTag)
"""
import argparse
import hashlib
import os
import random
import signal
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import tern_tc_batch_params as bp  # noqa: E402  (S = bp.SPEC, bp.SPEC_FILE/SHA256)
import tern_tc_reopen_t27_params as rtp  # noqa: E402  (link constants of the pinned reopen spec)
import tern_tc_reopen as ro  # noqa: E402  (serial_link, Stall, stall_link, ReopenExhausted)
import tern_tc_retransmit as rt  # noqa: E402  (RxLoss, byte-level, op-agnostic)
import tern_tc_batch_runner as br  # noqa: E402  (run, rehearsal_passes, BatchBudget, HuntingBatchCell)
import tern_tc_layer_ax7203 as h  # noqa: E402  (TEST_KEY, load_key, install_key)

S = bp.SPEC

# The pins the board run stands on: the batch spec itself, plus every file it
# pins that this arm's verdict depends on. (file-key, sha-key) pairs because
# the plan doc's file key is PLAN_DOC, not PLAN_FILE.
PIN_PAIRS = [("HARNESS_FILE", "HARNESS_SHA256"),
             ("MAC32_FILE", "MAC32_SHA256"),
             ("NODE_RTL_FILE", "NODE_RTL_SHA256"),
             ("SIP_RTL_FILE", "SIP_RTL_SHA256"),
             ("REOPEN_SPEC_FILE", "REOPEN_SPEC_SHA256"),
             ("PLAN_DOC", "PLAN_SHA256")]

# Ceilings, every one from a pinned spec. The wall ceilings are this run's own
# pre-registration (RTL plan: "it does not inherit the projection").
RT_MAX = S["BATCH_RETRANSMITS_MAX"]      # 13, the design's whole-run loss bound
RESYNC_MAX = br.MAX_RESYNCS              # 32, runner policy, as in tern_tc_retransmit
REOPEN_MAX = rtp.SPEC["MAX_REOPENS"]        # 4, the reopen spec the batch spec pins
LIMIT_S_PAIR = 240                       # pair: ~38 KB on the wire, generous 7x
LIMIT_S_FULL = 900                       # full L2 shapes; the model says 235, we claim nothing

RESP = S["RESP_LEN"]                     # 19, SETX answer
RESP6 = S["RESP_DOT6_LEN"]               # 24, DOT6 answer
PLANES = br.PLANES


def sha256_file(rel):
    hsh = hashlib.sha256()
    with open(os.path.join(os.path.dirname(HERE), rel), "rb") as fh:
        for blk in iter(lambda: fh.read(65536), b""):
            hsh.update(blk)
    return hsh.hexdigest()


def pins_ok(log=print):
    ok = True
    for rel, want in [(bp.SPEC_FILE, bp.SPEC_SHA256)] + [(S[f], S[s]) for f, s in PIN_PAIRS]:
        got = sha256_file(rel)
        if got != want:
            log(f"PIN MISMATCH {rel}: {got[:16]} != {want[:16]}; nothing run")
            ok = False
    return ok


# ---------------------------------------------------------------------------
# Workload and its pre-computed frame arithmetic
# ---------------------------------------------------------------------------

def full_passes():
    """The spec's own L2 shapes; frame counts cross-checked against SETX_*/WQ_L2/SETX_DOWN/DOWN_L2."""
    rng = random.Random(0xB47C4)  # any seed: only the shapes are pinned here
    return [br.build_pass(rng, "wq", S["R_WQ"], S["C_WQ"] * 32),
            br.build_pass(rng, "down", S["R_DOWN"], S["C_DOWN"] * 32)]


def frame_counts(pss):
    """(name, R, C, setx, dot6) per pass; skip_zero=False so sent == these exactly."""
    return [(p["name"], p["R"], p["C"], PLANES * p["C"], p["R"] * p["C"]) for p in pss]


def workload_line(pss, limit_s):
    parts = [f"{n}: {r} rows x {c * 32} wide (setx {sx}, dot6 {d})" for n, r, c, sx, d in frame_counts(pss)]
    return ("workload " + ", ".join(parts)
            + f"; ceilings retransmits<={RT_MAX} resyncs<={RESYNC_MAX} reopens<={REOPEN_MAX} wall<={limit_s}s")


# ---------------------------------------------------------------------------
# The one main path refcell and board share
# ---------------------------------------------------------------------------

class _WallCeiling(Exception):
    pass


def run_workload(link, pss, key, limit_s, log=lambda *_: None):
    """br.run under this run's own wall ceiling; returns (results, budget, wall_s, stopped_why)."""
    t0 = time.monotonic()

    def _timeout(signum, frame):
        raise _WallCeiling(f"{time.monotonic() - t0:.1f} s > {limit_s} s")

    was = signal.signal(signal.SIGALRM, _timeout)
    signal.alarm(int(limit_s))
    try:
        res, budget = br.run(link, pss, key=key, log=log)
        why = None
    except _WallCeiling as exc:
        res, budget, why = [], None, f"wall ceiling {exc}"
    except ro.ReopenExhausted as exc:
        res, budget, why = [], None, f"reopens exhausted: {exc}"
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, was)
    return res, budget, time.monotonic() - t0, why


def verdict(res, budget, wall_s, stopped_why, pss):
    """The pre-registered success predicate, nothing softer."""
    if stopped_why is not None:
        return False, f"run stopped: {stopped_why}"
    if budget is None or not res:
        return False, "no results"
    rows = sum(r["rows"] for r in res)
    exact = sum(r["exact"] for r in res)
    for (n, r, c, sx, d), got in zip(frame_counts(pss), res):
        if got["frames_batched"] != sx + d:
            return False, (f"pass {n}: {got['frames_batched']} frames credited, pre-computed {sx + d} "
                           f"(sent {got['sent_setx']} setx + {got['sent_dot6']} dot6, "
                           f"{got['rt']['retransmits']} retransmits)")
    if exact != rows:
        bad = next(r for r in res if r["exact"] < r["rows"])
        return False, (f"{rows - exact}/{rows} rows differ vs int8 oracle "
                       f"(first in pass {bad['per_pass']['name']})")
    if budget.retransmits > RT_MAX:
        return False, f"retransmits {budget.retransmits} > ceiling {RT_MAX}"
    if budget.resyncs > RESYNC_MAX:
        return False, f"resyncs {budget.resyncs} > ceiling {RESYNC_MAX}"
    reopens = getattr(_current_link, "reopens", 0)
    if reopens > REOPEN_MAX:
        return False, f"reopens {reopens} > ceiling {REOPEN_MAX}"
    if wall_s > LIMIT_OF[0]:
        return False, f"wall {wall_s:.1f} s > ceiling {LIMIT_OF[0]} s"
    return True, (f"{exact}/{rows} rows bit-exact vs int8 oracle; transport within ceilings "
                  f"({budget.retransmits}/{RT_MAX} retransmits, {budget.resyncs}/{RESYNC_MAX} resyncs, "
                  f"{reopens}/{REOPEN_MAX} reopens, {wall_s:.1f}/{LIMIT_OF[0]} s)")


# The verdict needs the link's reopen count and the active wall ceiling; rather
# than threading them through br.run's signatures (which this arm must not
# edit), the active run records them here. Module-level run state, single run
# per process -- exactly the board discipline.
_current_link = None
LIMIT_OF = [LIMIT_S_PAIR]


# ---------------------------------------------------------------------------
# Rehearsal link: the parser the node has, answer holes, one scheduled reopen
# ---------------------------------------------------------------------------

def refcell_link(log=print):
    """HuntingBatchCell behind the hunting parser, two short answer holes and one rx
    stall on the last DOT6 answer that only a reopen clears -- positions computed from
    the pair's own counts. Measured 9/13 retransmits: the ceiling is real headroom,
    not the rehearsal's own edge. (The runner's own 3-hole schedule lands exactly on
    13 because the ceiling was calibrated from it -- a rehearsal at its own edge
    teaches nothing about the margin below it. Moving the stall from the third-last
    to the last answer alone drops the count 13 -> 9: each resync requeues the whole
    inflight window, and a late stall finds almost nothing in flight.)"""
    pss = br.rehearsal_passes()
    n_setx = sum(PLANES * p["C"] for p in pss)
    n_dot6 = sum(p["R"] * p["C"] for p in pss)
    holes = [(7 * RESP + 4, 8),                           # tag of one SETX answer, mid wq
             (n_setx * RESP + 10 * RESP6 + 6, 12)]        # tag of one DOT6 answer, mid down
    stall_at = n_setx * RESP + (n_dot6 - 1) * RESP6 + 11  # last DOT6 answer; flush meets silence
    cell = rt.RxLoss(br.HuntingBatchCell(key=h.TEST_KEY), holes)
    stall = ro.Stall(cell, rx_at=[stall_at])
    link = ro.stall_link(stall, S["FLUSH_BYTES"], rtp.SPEC["REOPEN_WAIT_S"], REOPEN_MAX, log=log)
    return link, stall, holes, stall_at


# ---------------------------------------------------------------------------
# Self-test (hermetic: no board, no port)
# ---------------------------------------------------------------------------

def self_test():
    ok = True

    def check(cond, what):
        nonlocal ok
        print(f"  {'ok  ' if cond else 'FAIL'} {what}")
        ok = ok and bool(cond)

    check(pins_ok(log=lambda s: print("  " + s)), "the batch spec and every pin it carries hold")

    pss = br.rehearsal_passes()
    counts = frame_counts(pss)
    check(counts == [("wq", 16, 10, 60, 160), ("down", 16, 27, 162, 432)],
          f"the pair's pre-computed frames are the pinned ones: {counts}")
    full = frame_counts(full_passes())
    check(full == [("wq", S["R_WQ"], S["C_WQ"], S["SETX_WQ"], S["WQ_L2"]),
                   ("down", S["R_DOWN"], S["C_DOWN"], S["SETX_DOWN"], S["DOWN_L2"])],
          "the --full shapes reproduce the spec's own SETX_*/L2 frame counts")

    # The main path over a clean cell: sent == pre-computed, everything exact, PASS verdict.
    global _current_link
    link = ro.Stall(br.HuntingBatchCell(key=h.TEST_KEY))
    _current_link = link
    LIMIT_OF[0] = LIMIT_S_PAIR
    res, b, wall, why = run_workload(link, pss, h.TEST_KEY, LIMIT_S_PAIR)
    okv, whyv = verdict(res, b, wall, why, pss)
    check(okv and all(r["exact"] == r["rows"] for r in res) and b.retransmits == 0,
          f"clean link through the main path: {whyv}")

    # The refcell: the scheduled holes and the one reopen, same verdict PASS, margin below ceilings.
    quiet = []
    link, stall, holes, stall_at = refcell_link(log=quiet.append)
    _current_link = link
    res, b, wall, why = run_workload(link, pss, h.TEST_KEY, LIMIT_S_PAIR, log=quiet.append)
    okv, whyv = verdict(res, b, wall, why, pss)
    check(okv and 0 < b.retransmits < RT_MAX and link.reopens == 1 and b.soft["lost"] >= len(holes),
          f"refcell with {len(holes)} holes + 1 reopen: {whyv}")

    # Negative: a lie in the oracle must fail the verdict, not pass it.
    lied = br.rehearsal_passes()
    lied[1]["oracle"][0] += 1
    link = ro.Stall(br.HuntingBatchCell(key=h.TEST_KEY))
    _current_link = link
    res, b, wall, why = run_workload(link, lied, h.TEST_KEY, LIMIT_S_PAIR)
    okv, whyv = verdict(res, b, wall, why, lied)
    check(not okv and "differ vs int8 oracle" in whyv, f"a one-row oracle lie fails the verdict: {whyv}")

    # Negative: a stall no reopen clears stops the run as FAIL, never a hang.
    link = ro.stall_link(ro.Dead(br.HuntingBatchCell(key=h.TEST_KEY), rx_at=[7 * RESP + 4]),
                         S["FLUSH_BYTES"], rtp.SPEC["REOPEN_WAIT_S"], 1, log=lambda s: None)
    _current_link = link
    res, b, wall, why = run_workload(link, pss, h.TEST_KEY, 30)
    okv, whyv = verdict(res, b, wall, why, pss)
    check(not okv and ("stopped" in whyv or "frames credited" in whyv),
          f"a dead line ends as FAIL ({whyv}), not a hang and never a pass")

    return ok


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--self-test", action="store_true", help="hermetic; no board")
    mode.add_argument("--refcell", action="store_true", help="rehearsal: same main path, scheduled losses")
    mode.add_argument("--port", help="board mode: the UART the node is on")
    ap.add_argument("--keys", default="../trinet-keys.txt", help="key file (board mode)")
    ap.add_argument("--node", default="node0", help="node name in the key file (board mode)")
    ap.add_argument("--setkey", action="store_true", help="install the node key first (SRAM wipe after flash)")
    ap.add_argument("--full", action="store_true", help="the spec's L2 shapes (320 rows/pass), not the pair")
    ap.add_argument("--limit-s", type=int, default=None, help="override the pre-registered wall ceiling")
    args = ap.parse_args()

    print(f"# start {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}")
    if not pins_ok():
        return 2
    pins_txt = (f"spec {bp.SPEC_FILE} sha256 {bp.SPEC_SHA256[:16]}; "
                + ", ".join(f"{S[f].split('/')[-1]} {S[s][:16]}" for f, s in PIN_PAIRS)
                + " (pins checked)")
    print(pins_txt)

    if args.self_test:
        print("tern_tc_batch_board self-test:")
        return 0 if self_test() else 1

    pss = full_passes() if args.full else br.rehearsal_passes()
    limit_s = args.limit_s or (LIMIT_S_FULL if args.full else LIMIT_S_PAIR)
    print(f"# limit {limit_s} s")
    print(workload_line(pss, limit_s))

    global _current_link
    if args.refcell:
        quiet = []
        link, _stall, holes, stall_at = refcell_link(log=quiet.append)
        key = h.TEST_KEY
        print(f"refcell: holes {holes}, stall at {stall_at} (reopen clears), test key")
    else:
        if not args.port:
            ap.error("board mode needs --port")
        lock = subprocess.run(["lsof", args.port], capture_output=True, text=True)
        if lock.stdout.strip():
            print(f"# REFUSED: {args.port} is held by another process (UART lock doctrine)")
            print(f"# {lock.stdout.strip().splitlines()[1] if len(lock.stdout.splitlines()) > 1 else lock.stdout.strip()}")
            return 2
        print(f"# cmd python3 -u conformance/tern_tc_batch_board_ax7203.py --port {args.port}"
              + (" --setkey" if args.setkey else "") + (" --full" if args.full else ""))
        key = h.load_key(args.keys, args.node)
        link = ro.serial_link(args.port, S["BAUD"], rtp.SPEC["REOPEN_WAIT_S"], REOPEN_MAX, S["FLUSH_BYTES"])
        print(f"# uart {args.port} @ {S['BAUD']} baud; reopen link (wait {rtp.SPEC['REOPEN_WAIT_S']} s, "
              f"max {REOPEN_MAX})")
        print(f"key node {args.node} fingerprint {hashlib.sha256(key).hexdigest()[:16]} (never the key)")
        if args.setkey:
            node_id = h.install_key(link, key)
            if node_id is None:
                print("RESULT: FAIL - setkey was not credited by the node")
                return 3
            print(f"setkey node {args.node} acked by node id {node_id}")

    _current_link = link
    LIMIT_OF[0] = limit_s
    res, budget, wall, why = run_workload(link, pss, key, limit_s)
    for r in res:
        print(f"pass {r['per_pass']['name']}: {r['exact']}/{r['rows']} rows exact, "
              f"{r['sent_setx']} setx + {r['sent_dot6']} dot6 frames, "
              f"{r['rt']['retransmits']} retransmits, {r['rt']['resyncs']} resyncs")
    if budget is not None:
        print(f"transport: retransmits {budget.retransmits}/{RT_MAX}, resyncs {budget.resyncs}/{RESYNC_MAX}, "
              f"reopens {getattr(_current_link, 'reopens', 0)}/{REOPEN_MAX}, wall {wall:.1f}/{limit_s} s")
    okv, whyv = verdict(res, budget, wall, why, pss)
    print(f"RESULT: {'PASS' if okv else 'FAIL'} - {whyv}")
    return 0 if okv else 1


if __name__ == "__main__":
    sys.exit(main())
