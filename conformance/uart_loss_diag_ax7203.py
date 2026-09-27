#!/usr/bin/env python3
"""UART loss diagnostic: keep going after a hole in the answer stream, and count the holes.

Pre-registered in specs/trinet/uart_loss_diag_ax7203.t27; every number comes from the generated
uart_loss_diag_params.py. The layer harness, tern_tc_layer_ax7203.py, stops at the first unframed
read, so a board run shows at most one loss. This runner sends the same jobs through the same link
with the same I/O pattern, and when a frame fails it scans forward for the next ANCHOR: an answer
whose SipHash tag verifies under the key for a job still in flight. Then

    lost answers = M - E        hole bytes = RESP_LEN * (M - E) - q

with E the first unanswered job, M the anchor's job, q the bytes read from where E's answer should
have started to the anchor. It imports the harness and never edits it; the harness's own pass line
and its words for a full pass are not printed here.

    python3 uart_loss_diag_ax7203.py --self-test
    python3 uart_loss_diag_ax7203.py --arm 0 --setkey --port /dev/cu.usbserial-110 \\
        --keys ../trinet-keys.txt --json board_runs/uart_loss_w64.json
    python3 uart_loss_diag_ax7203.py --compare board_runs/uart_loss_w64.json board_runs/uart_loss_w24.json

Author: Dmitrii Vasilev (@gHashTag)
"""
import argparse
import hashlib
import json
import math
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from uart_loss_diag_params import SPEC, SPEC_FILE, SPEC_SHA256  # noqa: E402
import tern_tc_layer_ax7203 as h  # noqa: E402
from trinet_mac32_conformance_ax7203 import (  # noqa: E402
    OP_MAC32, golden_dot, receipt_preimage, siphash24)

RESP_LEN = SPEC["RESP_LEN"]
FIRST = SPEC["FIRST_JOB_NONCE"]


