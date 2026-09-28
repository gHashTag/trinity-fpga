#!/usr/bin/env python3
"""The trained tern_tc weights on the AX7203 node cell, with every receipt checked.

Reads the TC02 binary exported from the trained tern_tc checkpoint
(igla-coder-gpu/c_infer/model.bin), splits every row of every chosen ternary
weight matrix into 32-trit chunks, sends each chunk to the TRI-NET node cell
over UART, and accepts an answer only if ALL of these hold for its response:

  * status is 0x01 (keyed: the node holds a key and signed the answer);
  * the nonce echoes one this run issued, exactly once;
  * node_id equals the one the first response pinned;
  * the 8-byte SipHash-2-4 tag equals siphash24(preimage, key) recomputed here;
  * y equals the dot product of that chunk's operands.

A row passes only if every one of its chunks was accepted AND the chunk sum
equals the row dot computed straight from the model's int8 weights, not from
the packed wire bytes, so a packing bug cannot hide behind a shared oracle.

WHY THIS FILE WAS REWRITTEN (2026-09-26). The first version printed
"receipts authenticated under node0's key" but never compared a tag: it built
the preimage and dropped it, and counted `status == 0x01` as authentication.
It also compared only per-row sums (chunk errors could cancel) and never
checked the nonce echo. Its dot-product result stands; its receipt count does
not, until this version reruns on the board.

WHAT THE CELL CAN ALREADY DO THAT WAS BOOKED AS FUTURE WORK.
  * w_down has an 864-wide input. 864 = 27 x 32, so it is 27 chunks per row on
    the same 32-wide cell, not a wider cell.
  * wk and wv also have a 320-wide input and were skipped.
  * int8 activations: every q in [-127, 127] is a sum of 6 balanced-ternary
    digits, q = sum_k 3^k d_k with d_k in {-1, 0, +1}. So w.q = sum_k 3^k (w.d_k)
    and each w.d_k is an ordinary ternary x ternary job. `--act int8` runs
    6 digit planes per vector and recombines them on the host. The cell does
    only ternary work; the powers of 3 are applied here, in the open.

Board-free checks:
    python3 tern_tc_layer_ax7203.py --self-test
RTL co-simulation (the real trinet_node_core under iverilog, no board):
    python3 tern_tc_layer_ax7203.py --synthetic --layers 0 --all --setkey \\
        --keys test --emit-requests req.hex
    (run formal/tern_tc_layer_rtl_tb.v, which writes resp.hex)
    python3 tern_tc_layer_ax7203.py --synthetic --layers 0 --all --setkey \\
        --keys test --responses resp.hex
Board:
    python3 tern_tc_layer_ax7203.py --all --setkey --port /dev/cu.usbserial-130 \\
        --baud 1144744 --keys ../trinet-keys.txt --model ~/igla-coder-gpu/c_infer/model.bin

Author: Dmitrii Vasilev (@gHashTag)
"""
import argparse
import os
import random
import struct
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from trinet_mac32_conformance_ax7203 import (  # noqa: E402
    N_TRITS, OP_MAC32, STATUS_OK,
    golden_dot, pack_trits, receipt_preimage, siphash24, unpack_trits,
)

OP_SETKEY = 0x02
ST_KEY_SET = 0x02
ST_KEY_LOCKED = 0x03
ST_NO_KEY = 0x04
MAGIC_RESP = 0xA5
RESP_LEN = 19
SETKEY_NONCE = 0x7E7E0001
FIRST_JOB_NONCE = 0x00010000       # keep job nonces clear of the setkey nonce

KINDS = ("wq", "wk", "wv", "wo", "gate", "up", "down")
LEGACY_B1 = ("wq", "wo", "gate", "up")   # the 24-matrix set of commit 1f131fd
INT8_DIGITS = 6                          # 3^6 = 729: covers [-364, 364]

# A public test key (the SipHash reference key). Never deploy it.
TEST_KEY = bytes(range(16))


# ---------------------------------------------------------------------------
# Model file
# ---------------------------------------------------------------------------

