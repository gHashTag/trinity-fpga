#!/usr/bin/env python3
"""tern_tc_batch_runner.py -- the batched wire protocol's job stream, pipelined, losses asked for again.

The model-level rehearsal of the L2 design pinned by
specs/trinet/tern_tc_batch_ax7203.t27 (protocol-design; no RTL exists, nothing
here ran on hardware). tern_tc_batch_model.py proved one SETX and one DOT6
against one BatchCell, stop-and-wait. This runner is the missing consumer: it
drives whole matrix passes through BatchCell the way tern_tc_retransmit.py's
run() drove RefCell -- one window, nonces from one space, losses recovered
under fresh retry nonces -- and recombines every row against the int8 oracle.

WHAT IS NEW HERE BESIDES SCALE (and why each is pinned by a self-test check):
  * Mixed answer lengths. A SETX answer is the standard 19-byte frame; a DOT6
    answer is 24 bytes; both start with A5 and neither carries a length. The
    runner reads 19 bytes, then resolves the shape: the standard nonce sits at
    bytes 3..6, the DOT6 nonce at 8..11, and only a nonce this run issued is a
    shape witness. When both readings name issued nonces -- a genuine DOT6
    frame whose y bytes 2..5 happen to spell an issued little-endian nonce --
    the tag decides: an interpretation whose SipHash tag verifies is real
    (a false tag match is 2^-64); neither verifying is a resync, never a
    credit and never a stop. The self-test crafts exactly that collision and
    shows the run survives it (check "shape ambiguity").
  * Nonce accounting across both ops. SETX and DOT6 draw from one space
    (FIRST_JOB_NONCE + job index; retries from RETRY_BASE up, one Budget
    shared by every pass), so a nonce is never spent twice and the duplicate
    check covers both shapes.
  * Zero-plane skip. The host pinned x, so it knows which planes of a chunk
    are all-zero trits; it clears their mask bits (they would answer y = 0)
    and skips the DOT6 frame entirely when no plane is left. The preimage
    still MACs all 48 RAM bytes the node reads, mask or no mask, so skipping
    changes no receipt -- the check pins results identical to the unskipped
    run, frame counts lower.
  * Pass isolation for retries. Each pass runs to completion (all its jobs
    credited or the run stopped) before the next pass's SETX may overwrite
    the node's x RAM, so a late retry can never read the next pass's x and
    burn its receipt.

WHAT THIS DOES NOT SETTLE. The setkey exchange under loss (cells are pre-keyed
here; SETKEY keeps RefCell semantics and is exercised in the model's
self-test), out-of-range addressing (the model raises; the hunting cell drops
such garbage frames and the spec leaves the real behaviour to the RTL), and
every throughput number (the spec's projections are link arithmetic; a real
run gets its own pre-registration).

    python3 tern_tc_batch_runner.py --self-test
    python3 tern_tc_batch_runner.py --rehearsal

Author: Dmitrii Vasilev (@gHashTag)
"""
import argparse
import collections
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from trinet_mac32_conformance_ax7203 import (  # noqa: E402
    N_TRITS, STATUS_OK, golden_dot, pack_trits, siphash24,
)
from tern_tc_layer_ax7203 import (  # noqa: E402
    MAGIC_RESP, RESP_LEN, TEST_KEY, balanced_ternary, parse,
)
from tern_tc_retransmit import RxLoss, TxLoss  # noqa: E402  (byte-level, op-agnostic)
from tern_tc_batch_model import (  # noqa: E402
    BatchCell, S, dot6_preimage, dot6_request, parse_dot6, setx_preimage,
    setx_request,
)

PLANES = S["PLANES"]
MASK_ALL = S["DOT6_MASK_ALL"]
WINDOW = S["WINDOW"]
FIRST_JOB_NONCE = S["FIRST_JOB_NONCE"]
RETRY_BASE = S["RETRY_BASE"]
FLUSH_BYTES = S["FLUSH_BYTES"]
RT_CEILING = S["BATCH_RETRANSMITS_MAX"]     # 13: the design's whole-run loss bound
MAX_ATTEMPTS = 3                            # runner policy, as in tern_tc_retransmit
MAX_RESYNCS = 32                            # runner policy, as in tern_tc_retransmit
DRAIN_CHUNK = 4096

