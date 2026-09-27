#!/usr/bin/env python3
"""tern_tc_reopen.py -- close and reopen the serial port when a resync meets a silent line.

Pre-registered in specs/trinet/tern_tc_reopen_ax7203.t27. The runner,
tern_tc_generate_reopen_ax7203.py, passes every constant in from the generated
tern_tc_reopen_params.py; nothing here is a tunable.

WHY. The retransmit run of 2026-09-27 (TERN_TC_RETRANSMIT.md) stopped in call 145 of 192. A short
read collected 11 bytes; the next two resyncs collected 0 bytes each. The protocol's resync (FLUSH
zero bytes, then the same jobs asked again on the same open port) brought nothing back, and one job
reached its attempts ceiling. Four minutes later a freshly opened port gave 3840/3840 with the key
still held, so the FPGA had not been reconfigured. The hypothesis this module tests: closing and
reopening the port inside the run clears such a stop.

WHAT CHANGES. Only the link. tern_tc_retransmit.py decides what is lost, what is asked again and what
stops the run; it is imported unchanged and pinned by sha256. ReopenLink sits between it and the port.

HOW THE LINK KNOWS. The protocol writes FLUSH zero bytes once per resync and nowhere else: a request
and a setkey frame both start with AA 55. ReopenLink counts the answer bytes it has returned since the
last flush. A flush after zero bytes means the line was silent through a whole resync (the short read
that started it and the drain before the flush) and everything since the previous flush. Then, before
it passes the flush on, it closes the port, waits and opens the port again; the wait doubles with each
reopen. An ordinary hole never triggers it, because the answers around a hole are bytes. The
self-test checks the coupling: in every scenario the link sees exactly one flush per resync.

WHAT IT CANNOT DO. It cannot credit anything. The protocol still checks every answer; a job whose
answer was lost across a reopen is asked again under a fresh nonce and counts toward its attempts.
Past MAX_REOPENS the link raises ReopenExhausted, and the run fails.

    python3 tern_tc_reopen.py --self-test    # reference cells, no port
    python3 tern_tc_reopen.py --pty-test     # the real SerialLink closed and reopened, over a pseudo-terminal

Author: Dmitrii Vasilev (@gHashTag)
"""
import os
import sys
import tempfile
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import tern_tc_layer_ax7203 as h  # noqa: E402
import tern_tc_retransmit as rt  # noqa: E402


class ReopenExhausted(RuntimeError):
    """More reopens than the pre-registered ceiling: the run fails."""


class ReopenLink:
    """The protocol's link, with a port that is closed and reopened on a silent resync."""

    def __init__(self, open_port, close_port, flush_bytes, wait_s, max_reopens,
                 sleep=time.sleep, log=print):
        self.open_port, self.close_port = open_port, close_port
        self.flush = bytes(flush_bytes)
        self.wait_s, self.max_reopens = wait_s, max_reopens
        self.sleep, self.log = sleep, log
        self.port = open_port()
        self.rx_since_flush = 0
        self.flushes = self.reopens = 0
        self.waited = []
        self.events = []

    def read(self, n):
        b = self.port.read(n)
        self.rx_since_flush += len(b)
        return b

    def write(self, b):
        if b == self.flush:
            self.flushes += 1
            if self.rx_since_flush == 0:
                self._reopen()
            self.rx_since_flush = 0
        self.port.write(b)

    def _reopen(self):
        if self.reopens >= self.max_reopens:
            raise ReopenExhausted(f"reopen {self.reopens + 1} > ceiling {self.max_reopens} "
                                  f"(flush {self.flushes} met a silent line again)")
        wait = self.wait_s * 2 ** self.reopens
        self.reopens += 1
        t0 = time.monotonic()
        self.close_port(self.port)
        self.sleep(wait)
        self.port = self.open_port()
        msg = (f"reopen {self.reopens}: flush {self.flushes} after 0 bytes since the last flush; "
               f"port closed, {wait} s, opened again ({time.monotonic() - t0:.2f} s)")
        self.waited.append(wait)
        self.events.append(msg)
        self.log("  " + msg)

    def summary(self):
        return f"reopens {self.reopens} (ceiling {self.max_reopens}), flushes seen {self.flushes}"


