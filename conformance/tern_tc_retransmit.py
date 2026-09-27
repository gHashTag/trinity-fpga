#!/usr/bin/env python3
"""tern_tc_retransmit.py -- the tern_tc job stream, with lost answers asked for again.

Pre-registered in specs/trinet/tern_tc_retransmit_ax7203.t27. The runner,
tern_tc_generate_rt_ax7203.py, passes every constant in from the generated
tern_tc_retransmit_params.py; nothing here is a tunable.

WHY. The layer harness's run() (tern_tc_layer_ax7203.py) stops at the first short or unframed
read: "a lost frame makes the rest a guess". That is right for measuring the link, and it ended
the 2026-09-27 generation attempt in call 183 of 192 on a 56-byte hole in the answer stream
(TERN_TC_GENERATE.md). No answer in that run failed its tag, nonce, node id or value. This module
keeps every check the harness makes on an answer and changes one thing: an answer that did not
arrive, or arrived unreadable, is asked for again under a fresh nonce.

WHY THE NODE NEEDS NO CHANGE. fpga/portable/trinet_node_core.v keeps no nonce state: it latches
NONCE from the request and echoes it (nonce_b, lines 142-144 and the preimage), and it answers
every complete frame. A re-sent job is a new request to it. After a request byte is lost the
parser can sit inside a frame (it has no timeout, lines 134-152); FLUSH zero bytes finish any
partial frame and never start one, because a frame starts with AA 55. The key is locked after
setkey (line 217), so a mangled frame whose op byte reads 0x02 changes nothing.

WHY A RETRY CANNOT MASK A LIE. An answer is credited only when its tag verifies under the key over
(op, nonce, w, x, y, node) with the w and x this host sent for that nonce, and y equals the
host's own dot product. A tag that verifies over a wrong y is a lie and ends the run; so do a
second answer to one nonce, a status other than OK, and a verified answer from another node id.
What is retried is only what could not be verified: missing answers, unframed bytes, and frames
whose tag does not verify. Each job gets at most MAX_ATTEMPTS nonces, the run at most
MAX_RETRANSMITS retries and MAX_RESYNCS resyncs; past any of them the run fails.

HOW A LOSS IS FOUND.
  in order  The node answers in request order. An answer to nonce k means every nonce written
            before k and still in flight has no answer coming: those jobs are queued again.
  resync    A short read, a first byte that is not A5, or a nonce this run never wrote. The host
            stops writing, reads until the line is quiet, writes FLUSH zero bytes, reads until
            quiet again, and scans the bytes it collected for A5 frames whose nonce it wrote;
            each is checked exactly as above. Every nonce still in flight after that is lost.

    python3 tern_tc_retransmit.py --self-test

Author: Dmitrii Vasilev (@gHashTag)
"""
import collections
import os
import random
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import tern_tc_layer_ax7203 as h  # noqa: E402

DRAIN_CHUNK = 4096


class Budget:
    """State one board run shares across its calls: retry nonces, ceilings, the node pin, events."""

    def __init__(self, retry_base, max_attempts, max_retransmits, max_resyncs, flush_bytes,
                 keep_events=64):
        self.next_retry = retry_base
        self.max_attempts, self.max_retransmits = max_attempts, max_retransmits
        self.max_resyncs, self.flush_bytes = max_resyncs, flush_bytes
        self.node = None
        self.retransmits = self.resyncs = 0
        self.soft = dict(lost=0, unverified=0, foreign=0, late=0, scanned_skip=0)
        self.events, self.keep_events = [], keep_events
        self.calls = 0

    def event(self, msg):
        if len(self.events) < self.keep_events:
            self.events.append(f"call {self.calls}: {msg}")

    def summary(self):
        s = self.soft
        return (f"retransmitted jobs {self.retransmits} (ceiling {self.max_retransmits}), "
                f"resyncs {self.resyncs} (ceiling {self.max_resyncs}), lost {s['lost']}, "
                f"unverified {s['unverified']}, foreign frames {s['foreign']}, "
                f"late answers {s['late']}, bytes skipped while scanning {s['scanned_skip']}")


def _drain(link):
    out = bytearray()
    while True:
        b = link.read(DRAIN_CHUNK)
        out += b
        if len(b) < DRAIN_CHUNK:
            return bytes(out)