ZERO_CHUNK = b"\x00" * S["SETX_CHUNK_BYTES"]


# ---------------------------------------------------------------------------
# The workload: int8 passes decomposed exactly as mini_pass does
# ---------------------------------------------------------------------------

def build_pass(rng, name, rows_n, in_dim, zero_chunk=None):
    """One activation vector through rows_n ternary rows, in the harness's decomposition."""
    C = in_dim // N_TRITS
    q = [rng.randint(-127, 127) for _ in range(in_dim)]
    if zero_chunk is not None:
        for j in range(zero_chunk * N_TRITS, (zero_chunk + 1) * N_TRITS):
            q[j] = 0
    digs = [balanced_ternary(v) for v in q]
    plane_trits = [[d[k] for d in digs] for k in range(PLANES)]
    x8 = [[pack_trits(plane_trits[p][c * N_TRITS:(c + 1) * N_TRITS]) for c in range(C)]
          for p in range(PLANES)]
    rows = [[rng.choice((-1, 0, 1)) for _ in range(in_dim)] for _ in range(rows_n)]
    w8 = [[pack_trits(row[c * N_TRITS:(c + 1) * N_TRITS]) for c in range(C)] for row in rows]
    oracle = [sum(w * v for w, v in zip(row, q)) for row in rows]
    return dict(name=name, R=rows_n, C=C, x8=x8, w8=w8, oracle=oracle,
                zero_chunk=zero_chunk)


def rehearsal_passes(seed=0xA7203):
    """The pair-shaped workload: a 320-wide pass and an 864-wide (RAM-depth) pass."""
    rng = random.Random(seed)
    return [build_pass(rng, "wq", 16, 320), build_pass(rng, "down", 16, 864)]


# ---------------------------------------------------------------------------
# Budget, shared by every pass of one run
# ---------------------------------------------------------------------------

class BatchBudget:
    """State one run shares across its passes: retry nonces, ceilings, the node pin, events."""

    def __init__(self, retry_base=RETRY_BASE, max_attempts=MAX_ATTEMPTS,
                 max_retransmits=RT_CEILING, max_resyncs=MAX_RESYNCS,
                 flush_bytes=FLUSH_BYTES, keep_events=64):
        self.next_retry = retry_base
        self.max_attempts, self.max_retransmits = max_attempts, max_retransmits
        self.max_resyncs, self.flush_bytes = max_resyncs, flush_bytes
        self.node = None
        self.retransmits = self.resyncs = 0
        self.soft = dict(lost=0, unverified=0, late=0, shape_both=0, scanned_skip=0)
        self.events, self.keep_events = [], keep_events

    def event(self, msg):
        if len(self.events) < self.keep_events:
            self.events.append(msg)

    def summary(self):
        s = self.soft
        return (f"retransmitted jobs {self.retransmits} (ceiling {self.max_retransmits}), "
                f"resyncs {self.resyncs} (ceiling {self.max_resyncs}), lost {s['lost']}, "
                f"unverified {s['unverified']}, late answers {s['late']}, "
                f"both-shape frames {s['shape_both']}, bytes skipped while scanning {s['scanned_skip']}")


def _drain(link):
    out = bytearray()
    while True:
        b = link.read(DRAIN_CHUNK)
        out += b
        if len(b) < DRAIN_CHUNK:
            return bytes(out)


# ---------------------------------------------------------------------------
# The runner
# ---------------------------------------------------------------------------