def serial_link(port, baud, wait_s, max_reopens, flush_bytes, log=print):
    """The board link: h.SerialLink, the harness's own open, behind ReopenLink."""
    return ReopenLink(lambda: h.SerialLink(port, baud), lambda p: p.ser.close(), flush_bytes,
                      wait_s, max_reopens, log=log)


# ---------------------------------------------------------------------------
# Rehearsal port: a direction goes dead until the port is reopened
# ---------------------------------------------------------------------------

class Stall:
    """From a scheduled byte on, one direction delivers nothing until reopen() is called.

    rx_at: offsets in the delivered answer stream. From each, the cell still answers, but nothing
    reaches the host (the retransmit run's shape: 11 bytes of an answer, then silence). tx_at:
    offsets in the request stream. From each, no request byte reaches the cell. reopen() ends a stall
    and drops what the cell produced meanwhile, as h.SerialLink's reset_input_buffer does on a real
    open. The cell's frame parser keeps its state across a reopen: the FPGA is not reset by it.
    """

    def __init__(self, inner, rx_at=(), tx_at=()):
        self.inner = inner
        self.rx_at, self.tx_at = sorted(rx_at), sorted(tx_at)
        self.rx_pos = self.tx_pos = 0
        self.rx_dead = self.tx_dead = False
        self.entered = self.cleared = 0

    def write(self, b):
        lo, self.tx_pos = self.tx_pos, self.tx_pos + len(b)
        if not self.tx_dead and self.tx_at and self.tx_at[0] < self.tx_pos:
            at = max(self.tx_at.pop(0), lo)
            self.inner.write(b[:at - lo])
            self.tx_dead, self.entered = True, self.entered + 1
            return
        if not self.tx_dead:
            self.inner.write(b)

    def read(self, n):
        b = self.inner.read(n)
        if self.rx_dead:
            return b""
        lo = self.rx_pos
        if self.rx_at and self.rx_at[0] < lo + len(b):
            at = max(self.rx_at.pop(0), lo)
            b = b[:at - lo]
            self.rx_dead, self.entered = True, self.entered + 1
        self.rx_pos += len(b)
        return b

    def reopen(self):
        if self.rx_dead or self.tx_dead:
            self.cleared += 1
        self.rx_dead = self.tx_dead = False
        while self.inner.read(4096):
            pass
        return self


def stall_link(stall, flush_bytes, wait_s, max_reopens, sleep=lambda s: None, log=print):
    """The rehearsal link: ReopenLink over a Stall, with the waits recorded instead of slept."""
    return ReopenLink(lambda: stall.reopen(), lambda p: None, flush_bytes, wait_s, max_reopens,
                      sleep=sleep, log=log)


class Dead(Stall):
    """A stall that no reopen clears: the answer stream stays silent from rx_at[0] on."""

    def reopen(self):
        while self.inner.read(4096):
            pass
        return self


# ---------------------------------------------------------------------------
# Self-test: the reopen fires on a silent resync, never on a hole, and never credits anything
# ---------------------------------------------------------------------------