def load_tc02(path, kinds, layers=None):
    """Chosen ternary matrices of a TC02 file as [(name, rows, in_dim)].

    Layout per igla-coder-gpu/scripts/export_tc_bin.py: header, f32 embed,
    then per layer: norm1, wq+g, wk+g, wv+g, wo+g, norm2, gate+g, up+g, down+g.
    Each weight is int8 in {-1, 0, +1}, row-major [out][in].
    """
    f = open(path, "rb")
    if f.read(4) != b"TC02":
        raise SystemExit(f"{path}: not a TC02 file")
    n_layer, n_head, n_kv_head, d_model, d_ff, head_dim, vocab = \
        struct.unpack("<7i", f.read(28))
    qd, kvd = n_head * head_dim, n_kv_head * head_dim
    shapes = [("wq", qd, d_model), ("wk", kvd, d_model), ("wv", kvd, d_model),
              ("wo", d_model, qd), ("gate", d_ff, d_model), ("up", d_ff, d_model),
              ("down", d_model, d_ff)]
    f.seek(4 * vocab * d_model, 1)                      # embed (f32)
    out = []
    for L in range(n_layer):
        f.seek(4 * d_model, 1)                          # norm1
        for kind, n_out, n_in in shapes:
            if kind == "gate":
                f.seek(4 * d_model, 1)                  # norm2
            want = kind in kinds and (layers is None or L in layers)
            if want:
                buf = struct.unpack(f"<{n_out * n_in}b", f.read(n_out * n_in))
                if not set(buf) <= {-1, 0, 1}:
                    raise SystemExit(f"L{L}/{kind}: weights are not ternary")
                rows = [buf[r * n_in:(r + 1) * n_in] for r in range(n_out)]
                out.append((f"L{L}/{kind}", rows, n_in))
            else:
                f.seek(n_out * n_in, 1)
            f.seek(4, 1)                                # per-tensor scale g
    return out, dict(n_layer=n_layer, d_model=d_model, d_ff=d_ff, vocab=vocab)


def write_synthetic_tc02(path, seed=0x7C02, density=0.597, n_layer=6, n_head=5,
                         n_kv_head=1, d_model=320, d_ff=864, head_dim=64,
                         vocab=64):
    """A TC02 file with tern_tc's shapes and random ternary weights.

    Used where the trained model.bin is not available (CI, the cloud, RTL
    co-simulation). Its vocab is shrunk because only the skip matters.
    """
    rng = random.Random(seed)
    qd, kvd = n_head * head_dim, n_kv_head * head_dim

    def tern(n):
        return bytes((rng.choice((1, 0xFF)) if rng.random() < density else 0)
                     for _ in range(n))

    with open(path, "wb") as f:
        f.write(b"TC02")
        f.write(struct.pack("<7i", n_layer, n_head, n_kv_head, d_model, d_ff,
                            head_dim, vocab))
        f.write(bytes(4 * vocab * d_model))
        for _ in range(n_layer):
            f.write(bytes(4 * d_model))
            for n_out, n_in in ((qd, d_model), (kvd, d_model), (kvd, d_model),
                                (d_model, qd)):
                f.write(tern(n_out * n_in) + struct.pack("<f", 1.0))
            f.write(bytes(4 * d_model))
            for n_out, n_in in ((d_ff, d_model), (d_ff, d_model), (d_model, d_ff)):
                f.write(tern(n_out * n_in) + struct.pack("<f", 1.0))
        f.write(bytes(4 * d_model))


# ---------------------------------------------------------------------------
# Activations
# ---------------------------------------------------------------------------

def balanced_ternary(q, digits=INT8_DIGITS):
    """q -> [d_0 .. d_{digits-1}], d_k in {-1,0,+1}, q = sum 3^k d_k."""
    out = []
    for _ in range(digits):
        r = q % 3
        d = -1 if r == 2 else r
        out.append(d)
        q = (q - d) // 3
    if q != 0:
        raise ValueError("value out of range for balanced-ternary digits")
    return out


def make_vectors(in_dim, act, n_x, rng):
    """Activation vectors for one input width: [(values, planes)].

    planes = [(weight, trit_vector)]; the row dot is sum weight * (w . trits).
    """
    vecs = []
    for _ in range(n_x):
        if act == "ternary":
            x = [rng.choice((-1, 0, 1)) for _ in range(in_dim)]
            vecs.append((x, [(1, x)]))
        else:
            x = [rng.randint(-127, 127) for _ in range(in_dim)]
            digs = [balanced_ternary(v) for v in x]
            planes = [(3 ** k, [d[k] for d in digs]) for k in range(INT8_DIGITS)]
            vecs.append((x, planes))
    return vecs


# ---------------------------------------------------------------------------
# Jobs
# ---------------------------------------------------------------------------

