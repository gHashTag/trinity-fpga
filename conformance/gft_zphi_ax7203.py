#!/usr/bin/env python3
"""GFTernary weights on Z[phi] activations, on the AX7203 node cell, every receipt checked.

The TNF paper's weight is GFTernary: t*phi with t in {-1, 0, +1}. Its accumulator
lives in Z[phi] = {a + b*phi : a, b integers}, which is closed because
phi^2 = phi + 1. Applying a weight to a + b*phi gives

    t*phi*(a + b*phi) = t*(b + (a + b)*phi)

(the Fibonacci step), so one output of a GFTernary layer is

    sum_i t_i*phi*(a_i + b_i*phi) = W.b + (W.a + W.b)*phi

and W.a, W.b are ordinary ternary-by-integer dots. With a_i, b_i in [-127, 127]
each is 6 balanced-ternary digit planes, so one 32-wide chunk of one output
costs 12 jobs on the existing node cell. No new RTL, no reflash.

What is checked, and against what:
  * every answer goes through tern_tc_layer_ax7203.run(): status, nonce echo,
    node id, SipHash-2-4 tag recomputed under the key, and y;
  * the oracle is plain Z[phi] multiplication, (a, b)(c, d) = (ac + bd,
    ad + bc + bd), applied to (0, t_i) and (a_i, b_i) and summed. It uses
    neither the Fibonacci shortcut nor the digit split;
  * each output becomes two rows: R must equal the oracle's rational part, and
    A must equal the oracle's phi part minus its rational part. Since
    (R, A) -> (R, A + R) is one-to-one, both rows are bit-exact exactly when the
    output assembled from board answers equals the oracle in Z[phi].

What it does not show: a TNF accumulator (rounding into TNF16 and so on) has no
RTL and does not run here. The digit recombination and the phi assembly (one
integer add per output) happen on the host, in the open. The node computes only
ternary-by-ternary dots, as in tern_tc_layer_ax7203.py.

Board-free checks:
    python3 gft_zphi_ax7203.py --self-test
Board (layer 0, all 7 matrices, one Z[phi] activation vector: 403,200 jobs):
    python3 gft_zphi_ax7203.py --setkey --port <port> --baud 1144744 \\
        --keys ../trinet-keys.txt --model ~/igla-coder-gpu/c_infer/model.bin

Author: Dmitrii Vasilev (@gHashTag)
"""
import argparse
import os
import random
import sys
import time
from decimal import Decimal, getcontext

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tern_tc_layer_ax7203 import (  # noqa: E402
    DEFAULT_WINDOW, FIRST_JOB_NONCE, INT8_DIGITS, KINDS, N_TRITS, OP_MAC32,
    TEST_KEY, RefCell, ReplayLink, SerialLink, balanced_ternary, install_key,
    load_key, load_tc02, pack_trits, report, request, run, setkey_request,
    write_synthetic_tc02,
)

ACT_RANGE = 127          # a_i, b_i in [-127, 127]: 6 balanced-ternary digits


# ---------------------------------------------------------------------------
# Z[phi], exact
# ---------------------------------------------------------------------------

def zmul(p, q):
    """(a + b phi)(c + d phi) with phi^2 = phi + 1."""
    a, b = p
    c, d = q
    return (a * c + b * d, a * d + b * c + b * d)


def zmul_wrong(p, q):
    """A deliberately wrong algebra (phi^2 = 1), for the negative control."""
    a, b = p
    c, d = q
    return (a * c + b * d, a * d + b * c)


def oracle_row(trits, acts, mul=zmul, weight_is_phi=True):
    """sum_i w_i * x_i in Z[phi], w_i = t_i*phi (GFTernary) or t_i."""
    r = p = 0
    for t, x in zip(trits, acts):
        w = (0, t) if weight_is_phi else (t, 0)
        u, v = mul(w, x)
        r += u
        p += v
    return r, p


# ---------------------------------------------------------------------------
# Jobs
# ---------------------------------------------------------------------------

def make_zphi_vector(in_dim, rng):
    return [(rng.randint(-ACT_RANGE, ACT_RANGE), rng.randint(-ACT_RANGE, ACT_RANGE))
            for _ in range(in_dim)]


def planes(values, skip=()):
    digs = [balanced_ternary(v) for v in values]
    return [(3 ** k, [d[k] for d in digs]) for k in range(INT8_DIGITS) if k not in skip]