def self_test(retry_base=0x20000000, max_attempts=4, max_retransmits=256, max_resyncs=32,
              flush_bytes=24, wait_s=2, max_reopens=4):
    ok = True

    def check(cond, what):
        nonlocal ok
        print(f"  {'ok  ' if cond else 'FAIL'} {what}")
        ok = ok and bool(cond)

    def budget(max_rt=max_retransmits):
        return rt.Budget(retry_base, max_attempts, max_rt, max_resyncs, flush_bytes)

    def go(port, jobs, ref, reopens=max_reopens, b=None):
        b = b or budget()
        link = stall_link(port, flush_bytes, wait_s, reopens, log=lambda *_: None)
        err = None
        try:
            res = rt.run(link, jobs, ref, h.TEST_KEY, 24, h.FIRST_JOB_NONCE, b, log=lambda *_: None)
        except ReopenExhausted as e:
            res, err = None, str(e)
        passed = (res is not None and res["counts"]["accepted"] == len(jobs)
                  and res["exact"] == res["rows"])
        return res, b, link, passed, err

    print("self-test tern_tc_reopen (no board, no port)")
    with tempfile.TemporaryDirectory() as scratch:
        path = os.path.join(scratch, "synthetic_tc02.bin")
        h.write_synthetic_tc02(path)
        small, _ = h.load_tc02(path, ("wk", "down"), layers={0})
    small = [(n, r[:6], i) for n, r, i in small]
    jobs, ref = h.build_jobs(small, "int8", 1, seed=3)
    R, Q = h.RESP_LEN, 24
    check(len(jobs) > 200, f"{len(jobs)} jobs, {len(ref)} rows (layer 0 wk and down, 6 rows each)")

    cell = lambda **k: rt.HuntingCell(key=h.TEST_KEY, **k)  # noqa: E731
    res, b, link, passed, err = go(Stall(cell()), jobs, ref)
    check(passed and link.flushes == 0 and link.reopens == 0 and b.resyncs == 0,
          "clean link: every receipt, no flush, no reopen")

    holes = [
        ("16 bytes lost mid-answer", rt.RxLoss(cell(), [(5 * R + 8, 16)])),
        ("the generation hole: 18 bytes of one answer and 2 whole answers", rt.RxLoss(cell(), [(40 * R + 1, 56)])),
        ("the call's last answer lost", rt.RxLoss(cell(), [((len(jobs) - 1) * R, R)])),
        ("a request's AA lost", rt.TxLoss(cell(), [Q * 120])),
        ("the call's last request loses its last byte", rt.TxLoss(cell(), [Q * len(jobs) - 1])),
        ("two holes 3 answers apart", rt.RxLoss(cell(), [(60 * R + 3, 20), (63 * R + 5, 30)])),
    ]
    for what, inner in holes:
        res, b, link, passed, err = go(Stall(inner), jobs, ref)
        check(passed and link.reopens == 0 and link.flushes == b.resyncs and b.retransmits + b.resyncs >= 1,
              f"an ordinary hole never reopens ({b.resyncs} resyncs = {link.flushes} flushes seen, "
              f"{b.retransmits} retransmitted): {what}")

    stalls = [
        ("answers stop 11 bytes into answer 100 (the retransmit run's shape)", dict(rx_at=[100 * R + 11])),
        ("answers stop on a frame boundary", dict(rx_at=[150 * R])),
        ("requests stop 5 bytes into request 120: the node's parser is left inside a frame",
         dict(tx_at=[120 * Q + 5])),
        ("requests stop on a frame boundary", dict(tx_at=[200 * Q])),
        ("both directions, one after the other", dict(rx_at=[60 * R + 3], tx_at=[180 * Q + 17])),
    ]
    for what, sched in stalls:
        port = Stall(cell(), **sched)
        n = len(sched.get("rx_at", [])) + len(sched.get("tx_at", []))
        res, b, link, passed, err = go(port, jobs, ref)
        check(passed and link.reopens == n == port.cleared and link.flushes == b.resyncs
              and link.waited == [wait_s * 2 ** k for k in range(n)] and b.retransmits <= 2 * 24 * n + 4,
              f"cleared by {link.reopens} reopen(s), waits {link.waited} s, {b.resyncs} resyncs, "
              f"{b.retransmits} retransmitted, {res['counts']['accepted'] if res else 0}/{len(jobs)}: {what}")

    port = Dead(cell(), rx_at=[100 * R + 11])
    res, b, link, passed, err = go(port, jobs, ref)
    check(not passed and res is not None and res["counts"]["exhausted"] == 1
          and 1 <= link.reopens <= max_reopens and err is None,
          f"a stall no reopen clears: the job's attempts run out after {link.reopens} reopens, run fails")
    res, b, link, passed, err = go(Dead(cell(), rx_at=[100 * R + 11]), jobs, ref, reopens=1)
    check(not passed and err is not None and "ceiling 1" in err,
          f"past MAX_REOPENS the link raises and the run fails ({err})")

    for fault, kind, what in (("lie", "lie", "a wrong answer with a valid tag"),
                              ("impersonate", "node", "a verified answer from another node id")):
        port = Stall(cell(fault=fault, fault_at=150), rx_at=[100 * R + 11])
        res, b, link, passed, err = go(port, jobs, ref)
        check(not passed and res["counts"][kind] == 1 and link.reopens == 1,
              f"after a reopen, {what} still stops the run ('{kind}')")
    port = Stall(rt.RxLoss(cell(), [(30 * R + 2, 40)]), rx_at=[120 * R + 11], tx_at=[250 * Q + 9])
    res, b, link, passed, err = go(port, jobs, ref)
    check(passed and link.reopens == 2 and res["counts"]["duplicate"] == 0,
          f"a hole, then two stalls: {res['counts']['accepted']}/{len(jobs)}, 2 reopens, no answer credited twice")

    b = budget()
    r1 = go(Stall(cell(), rx_at=[100 * R + 11]), jobs, ref, b=b)
    r2 = go(Stall(cell(), tx_at=[50 * Q + 5]), jobs, ref, b=b)
    check(r1[3] and r2[3] and b.next_retry == retry_base + b.retransmits,
          f"two calls share one budget across reopens: retry nonces continue ({b.retransmits} used)")
    print(f"self-test tern_tc_reopen: {'PASS' if ok else 'FAIL'}")
    return ok


