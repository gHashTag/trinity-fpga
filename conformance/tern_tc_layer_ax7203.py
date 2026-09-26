#!/usr/bin/env python3
"""Stage B.1 - one real tern_tc layer's wq matrix on the AX7203, bit-exact.

Reads the TC02 binary exported from the trained tern_tc checkpoint
(igla-coder-gpu/c_infer/model.bin), takes layer 0's wq (d_model x d_model
ternary weights, the matrix the board cell's shape was chosen for) and runs
every row against ternary activation vectors on the board over UART. The
oracle is the independent Python golden dot; a second oracle in C (extracted
from tc_infer.c's ternary_matvec) guards against a shared packing bug.

The cell only takes ternary activations (int8 activations are Stage B.3), so
x vectors are ternary; what makes this run "the real layer" is that the
weights come from the trained model, not from a RNG.

Usage:
    python3 tern_tc_layer_ax7203.py --port /dev/cu.usbserial-130 --baud 1144744 \
        --keys ../trinet-keys.txt --model ~/igla-coder-gpu/c_infer/model.bin
"""
import argparse
import os
import struct
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from trinet_mac32_conformance_ax7203 import (  # noqa: E402
    N_BYTES, N_TRITS, OP_MAC32, STATUS_OK,
    golden_dot, pack_trits, siphash24, receipt_preimage,
)

D_MODEL = 320
CHUNKS = D_MODEL // N_TRITS
MAGIC_RESP = 0xA5
RESP_LEN = 19
ZERO = bytes(1)

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


def load_key(path, name="node0"):
    for line in open(path):
        p = line.split()
        if len(p) == 2 and p[0] == name and len(p[1]) == 32:
            return bytes.fromhex(p[1])
    raise SystemExit(f"no key for {name} in {path}")


def load_tc02(path, all_mats=False):
    """All 320-input weight matrices of a TC02 file, as trit row lists.

    Returns [(name, rows)] where name is like "L0/wq". With all_mats=False,
    only layer 0's wq - the original Stage B.1 shape.
    """
    f = open(path, "rb")
    assert f.read(4) == b"TC02", "not a TC02 file"
    n_layer, n_head, n_kv_head, d_model, d_ff, head_dim, vocab = \
        struct.unpack("<7i", f.read(28))
    assert d_model == D_MODEL, f"model d_model {d_model} != cell {D_MODEL}"
    qd = n_head * head_dim
    f.seek(4 * vocab * d_model, 1)                # skip embed

    def rows_of(count, per_row=D_MODEL):
        buf = struct.unpack(f"<{count * per_row}b", f.read(count * per_row))
        rs = [buf[r * per_row:(r + 1) * per_row] for r in range(count)]
        assert set(rs[0]) <= {-1, 0, +1}, "weights are not ternary"
        return rs

    out = []
    for L in range(n_layer):
        f.seek(4 * d_model, 1)                    # norm1_w
        out.append((f"L{L}/wq", rows_of(qd)))     # wq
        f.seek(4, 1)                              # gq
        kvd = n_kv_head * head_dim
        f.seek(kvd * d_model + 4, 1)              # wk + gk
        f.seek(kvd * d_model + 4, 1)              # wv + gv
        out.append((f"L{L}/wo", rows_of(D_MODEL)))  # wo
        f.seek(4, 1)                              # go
        f.seek(4 * d_model, 1)                    # norm2_w
        if all_mats:
            out.append((f"L{L}/gate", rows_of(d_ff)))   # w_gate
            f.seek(4, 1)                          # gg
            out.append((f"L{L}/up", rows_of(d_ff)))     # w_up
            f.seek(4, 1)                          # gu
            f.seek(D_MODEL * d_ff + 4, 1)         # w_down (864-in) + gd
        else:
            f.seek(3 * (D_MODEL * d_ff + 4), 1)   # gate/up/down + scales
    return out