def build_jobs(mats, n_x, seed, mul=zmul, weight_is_phi=True, skip=()):
    """Jobs (w_bytes, x_bytes, row_id, weight) and rows (name, xi, r, ref).

    Output (matrix, x, r) -> two rows: `name:1` (R = W.b) and `name:phi`
    (A = W.a). Their references come from the Z[phi] oracle, not from W.a, W.b.
    """
    rng = random.Random(seed)
    cache = {}
    jobs, rows_ref = [], []
    for name, rows, in_dim in mats:
        if in_dim % N_TRITS:
            raise SystemExit(f"{name}: input {in_dim} is not a multiple of {N_TRITS}")
        chunks = in_dim // N_TRITS
        if in_dim not in cache:
            vecs = []
            for _ in range(n_x):
                x = make_zphi_vector(in_dim, rng)
                packed = {}
                for part, vals in (("a", [a for a, _ in x]), ("b", [b for _, b in x])):
                    packed[part] = [(wt, [pack_trits(tr[c * N_TRITS:(c + 1) * N_TRITS])
                                          for c in range(chunks)])
                                    for wt, tr in planes(vals, skip)]
                vecs.append((x, packed))
            cache[in_dim] = vecs
        for xi, (x, packed) in enumerate(cache[in_dim]):
            for r, row in enumerate(rows):
                rat, phi = oracle_row(row, x, mul, weight_is_phi)
                wbs = [pack_trits(row[c * N_TRITS:(c + 1) * N_TRITS]) for c in range(chunks)]
                for suffix, part, ref in ((":1", "b", rat), (":phi", "a", phi - rat)):
                    row_id = len(rows_ref)
                    rows_ref.append((name + suffix, xi, r, ref))
                    for wt, xbs in packed[part]:
                        for c in range(chunks):
                            jobs.append((wbs[c], xbs[c], row_id, wt))
    if FIRST_JOB_NONCE + len(jobs) >= 1 << 32:
        raise SystemExit("too many jobs for a 32-bit nonce")
    return jobs, rows_ref


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

def self_test(scratch):
    ok = True

    def check(cond, what):
        nonlocal ok
        print(f"  {'ok  ' if cond else 'FAIL'} {what}")
        ok = ok and cond

    print("self-test (no board)")
    getcontext().prec = 60
    phi = (1 + Decimal(5).sqrt()) / 2
    rng = random.Random(7)
    worst = Decimal(0)
    for _ in range(2000):
        p = (rng.randint(-10**6, 10**6), rng.randint(-10**6, 10**6))
        q = (rng.randint(-10**6, 10**6), rng.randint(-10**6, 10**6))
        u, v = zmul(p, q)
        exact = (p[0] + p[1] * phi) * (q[0] + q[1] * phi)
        worst = max(worst, abs(exact - (u + v * phi)))
    check(worst < Decimal(10) ** -40,
          f"Z[phi] multiply agrees with 60-digit decimal phi on 2000 pairs (worst {worst:.1e})")
    check(all(zmul((0, t), (a, b)) == (t * b, t * (a + b))
              for t in (-1, 0, 1) for a in range(-20, 21) for b in range(-20, 21)),
          "a GFTernary weight applies as the Fibonacci step t*(b, a + b)")

    path = os.path.join(scratch, "synthetic_tc02.bin")
    write_synthetic_tc02(path)
    small, _ = load_tc02(path, ("wk", "down"), layers={0})
    small = [(n, r[:6], i) for n, r, i in small]

    jobs, ref = build_jobs(small, 1, seed=3)
    check(len(jobs) == 6 * (10 + 27) * 2 * INT8_DIGITS,
          f"12 jobs per chunk: {len(jobs)} jobs for 6 rows of wk and 6 of w_down")
    res = run(RefCell(key=TEST_KEY), jobs, ref, TEST_KEY, log=lambda *_: None)
    check(res["exact"] == res["rows"] and res["counts"]["accepted"] == len(jobs),
          f"honest cell: {res['exact']}/{res['rows']} rows, "
          f"{res['counts']['accepted']}/{len(jobs)} receipts")

    controls = [
        (dict(mul=zmul_wrong), "an oracle with phi^2 = 1 instead of phi + 1"),
        (dict(weight_is_phi=False), "weights taken as t, not t*phi (scale forgotten)"),
        (dict(skip=(0,)), "the host dropping digit plane 3^0"),
    ]
    for kw, what in controls:
        j2, r2 = build_jobs(small, 1, seed=3, **kw)
        res = run(RefCell(key=TEST_KEY), j2, r2, TEST_KEY, log=lambda *_: None)
        check(res["exact"] < res["rows"], f"rows fail under {what}: "
                                          f"{res['exact']}/{res['rows']}")
    res = run(RefCell(key=TEST_KEY, fault="lie"), jobs, ref, TEST_KEY, window=1,
              log=lambda *_: None)
    check(res["counts"]["lie"] > 0 and res["exact"] < res["rows"],
          "a validly signed wrong answer is rejected ('lie') and its row fails")
    res = run(RefCell(key=TEST_KEY, fault="wrong_key"), jobs, ref, TEST_KEY, window=1,
              log=lambda *_: None)
    check(res["counts"]["accepted"] == 0, "a cell signing with another key earns nothing")
    print(f"self-test: {'PASS' if ok else 'FAIL'}")
    return ok