def pty_test(baud=115200, wait_s=0.2):
    """The real SerialLink closed and reopened by ReopenLink, over a pseudo-terminal pair.

    A thread plays the node on the master side: it answers every 24-byte frame with the reference
    cell, and goes silent after its 40th answer until the slave side has been closed and opened
    again. That checks what the rehearsal cannot: that pyserial on this Mac really closes and reopens
    the device and that the protocol carries on over the new descriptor.

    A pty carries no baud rate and refuses macOS's custom-speed ioctl (IOSSIOSPEED, errno 25), so
    this test opens at the standard 115200. The run's 1144744 goes through that ioctl on every open,
    the first one included, so a board run that starts at all has exercised it once.
    """
    import pty
    import select
    import tty
    print("pty test tern_tc_reopen (no board)")
    master, slave = pty.openpty()
    name = os.ttyname(slave)
    tty.setraw(master)
    cell = rt.HuntingCell(key=h.TEST_KEY)
    lock = threading.Lock()
    state = dict(answered=0, silent=False, stop=False, opens=0)

    def node():
        while not state["stop"]:
            if not select.select([master], [], [], 0.05)[0]:
                continue
            try:
                b = os.read(master, 4096)
            except OSError:
                time.sleep(0.01)
                continue
            with lock:
                cell.write(b)
                out = cell.read(1 << 20)
                for k in range(0, len(out), h.RESP_LEN):
                    if state["silent"]:
                        break
                    os.write(master, out[k:k + h.RESP_LEN])
                    state["answered"] += 1
                    if state["answered"] == 40:
                        state["silent"] = True

    t = threading.Thread(target=node, daemon=True)
    t.start()
    opened = []

    def open_port():
        link = h.SerialLink(name, baud)
        opened.append(link)
        with lock:
            state["opens"] += 1
            if state["opens"] > 1:
                state["silent"] = False
        return link

    ok = True
    try:
        link = ReopenLink(open_port, lambda p: p.ser.close(), 24, wait_s, 2, log=print)
        with tempfile.TemporaryDirectory() as scratch:
            path = os.path.join(scratch, "synthetic_tc02.bin")
            h.write_synthetic_tc02(path)
            small, _ = h.load_tc02(path, ("wk",), layers={0})
        small = [(n, r[:2], i) for n, r, i in small]
        jobs, ref = h.build_jobs(small, "int8", 1, seed=5)
        b = rt.Budget(0x20000000, 4, 256, 32, 24)
        res = rt.run(link, jobs, ref, h.TEST_KEY, 24, h.FIRST_JOB_NONCE, b, log=lambda *_: None)
        passed = res["counts"]["accepted"] == len(jobs) and res["exact"] == res["rows"]
        first_closed = len(opened) >= 2 and not opened[0].ser.is_open
        print(f"  slave {name}: {len(jobs)} jobs, {res['counts']['accepted']} verified, "
              f"{res['exact']}/{res['rows']} rows, {b.resyncs} resyncs, {link.summary()}")
        ok = passed and link.reopens == 1 and first_closed and opened[-1].ser.is_open
        print(f"  {'ok  ' if ok else 'FAIL'} silent after answer 40; one reopen closed the first "
              f"descriptor ({first_closed}) and the run finished on the second")
    finally:
        state["stop"] = True
        t.join(1)
        for link in opened:
            with_close = getattr(link.ser, "close", None)
            if with_close:
                with_close()
        os.close(master)
        try:
            os.close(slave)
        except OSError:
            pass
    print(f"pty test tern_tc_reopen: {'PASS' if ok else 'FAIL'}")
    return ok


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        sys.exit(0 if self_test() else 1)
    if "--pty-test" in sys.argv:
        sys.exit(0 if pty_test() else 1)
    print(__doc__)
    sys.exit(2)
