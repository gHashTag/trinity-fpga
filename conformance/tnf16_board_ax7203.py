#!/usr/bin/env python3
"""TNF16 add and mul on the ALINX AX7203: every board request, checked word for word.

The bitstream is tnf16_board_ax7203 (fpga/vivado/tnf16_board_ax7203.v). Requests, expected
words, the wire format, the window and the pass line all come from
specs/trinet/tnf16_on_board_ax7203.t27 through the generated tnf16_board_params.SPEC; the
expected words come from tnf_ref.py through tnf16_board_vectors.requests().

    python3 tnf16_board_ax7203.py --self-test
    python3 tnf16_board_ax7203.py --port /dev/cu.usbserial-1130

Each response must be RESP_OK, echo the request's SEQ and carry the reference word. A wrong
word is a fail and the run goes on. A short, unframed or out-of-sequence response means the
link lost bytes: the run stops there, and every request not answered by then is lost.
Pass: exactly SPEC["PASS_LINE"], and exit 0.
"""
import argparse
import hashlib
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from tnf16_board_params import SPEC, SPEC_SHA256  # noqa: E402
import tnf16_board_vectors as vectors  # noqa: E402

SYNC = bytes([SPEC["SYNC0"], SPEC["SYNC1"]])
RESP_OK, RESP_BADOP = SPEC["RESP_OK"], SPEC["RESP_BADOP"]
RESP_BYTES, REQ_BYTES = SPEC["RESP_BYTES"], SPEC["REQ_BYTES"]
OPB = SPEC["OPERAND_BYTES"]
WORD_MASK = (1 << SPEC["WORD_BITS"]) - 1
SHOW = 20


def frame(op, seq, a, b):
    out = SYNC + bytes([op, seq]) + a.to_bytes(OPB, "little") + b.to_bytes(OPB, "little")
    assert len(out) == REQ_BYTES
    return out


def vectors_sha256(reqs):
    """Same bytes as `tnf16_board_vectors.py --write`, so a run names the exact request list."""
    h = hashlib.sha256()
    for _name, op, a, b, want in reqs:
        h.update(f"{op:x} {a:05x} {b:05x} {want:05x}\n".encode())
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
            _name, op, a, b, _want = reqs[sent]
            link.write(frame(op, sent & 0xFF, a, b))
            sent += 1
        raw = link.read(RESP_BYTES)
        seq = answered & 0xFF
        if len(raw) < RESP_BYTES or raw[0] not in (RESP_OK, RESP_BADOP) or raw[1] != seq:
            waiting = getattr(link, "waiting", lambda: None)()
            stop = (f"after {answered} answers, {sent - answered} in flight: expected "
                    f"{RESP_OK:02x} {seq:02x} ..., read {len(raw)} bytes [{raw.hex(' ')}]"
                    + (f", {waiting} more waiting" if waiting is not None else ""))
            break
        name, op, a, b, want = reqs[answered]
        y = int.from_bytes(raw[2:], "little")
        if raw[0] == RESP_OK and y == want:
            ok += 1
            per[(name, op)][0] += 1
        else:
            fails += 1
            if len(first_bad) < SHOW:
                first_bad.append(f"request {answered} {name} op {op} a {a:05x} b {b:05x}: board "
                                 f"{raw[0]:02x} y {y:06x}, reference {want:05x}")
        answered += 1
    return dict(n=n, ok=ok, fails=fails, lost=n - answered, sent=sent, answered=answered,
                per=per, first_bad=first_bad, stop=stop, window=window)


def result_line(res):
    return f"TNF16 RESULT: {res['ok']}/{res['n']} bit-exact (fails={res['fails']}, lost={res['lost']})"


def report(res, elapsed=None, log=print):
    for (name, op), (good, tot) in sorted(res["per"].items()):
        tag = "ok  " if good == tot else "FAIL"
        log(f"  [{tag}] {name:8s} {'add' if op == SPEC['OP_ADD'] else 'mul'} {good:7d}/{tot}")
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
    """tnf16_board_ax7203 in Python: its parser and tnf16_rtl_model as the core.

    `fault` breaks exactly one thing at response `at`, so the self-test can show every
    check firing.
    """

    def __init__(self, fault=None, at=7):
        import tnf16_rtl_model as model
        self.model, self.fault, self.at = model, fault, at
        self.rx, self.out, self.n = b"", bytearray(), 0

    def write(self, b):
        self.rx += b
        while len(self.rx) >= REQ_BYTES:
            fr, self.rx = self.rx[:REQ_BYTES], self.rx[REQ_BYTES:]
            assert fr[:2] == SYNC
            op, seq = fr[2], fr[3]
            a = int.from_bytes(fr[4:4 + OPB], "little") & WORD_MASK
            b_ = int.from_bytes(fr[4 + OPB:4 + 2 * OPB], "little") & WORD_MASK
            y = self.model.compute(op, a, b_)
            resp = bytearray([RESP_BADOP, seq, 0, 0, 0] if y is None
                             else [RESP_OK, seq, *y.to_bytes(OPB, "little")])
            hit = self.n == self.at
            self.n += 1
            if hit and self.fault == "lie":
                resp[2] ^= 1
            if hit and self.fault == "high_bits":
                resp[4] |= 0x08
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
    reqs = []
    for op, a, b, want in vectors.pinned():
        reqs.append(("pinned", op, a, b, want))
    reqs += [("edge", op, a, b, vectors.golden(op, a, b)) for op, a, b in vectors.edge()]
    quiet = lambda *_: None  # noqa: E731
    good = True

    def check(cond, what):
        nonlocal good
        print(f"  [{'ok  ' if cond else 'FAIL'}] {what}")
        good = good and cond

    print(f"self-test on {len(reqs)} requests (pinned + edge), model board, window {SPEC['WINDOW']}")
    res = run(ModelBoard(), reqs, SPEC["WINDOW"], quiet)
    check(report(res, log=quiet) and res["ok"] == len(reqs), "clean model board passes every request")
    for fault, want in (("lie", "fails=1"), ("high_bits", "fails=1"), ("badop", "fails=1"),
                        ("seq", "lost"), ("drop", "lost"), ("slip", "lost")):
        res = run(ModelBoard(fault), reqs, SPEC["WINDOW"], quiet)
        passed = report(res, log=quiet)
        if want == "fails=1":
            cond = not passed and res["fails"] == 1 and res["lost"] == 0
        else:
            cond = not passed and res["lost"] > 0 and res["stop"] is not None and res["answered"] == 7
        check(cond, f"fault {fault:9s} caught: {result_line(res)}")
    # Operand bits above the word must not reach the core.
    fr = frame(SPEC["OP_ADD"], 0, SPEC["ONE"] | (0x1F << SPEC["WORD_BITS"]), SPEC["ONE"])
    mb = ModelBoard()
    mb.write(fr)
    y = int.from_bytes(mb.read(RESP_BYTES)[2:], "little")
    check(y == vectors.golden(SPEC["OP_ADD"], SPEC["ONE"], SPEC["ONE"]), "junk above bit 18 of an operand is ignored")
    check(frame(1, 2, 0x030201, 0x060504) == bytes([SPEC["SYNC0"], SPEC["SYNC1"], 1, 2, 1, 2, 3, 4, 5, 6]),
          "frame layout SYNC0 SYNC1 OP SEQ a0 a1 a2 b0 b1 b2")
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
    passed = report(res, time.monotonic() - t0)
    if passed and result_line(res) != SPEC["PASS_LINE"]:
        print(f"PROBLEM: a pass must print the spec's line, {SPEC['PASS_LINE']!r}")
        return 1
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
