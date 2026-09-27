#!/usr/bin/env python3
"""MXFP4 and TNF4 block dot products on the ALINX AX7203: every board request, checked word for word.

The bitstream is mxdot4_board_ax7203 (fpga/vivado/mxdot4_board_ax7203.v, FORMATS=3). Requests,
expected words, the wire format, the window and the pass line all come from
specs/trinet/mxdot4_on_board_ax7203.t27 through the generated mxdot4_board_params.SPEC; the
expected words come from mxfp_ref.py and block_tnf.py through mxdot4_board_vectors.requests().

    python3 mxdot4_board_ax7203.py --self-test
    tri fpga-run mxdot4_board_ax7203 -- python3 conformance/mxdot4_board_ax7203.py --port /dev/cu.usbserial-1130

Each response must be RESP_OK, echo the request's SEQ and carry the reference word. A wrong
word is a fail and the run goes on. A short, unframed or out-of-sequence response means the
link lost bytes: the run stops there, and every request not answered by then is lost.
Pass: exactly SPEC["PASS_LINE"], and exit 0.

A pass says the board computes both formats' block dot products exactly. It says nothing about
which format is the better number format: that is the block axis, measured elsewhere.
"""
import argparse
import hashlib
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from mxdot4_board_params import SPEC, SPEC_SHA256  # noqa: E402
import mxdot4_board_vectors as vectors  # noqa: E402

SYNC = bytes([SPEC["SYNC0"], SPEC["SYNC1"]])
RESP_OK, RESP_BADOP = SPEC["RESP_OK"], SPEC["RESP_BADOP"]
RESP_BYTES, REQ_BYTES = SPEC["RESP_BYTES"], SPEC["REQ_BYTES"]
RB = SPEC["RESULT_BYTES"]
OP_NAME = vectors.OP_NAME
SHOW = 20


def frame(op, seq, sa, sb, a, b):
    out = SYNC + bytes([op, seq, sa, sb]) + vectors.pack(a) + vectors.pack(b)
    assert len(out) == REQ_BYTES
    return out


def vectors_sha256(reqs):
    """Same bytes as `mxdot4_board_vectors.py --write`, so a run names the exact request list."""
    h = hashlib.sha256()
    for _name, op, sa, sb, a, b, want in reqs:
        h.update((vectors.hex_line(op, sa, sb, a, b, want) + "\n").encode())
    return h.hexdigest()


class SerialLink:
    def __init__(self, port, baud):
        import serial
        self.ser = serial.Serial(port, baud, timeout=2)
        self.ser.reset_input_buffer()

    def write(self, b):
        self.ser.write(b)

    def read(self, n):
        return self.ser.read(n)

    def waiting(self):
        return self.ser.in_waiting


def run(link, reqs, window, log=print):
    n = len(reqs)
    per = {}
    for name, op, *_ in reqs:
        per.setdefault((name, op), [0, 0])[1] += 1
    ok = fails = sent = answered = 0
    first_bad, stop = [], None
    while answered < n:
        while sent < n and sent - answered < window:
            _name, op, sa, sb, a, b, _want = reqs[sent]
            link.write(frame(op, sent & 0xFF, sa, sb, a, b))
            sent += 1
        raw = link.read(RESP_BYTES)
        seq = answered & 0xFF
        if len(raw) < RESP_BYTES or raw[0] not in (RESP_OK, RESP_BADOP) or raw[1] != seq:
            waiting = getattr(link, "waiting", lambda: None)()
            stop = (f"after {answered} answers, {sent - answered} in flight: expected "
                    f"{RESP_OK:02x} {seq:02x} ..., read {len(raw)} bytes [{raw.hex(' ')}]"
                    + (f", {waiting} more waiting" if waiting is not None else ""))
            break
        name, op, sa, sb, a, b, want = reqs[answered]
        y = int.from_bytes(raw[2:], "little")
        if raw[0] == RESP_OK and y == want:
            ok += 1
            per[(name, op)][0] += 1
        else:
            fails += 1
            if len(first_bad) < SHOW:
                first_bad.append(f"request {answered} {name} {OP_NAME[op]} sa {sa} sb {sb}: board "
                                 f"{raw[0]:02x} y {y:06x}, reference {want:06x}")
        answered += 1
    return dict(n=n, ok=ok, fails=fails, lost=n - answered, sent=sent, answered=answered,
                per=per, first_bad=first_bad, stop=stop, window=window)