def run_pass(link, pss, key, budget, window=WINDOW, first_nonce=FIRST_JOB_NONCE,
             skip_zero=False, pass_index=0, log=lambda *_: None):
    """One matrix pass pipelined; re-request what is lost; stop at the first provably wrong answer.

    Jobs: every (plane, chunk) SETX upload first, then every (row, chunk) DOT6,
    so the node's RAM holds the pass's x before any dot reads it (requests are
    answered in order; a retry of an earlier job re-sends identical bytes).
    With skip_zero, all-zero plane chunks lose their mask bit and a chunk with
    no live plane loses its frame; skipped chunks contribute y = 0.

    Returns dict(counts, exact, rows, sent, answered, window, node, first_bad,
    rt, per_pass, skipped, frames_now, frames_batched).
    """
    R, C = pss["R"], pss["C"]
    jobs, skipped = [], 0
    for p in range(PLANES):
        for c in range(C):
            jobs.append(("setx", p, c, pss["x8"][p][c]))
    for rid in range(R):
        for c in range(C):
            mask = MASK_ALL
            if skip_zero:
                for p in range(PLANES):
                    if pss["x8"][p][c] == ZERO_CHUNK:
                        mask &= ~(1 << p)
                if mask == 0:
                    skipped += 1                       # no plane can move this chunk's dots
                    continue
            believed = [pss["x8"][p][c] for p in range(PLANES)]
            jobs.append(("dot6", rid, c, pss["w8"][rid][c], mask, believed))
    n = len(jobs)
    got = [None] * n
    attempts = [0] * n
    counts = dict(accepted=0, lie=0, status=0, node=0, duplicate=0, exhausted=0)
    issued = {}                                   # nonce -> job index, both shapes
    answered = set()
    inflight = collections.OrderedDict()          # nonce -> job index, in write order
    queue = collections.deque(range(n))
    first_bad = []
    state = dict(stop=False, sent=0, sent_setx=0, sent_dot6=0, retransmits=0, resyncs=0)

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

    def preimage_and_expect(job, nonce_b, r):
        """(preimage, expected y) for the job this nonce was issued for, frame's own y/node."""
        if job[0] == "setx":
            _op, plane, chunk, x8 = job
            return (setx_preimage(nonce_b, plane, chunk, x8, r["y"], r["node_id"]),
                    chunk)                        # y echoes the chunk index
        _op, rid, chunk, w8, mask, believed = job
        expect = [golden_dot(w8, believed[p]) if mask >> p & 1 else 0
                  for p in range(PLANES)]
        return (dot6_preimage(nonce_b, w8, chunk, mask, b"".join(believed),
                              r["ys"], r["node_id"]), expect)

    def peek(raw, shape, nonce):
        """Pure verdict for one shape reading of `raw`; no state changes. tag_ok decides reality."""
        job = jobs[issued[nonce]]
        if shape == "std":
            if job[0] != "setx" or len(raw) < RESP_LEN:
                return dict(tag_ok=False, dup=nonce in answered, status_ok=False)
            r = parse(raw)
        else:
            if job[0] != "dot6" or len(raw) < S["RESP_DOT6_LEN"]:
                return dict(tag_ok=False, dup=nonce in answered, status_ok=False)
            r = parse_dot6(raw)
        pre, expect = preimage_and_expect(job, nonce.to_bytes(4, "little"), r)
        y = r["y"] if shape == "std" else r["ys"]
        return dict(tag_ok=r["tag"] == siphash24(pre, key), dup=nonce in answered,
                    status_ok=r["status"] == STATUS_OK, y_ok=y == expect,
                    node_id=r["node_id"], is_setx=job[0] == "setx", job=job)

    def settle(raw, shape, nonce):
        """One frame already shaped; every check the model's BatchHost makes, plus loss inference."""
        job = jobs[issued[nonce]]
        if (shape == "std") != (job[0] == "setx"):
            budget.soft["unverified"] += 1        # shape witness against the wrong job kind
            if nonce in inflight:
                lose(nonce, "shaped as the other op")
            return True
        r = parse(raw) if shape == "std" else parse_dot6(raw)
        if nonce in answered:
            hard("duplicate", f"nonce {nonce:#010x} answered twice: {raw.hex(' ')}")
            return True
        answered.add(nonce)
        if r["status"] != STATUS_OK:
            hard("status", f"nonce {nonce:#010x}: status {r['status']:#04x}")
            return True
        pre, expect = preimage_and_expect(job, nonce.to_bytes(4, "little"), r)
        tag_ok = r["tag"] == siphash24(pre, key)
        live = nonce in inflight                   # everything written before it is not coming
        if live:
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
        y = r["y"] if shape == "std" else r["ys"]
        if y != expect:
            hard("lie", f"nonce {nonce:#010x}: y={y} expected {expect}, "
                        f"and the tag signs the wrong answer")
            return True
        if live:
            del inflight[nonce]
            i = issued[nonce]
            if got[i] is None:
                got[i] = True if shape == "std" else r["ys"]
                counts["accepted"] += 1
        else:
            budget.soft["late"] += 1
        return True

    def read_frame():
        """Read 19 bytes; resolve the shape by issued nonces; the tag breaks ties."""
        raw = link.read(RESP_LEN)
        if len(raw) < RESP_LEN or raw[0] != MAGIC_RESP:
            return ("resync", raw)
        n19 = int.from_bytes(raw[3:7], "little")
        n24 = int.from_bytes(raw[8:12], "little")
        has19, has24 = n19 in issued, n24 in issued
        if not has19 and not has24:
            return ("resync", raw)
        if has19 and not has24:
            return ("std", raw)
        raw24 = raw + link.read(S["RESP_DOT6_LEN"] - RESP_LEN)
        if len(raw24) < S["RESP_DOT6_LEN"]:
            return ("resync", raw24)              # a DOT6 shape witness cut short
        if has19 and has24:
            budget.soft["shape_both"] += 1
            v19, v24 = peek(raw, "std", n19), peek(raw24, "dot6", n24)
            if v19["tag_ok"] and not v24["tag_ok"]:
                return ("std", raw)
            if v24["tag_ok"]:
                return ("dot6", raw24)            # only a real DOT6 answer verifies here
            budget.event(f"nonce {n19:#010x}/{n24:#010x}: both shapes read, neither verifies")
            return ("resync", raw24)
        return ("dot6", raw24)

    def scan(buf):
        pos = 0
        while pos + RESP_LEN <= len(buf) and not state["stop"]:
            if buf[pos] != MAGIC_RESP:
                pos += 1
                budget.soft["scanned_skip"] += 1
                continue
            n19 = (int.from_bytes(buf[pos + 3:pos + 7], "little")
                   if pos + 7 <= len(buf) else None)
            n24 = (int.from_bytes(buf[pos + 8:pos + 12], "little")
                   if pos + 12 <= len(buf) else None)
            used = 0
            if n19 in issued and pos + RESP_LEN <= len(buf):
                v = peek(buf[pos:pos + RESP_LEN], "std", n19)
                if v["tag_ok"] or not (n24 in issued and pos + S["RESP_DOT6_LEN"] <= len(buf)):
                    settle(buf[pos:pos + RESP_LEN], "std", n19)
                    used = RESP_LEN
            if not used and n24 in issued and pos + S["RESP_DOT6_LEN"] <= len(buf):
                v = peek(buf[pos:pos + S["RESP_DOT6_LEN"]], "dot6", n24)
                if v["tag_ok"] or n19 not in issued:
                    settle(buf[pos:pos + S["RESP_DOT6_LEN"]], "dot6", n24)
                    used = S["RESP_DOT6_LEN"]
            pos += used if used else 1
            if not used:
                budget.soft["scanned_skip"] += 1
        if not state["stop"]:
            budget.soft["scanned_skip"] += len(buf) - pos if pos < len(buf) else 0

    def resync(raw, why):
        budget.resyncs += 1
        state["resyncs"] += 1
        if budget.resyncs > budget.max_resyncs:
            hard("exhausted", f"resync {budget.resyncs} > ceiling {budget.max_resyncs} ({why})")
            return
        buf = bytearray(raw) + _drain(link)
        link.write(bytes(budget.flush_bytes))
        buf += _drain(link)
        budget.event(f"resync ({why}): {len(buf)} bytes collected, {len(inflight)} in flight")
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
                    hard("exhausted", f"job {i} lost {attempts[i]} times "
                                      f"(ceiling {budget.max_attempts})")
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
            job = jobs[i]
            if job[0] == "setx":
                link.write(setx_request(nonce, job[1], job[2], job[3]))
                state["sent_setx"] += 1
            else:
                link.write(dot6_request(nonce, job[3], job[2], job[4]))
                state["sent_dot6"] += 1
            issued[nonce] = i
            inflight[nonce] = i
            state["sent"] += 1
        if state["stop"] or not inflight:
            continue
        shape, raw = read_frame()
        if shape == "resync":
            resync(raw, f"{'short read' if len(raw) < RESP_LEN else 'unframed'}, "
                        f"{len(raw)} bytes")
        elif shape == "std":
            settle(raw, "std", int.from_bytes(raw[3:7], "little"))
        else:
            settle(raw, "dot6", int.from_bytes(raw[8:12], "little"))

    acc = [0] * R
    complete = [True] * R
    for j, job in enumerate(jobs):
        if job[0] != "dot6":
            continue
        rid, ys = job[1], got[j]
        if ys is None:
            complete[rid] = False
        else:
            acc[rid] += sum(3 ** p * y for p, y in enumerate(ys))
    exact = sum(1 for rid in range(R) if complete[rid] and acc[rid] == pss["oracle"][rid])
    counts["missing"] = n - counts["accepted"]
    frames_now = R * PLANES * C
    return dict(counts=counts, exact=exact, rows=R, sent=state["sent"],
                sent_setx=state["sent_setx"], sent_dot6=state["sent_dot6"],
                answered=counts["accepted"], window=window, node=budget.node,
                first_bad=first_bad + budget.events[-4:] if state["stop"] else first_bad,
                rt=dict(retransmits=state["retransmits"], resyncs=state["resyncs"]),
                per_pass=dict(name=pss["name"], R=R, C=C, exact=exact, skipped=skipped),
                skipped=skipped, frames_now=frames_now,
                frames_batched=state["sent_setx"] + state["sent_dot6"] - state["retransmits"])