def build_jobs(mats, act, n_x, seed):
    """Every chunk job, plus the per-row reference computed from int weights.

    A job is (w_bytes, x_bytes, row_id, weight); its nonce is
    FIRST_JOB_NONCE + its index, so nothing else needs storing per job.
    """
    rng = random.Random(seed)
    vec_cache = {}
    jobs, rows_ref = [], []
    for name, rows, in_dim in mats:
        if in_dim % N_TRITS:
            raise SystemExit(f"{name}: input {in_dim} is not a multiple of {N_TRITS}")
        chunks = in_dim // N_TRITS
        if in_dim not in vec_cache:
            vecs = make_vectors(in_dim, act, n_x, rng)
            vec_cache[in_dim] = [
                (x, [(weight, [pack_trits(trits[c * N_TRITS:(c + 1) * N_TRITS])
                               for c in range(chunks)])
                     for weight, trits in planes])
                for x, planes in vecs]
        for xi, (x, planes) in enumerate(vec_cache[in_dim]):
            for r, row in enumerate(rows):
                row_id = len(rows_ref)
                rows_ref.append((name, xi, r, sum(w * v for w, v in zip(row, x))))
                wbs = [pack_trits(row[c * N_TRITS:(c + 1) * N_TRITS])
                       for c in range(chunks)]
                for weight, xbs in planes:
                    for c in range(chunks):
                        jobs.append((wbs[c], xbs[c], row_id, weight))
    if FIRST_JOB_NONCE + len(jobs) >= 1 << 32:
        raise SystemExit("too many jobs for a 32-bit nonce")
    return jobs, rows_ref


def request(op, nonce, w, x):
    return bytes([0xAA, 0x55, op]) + nonce.to_bytes(4, "little") + w + x + b"\x00"


def setkey_request(key):
    return request(OP_SETKEY, SETKEY_NONCE, key[:8], key[8:])


def parse(raw):
    return {
        "y": raw[1] - 256 if raw[1] > 127 else raw[1],
        "status": raw[2],
        "nonce": int.from_bytes(raw[3:7], "little"),
        "node_id": int.from_bytes(raw[7:11], "little"),
        "tag": int.from_bytes(raw[11:19], "little"),
    }


# ---------------------------------------------------------------------------
# Transports: a serial port, a recorded response stream, or a reference cell
# ---------------------------------------------------------------------------

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


class ReplayLink:
    """Responses recorded by the RTL testbench: one hex byte per line."""

    def __init__(self, path):
        self.buf = bytes(int(t, 16) for t in open(path).read().split())
        self.pos = 0

    def write(self, b):
        pass

    def read(self, n):
        out = self.buf[self.pos:self.pos + n]
        self.pos += len(out)
        return out


class UdpLink:
    """E5's Ethernet transport (NODE_ETHERNET_PLAN.md, "What the port could
    carry"): one datagram per write, 4-byte little-endian sequence in front.
    The peer echoes the request's sequence on its answer datagram; read()
    strips it and hands out payload bytes in arrival order — the runner
    classifies by nonce, so order is free, and a lost datagram surfaces as
    the honest short read the runner already stops on. The whole read waits
    at most `timeout` seconds, like SerialLink's per-read timeout.
    K-frames-per-datagram is E4's wire optimisation and lands with its
    cosim, not here. `echo_bad` counts answer datagrams whose sequence names
    nothing we sent — a peer bug, diagnosed not trusted away.
    """

    def __init__(self, host, port, timeout=2.0):
        import socket
        self._s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._timeout = timeout
        self.addr = (host, port)
        self.seq = 0
        self.pending = bytearray()
        self.echo_ok = 0
        self.echo_bad = 0

    def write(self, b):
        self._s.sendto(self.seq.to_bytes(4, "little") + b, self.addr)
        self.seq += 1

    def _recv_one(self, timeout):
        """One datagram into pending; False when nothing arrived in time."""
        import socket
        self._s.settimeout(timeout)
        try:
            dgram, _peer = self._s.recvfrom(65535)
        except (TimeoutError, BlockingIOError, socket.timeout):
            return False
        if len(dgram) >= 4:
            echo = int.from_bytes(dgram[:4], "little")
            if 0 <= echo < self.seq:
                self.echo_ok += 1
            else:
                self.echo_bad += 1
            self.pending += dgram[4:]
        return True

    def read(self, n):
        deadline = time.monotonic() + self._timeout
        while len(self.pending) < n:
            if not self._recv_one(max(0.0, deadline - time.monotonic())):
                break
        out, self.pending = bytes(self.pending[:n]), self.pending[n:]
        return out

    def waiting(self):
        while self._recv_one(0.0):
            pass
        return len(self.pending)