def result_line(res):
    return f"MXDOT4 RESULT: {res['ok']}/{res['n']} bit-exact (fails={res['fails']}, lost={res['lost']})"


def report(res, elapsed=None, log=print):
    for (name, op), (good, tot) in sorted(res["per"].items()):
        tag = "ok  " if good == tot else "FAIL"
        log(f"  [{tag}] {name:8s} {OP_NAME[op]:5s} {good:7d}/{tot}")
    log(f"sent {res['sent']}, answered {res['answered']}, window {res['window']}")
    if elapsed:
        log(f"elapsed {elapsed:.1f} s ({res['answered'] / elapsed:.0f} answers/s)")
    for m in res["first_bad"]:
        log(f"  ! {m}")
    if res["stop"]:
        log(f"  ! LINK: {res['stop']}")
    log(result_line(res))
    return res["ok"] == res["n"] and res["fails"] == 0 and res["lost"] == 0


# ---------------------------------------------------------------------------
# Self-test: a model board behind a fake port, and each check shown able to fail
# ---------------------------------------------------------------------------

class ModelBoard:
    """mxdot4_board_ax7203 in Python: its parser, and mxdot4_core as the RTL computes it.

    The core model reads the spec's integer tables (what the RTL is generated from) and
    builds the word bit by bit as mxdot4_core.v does, not through vectors.golden(), which
    reads the references. `fault` breaks exactly one thing at response `at`, so the
    self-test can show every check firing.
    """

    TABLE = {SPEC["OP_MXFP4"]: SPEC["E2M1_INT"], SPEC["OP_TNF4"]: SPEC["TNF4_INT"]}

    def __init__(self, fault=None, at=7):
        self.fault, self.at = fault, at
        self.rx, self.out, self.n = b"", bytearray(), 0

    def core(self, op, sa, sb, a_bytes, b_bytes):
        if op not in self.TABLE:
            return None
        if sa == SPEC["SCALE_NAN"] or sb == SPEC["SCALE_NAN"]:
            return SPEC["NAN_WORD"]
        t, s = self.TABLE[op], 0
        av, bv = int.from_bytes(a_bytes, "little"), int.from_bytes(b_bytes, "little")
        for i in range(SPEC["BLOCK"]):
            ea, eb = av >> (4 * i) & 15, bv >> (4 * i) & 15
            m = t[ea & 7] * t[eb & 7]
            s += -m if (ea ^ eb) & 8 else m
        return (s & ((1 << SPEC["SUM_BITS"]) - 1)) | ((sa + sb) << SPEC["EXP_SHIFT"])

    def write(self, b):
        self.rx += b
        while len(self.rx) >= REQ_BYTES:
            fr, self.rx = self.rx[:REQ_BYTES], self.rx[REQ_BYTES:]
            assert fr[:2] == SYNC
            op, seq, sa, sb = fr[2], fr[3], fr[4], fr[5]
            bb = SPEC["BLOCK_BYTES"]
            y = self.core(op, sa, sb, fr[6:6 + bb], fr[6 + bb:6 + 2 * bb])
            resp = bytearray([RESP_BADOP, seq, 0, 0, 0] if y is None
                             else [RESP_OK, seq, *y.to_bytes(RB, "little")])
            hit = self.n == self.at
            self.n += 1
            if hit and self.fault == "lie":
                resp[2] ^= 1
            if hit and self.fault == "exponent":
                resp[3] ^= 0x40                    # word bit 14, the exponent's lowest
            if hit and self.fault == "nan":
                resp[4] |= 0x80
            if hit and self.fault == "badop":
                resp[0] = RESP_BADOP
            if hit and self.fault == "seq":
                resp[1] ^= 0x01
            if hit and self.fault == "drop":
                continue
            if hit and self.fault == "slip":
                resp = resp[2:]
            self.out += resp

    def read(self, n):
        out, self.out = bytes(self.out[:n]), self.out[n:]
        return out

    def waiting(self):
        return len(self.out)