def run(link, passes, key=TEST_KEY, budget=None, skip_zero=False, log=lambda *_: None):
    """Every pass through one shared Budget: retry nonces continue, the node pins once."""
    budget = budget or BatchBudget()
    out = []
    for pi, pss in enumerate(passes):
        out.append(run_pass(link, pss, key, budget, skip_zero=skip_zero,
                            pass_index=pi, log=log))
    return out, budget


# ---------------------------------------------------------------------------
# Links for the rehearsal: the parser the node really has, on top of BatchCell
# ---------------------------------------------------------------------------

class HuntingParser:
    """trinet_node_core.v's frame parser (lines 134-152) as a mixin: hunt AA 55, take 22 bytes."""

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
                    fr = b"\xaa\x55" + bytes(self.body)
                    self.fstate = 0
                    try:
                        self._answer(fr)
                    except ValueError:
                        pass        # garbage landed out of the model's RAM; the spec leaves
                                   # the real node's answer to the RTL, so this rehearsal drops it

    def __init_mixin__(self):
        self.fstate, self.body = 0, bytearray()


class HuntingBatchCell(HuntingParser, BatchCell):
    """BatchCell behind the hunting parser, for request-byte losses."""

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.__init_mixin__()


# ---------------------------------------------------------------------------
# Rehearsal: one honest link, one that loses, the same numbers out
# ---------------------------------------------------------------------------