class UdpCellBridge:
    """A software cell served over UDP: the self-test's stand-in for E4's
    node, and the byte-exact peer E4's cosim will reuse. One datagram per
    request batch, the sequence echoed, the cell's answers in the payload.
    `drop_at` (1-based, counting every datagram) loses one request datagram
    whole — the way a real datagram link can — so a test can show the
    receipt machinery meets that loss the same way it meets a serial slip.
    """

    def __init__(self, cell, host="127.0.0.1"):
        import socket, threading
        self.cell = cell
        self.s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.s.bind((host, 0))
        self.addr = self.s.getsockname()
        self.n = 0
        self.drop_at = None
        self._stop = False
        self.t = threading.Thread(target=self._serve, daemon=True)
        self.t.start()

    def _serve(self):
        import socket
        self.s.settimeout(0.2)
        while not self._stop:
            try:
                dgram, peer = self.s.recvfrom(65535)
            except (TimeoutError, socket.timeout):
                continue
            self.n += 1
            if len(dgram) >= 4 and self.n != self.drop_at:
                self.cell.write(dgram[4:])
                out = self.cell.read(1 << 20)
                if out:
                    self.s.sendto(dgram[:4] + out, peer)

    def stop(self):
        self._stop = True
        self.t.join(timeout=1.0)
        self.s.close()


class RefCell:
    """A Python model of fpga/portable/trinet_node_core.v, for negative controls.

    `fault` makes it misbehave in exactly one way, so the self-test can show
    that each check can fail.
    """

    def __init__(self, node_id=0x5452494E, key=None, fault=None, fault_at=5):
        self.node_id, self.key, self.fault, self.fault_at = node_id, key, fault, fault_at
        self.rx, self.out, self.n = b"", bytearray(), 0

    def write(self, b):
        self.rx += b
        while len(self.rx) >= 24:
            frame, self.rx = self.rx[:24], self.rx[24:]
            self._answer(frame)

    def _answer(self, fr):
        op, nonce, w, x = fr[2], fr[3:7], fr[7:15], fr[15:23]
        if op == OP_SETKEY:
            if self.key is None:
                self.key, status = w + x, ST_KEY_SET
            else:
                status = ST_KEY_LOCKED
            y, sign_key = 0, w + x if status == ST_KEY_SET else self.key
        else:
            y = golden_dot(w, x)
            status = STATUS_OK if self.key is not None else ST_NO_KEY
            sign_key = self.key or bytes(16)
        node = self.node_id
        hit = op == OP_MAC32 and self.n == self.fault_at
        if op == OP_MAC32:
            self.n += 1
        if hit and self.fault == "lie":          # wrong answer, honestly signed
            y += 2
        if hit and self.fault == "nonce":
            nonce = (int.from_bytes(nonce, "little") ^ 0x40000000).to_bytes(4, "little")
        if hit and self.fault == "impersonate":
            node ^= 1
        if self.fault == "wrong_key":
            sign_key = bytes(16 - i for i in range(16))
        tag = siphash24(receipt_preimage(op, nonce, w, x, y & 0xFF, node), sign_key)
        resp = (bytes([MAGIC_RESP, y & 0xFF, status]) + nonce
                + node.to_bytes(4, "little") + tag.to_bytes(8, "little"))
        if hit and self.fault == "damage":
            resp = resp[:12] + bytes([resp[12] ^ 0x10]) + resp[13:]
        if hit and self.fault == "drop":
            return
        self.out += resp

    def read(self, n):
        out, self.out = bytes(self.out[:n]), self.out[n:]
        return out


class SlipLink:
    """Loses `count` bytes of the answer stream from byte offset `at`.

    The 2026-09-27 board run lost 16 bytes: the last 11 of one answer (node id
    bytes 2-4 and the tag) and the first 5 of the next, so the harness saw
    node id bytes `4e 01 00 4e` and then an unframed read.
    """

    def __init__(self, inner, at, count):
        self.inner, self.at, self.count, self.pos = inner, at, count, 0

    def write(self, b):
        self.inner.write(b)

    def read(self, n):
        out = bytearray()
        while len(out) < n:
            b = self.inner.read(1)
            if not b:
                break
            if not self.at <= self.pos < self.at + self.count:
                out += b
            self.pos += 1
        return bytes(out)


# ---------------------------------------------------------------------------
# The run
# ---------------------------------------------------------------------------

def install_key(link, key, log=print):
    """op 0x02, then check the ack is signed with the key we sent."""
    link.write(setkey_request(key))
    raw = link.read(RESP_LEN)
    if len(raw) < RESP_LEN or raw[0] != MAGIC_RESP:
        log("setkey: no answer")
        return None
    r = parse(raw)
    if r["status"] == ST_KEY_SET:
        pre = receipt_preimage(OP_SETKEY, SETKEY_NONCE.to_bytes(4, "little"),
                               key[:8], key[8:], 0, r["node_id"])
        if r["tag"] != siphash24(pre, key):
            log("setkey: ack status 0x02 but its tag does not verify under our key")
            return None
        log(f"setkey: key installed on node {r['node_id']:#010x}; ack tag verifies")
    elif r["status"] == ST_KEY_LOCKED:
        log(f"setkey: node {r['node_id']:#010x} already holds a key "
            f"(0x03); receipts below will show whether it is ours")
    else:
        log(f"setkey: unexpected status {r['status']:#04x}")
        return None
    return r["node_id"]