def sha256_file(rel):
    with open(os.path.join(REPO, rel), "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def pins_ok(log=print):
    """The spec, the harness and the MAC32 module must be the bytes the spec names."""
    ok = True
    for rel, want in ((SPEC_FILE, SPEC_SHA256), (SPEC["HARNESS_FILE"], SPEC["HARNESS_SHA256"]),
                      (SPEC["MAC32_FILE"], SPEC["MAC32_SHA256"])):
        got = sha256_file(rel)
        if got != want:
            log(f"PIN MISMATCH {rel}: {got[:16]} != {want[:16]}; regenerate or restore, nothing run")
            ok = False
    return ok


# ---------------------------------------------------------------------------
# The counter
# ---------------------------------------------------------------------------

def run_arm(link, jobs, n_jobs, key, window, log=print, limit_s=None, drain=None):
    """Send n_jobs (job i = jobs[i % len(jobs)]) with `window` in flight; count every event."""
    P = len(jobs)
    node_id, magic, st_ok = SPEC["NODE_ID"], SPEC["MAGIC_RESP"], SPEC["STATUS_OK"]
    span = RESP_LEN * (window + SPEC["RESYNC_SPARE_FRAMES"])
    pending = bytearray()             # bytes read past an anchor, consumed before the link
    E = sent = 0
    accepted = wrong_y = lost = 0
    events, stalls, aborted, stopped = [], 0, None, False
    max_pause, pause_at, t_back = 0.0, 0, time.monotonic()
    t0 = time.monotonic()

    def read(n):
        nonlocal pending
        if pending:
            out, pending = bytes(pending[:n]), pending[n:]
            if len(out) < n:
                out += link.read(n - len(out))
            return out
        return link.read(n)

    def check(fr):
        """(job index, y right) if fr is a signed answer for a job in flight, else None."""
        if len(fr) < RESP_LEN or fr[0] != magic or fr[2] != st_ok:
            return None
        r = h.parse(fr)
        i = r["nonce"] - FIRST
        if r["node_id"] != node_id or not E <= i < sent:
            return None
        w, x, _row, _weight = jobs[i % P]
        pre = receipt_preimage(OP_MAC32, r["nonce"].to_bytes(4, "little"), w, x, r["y"] & 0xFF,
                               r["node_id"])
        if r["tag"] != siphash24(pre, key):
            return None
        return i, r["y"] == golden_dot(w, x)

    def event(kind, i, q, hole, extra=""):
        ev = dict(kind=kind, E=E, M=i, q=q, hole=hole, lost=(i - E) if i is not None else None,
                  sent=sent, accepted=accepted)
        events.append(ev)
        if len(events) <= SPEC["EVENT_LINES_MAX"]:
            log(f"  event {len(events):4d} {kind:<10} at job {E} (sent {sent}): "
                + (f"anchor job {i} at +{q}, hole {hole} B, {i - E} answer(s) lost"
                   if i is not None else "no anchor") + extra)

    while sent < n_jobs or sent > E:
        if limit_s and not stopped and time.monotonic() - t0 > limit_s:
            stopped = True
            log(f"  limit {limit_s} s reached after {sent} sent; finishing the jobs in flight")
        while sent < n_jobs and sent - E < window and not stopped:
            w, x, _row, _weight = jobs[sent % P]
            link.write(h.request(OP_MAC32, FIRST + sent, w, x))
            sent += 1
        if sent == E:
            break
        t_read = time.monotonic()
        if t_read - t_back > max_pause:
            max_pause, pause_at = t_read - t_back, accepted + wrong_y
        fr = read(RESP_LEN)
        t_back = time.monotonic()
        v = check(fr)
        if v is not None:
            i, y_ok = v
            if i > E:
                event("whole", i, 0, RESP_LEN * (i - E))
                lost += i - E
            E = i + 1
            accepted += y_ok
            wrong_y += not y_ok
            stalls = 0
            continue

        # Resync: scan forward, byte by byte, for an anchor.
        scan, o, found = bytearray(fr), 1, None
        while found is None:
            while o + RESP_LEN <= len(scan):
                if scan[o] == magic:
                    v = check(bytes(scan[o:o + RESP_LEN]))
                    if v is not None:
                        found = (o, v)
                        break
                o += 1
            if found or len(scan) >= span + RESP_LEN:
                break
            more = read(RESP_LEN)
            if not more:
                break
            scan += more
        if found:
            o, (i, y_ok) = found
            hole = RESP_LEN * (i - E) - o
            kind = "bytes" if hole > 0 else ("damaged" if hole == 0 else "inserted")
            event(kind, i, o, hole, f"; {len(scan)} B scanned")
            lost += i - E
            E = i + 1
            accepted += y_ok
            wrong_y += not y_ok
            pending = scan[o + RESP_LEN:] + pending
            stalls = 0
            continue

        # Unresolved: stop, let the link go quiet, count everything in flight as lost.
        drained = len(scan)
        while True:
            chunk = (drain or link.read)(4096)
            if not chunk:
                break
            drained += len(chunk)
        pending = bytearray()
        event("unresolved", None, None, None, f"; {drained} B read and dropped, "
                                               f"{sent - E} in flight lost")
        lost += sent - E
        E = sent
        stalls += 1
        if stalls >= SPEC["STALLS_TO_ABORT"]:
            aborted = f"{stalls} unresolved events in a row after {sent} sent"
            log(f"  ARM ABORTED: {aborted}")
            break

    return dict(window=window, planned=n_jobs, sent=sent, accepted=accepted, wrong_y=wrong_y,
                lost=lost, in_flight_at_end=sent - E, events=events, aborted=aborted,
                stopped_at_limit=stopped, max_pause_ms=round(1000 * max_pause, 1),
                pause_at=pause_at, elapsed_s=round(time.monotonic() - t0, 2))


# ---------------------------------------------------------------------------
# Statistics (exact, no scipy)
# ---------------------------------------------------------------------------

def _pois_cdf(k, lam):
    if lam <= 0:
        return 1.0
    term = s = math.exp(-lam)
    for j in range(1, k + 1):
        term *= lam / j
        s += term
    return min(s, 1.0)


def poisson_ci(k, conf=0.95):
    """Exact (Garwood) interval for a Poisson count k."""
    a = (1 - conf) / 2

    def solve(f, lo, hi):
        for _ in range(200):
            mid = (lo + hi) / 2
            if f(mid):
                hi = mid
            else:
                lo = mid
        return (lo + hi) / 2
    top = 10.0 * (k + 10)
    upper = solve(lambda lam: _pois_cdf(k, lam) <= a, 0.0, top)
    lower = 0.0 if k == 0 else solve(lambda lam: 1 - _pois_cdf(k - 1, lam) >= a, 0.0, top)
    return lower, upper


def binom_tail_half(e, n):
    """P[X >= e] for X ~ Binomial(n, 1/2), exact."""
    return sum(math.comb(n, j) for j in range(e, n + 1)) / 2 ** n


def loss_events(res):
    return [e for e in res["events"] if e["kind"] in ("bytes", "whole", "unresolved")]


def summarize(res, log=print):
    ev = res["events"]
    kinds = {}
    for e in ev:
        kinds[e["kind"]] = kinds.get(e["kind"], 0) + 1
    k = len(loss_events(res))
    n = res["sent"]
    lo, hi = poisson_ci(k)
    holes = sorted(e["hole"] for e in ev if e["hole"] is not None and e["hole"] > 0)
    booked = res["accepted"] + res["wrong_y"] + res["lost"] + res["in_flight_at_end"]
    instrument_ok = booked == n and res["in_flight_at_end"] == 0
    log("-" * 66)
    log(f"window                      : {res['window']} ({RESP_LEN * res['window']} B in flight)")
    log(f"jobs sent                   : {n} of {res['planned']} planned"
        + (" (stopped at the time limit)" if res["stopped_at_limit"] else "")
        + (f" (ABORTED: {res['aborted']})" if res["aborted"] else ""))
    log(f"answers accepted (tag + y)  : {res['accepted']}")
    log(f"wrong y under a valid tag   : {res['wrong_y']}"
        + ("   <-- COMPUTE FAULT, not a UART loss" if res["wrong_y"] else ""))
    log(f"answers lost                : {res['lost']}")
    log(f"events                      : {len(ev)} {kinds if kinds else ''}")
    log(f"loss events (bytes/whole/unresolved): {k}")
    if n:
        per = f"1 per {n / k:,.0f} jobs" if k else "none"
        log(f"loss rate                   : {per}; 95 % interval "
            f"[{1e6 * lo / n:.3f}, {1e6 * hi / n:.3f}] per 10^6 jobs")
    log(f"hole sizes (bytes)          : {holes if holes else '-'}")
    log(f"longest host pause          : {res['max_pause_ms']} ms (after {res['pause_at']} answers)")
    log(f"elapsed                     : {res['elapsed_s']} s")
    log(f"instrument check            : {'ok' if instrument_ok else 'BROKEN'} "
        f"(accepted + wrong y + lost + in flight = {booked}, sent = {n})")
    log("-" * 66)
    return dict(loss_events=k, rate_ci_per_job=[lo / n if n else None, hi / n if n else None],
                kinds=kinds, holes=holes, instrument_ok=instrument_ok)


def compare(a, b, log=print):
    """The pre-registered claim: does window 64 lose more often than window 24?"""
    by_w = {r["window"]: r for r in (a, b)}
    w_hi, w_lo = SPEC["ARM_WINDOWS"]
    r_hi, r_lo = by_w.get(w_hi), by_w.get(w_lo)
    if r_hi is None or r_lo is None:
        log("compare: need one record per window in ARM_WINDOWS")
        return None
    bad = [r for r in (r_hi, r_lo) if not r["summary"]["instrument_ok"] or r["aborted"]
           or r["stopped_at_limit"] or r["sent"] != SPEC["JOBS_PER_ARM"]]
    e_hi, e_lo = r_hi["summary"]["loss_events"], r_lo["summary"]["loss_events"]
    n = e_hi + e_lo
    p = binom_tail_half(e_hi, n) if n else 1.0
    claim = not bad and n > 0 and p * SPEC["ALPHA_INV"] <= 1
    log(f"window {w_hi}: {e_hi} loss events in {r_hi['sent']} jobs; window {w_lo}: {e_lo} in {r_lo['sent']}")
    log(f"P[X >= {e_hi} | n = {n}, 1/2] = {p:.3g}; threshold 1/{SPEC['ALPHA_INV']}")
    if bad:
        log("CLAIM_W64_WORSE: not decidable (an arm was aborted, cut short or failed its instrument check)")
    else:
        log(f"CLAIM_W64_WORSE: {'yes' if claim else 'no'}")
    wy = r_hi["wrong_y"] + r_lo["wrong_y"]
    if wy:
        log(f"COMPUTE FAULT: {wy} answers carry a valid tag and a wrong y")
    return dict(e_hi=e_hi, e_lo=e_lo, p=p, claim=claim, decidable=not bad)


# ---------------------------------------------------------------------------
# Self-test: every kind of event, made on purpose and counted right
# ---------------------------------------------------------------------------

class HoleLink:
    """Drops byte runs [(offset, count), ...] from an inner link's answer stream."""

    def __init__(self, inner, holes):
        self.inner, self.holes, self.pos = inner, holes, 0

    def write(self, b):
        self.inner.write(b)

    def read(self, n):
        out = bytearray()
        while len(out) < n:
            b = self.inner.read(1)
            if not b:
                break
            if not any(a <= self.pos < a + c for a, c in self.holes):
                out += b
            self.pos += 1
        return bytes(out)


class DeadAfter:
    """Answers the first `k` answers' bytes, then nothing (a node that stopped)."""

    def __init__(self, inner, k):
        self.inner, self.left = inner, k * RESP_LEN

    def write(self, b):
        self.inner.write(b)

    def read(self, n):
        n = min(n, self.left)
        out = self.inner.read(n) if n else b""
        self.left -= len(out)
        return out


def self_test():
    rng_jobs = []
    import random
    rnd = random.Random(7)
    for _ in range(97):                      # a pass length that does not divide the job count
        w = bytes(rnd.randrange(256) for _ in range(8))
        x = bytes(rnd.randrange(256) for _ in range(8))
        rng_jobs.append((w, x, 0, 1))
    key = h.TEST_KEY
    node = SPEC["NODE_ID"]
    quiet = lambda *_: None  # noqa: E731
    ok = True

    def cell(**kw):
        return h.RefCell(node_id=node, key=key, **kw)

    def case(name, link, n, window, want):
        nonlocal ok
        r = run_arm(link, rng_jobs, n, key, window, log=quiet)
        s = summarize(r, log=quiet)
        got = dict(kinds=s["kinds"], holes=s["holes"], lost=r["lost"], accepted=r["accepted"],
                   wrong_y=r["wrong_y"], instrument_ok=s["instrument_ok"],
                   aborted=bool(r["aborted"]))
        bad = {k: (got[k], v) for k, v in want.items() if got[k] != v}
        print(f"  [{'ok ' if not bad else 'FAIL'}] {name}" + (f"  got/want {bad}" if bad else ""))
        ok &= not bad

    print("self-test (reference cell, test key):")
    case("clean, window 64", cell(), 3000, 64,
         dict(kinds={}, lost=0, accepted=3000, wrong_y=0, instrument_ok=True))
    # The five recorded hole sizes, at offsets that cut mid-answer and across answers.
    holes = [(19 * 100 + 8, 16), (19 * 400 + 3, 53), (19 * 900 + 15, 4), (19 * 1500 + 1, 59),
             (19 * 2200 + 12, 7)]
    want_lost = sum((a + c - 1) // 19 - a // 19 + 1 for a, c in holes)
    case("five holes 16/53/4/59/7 B", HoleLink(cell(), holes), 3000, 64,
         dict(kinds={"bytes": 5}, holes=[4, 7, 16, 53, 59], lost=want_lost,
              accepted=3000 - want_lost, instrument_ok=True))
    case("hole of exactly two answers, on a boundary", HoleLink(cell(), [(19 * 50, 38)]), 500, 24,
         dict(kinds={"whole": 1}, holes=[38], lost=2, accepted=498, instrument_ok=True))
    case("dropped answer (node skipped one)", cell(fault="drop", fault_at=40), 500, 24,
         dict(kinds={"whole": 1}, holes=[19], lost=1, accepted=499))
    case("tag damaged in place", cell(fault="damage", fault_at=40), 500, 24,
         dict(kinds={"damaged": 1}, holes=[], lost=1, accepted=499))
    case("wrong y, honestly signed", cell(fault="lie", fault_at=40), 500, 24,
         dict(kinds={}, lost=0, accepted=499, wrong_y=1))
    case("wrong key: no anchor ever, arm aborts", cell(fault="wrong_key"), 500, 24,
         dict(kinds={"unresolved": SPEC["STALLS_TO_ABORT"]}, accepted=0, aborted=True))
    case("node stops after 200 answers", DeadAfter(cell(), 200), 500, 24,
         dict(kinds={"unresolved": SPEC["STALLS_TO_ABORT"]}, accepted=200, aborted=True))
    # statistics
    lo, hi = poisson_ci(0)
    st = abs(hi - 3.6889) < 1e-3 and lo == 0.0
    lo, hi = poisson_ci(10)
    st &= abs(lo - 4.7954) < 1e-3 and abs(hi - 18.3904) < 1e-3
    st &= abs(binom_tail_half(7, 7) - 1 / 128) < 1e-12 and binom_tail_half(6, 6) * 100 > 1
    print(f"  [{'ok ' if st else 'FAIL'}] exact Poisson intervals and the binomial threshold")
    ok &= st
    print(f"self-test: {'PASS' if ok else 'FAIL'}")
    return ok


# ---------------------------------------------------------------------------

def main():
    a = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    a.add_argument("--arm", type=int, choices=range(len(SPEC["ARM_WINDOWS"])))
    a.add_argument("--port", default="/dev/cu.usbserial-110")
    a.add_argument("--keys", default="../trinet-keys.txt")
    a.add_argument("--node", default="node0")
    a.add_argument("--setkey", action="store_true")
    a.add_argument("--json", help="write the arm's record here")
    a.add_argument("--self-test", action="store_true")
    a.add_argument("--compare", nargs=2, metavar="JSON")
    args = a.parse_args()

    if args.self_test:
        return 0 if (pins_ok() and self_test()) else 1
    if args.compare:
        recs = [json.load(open(p)) for p in args.compare]
        r = compare(*recs)
        return 0 if r is not None else 1
    if args.arm is None:
        a.error("give --arm, --self-test or --compare")
    if not pins_ok():
        return 2

    window = SPEC["ARM_WINDOWS"][args.arm]
    print(f"spec {SPEC_FILE} sha256 {SPEC_SHA256[:16]}; harness pinned {SPEC['HARNESS_SHA256'][:16]}")
    mats, _hdr = h.load_tc02(os.path.expanduser(SPEC["MODEL"]), h.KINDS, None)
    jobs, _rows = h.build_jobs(mats, "ternary", SPEC["N_X"], SPEC["SEED"])
    if len(jobs) != SPEC["JOBS_PER_PASS"]:
        print(f"job list has {len(jobs)} entries, spec says {SPEC['JOBS_PER_PASS']}; nothing run")
        return 2
    key = h.load_key(args.keys, args.node)
    print(f"arm {args.arm}: window {window}, {SPEC['JOBS_PER_ARM']} jobs "
          f"({SPEC['PASSES']} x {SPEC['JOBS_PER_PASS']}), port {args.port} @ {SPEC['BAUD']}")
    link = h.SerialLink(args.port, SPEC["BAUD"])
    if args.setkey and h.install_key(link, key) is None:
        print("setkey failed before the first job (a retry is allowed once, both logs kept)")
        return 3
    res = run_arm(link, jobs, SPEC["JOBS_PER_ARM"], key, window, limit_s=SPEC["ARM_LIMIT_S"])
    res["summary"] = summarize(res)
    res["spec_sha256"] = SPEC_SHA256
    if args.json:
        with open(args.json, "w") as f:
            json.dump(res, f, indent=1)
        print(f"record: {args.json}")
    return 0 if res["summary"]["instrument_ok"] and not res["aborted"] else 1


if __name__ == "__main__":
    sys.exit(main())