def rehearsal(passes=None, seed=0xA7203):
    """The pair: honest link, then the same passes over holes in both wires."""
    pss = passes if passes is not None else rehearsal_passes(seed)
    honest, b1 = run(BatchCell(key=TEST_KEY), pss)
    ok1 = all(r["exact"] == r["rows"] for r in honest) and b1.retransmits == 0
    n_setx = sum(PLANES * p["C"] for p in pss)
    n_dot6 = sum(p["R"] * p["C"] for p in pss)
    holes = [(7 * RESP_LEN + 4, 12),                      # mid SETX answer
             (n_setx * RESP_LEN + 10 * 24 + 6, 16),       # across two DOT6 answers
             (n_setx * RESP_LEN + (n_dot6 - 1) * 24, 24)]  # the last DOT6 answer
    corrupt, b2 = run(RxLoss(BatchCell(key=TEST_KEY), holes), pss)
    ok2 = (all(r["exact"] == r["rows"] for r in corrupt) and b2.retransmits > 0
           and [r["exact"] for r in corrupt] == [r["exact"] for r in honest])
    return dict(honest_ok=ok1, corrupt_ok=ok2, honest=honest, corrupt=corrupt,
                b1=b1, b2=b2, holes=holes)


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

def self_test():
    ok = True

    def check(cond, what):
        nonlocal ok
        print(f"  {'ok  ' if cond else 'FAIL'} {what}")
        ok = ok and bool(cond)

    def go(link, pss, budget=None, **kw):
        res, b = run(link, pss, budget=budget, **kw)
        passed = all(r["exact"] == r["rows"] for r in res)
        return res, b, passed

    print("self-test tern_tc_batch_runner (no board, no RTL)")
    check(WINDOW == 24 and RT_CEILING == 13 and FLUSH_BYTES == 24
          and RETRY_BASE == 0x20000000 and FIRST_JOB_NONCE == 65536,
          "constants come from the spec's params (window 24, ceiling 13, flush 24)")

    pss = rehearsal_passes()
    res, b, passed = go(BatchCell(key=TEST_KEY), pss)
    n_setx = sum(PLANES * p["C"] for p in pss)
    n_dot6 = sum(p["R"] * p["C"] for p in pss)
    check(passed and all(r["counts"]["accepted"] == r["sent"] == r["frames_batched"]
                         for r in res) and b.retransmits == 0 and b.resyncs == 0,
          f"clean link, two passes: every receipt ({res[0]['frames_batched']}+"
          f"{res[1]['frames_batched']} frames), every row, no retransmit, no resync")
    check(all(r["sent_setx"] == PLANES * p["C"] and r["sent_dot6"] == p["R"] * p["C"]
              and r["frames_now"] == p["R"] * PLANES * p["C"]
              and r["frames_now"] > 4 * r["frames_batched"] for r, p in zip(res, pss)),
          "frame economy: SETX {PLANES}xC then RxC DOT6 per pass, >4x fewer than today")
    check(b.next_retry == RETRY_BASE and b.node == 0x5452494E,
          "one budget across both passes: retry space untouched, node pinned once")

    res2, b2, passed2 = go(HuntingBatchCell(key=TEST_KEY), pss)
    check(passed2 and [r["exact"] for r in res2] == [r["exact"] for r in res]
          and b2.retransmits == 0,
          "the RTL hunting parser agrees with the aligned model on a clean link")

    one = [build_pass(random.Random(7), "one", 12, 320)]

    def holes_at(specs):
        return RxLoss(BatchCell(key=TEST_KEY), specs)

    cases = [
        ("12 bytes lost mid SETX answer", holes_at([(7 * RESP_LEN + 4, 12)]), (1, 6)),
        ("a whole DOT6 answer lost, stream still aligned",
         holes_at([(PLANES * 10 * RESP_LEN + 5 * 24, 24)]), (1, 6)),
        ("16 bytes lost across two DOT6 answers",
         holes_at([(PLANES * 10 * RESP_LEN + 10 * 24 + 6, 16)]), (1, 8)),
        ("the last answer of the pass lost",
         holes_at([(PLANES * 10 * RESP_LEN + (12 * 10 - 1) * 24, 24)]), (1, 6)),
        ("two holes, one in each phase",
         holes_at([(3 * RESP_LEN + 2, 9), (PLANES * 10 * RESP_LEN + 30 * 24 + 3, 20)]), (2, 10)),
        ("a flipped tag bit on a DOT6 (fault damage)",
         BatchCell(key=TEST_KEY, fault="damage", fault_at=5), (1, 8)),
        ("a swallowed DOT6 answer (fault drop)",
         BatchCell(key=TEST_KEY, fault="drop", fault_at=5), (1, 6)),
        ("an answer under a nonce never issued (fault nonce)",
         BatchCell(key=TEST_KEY, fault="nonce", fault_at=5), (1, 8)),
    ]
    for what, link, lo_hi in cases:
        res, b, passed = go(link, one)
        lo, hi = lo_hi
        check(passed and lo <= b.retransmits <= hi and b.resyncs <= 3,
              f"recovered, {b.retransmits} retransmitted, {b.resyncs} resyncs: {what}")

    tx = [
        ("one request byte lost (a w byte): the parser eats the next frame's magic",
         TxLoss(HuntingBatchCell(key=TEST_KEY), [24 * 40 + 10]), (1, 8)),
        ("a request's last byte lost: the frame limps, the parser mis-answers it",
         TxLoss(HuntingBatchCell(key=TEST_KEY), [24 * 111]), (1, 8)),
        ("a request's AA lost: the node never sees that frame",
         TxLoss(HuntingBatchCell(key=TEST_KEY), [24 * 150]), (1, 8)),
    ]
    for what, link, lo_hi in tx:
        res, b, passed = go(link, one)
        lo, hi = lo_hi
        check(passed and lo <= b.retransmits + b.resyncs <= hi,
              f"recovered, {b.retransmits} retransmitted, {b.resyncs} resyncs: {what}")

    # The shape ambiguity, crafted: a DOT6 frame whose y bytes 2..5 spell an
    # issued little-endian nonce, so the 19-byte read names two live shapes.
    found = None
    for t in range(500):
        p = build_pass(random.Random(1000 + t), "amb", 8, 64)
        for rid in range(p["R"]):
            for c in range(p["C"]):
                ys = [golden_dot(p["w8"][rid][c], p["x8"][pl][c]) for pl in range(PLANES)]
                # the spelled nonce must be a SETX-phase nonce (below PLANES*C): those
                # are all issued from the first window on, so the both-shape read is
                # guaranteed while the pass runs, not a matter of timing
                if (ys[5] & 0xFF) == 0 and (ys[4] & 0xFF) == 1 and (ys[3] & 0xFF) == 0 \
                        and 0 <= (ys[2] & 0xFF) < PLANES * p["C"]:
                    found = (t, rid, c, ys)
                    break
            if found:
                break
        if found:
            break
    check(found is not None, "a workload with a y-nonce collision exists (search found one)")
    if found:
        t, rid, c, ys = found
        p = build_pass(random.Random(1000 + t), "amb", 8, 64)
        res, b, passed = go(BatchCell(key=TEST_KEY), [p])
        check(passed and b.soft["shape_both"] >= 1
              and res[0]["counts"]["status"] == 0 and res[0]["counts"]["duplicate"] == 0,
              f"the colliding frame (ys[2..5]={ys[2:6]} spell an issued nonce) settles by "
              f"tag, not by a false status/duplicate stop ({b.soft['shape_both']} both-shape frames)")

    stops = [
        ("lie", "lie", "a wrong y byte with a valid tag"),
        ("wrong_key", "exhausted", "a cell signing with another key"),
    ]
    for fault, kind, what in stops:
        res, b, passed = go(BatchCell(key=TEST_KEY, fault=fault, fault_at=5), one)
        check(not passed and sum(r["counts"][kind] for r in res) > 0,
              f"still stops the run on {what} ('{kind}')")
    res, b, passed = go(BatchCell(key=None), one)
    check(not passed and res[0]["counts"]["status"] == 1 and b.retransmits == 0,
          "an unkeyed cell (status 0x04) stops the run at its first answer, no retry")

    res, b, passed = go(BatchCell(key=TEST_KEY, fault="replay", fault_at=6), one)
    check(not passed and res[0]["counts"]["duplicate"] == 1,
          "one DOT6 answer served twice stops the run ('duplicate')")

    res, b, passed = go(BatchCell(key=TEST_KEY, fault="ram_drift", fault_at=3), one)
    check(not passed and res[0]["counts"]["exhausted"] == 1
          and res[0]["exact"] < res[0]["rows"],
          "RAM drift after an honest SETX is never credited: retries burn out and the run stops")

    rng = random.Random(0xB47C)
    base = build_pass(rng, "sparse", 12, 320, zero_chunk=1)
    res_a, _, p_a = go(BatchCell(key=TEST_KEY), [base])
    res_b, _, p_b = go(BatchCell(key=TEST_KEY), [base], skip_zero=True)
    check(p_a and p_b and res_a[0]["exact"] == res_b[0]["exact"]
          and res_b[0]["skipped"] == base["R"]
          and res_b[0]["sent_dot6"] == res_a[0]["sent_dot6"] - base["R"],
          f"zero-plane skip: identical rows, the all-zero chunk's {base['R']} DOT6 frames skipped")

    stopped = clean = 0
    for seed in range(6):
        rng = random.Random(seed)
        small = build_pass(rng, "sweep", 6, 64)
        stream = (PLANES * small["C"]) * RESP_LEN + small["R"] * small["C"] * 24
        holes = [(rng.randrange(stream), rng.randrange(1, 40)) for _ in range(2)]
        link = RxLoss(BatchCell(key=TEST_KEY, fault="lie", fault_at=3), holes)
        res, b, passed = go(link, [small])
        stopped += not passed and res[0]["counts"]["lie"] == 1
        clean += passed and res[0]["exact"] == res[0]["rows"]
    for seed in range(8):
        rng = random.Random(100 + seed)
        small = build_pass(rng, "sweep", 6, 64)
        stream = (PLANES * small["C"]) * RESP_LEN + small["R"] * small["C"] * 24
        holes = [(rng.randrange(stream), rng.randrange(1, 40)) for _ in range(2)]
        res, b, passed = go(RxLoss(BatchCell(key=TEST_KEY), holes), [small])
        clean += passed and res[0]["exact"] == res[0]["rows"]
    check(stopped >= 2 and stopped + clean == 14,
          f"14 random hole patterns: {stopped} stopped on the lie, {clean} passed clean")

    pair = rehearsal(pss)
    check(pair["honest_ok"] and pair["corrupt_ok"] and pair["b2"].retransmits >= 2
          and [r["exact"] for r in pair["corrupt"]] == [r["exact"] for r in pair["honest"]],
          f"rehearsal pair: honest and corrupt links agree on every row "
          f"({pair['b2'].retransmits} retransmits over 3 holes)")
    print(f"self-test: {'PASS' if ok else 'FAIL'}")
    return ok


def main():
    a = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    a.add_argument("--self-test", action="store_true")
    a.add_argument("--rehearsal", action="store_true",
                   help="run the honest/corrupt pair once and print its summary")
    args = a.parse_args()
    if args.self_test:
        return 0 if self_test() else 1
    if args.rehearsal:
        pair = rehearsal()
        print(f"honest: {'PASS' if pair['honest_ok'] else 'FAIL'}   "
              f"corrupt: {'PASS' if pair['corrupt_ok'] else 'FAIL'}")
        print(f"  honest  {pair['b1'].summary()}")
        print(f"  corrupt {pair['b2'].summary()}")
        return 0 if pair["honest_ok"] and pair["corrupt_ok"] else 1
    print(__doc__)
    return 0


if __name__ == "__main__":
    sys.exit(main())