DEFAULT_WINDOW = 24
# Jobs in flight. With W in flight, at most 19*W answer bytes are on their way
# to the host. The AX7203's UART bridge is a CP2102N: a 512-byte receive
# buffer, and its datasheet requires handshaking above 1 Mbaud. The node has no
# RTS/CTS, so it cannot be held off. Measured 2026-09-27 on --all, same setup:
# 24 (456 B) and 26 (494 B) clean over 403,200 jobs; 30 (570 B) and 64
# (1,216 B) lost answer bytes. Keep 19*W under 512 until the link has flow
# control. What stalls the bridge's USB transfers is not measured.


def run(link, jobs, rows_ref, key, window=DEFAULT_WINDOW, log=print):
    """Send jobs pipelined, classify every response, then rebuild rows."""
    n = len(jobs)
    got = [None] * n
    counts = dict(accepted=0, lie=0, damage=0, tag=0, status=0, node=0,
                  fabricated=0, duplicate=0, short=0)
    answered = 0
    node_pin = None
    sent = outstanding = 0
    first_bad = []
    # Longest time the host spent between two reads (checking, then writing):
    # while it is away, answers queue up in the receive path.
    max_pause, pause_at = 0.0, 0
    t_back = time.monotonic()

    def bad(kind, msg):
        counts[kind] += 1
        if len(first_bad) < 8:
            first_bad.append(msg)

    seen = bytearray(n)
    while sent < n or outstanding:
        while sent < n and outstanding < window:
            w, x, _row, _weight = jobs[sent]
            link.write(request(OP_MAC32, FIRST_JOB_NONCE + sent, w, x))
            sent += 1
            outstanding += 1
        t_read = time.monotonic()
        pause = t_read - t_back
        if pause > max_pause:
            max_pause, pause_at = pause, answered
        raw = link.read(RESP_LEN)
        t_back = time.monotonic()
        if len(raw) < RESP_LEN or raw[0] != MAGIC_RESP:
            waiting = getattr(link, "waiting", lambda: None)()
            bad("short", f"after {sent} sent, {outstanding} outstanding: short or "
                         f"unframed read ({len(raw)} bytes) {raw.hex(' ')}"
                         + (f"; {waiting} more bytes waiting" if waiting is not None else ""))
            break                        # stop: a lost frame makes the rest a guess
        outstanding -= 1
        r = parse(raw)
        i = r["nonce"] - FIRST_JOB_NONCE
        if not 0 <= i < sent:
            bad("fabricated", f"nonce {r['nonce']:#010x} was never issued: {raw.hex(' ')}")
            continue
        if seen[i]:
            bad("duplicate", f"nonce {r['nonce']:#010x} answered twice")
            continue
        seen[i] = 1
        answered += 1
        if r["status"] != STATUS_OK:
            bad("status", f"nonce {r['nonce']:#010x}: status {r['status']:#04x}")
            continue
        if node_pin is None:
            node_pin = r["node_id"]
        if r["node_id"] != node_pin:
            bad("node", f"nonce {r['nonce']:#010x}: node {r['node_id']:#010x} "
                        f"!= {node_pin:#010x}: {raw.hex(' ')}")
            continue
        w, x, _row, _weight = jobs[i]
        nb = r["nonce"].to_bytes(4, "little")
        expect = golden_dot(w, x)
        tag_ok = r["tag"] == siphash24(
            receipt_preimage(OP_MAC32, nb, w, x, r["y"] & 0xFF, r["node_id"]), key)
        if tag_ok and r["y"] == expect:
            counts["accepted"] += 1
            got[i] = r["y"]
        elif tag_ok:
            bad("lie", f"nonce {r['nonce']:#010x}: y={r['y']} expected {expect}, "
                       f"and the tag signs the wrong answer")
        elif r["y"] != expect:
            bad("damage", f"nonce {r['nonce']:#010x}: y={r['y']} expected {expect}, "
                          f"tag fits neither")
        else:
            bad("tag", f"nonce {r['nonce']:#010x}: right y, tag does not verify")

    acc = {}
    complete = {}
    for (_w, _x, rid, weight), y in zip(jobs, got):
        if y is None:
            complete[rid] = False
        else:
            complete.setdefault(rid, True)
            acc[rid] = acc.get(rid, 0) + weight * y
    exact = sum(1 for rid, ref in enumerate(rows_ref)
                if complete.get(rid) and acc.get(rid) == ref[3])
    counts["missing"] = n - answered
    return dict(counts=counts, exact=exact, rows=len(rows_ref), jobs=len(jobs),
                sent=sent, answered=answered, window=window,
                max_pause=max_pause, pause_at=pause_at,
                node=node_pin, first_bad=first_bad,
                per_matrix=_per_matrix(rows_ref, acc, complete))