def run(link, jobs, rows_ref, key, window, first_nonce, budget, log=print):
    """Send jobs pipelined; re-request what is lost; stop at the first answer that is provably wrong.

    Returns the dict tern_tc_layer_ax7203.run() returns (counts, exact, rows, jobs, sent, answered,
    window, max_pause, pause_at, node, first_bad, per_matrix), so the generation runner's
    BoardDots reads it unchanged, plus `rt`, this call's share of the budget.
    """
    budget.calls += 1
    n = len(jobs)
    got = [None] * n
    attempts = [0] * n
    counts = dict(accepted=0, lie=0, status=0, node=0, duplicate=0, exhausted=0)
    issued = {}                                   # nonce -> job, every nonce this call wrote
    answered = set()                              # nonces that have had an answer
    inflight = collections.OrderedDict()          # nonce -> job, in write order
    queue = collections.deque(range(n))           # jobs to write; retries go to the front
    first_bad = []
    state = dict(stop=False, sent=0, retransmits=0, resyncs=0)
    max_pause, pause_at = 0.0, 0
    t_back = time.monotonic()

    def hard(kind, msg):
        counts[kind] += 1
        state["stop"] = True
        if len(first_bad) < 8:
            first_bad.append(msg)

    def lose(nonce, why):
        i = inflight.pop(nonce)
        budget.soft["lost"] += 1
        if got[i] is None and i not in queue:
            queue.appendleft(i)
        budget.event(f"nonce {nonce:#010x} (job {i}) {why}; job queued again")

    def settle(raw):
        """One 19-byte frame that starts with A5. False if its nonce was never written."""
        r = h.parse(raw)
        nonce = r["nonce"]
        i = issued.get(nonce)
        if i is None:
            return False
        if nonce in answered:
            hard("duplicate", f"nonce {nonce:#010x} answered twice: {raw.hex(' ')}")
            return True
        answered.add(nonce)
        if r["status"] != h.STATUS_OK:
            hard("status", f"nonce {nonce:#010x}: status {r['status']:#04x}")
            return True
        w, x, _row, _weight = jobs[i]
        nb = nonce.to_bytes(4, "little")
        tag_ok = r["tag"] == h.siphash24(
            h.receipt_preimage(h.OP_MAC32, nb, w, x, r["y"] & 0xFF, r["node_id"]), key)
        live = nonce in inflight
        if live:                                  # everything written before it is not coming
            for older in list(inflight):
                if older == nonce:
                    break
                lose(older, f"had no answer before nonce {nonce:#010x}")
        if not tag_ok:
            budget.soft["unverified"] += 1
            if live:
                lose(nonce, "answered with a tag that does not verify")
            return True
        if budget.node is None:
            budget.node = r["node_id"]
        if r["node_id"] != budget.node:
            hard("node", f"nonce {nonce:#010x}: node {r['node_id']:#010x} != "
                         f"{budget.node:#010x}: {raw.hex(' ')}")
            return True
        expect = h.golden_dot(w, x)
        if r["y"] != expect:
            hard("lie", f"nonce {nonce:#010x}: y={r['y']} expected {expect}, "
                        f"and the tag signs the wrong answer")
            return True
        if live:
            del inflight[nonce]
        if live and got[i] is None:
            got[i] = r["y"]
            counts["accepted"] += 1
        else:
            budget.soft["late"] += 1
        return True

    def scan(buf):
        pos = 0
        while pos + h.RESP_LEN <= len(buf) and not state["stop"]:
            if buf[pos] == h.MAGIC_RESP and settle(buf[pos:pos + h.RESP_LEN]):
                pos += h.RESP_LEN
            else:
                pos += 1
                budget.soft["scanned_skip"] += 1
        budget.soft["scanned_skip"] += max(0, len(buf) - pos) if not state["stop"] else 0

    def resync(raw, why):
        budget.resyncs += 1
        state["resyncs"] += 1
        if budget.resyncs > budget.max_resyncs:
            hard("exhausted", f"resync {budget.resyncs} > ceiling {budget.max_resyncs} ({why})")
            return
        buf = bytearray(raw) + _drain(link)
        link.write(bytes(budget.flush_bytes))
        buf += _drain(link)
        before = len(inflight)
        budget.event(f"resync ({why}): {len(buf)} bytes collected, {before} in flight")
        scan(bytes(buf))
        for nonce in list(inflight):
            lose(nonce, "had no verifiable answer by the end of a resync")

    while (queue or inflight) and not state["stop"]:
        while queue and len(inflight) < window and not state["stop"]:
            i = queue.popleft()
            if attempts[i] == 0:
                nonce = first_nonce + i
            else:
                if attempts[i] >= budget.max_attempts:
                    hard("exhausted", f"job {i} lost {attempts[i]} times (ceiling {budget.max_attempts})")
                    break
                if budget.retransmits >= budget.max_retransmits:
                    hard("exhausted", f"retransmit {budget.retransmits + 1} > ceiling "
                                      f"{budget.max_retransmits}")
                    break
                nonce = budget.next_retry
                budget.next_retry += 1
                budget.retransmits += 1
                state["retransmits"] += 1
            attempts[i] += 1
            w, x, _row, _weight = jobs[i]
            issued[nonce] = i
            inflight[nonce] = i
            link.write(h.request(h.OP_MAC32, nonce, w, x))
            state["sent"] += 1
        if state["stop"] or not inflight:
            continue
        t_read = time.monotonic()
        if t_read - t_back > max_pause:
            max_pause, pause_at = t_read - t_back, counts["accepted"]
        raw = link.read(h.RESP_LEN)
        t_back = time.monotonic()
        if len(raw) < h.RESP_LEN:
            resync(raw, f"short read, {len(raw)} bytes")
        elif raw[0] != h.MAGIC_RESP:
            resync(raw, f"unframed read {raw[:8].hex(' ')}")
        elif not settle(raw):
            budget.soft["foreign"] += 1
            resync(raw, f"frame with a nonce this call never wrote, {h.parse(raw)['nonce']:#010x}")

    acc, complete = {}, {}
    for (_w, _x, rid, weight), y in zip(jobs, got):
        if y is None:
            complete[rid] = False
        else:
            complete.setdefault(rid, True)
            acc[rid] = acc.get(rid, 0) + weight * y
    exact = sum(1 for rid, ref in enumerate(rows_ref)
                if complete.get(rid) and acc.get(rid) == ref[3])
    counts["missing"] = n - counts["accepted"]
    return dict(counts=counts, exact=exact, rows=len(rows_ref), jobs=n,
                sent=state["sent"], answered=counts["accepted"], window=window,
                max_pause=max_pause, pause_at=pause_at, node=budget.node,
                first_bad=first_bad + budget.events[-4:] if state["stop"] else first_bad,
                per_matrix=h._per_matrix(rows_ref, acc, complete),
                rt=dict(retransmits=state["retransmits"], resyncs=state["resyncs"]))