def self_test():
    rng = vectors.SplitMix64(SPEC["RANDOM_SEED"])
    rows = vectors.pinned() + vectors.edge(rng)
    reqs = [(name, op, sa, sb, a, b, vectors.golden(op, sa, sb, a, b)) for name, op, sa, sb, a, b in rows]
    quiet = lambda *_: None  # noqa: E731
    good = True

    def check(cond, what):
        nonlocal good
        print(f"  [{'ok  ' if cond else 'FAIL'}] {what}")
        good = good and cond

    print(f"self-test on {len(reqs)} requests (pinned + edge), model board, window {SPEC['WINDOW']}")
    res = run(ModelBoard(), reqs, SPEC["WINDOW"], quiet)
    check(report(res, log=quiet) and res["ok"] == len(reqs), "clean model board passes every request")
    for fault, want in (("lie", "fails=1"), ("exponent", "fails=1"), ("nan", "fails=1"),
                        ("badop", "fails=1"), ("seq", "lost"), ("drop", "lost"), ("slip", "lost")):
        res = run(ModelBoard(fault), reqs, SPEC["WINDOW"], quiet)
        passed = report(res, log=quiet)
        if want == "fails=1":
            cond = not passed and res["fails"] == 1 and res["lost"] == 0
        else:
            cond = not passed and res["lost"] > 0 and res["stop"] is not None and res["answered"] == 7
        check(cond, f"fault {fault:9s} caught: {result_line(res)}")
    # A board with the formats' tables swapped must fail on the first block they differ on.
    swapped = ModelBoard()
    swapped.TABLE = {SPEC["OP_MXFP4"]: SPEC["TNF4_INT"], SPEC["OP_TNF4"]: SPEC["E2M1_INT"]}
    res = run(swapped, reqs, SPEC["WINDOW"], quiet)
    check(not report(res, log=quiet) and res["fails"] > 0 and res["lost"] == 0,
          f"swapped tables caught: {result_line(res)}")
    # Unknown opcodes come back BADOP with a zero word.
    for op in (0, 3, 255):
        mb = ModelBoard()
        mb.write(frame(op, 9, 127, 127, [1] * SPEC["BLOCK"], [1] * SPEC["BLOCK"]))
        check(mb.read(RESP_BYTES) == bytes([RESP_BADOP, 9, 0, 0, 0]), f"op {op} answered BADOP SEQ 0 0 0")
    codes = [c % 16 for c in range(SPEC["BLOCK"])]
    check(frame(1, 2, 3, 4, codes, codes)[:8] == bytes([SPEC["SYNC0"], SPEC["SYNC1"], 1, 2, 3, 4, 0x10, 0x32]),
          "frame layout SYNC0 SYNC1 OP SEQ SA SB, element 2j in the low nibble of byte j")
    print("SELF-TEST " + ("PASS" if good else "FAIL"))
    return good


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", default="/dev/cu.usbserial-1130")
    ap.add_argument("--baud", type=int, default=SPEC["HOST_BAUD"])
    ap.add_argument("--window", type=int, default=SPEC["WINDOW"])
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        return 0 if self_test() else 1

    print(f"# spec {SPEC['ID']} sha256 {SPEC_SHA256}")
    print(f"# port {args.port} baud {args.baud} (wire {SPEC['WIRE_BAUD']}) window {args.window}")
    reqs = vectors.requests()
    print(f"# vectors sha256 {vectors_sha256(reqs)} ({len(reqs)} requests)")
    link = SerialLink(args.port, args.baud)
    t0 = time.monotonic()
    res = run(link, reqs, args.window)
    elapsed = time.monotonic() - t0
    passed = report(res, elapsed)
    if elapsed > SPEC["RUN_LIMIT_S"]:
        print(f"PROBLEM: {elapsed:.0f} s is beyond the spec's RUN_LIMIT_S {SPEC['RUN_LIMIT_S']}")
    if passed and result_line(res) != SPEC["PASS_LINE"]:
        print(f"PROBLEM: a pass must print the spec's line, {SPEC['PASS_LINE']!r}")
        return 1
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