def _per_matrix(rows_ref, acc, complete):
    out = {}
    for rid, (name, _xi, _r, ref) in enumerate(rows_ref):
        t = out.setdefault(name, [0, 0])
        t[1] += 1
        if complete.get(rid) and acc.get(rid) == ref:
            t[0] += 1
    return out


def report(res, elapsed, act, log=print):
    c = res["counts"]
    for name, (ok, tot) in res["per_matrix"].items():
        log(f"  [{'ok ' if ok == tot else 'FAIL'}] {name:9s} {ok:6d}/{tot:<6d} rows bit-exact")
    log("-" * 66)
    log(f"jobs sent               : {res['sent']} of {res['jobs']} planned "
        f"(window {res['window']})")
    log(f"receipts verified (tag) : {c['accepted']}/{res['jobs']}"
        + (f" under node {res['node']:#010x}" if res["node"] is not None else ""))
    rejected = {k: v for k, v in c.items() if k != "accepted" and v}
    log(f"rejected                : {rejected if rejected else 'none'}")
    log(f"rows bit-exact          : {res['exact']}/{res['rows']}  (activations: {act})")
    if elapsed:
        log(f"elapsed                 : {elapsed:.2f} s ({res['answered'] / elapsed:.0f} "
            f"answers/s)")
        log(f"longest host pause      : {1000 * res['max_pause']:.1f} ms "
            f"(after {res['pause_at']} answers)")
    for m in res["first_bad"]:
        log(f"  ! {m}")
    log("-" * 66)
    return c["accepted"] == res["jobs"] and res["exact"] == res["rows"]


# ---------------------------------------------------------------------------
# Self-test: the checks, each shown able to fail
# ---------------------------------------------------------------------------

