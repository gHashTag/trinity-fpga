#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""trinet_matvec_demo.py — one ternary matvec of the `tc` shape on real silicon.

Roadmap item B.2 (research/MODEL_ON_FPGA_PLAN.md): run a d_model=320 matvec —
the primitive one layer of the TRI CLAW model needs — through the TRI-NET node
cell on the AX7203 and check it bit-exact against an independent integer
oracle computed here.

What this proves, exactly:
  * the board computes 320 ternary dot products of width 320 (3200 jobs of
    width 32) with every receipt authenticated under the node's key, and the
    assembled matvec equals the oracle row for row.

What this does NOT prove (honesty):
  * activations here are TERNARY, because the multiplier-free cell multiplies
    ternary by ternary. The real `tc` model uses int8 activations; supporting
    them is Stage B.3 (SoC) work, not this cell.
  * the weights are random ternary until Stage B.1 ships the real `model.bin`.
    The datapath is what is under test, not the weights.

Encoding law lives in exactly one place: `model_trits_to_cell_packed`. The
model side emits values in {-1, 0, +1}; the cell wants 2-bit codes
(00=0, 01=+1, 10=-1), LSB-first. Three incompatible encodings live in this
tree — never wire a second one in here.

Usage:
    python3 trinet_matvec_demo.py --self-test
    python3 trinet_matvec_demo.py --port /dev/cu.usbserial-130 --baud 1144744 \
        --keys ../../trinet-keys.txt