# ---------------------------------------------------------------------------
# Links for the rehearsal: the parser the node really has, and losses on either wire
# ---------------------------------------------------------------------------

class HuntingCell(h.RefCell):
    """h.RefCell behind trinet_node_core.v's frame parser (lines 134-152).

    RefCell cuts the request stream into 24-byte frames blindly, which is the node's behaviour
    only while no request byte is lost. This one hunts for AA 55, then takes 22 body bytes, with
    no timeout, as the RTL does, and answers every complete frame.
    """

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.fstate, self.body = 0, bytearray()

    def write(self, b):
        for c in b:
            if self.fstate == 0:
                self.fstate = 1 if c == 0xAA else 0
            elif self.fstate == 1:
                if c == 0x55:
                    self.fstate, self.body = 2, bytearray()
                elif c != 0xAA:
                    self.fstate = 0
            else:
                self.body.append(c)
                if len(self.body) == 22:
                    self._answer(b"\xaa\x55" + bytes(self.body))
                    self.fstate = 0


class RxLoss:
    """Drops answer bytes [at, at + count) for each (at, count), counted over the answer stream."""

    def __init__(self, inner, holes):
        self.inner, self.holes, self.pos = inner, sorted(holes), 0

    def write(self, b):
        self.inner.write(b)

    def read(self, n):
        out = bytearray()
        while len(out) < n:
            b = self.inner.read(n - len(out))
            if not b:
                break
            lo, self.pos = self.pos, self.pos + len(b)
            if any(a < self.pos and a + c > lo for a, c in self.holes):
                b = bytes(v for k, v in enumerate(b, lo)
                          if not any(a <= k < a + c for a, c in self.holes))
            out += b
        return bytes(out)


class TxLoss:
    """Drops request bytes at the given offsets, counted over the request stream."""

    def __init__(self, inner, drops):
        self.inner, self.drops, self.pos = inner, set(drops), 0

    def write(self, b):
        lo, self.pos = self.pos, self.pos + len(b)
        if any(lo <= d < self.pos for d in self.drops):
            b = bytes(v for k, v in enumerate(b, lo) if k not in self.drops)
        self.inner.write(b)

    def read(self, n):
        return self.inner.read(n)