# ---------------------------------------------------------------------------

def main():
    a = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    a.add_argument("--port", default="/dev/cu.usbserial-1130")
    a.add_argument("--baud", type=int, default=1144744)
    a.add_argument("--keys", default="../trinet-keys.txt",
                   help="key file, or 'test' for the public SipHash test key")
    a.add_argument("--node", default="node0")
    a.add_argument("--model", default=os.path.expanduser("~/igla-coder-gpu/c_infer/model.bin"))
    a.add_argument("--synthetic", action="store_true")
    a.add_argument("--mats", default=",".join(KINDS))
    a.add_argument("--layers", default="0")
    a.add_argument("--n_x", type=int, default=1)
    a.add_argument("--seed", type=int, default=0x2F1)
    a.add_argument("--window", type=int, default=DEFAULT_WINDOW)
    a.add_argument("--setkey", action="store_true")
    a.add_argument("--emit-requests", metavar="HEX")
    a.add_argument("--responses", metavar="HEX")
    a.add_argument("--self-test", action="store_true")
    args = a.parse_args()

    if args.self_test:
        return 0 if self_test(os.environ.get("TMPDIR", "/tmp")) else 1

    model = args.model
    if args.synthetic:
        model = os.path.join(os.environ.get("TMPDIR", "/tmp"), "synthetic_tc02.bin")
        write_synthetic_tc02(model)
    layers = set(int(v) for v in args.layers.split(","))
    mats, _ = load_tc02(model, tuple(args.mats.split(",")), layers)
    key = load_key(args.keys, args.node)
    jobs, rows_ref = build_jobs(mats, args.n_x, args.seed)
    outs = sum(len(r) for _, r, _ in mats) * args.n_x
    print(f"{'synthetic' if args.synthetic else os.path.basename(model)}: {len(mats)} matrices "
          f"(layers {sorted(layers)}), {outs} Z[phi] outputs, GFTernary weights t*phi")
    print(f"jobs: {len(jobs)} (32-trit chunks x 2 parts x {INT8_DIGITS} digit planes "
          f"x {args.n_x} x-vectors)")

    if args.emit_requests:
        stream = (setkey_request(key) if args.setkey else b"") + b"".join(
            request(OP_MAC32, FIRST_JOB_NONCE + i, w, x) for i, (w, x, _r, _wt) in enumerate(jobs))
        with open(args.emit_requests, "w") as f:
            f.write("\n".join(f"{b:02x}" for b in stream) + "\n")
        print(f"wrote {len(stream)} request bytes to {args.emit_requests}")
        return 0

    link = ReplayLink(args.responses) if args.responses else SerialLink(args.port, args.baud)
    if args.setkey and install_key(link, key) is None:
        return 1
    t0 = time.time()
    res = run(link, jobs, rows_ref, key, args.window)
    elapsed = None if args.responses else time.time() - t0
    passed = report(res, elapsed, "Z[phi], int8 components")
    if passed:
        src = "the RTL (iverilog)" if args.responses else "the AX7203"
        print(f"RESULT: every Z[phi] output above assembled from answers of {src},")
        print("        bit-exact against the Z[phi] oracle, every receipt verified under the key.")
        return 0
    print("RESULT: FAIL - do not cite these outputs as verified.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