Author: Dmitrii Vasilev (@gHashTag)
"""

import argparse
import os
import random
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from trinet_mac32_conformance_ax7203 import (  # noqa: E402
    N_BYTES, N_TRITS, OP_MAC32, STATUS_OK,
    golden_dot, pack_trits, receipt_preimage, siphash24, unpack_trits,
)

D_MODEL = 320
CHUNKS = D_MODEL // N_TRITS          # 10 dots of width 32 per row
ROWS = D_MODEL                       # 320 rows -> 3200 jobs
MAGIC_RESP = 0xA5
RESP_LEN = 19                        # v2: SipHash-2-4 keyed tag


def model_trits_to_cell_packed(trits) -> bytes:
    """The ONLY place the model's trit values meet the cell's wire codes."""
    return pack_trits(trits)


def random_ternary_vector(rng, n):
    return [rng.choice((-1, 0, +1)) for _ in range(n)]


def parse_keyed_response(raw: bytes):
    if len(raw) < RESP_LEN or raw[0] != MAGIC_RESP:
        return None
    return {
        "y": raw[1] - 256 if raw[1] > 127 else raw[1],
        "status": raw[2],
        "nonce": raw[3:7],
        "node_id": int.from_bytes(raw[7:11], "little"),
        "tag": int.from_bytes(raw[11:19], "little"),
    }


def load_key(path: str, name: str = "node0") -> bytes:
    for line in open(path):
        parts = line.split()
        if len(parts) == 2 and parts[0] == name and len(parts[1]) == 32:
            return bytes.fromhex(parts[1])
    raise SystemExit(f"no key for {name} in {path}")


def self_test() -> bool:
    rng = random.Random(0x7213)
    for _ in range(256):
        w = random_ternary_vector(rng, N_TRITS)
        x = random_ternary_vector(rng, N_TRITS)
        wb = model_trits_to_cell_packed(w)
        if unpack_trits(wb) != w:
            print("FAIL: pack/unpack round trip")
            return False
        brute = sum(a * b for a, b in zip(w, x))
        if golden_dot(wb, model_trits_to_cell_packed(x)) != brute:
            print("FAIL: golden dot vs brute force")
            return False
    key = bytes(range(16))
    nonce = bytes(4)
    pre = receipt_preimage(OP_MAC32, nonce, bytes(N_BYTES), bytes(N_BYTES), 0, 0)
    if siphash24(pre, key) != siphash24(pre, key):
        print("FAIL: siphash not deterministic")
        return False
    print(f"self-test: pack/oracle/dot OK ({ROWS}x{D_MODEL} shape ready)")
    return True


def run_matvec(port: str, baud: int, key: bytes, window: int = 64) -> bool:
    import serial

    rng = random.Random(0x7213)
    w_rows = [random_ternary_vector(rng, D_MODEL) for _ in range(ROWS)]
    x_vec = random_ternary_vector(rng, D_MODEL)

    # Oracle, row by row, from the packed cells (never from the trits).
    ref = []
    for r in w_rows:
        acc = 0
        for c in range(CHUNKS):
            wb = model_trits_to_cell_packed(r[c * N_TRITS:(c + 1) * N_TRITS])
            xb = model_trits_to_cell_packed(x_vec[c * N_TRITS:(c + 1) * N_TRITS])
            acc += golden_dot(wb, xb)
        ref.append(acc)

    jobs = []  # (job_index, request, w_bytes, x_bytes)
    for i in range(ROWS):
        for c in range(CHUNKS):
            wb = model_trits_to_cell_packed(w_rows[i][c * N_TRITS:(c + 1) * N_TRITS])
            xb = model_trits_to_cell_packed(x_vec[c * N_TRITS:(c + 1) * N_TRITS])
            jobs.append((i, bytes([0xAA, 0x55, OP_MAC32]) + i.to_bytes(4, "little") + wb + xb + b"\x00", wb, xb))

    ser = serial.Serial(port, baud, timeout=2)
    ser.reset_input_buffer()

    t0 = time.time()
    dot = {}            # (row, chunk) -> y
    authenticated = 0
    bad = []
    head = 0            # next job to send
    next_read = 0       # next job whose response is due

    def send(n):
        nonlocal head
        while head < len(jobs) and n > 0:
            ser.write(jobs[head][1])
            head += 1
            n -= 1

    send(window)
    while next_read < len(jobs):
        resp = parse_keyed_response(ser.read(RESP_LEN))
        if resp is None:
            bad.append(f"job {next_read}: no/short response")
            next_read += 1
            continue
        i, _req, wb, xb = jobs[next_read]
        expected = golden_dot(wb, xb)
        pre = receipt_preimage(OP_MAC32, resp["nonce"], wb, xb, resp["y"], resp["node_id"])
        tag_ok = resp["tag"] == siphash24(pre, key)
        if (resp["status"] == STATUS_OK and resp["nonce"] == i.to_bytes(4, "little")
                and resp["y"] == expected and tag_ok):
            authenticated += 1
            dot[(i, next_read % CHUNKS)] = resp["y"]
        else:
            bad.append(f"job {next_read}: status={resp['status']:#04x} y={resp['y']} "
                       f"expected={expected} tag_ok={tag_ok}")
        next_read += 1
        send(1)
    elapsed = time.time() - t0
    ser.close()

    # Assemble the matvec from silicon answers only.
    matvec = [sum(dot.get((i, c), None) if dot.get((i, c)) is not None else 10**9
                  for c in range(CHUNKS)) for i in range(ROWS)]
    exact = sum(1 for i in range(ROWS) if matvec[i] == ref[i])

    print(f"matvec {ROWS}x{D_MODEL} ternary x ternary on {port} @ {baud}")
    print("-" * 63)
    print(f"jobs (32-wide dots)   : {len(jobs)}")
    print(f"receipts authenticated: {authenticated}/{len(jobs)} under node0's key")
    print(f"rows bit-exact        : {exact}/{ROWS}")
    print(f"elapsed               : {elapsed:.2f} s ({len(jobs) / elapsed:.0f} jobs/s)")
    for b in bad[:8]:
        print(f"  {b}")
    print("-" * 63)
    if exact == ROWS and authenticated == len(jobs):
        print("RESULT: the datapath a model layer needs is verified on silicon.")
        print("        (ternary activations; int8 activations are Stage B.3.)")
        return True
    print("RESULT: not bit-exact — do not cite this as a verified model layer.")
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port")
    ap.add_argument("--baud", type=int, default=1144744)
    ap.add_argument("--keys", default="trinet-keys.txt")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        sys.exit(0 if self_test() else 1)
    if not a.port:
        ap.error("--port is required without --self-test")
    sys.exit(0 if run_matvec(a.port, a.baud, load_key(a.keys)) else 1)


if __name__ == "__main__":
    main()