def self_test(scratch):
    ok = True

    def check(cond, what):
        nonlocal ok
        print(f"  {'ok  ' if cond else 'FAIL'} {what}")
        ok = ok and cond

    print("self-test (no board)")
    rng = random.Random(1)
    for _ in range(500):
        t = [rng.choice((-1, 0, 1)) for _ in range(N_TRITS)]
        if unpack_trits(pack_trits(t)) != t:
            break
    else:
        t = None
    check(t is None, "pack/unpack round trip, 500 vectors")
    check(all(sum(3 ** k * d for k, d in enumerate(balanced_ternary(q))) == q
              for q in range(-364, 365)), "balanced-ternary digits rebuild every q in [-364, 364]")
    check(siphash24(bytes(range(26)), TEST_KEY) == 0x17D835B85BBB15F3,
          "siphash24 reproduces the published 26-byte vector")

    path = os.path.join(scratch, "synthetic_tc02.bin")
    write_synthetic_tc02(path)
    mats, hdr = load_tc02(path, KINDS)
    ins = {n.split("/")[1]: i for n, _, i in mats}
    check(len(mats) == 42 and ins["down"] == 864 and ins["wk"] == 320,
          "TC02 parse: 42 ternary matrices; w_down is 864-in (27 chunks), wk 320-in")
    n_w = sum(len(r) * i for _, r, i in mats)
    check(n_w == 6451200, f"TC02 parse: {n_w} ternary weights = tern_tc's 6.45M")

    small, _ = load_tc02(path, ("wk", "down"), layers={0})
    small = [(n, r[:6], i) for n, r, i in small]
    for act in ("ternary", "int8"):
        jobs, ref = build_jobs(small, act, 1, seed=3)
        res = run(RefCell(key=TEST_KEY), jobs, ref, TEST_KEY, log=lambda *_: None)
        check(res["exact"] == res["rows"] and res["counts"]["accepted"] == len(jobs),
              f"honest cell, {act} activations: {res['exact']}/{res['rows']} rows, "
              f"{res['counts']['accepted']}/{len(jobs)} receipts")

    jobs, ref = build_jobs(small, "ternary", 1, seed=3)
    cases = [
        ("wrong_key", "tag", "a cell signing with another key"),
        ("lie", "lie", "a wrong answer with a valid tag"),
        ("damage", "tag", "one flipped tag bit"),
        ("nonce", "fabricated", "a nonce this run never issued"),
        ("impersonate", "node", "a response from another node id"),
        ("drop", "short", "a dropped response"),
    ]
    for fault, kind, what in cases:
        res = run(RefCell(key=TEST_KEY, fault=fault), jobs, ref, TEST_KEY,
                  window=1, log=lambda *_: None)
        passed = res["counts"]["accepted"] == len(jobs) and res["exact"] == res["rows"]
        check(not passed and res["counts"][kind] > 0,
              f"rejects {what} (counted as '{kind}')")
    slip = SlipLink(RefCell(key=TEST_KEY), at=5 * RESP_LEN + 8, count=16)
    res = run(slip, jobs, ref, TEST_KEY, window=8, log=lambda *_: None)
    lines = []
    report(res, None, "ternary", log=lines.append)
    check(res["counts"]["accepted"] == 5 and res["counts"]["node"] == 1
          and res["counts"]["short"] == 1 and res["exact"] < res["rows"]
          and 5 < res["sent"] < len(jobs)
          and f"jobs sent               : {res['sent']} of {len(jobs)} planned" in "\n".join(lines),
          f"16 bytes lost mid-stream (as on the board, 2026-09-27): 5 credited, then stop; "
          f"'jobs sent' reports the {res['sent']} written, not the {len(jobs)} planned")
    cell = RefCell(key=None)
    res = run(cell, jobs, ref, TEST_KEY, log=lambda *_: None)
    check(res["counts"]["status"] == len(jobs) and res["exact"] == 0,
          "an unkeyed cell (status 0x04) gets no credit, though its y is right")
    cell = RefCell(key=None)
    check(install_key(cell, TEST_KEY, log=lambda *_: None) is not None,
          "setkey: ack tag verifies under the key sent")
    res = run(cell, jobs, ref, TEST_KEY, log=lambda *_: None)
    check(res["exact"] == res["rows"], "after setkey, the same cell passes")
    check(install_key(cell, bytes(16 - i for i in range(16)), log=lambda *_: None)
          is not None and run(cell, jobs, ref, TEST_KEY, log=lambda *_: None)["exact"]
          == res["rows"], "a second setkey is refused (0x03) and the first key holds")

    # E5's host half, ahead of E4 (NODE_ETHERNET_PLAN.md): the same receipt
    # machinery over UDP, one datagram per frame, against a software cell on
    # loopback — the peer E4's cosim will reuse.
    bridge = UdpCellBridge(RefCell(key=None))
    ulink = UdpLink(*bridge.addr)
    keyed = install_key(ulink, TEST_KEY, log=lambda *_: None) is not None
    res = run(ulink, jobs, ref, TEST_KEY, log=lambda *_: None)
    check(keyed and res["exact"] == res["rows"]
          and res["counts"]["accepted"] == len(jobs)
          and ulink.echo_ok == len(jobs) + 1 and ulink.echo_bad == 0,
          f"UDP transport: setkey + {res['counts']['accepted']}/{len(jobs)} receipts, "
          f"every row exact, every sequence echoed")
    bridge.stop()

    # A whole request datagram lost: no partial frame, no fabricated answer.
    # The sliding window does not stall on it — 221 of 222 credited — and the
    # run ends on the honest short read with exactly the dropped job's row
    # incomplete. Loss costs one job, never a wrong row.
    bridge = UdpCellBridge(RefCell(key=TEST_KEY))
    bridge.drop_at = 6                       # datagram 6 = request #4 (0-based)
    ulink = UdpLink(*bridge.addr)
    res = run(ulink, jobs, ref, TEST_KEY, log=lambda *_: None)
    check(res["counts"]["short"] == 1
          and res["counts"]["accepted"] == len(jobs) - 1
          and res["counts"]["missing"] == 1
          and res["exact"] == res["rows"] - 1 and ulink.echo_bad == 0,
          f"one lost request datagram: {res['counts']['accepted']} of {len(jobs)} "
          f"credited, {res['exact']}/{res['rows']} rows — the run ends on the "
          f"honest short read, the dropped job's row alone incomplete")
    bridge.stop()

    print(f"self-test: {'PASS' if ok else 'FAIL'}")
    return ok


# ---------------------------------------------------------------------------

def load_key(path, name="node0"):
    if path == "test":
        return TEST_KEY
    for line in open(path):
        p = line.split()
        if len(p) == 2 and p[0] == name and len(p[1]) == 32:
            return bytes.fromhex(p[1])
    raise SystemExit(f"no key for {name} in {path}")