# ---------------------------------------------------------------------------
# Self-test: what is recovered, what still stops the run, and that nothing unverified is credited
# ---------------------------------------------------------------------------

def self_test(retry_base=0x20000000, max_attempts=3, max_retransmits=256, max_resyncs=32,
              flush_bytes=24):
    ok = True

    def check(cond, what):
        nonlocal ok
        print(f"  {'ok  ' if cond else 'FAIL'} {what}")
        ok = ok and bool(cond)

    def budget():
        return Budget(retry_base, max_attempts, max_retransmits, max_resyncs, flush_bytes)

    def go(link, jobs, ref, window=24, b=None):
        b = b or budget()
        res = run(link, jobs, ref, h.TEST_KEY, window, h.FIRST_JOB_NONCE, b, log=lambda *_: None)
        passed = res["counts"]["accepted"] == len(jobs) and res["exact"] == res["rows"]
        return res, b, passed

    print("self-test tern_tc_retransmit (no board)")
    with tempfile.TemporaryDirectory() as scratch:
        path = os.path.join(scratch, "synthetic_tc02.bin")
        h.write_synthetic_tc02(path)
        small, _ = h.load_tc02(path, ("wk", "down"), layers={0})
    small = [(n, r[:6], i) for n, r, i in small]
    jobs, ref = h.build_jobs(small, "int8", 1, seed=3)
    R = h.RESP_LEN
    check(len(jobs) > 200, f"{len(jobs)} jobs, {len(ref)} rows (layer 0 wk and down, 6 rows each)")

    res, b, passed = go(h.RefCell(key=h.TEST_KEY), jobs, ref)
    check(passed and b.retransmits == 0 and b.resyncs == 0 and res["sent"] == len(jobs),
          "clean link: every receipt, every row, no retransmit, no resync")
    res, b, passed = go(HuntingCell(key=h.TEST_KEY), jobs, ref)
    check(passed and b.retransmits == 0, "the RTL parser model agrees with RefCell on a clean link")

    recovered = [
        ("16 bytes lost mid-answer (the 2026-09-27 slip)", RxLoss(h.RefCell(key=h.TEST_KEY), [(5 * R + 8, 16)])),
        ("56 bytes lost: 18 of one answer and 2 whole answers (the generation hole)",
         RxLoss(h.RefCell(key=h.TEST_KEY), [(40 * R + 1, 56)])),
        ("exactly one whole answer lost, stream still aligned", RxLoss(h.RefCell(key=h.TEST_KEY), [(7 * R, R)])),
        ("the last answer of the call lost", RxLoss(h.RefCell(key=h.TEST_KEY), [((len(jobs) - 1) * R, R)])),
        ("two holes 3 answers apart", RxLoss(h.RefCell(key=h.TEST_KEY), [(60 * R + 3, 20), (63 * R + 5, 30)])),
        ("one request byte lost (a w byte): the parser eats the next frame's magic",
         TxLoss(HuntingCell(key=h.TEST_KEY), [24 * 30 + 10])),
        ("a request's last byte lost: the next frame's AA completes it, and that next job is lost",
         TxLoss(HuntingCell(key=h.TEST_KEY), [24 * 90 + 23])),
        ("the call's last request loses its last byte: only the flush completes it (answer credited)",
         TxLoss(HuntingCell(key=h.TEST_KEY), [24 * len(jobs) - 1])),
        ("the call's last request loses a w byte: the flush completes it, the tag fails, asked again",
         TxLoss(HuntingCell(key=h.TEST_KEY), [24 * len(jobs) - 14])),
        ("a request's AA lost: the node never sees that frame", TxLoss(HuntingCell(key=h.TEST_KEY), [24 * 120])),
        ("a dropped answer (RefCell fault 'drop')", h.RefCell(key=h.TEST_KEY, fault="drop", fault_at=50)),
        ("an answer under a nonce never written (fault 'nonce')", h.RefCell(key=h.TEST_KEY, fault="nonce", fault_at=50)),
        ("one flipped tag bit (fault 'damage')", h.RefCell(key=h.TEST_KEY, fault="damage", fault_at=50)),
    ]
    for what, link in recovered:
        res, b, passed = go(link, jobs, ref)
        flush_only = "only the flush" in what
        check(passed and (b.retransmits == 0 and b.resyncs == 1 if flush_only else 0 < b.retransmits <= 8),
              f"recovered, {b.retransmits} retransmitted, {b.resyncs} resyncs: {what}")

    stops = [
        ("lie", "lie", "a wrong answer with a valid tag"),
        ("impersonate", "node", "a verified answer from another node id"),
        ("wrong_key", "exhausted", "a cell signing with another key (every tag fails)"),
    ]
    for fault, kind, what in stops:
        res, b, passed = go(h.RefCell(key=h.TEST_KEY, fault=fault, fault_at=50), jobs, ref)
        check(not passed and res["counts"][kind] > 0, f"still stops the run on {what} ('{kind}')")
    res, b, passed = go(RxLoss(h.RefCell(key=h.TEST_KEY, fault="lie", fault_at=80), [(20 * R + 4, 40)]), jobs, ref)
    check(not passed and res["counts"]["lie"] == 1, "a lie after a hole is still a lie")
    res, b, passed = go(h.RefCell(key=None), jobs, ref)
    check(not passed and res["counts"]["status"] == 1 and b.retransmits == 0,
          "an unkeyed cell (status 0x04) stops the run at its first answer, no retry")

    class Replay(h.RefCell):
        def _answer(self, fr):
            n0 = len(self.out)
            super()._answer(fr)
            if self.n == 60:
                self.out += self.out[n0:]
    res, b, passed = go(Replay(key=h.TEST_KEY), jobs, ref)
    check(not passed and res["counts"]["duplicate"] == 1, "one answer sent twice stops the run ('duplicate')")

    class Deaf(h.RefCell):                       # never answers job 70, under any nonce
        def _answer(self, fr):
            nonce = int.from_bytes(fr[3:7], "little")
            if nonce != h.FIRST_JOB_NONCE + 70 and nonce < retry_base:
                super()._answer(fr)
    res, b, passed = go(Deaf(key=h.TEST_KEY), jobs, ref)
    check(not passed and res["counts"]["exhausted"] == 1 and b.retransmits <= max_attempts,
          f"a job that is never answered stops the run after {max_attempts} attempts")
    res, b, passed = go(RxLoss(h.RefCell(key=h.TEST_KEY), [(k * 7 * R, R) for k in range(1, 40)]),
                        jobs, ref, b=Budget(retry_base, max_attempts, 5, max_resyncs, flush_bytes))
    check(not passed and res["counts"]["exhausted"] == 1 and b.retransmits == 5,
          "more losses than the retransmit ceiling stop the run at the ceiling")

    b = budget()
    rng = random.Random(27)
    stream = len(jobs) * R
    holes = [(rng.randrange(stream), rng.randrange(1, 60)) for _ in range(6)]
    res1, _, p1 = go(RxLoss(h.RefCell(key=h.TEST_KEY), holes), jobs, ref, b=b)
    res2, _, p2 = go(RxLoss(h.RefCell(key=h.TEST_KEY), holes), jobs, ref, b=b)
    check(p1 and p2 and b.next_retry == retry_base + b.retransmits and b.node == 0x5452494E,
          f"two calls share one budget: retry nonces continue ({b.retransmits} used), node pinned")

    # A lie is never credited. The lying answer can itself fall into a hole; then it never
    # arrives, the job is asked again, and the honest second answer is the one credited.
    stopped = clean = 0
    for seed in range(40):
        rng = random.Random(seed)
        holes = [(rng.randrange(stream), rng.randrange(1, 80)) for _ in range(rng.randrange(1, 5))]
        link = RxLoss(h.RefCell(key=h.TEST_KEY, fault="lie", fault_at=rng.randrange(len(jobs))), holes)
        res, b, passed = go(link, jobs, ref)
        stopped += not passed and res["counts"]["lie"] == 1 and sum(res["counts"][k] for k in
                                                                     ("node", "status", "duplicate", "exhausted")) == 0
        clean += passed and res["exact"] == res["rows"]
    check(stopped + clean == 40 and stopped >= 30,
          f"40 random hole patterns with a lying cell: {stopped} stopped on the lie, {clean} passed "
          f"because the lie itself fell into a hole and the re-asked job was answered honestly")
    print(f"self-test tern_tc_retransmit: {'PASS' if ok else 'FAIL'}")
    return ok


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        sys.exit(0 if self_test() else 1)
    print(__doc__)
    sys.exit(2)