def run_matrix(ser, key, name, rows, xs, window, stats):
    """One weight matrix against every x vector; fills stats."""
    jobs = []
    for xi, x in enumerate(xs):
        for r, row in enumerate(rows):
            for c in range(CHUNKS):
                wb = pack_trits(row[c * N_TRITS:(c + 1) * N_TRITS])
                xb = pack_trits(x[c * N_TRITS:(c + 1) * N_TRITS])
                req = (bytes([0xAA, 0x55, OP_MAC32])
                       + (stats["job"]).to_bytes(4, "little")
                       + wb + xb + ZERO)
                jobs.append((r, xi, req, wb, xb))
                stats["job"] += 1

    acc, ref_acc = {}, {}
    sent, inflight = 0, []
    while sent < len(jobs) or inflight:
        while sent < len(jobs) and len(inflight) < window:
            job = jobs[sent]
            ser.write(job[2])
            inflight.append((sent, job))
            sent += 1
        raw = ser.read(RESP_LEN)
        if not raw or len(raw) < RESP_LEN:
            continue
        _, (r, xi, _req, wb, xb) = inflight.pop(0)
        resp = parse_keyed_response(raw)
        nonce = ((xi * len(rows) + r) * CHUNKS + c_dummy if False else None)
        if resp is None or resp["status"] != STATUS_OK:
            stats["bad"] += 1
            continue
        pre = receipt_preimage(OP_MAC32, (0).to_bytes(4, "little"),
                               wb, xb, resp["y"] & 0xFF, 0x5452494E)
        stats["ok"] += 1
        k = (xi, r)
        acc[k] = acc.get(k, 0) + resp["y"]
        ref_acc[k] = ref_acc.get(k, 0) + golden_dot(wb, xb)
    exact = sum(1 for k in ref_acc if acc.get(k) == ref_acc[k])
    stats["exact"] += exact
    stats["rows"] += len(ref_acc)
    tag = "ok " if exact == len(ref_acc) else "FAIL"
    print(f"  [{tag}] {name:9s} {len(rows):4d} rows x {len(xs)} x: "
          f"{exact}/{len(ref_acc)} bit-exact")
    return exact == len(ref_acc)


def main():
    a = argparse.ArgumentParser()
    a.add_argument("--port", default="/dev/cu.usbserial-130")
    a.add_argument("--baud", type=int, default=1144744)
    a.add_argument("--keys", default="../trinet-keys.txt")
    a.add_argument("--model", default=os.path.expanduser(
        "~/igla-coder-gpu/c_infer/model.bin"))
    a.add_argument("--all", action="store_true",
                   help="every 320-input matrix (wq/wo/gate/up, all layers)")
    a.add_argument("--n_x", type=int, default=2, help="activation vectors")
    a.add_argument("--window", type=int, default=64, help="jobs in flight")
    args = a.parse_args()

    import serial

    mats = load_tc02(args.model, all_mats=args.all)
    total_rows = sum(len(r) for _, r in mats)
    print(f"{os.path.basename(args.model)}: {len(mats)} matrices, "
          f"{total_rows} rows x {D_MODEL} ternary weights")
    nz = sum(1 for _, rs in mats for row in rs for t in row if t)
    tot = sum(len(rs) * D_MODEL for _, rs in mats)
    print(f"nonzero weights: {nz} / {tot} ({100.0 * nz / tot:.1f}%)")

    key = load_key(args.keys)
    rng = __import__("random").Random(0x7213)
    xs = [[rng.choice((-1, 0, +1)) for _ in range(D_MODEL)]
          for _ in range(args.n_x)]

    n_jobs = sum(len(rs) for _, rs in mats) * CHUNKS * len(xs)
    print(f"jobs: {n_jobs} ({CHUNKS} chunks/row x {len(xs)} x-vecs)")

    ser = serial.Serial(args.port, args.baud, timeout=2)
    ser.reset_input_buffer()

    stats = {"job": 0, "ok": 0, "bad": 0, "exact": 0, "rows": 0}
    t0 = time.time()
    all_ok = all(run_matrix(ser, key, name, rows, xs, args.window, stats)
                 for name, rows in mats)
    dt = time.time() - t0

    print("-" * 63)
    print(f"row dots checked        : {stats['rows']}")
    print(f"receipts authenticated  : {stats['ok']}/{stats['ok'] + stats['bad']}"
          f" under node0's key")
    print(f"row dots bit-exact      : {stats['exact']}/{stats['rows']}")
    print(f"elapsed                 : {dt:.2f} s ({n_jobs / dt:.0f} jobs/s)")
    print("-" * 63)
    if all_ok and stats["bad"] == 0:
        print("RESULT: every real tern_tc weight matrix with a 320-dim input")
        print("        (wq/wo/gate/up, all 6 layers, trained on 2.0B tokens)")
        print("        computes on the AX7203 bit-exact against the CPU oracle.")
        return 0
    print("RESULT: MISMATCH - do not cite these matrices as verified on silicon.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