def main():
    a = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    a.add_argument("--port", default="/dev/cu.usbserial-130")
    a.add_argument("--baud", type=int, default=1144744)
    a.add_argument("--udp", metavar="HOST:PORT",
                   help="E5's Ethernet transport (NODE_ETHERNET_PLAN.md): TRI-NET "
                        "frames over UDP, one datagram per frame with a 4-byte "
                        "sequence, instead of the serial port")
    a.add_argument("--keys", default="../trinet-keys.txt",
                   help="key file, or 'test' for the public SipHash test key")
    a.add_argument("--node", default="node0", help="key name in the key file")
    a.add_argument("--model", default=os.path.expanduser(
        "~/igla-coder-gpu/c_infer/model.bin"))
    a.add_argument("--synthetic", action="store_true",
                   help="random ternary weights in tern_tc's shapes (no model.bin)")
    a.add_argument("--all", action="store_true",
                   help="every ternary matrix: wq wk wv wo gate up down")
    a.add_argument("--mats", help=f"comma list from {','.join(KINDS)} "
                                  f"(legacy B.1 set: {','.join(LEGACY_B1)})")
    a.add_argument("--layers", help="comma list of layer indices (default: all)")
    a.add_argument("--act", choices=("ternary", "int8"), default="ternary")
    a.add_argument("--n_x", type=int, default=2, help="activation vectors per width")
    a.add_argument("--seed", type=int, default=0x7213)
    a.add_argument("--window", type=int, default=DEFAULT_WINDOW,
                   help="jobs in flight (default "
                        f"{DEFAULT_WINDOW}; keep 19 x window under the CP2102N's "
                        "512-byte receive buffer)")
    a.add_argument("--setkey", action="store_true",
                   help="install the key first (op 0x02) and verify the ack")
    a.add_argument("--emit-requests", metavar="HEX",
                   help="write the request byte stream for the RTL testbench")
    a.add_argument("--responses", metavar="HEX",
                   help="verify a response stream recorded by the RTL testbench")
    a.add_argument("--self-test", action="store_true")
    args = a.parse_args()

    if args.self_test:
        scratch = os.environ.get("TMPDIR", "/tmp")
        return 0 if self_test(scratch) else 1

    kinds = KINDS if args.all else tuple((args.mats or "wq").split(","))
    layers = set(int(v) for v in args.layers.split(",")) if args.layers else (
        None if (args.all or args.mats) else {0})
    model = args.model
    if args.synthetic:
        model = os.path.join(os.environ.get("TMPDIR", "/tmp"), "synthetic_tc02.bin")
        write_synthetic_tc02(model)
    mats, _hdr = load_tc02(model, kinds, layers)
    key = load_key(args.keys, args.node)
    jobs, rows_ref = build_jobs(mats, args.act, args.n_x, args.seed)

    total_rows = sum(len(r) for _, r, _ in mats)
    nz = sum(1 for _, rs, _ in mats for row in rs for t in row if t)
    tot = sum(len(rs) * i for _, rs, i in mats)
    print(f"{'synthetic' if args.synthetic else os.path.basename(model)}: "
          f"{len(mats)} matrices, {total_rows} rows, {tot} ternary weights "
          f"({100.0 * nz / tot:.1f}% nonzero)")
    print(f"jobs: {len(jobs)} (32-trit chunks x {args.n_x} x-vectors"
          + (f" x {INT8_DIGITS} digit planes" if args.act == "int8" else "") + ")")

    if args.emit_requests:
        stream = (setkey_request(key) if args.setkey else b"") + b"".join(
            request(OP_MAC32, FIRST_JOB_NONCE + i, w, x)
            for i, (w, x, _row, _weight) in enumerate(jobs))
        with open(args.emit_requests, "w") as f:
            f.write("\n".join(f"{b:02x}" for b in stream) + "\n")
        print(f"wrote {len(stream)} request bytes ({len(jobs)} jobs"
              + (" + setkey" if args.setkey else "") + f") to {args.emit_requests}")
        return 0

    if args.responses:
        link = ReplayLink(args.responses)
    elif args.udp:
        if args.setkey:
            print("OP_SETKEY is refused on UDP (NODE_ETHERNET_PLAN.md, E4: the key\n"
                  "is set over the serial port only). Setkey once over serial, then\n"
                  "run --udp without --setkey.")
            return 1
        host, _, port = args.udp.rpartition(":")
        link = UdpLink(host, int(port))
    else:
        link = SerialLink(args.port, args.baud)
    if args.setkey and install_key(link, key) is None:
        return 1
    t0 = time.time()
    res = run(link, jobs, rows_ref, key, args.window)
    elapsed = None if args.responses else time.time() - t0
    if report(res, elapsed, args.act):
        src = "the RTL (iverilog)" if args.responses else "the AX7203"
        print(f"RESULT: every row above computed on {src} bit-exact against the")
        print("        int8-weight oracle, and every receipt verified under the key.")
        return 0
    print("RESULT: FAIL - do not cite these matrices as verified.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
