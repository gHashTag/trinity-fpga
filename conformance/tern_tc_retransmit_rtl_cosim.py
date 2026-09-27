#!/usr/bin/env python3
"""The retransmit protocol's request stream, replayed into the real node RTL under iverilog.

tern_tc_retransmit.py rehearses against HuntingCell, a Python model of trinet_node_core.v's frame
parser. This checks the model where it matters for the protocol: on a stream that re-sends jobs
under fresh nonces, carries a frame missing one byte, and carries the flush zeros.

  1. tern_tc_retransmit.run() drives a keyed HuntingCell through a link that drops one request
     byte (a w byte), one request's last byte, and 56 answer bytes; the exact bytes that reach
     the cell are recorded. The run must credit every job and retransmit.
  2. setkey + that recorded stream (zero-padded to whole frames, which cannot start a frame) goes
     through formal/tern_tc_layer_rtl_tb.v with fpga/portable/trinet_node_core.v and
     trinet_siphash24.v; the testbench writes every answer byte the RTL sends.
  3. A fresh, unkeyed HuntingCell gets the same bytes. Its answer stream must equal the RTL's,
     byte for byte. The run's decisions depend only on the answer bytes, so equality carries the
     rehearsal's outcome for this stream from the model to the RTL.
  4. Negative control: h.RefCell, which cuts frames every 24 bytes without hunting, must differ
     from the RTL on the same stream, or the stream does not exercise the parser.

    python3 tern_tc_retransmit_rtl_cosim.py [--jobs 400] [--keep DIR]

Needs iverilog and vvp on PATH. No board, no key file: the test key.
Author: Dmitrii Vasilev (@gHashTag)
"""
import argparse
import os
import random
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import tern_tc_layer_ax7203 as h  # noqa: E402
import tern_tc_retransmit as rt  # noqa: E402
from trinet_mac32_conformance_ax7203 import golden_dot, pack_trits, N_TRITS  # noqa: E402

TB = "formal/tern_tc_layer_rtl_tb.v"
RTL = ("fpga/portable/trinet_node_core.v", "fpga/openxc7-synth/trinet_siphash24.v")


class Recorder:
    def __init__(self, inner):
        self.inner, self.seen = inner, bytearray()

    def write(self, b):
        self.seen += b
        self.inner.write(b)

    def read(self, n):
        return self.inner.read(n)


def jobs_of(n, seed=27):
    rng = random.Random(seed)
    jobs, rows_ref = [], []
    for i in range(n):
        w = pack_trits([rng.choice((-1, 0, 1)) for _ in range(N_TRITS)])
        x = pack_trits([rng.choice((-1, 0, 1)) for _ in range(N_TRITS)])
        jobs.append((w, x, i, 1))
        rows_ref.append(("cosim", 0, i, golden_dot(w, x)))
    return jobs, rows_ref


def main():
    a = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    a.add_argument("--jobs", type=int, default=400)
    a.add_argument("--keep", metavar="DIR", help="keep req.hex, resp.hex and the build here")
    args = a.parse_args()
    for tool in ("iverilog", "vvp"):
        if shutil.which(tool) is None:
            print(f"{tool} not on PATH; nothing run")
            return 2
    n = args.jobs
    jobs, rows_ref = jobs_of(n)
    R, Q = h.RESP_LEN, 24
    tx_drops = [Q * (n // 4) + 10, Q * (n // 2) + Q - 1]
    rx_holes = [((3 * n // 4) * R + 1, 56)]
    rec = Recorder(rt.HuntingCell(key=h.TEST_KEY))
    link = rt.RxLoss(rt.TxLoss(rec, tx_drops), rx_holes)
    budget = rt.Budget(0x20000000, 3, 256, 32, 24)
    res = rt.run(link, jobs, rows_ref, h.TEST_KEY, 24, h.FIRST_JOB_NONCE, budget, log=lambda s: None)
    c = res["counts"]
    model_ok = c["accepted"] == n and res["exact"] == n and budget.retransmits > 0 and budget.resyncs > 0
    print(f"1. model run: {c['accepted']}/{n} credited, {res['exact']}/{n} rows, {budget.summary()}")
    print(f"   request bytes that reached the cell: {len(rec.seen)} "
          f"(= {n} jobs x 24 + retransmits x 24 + flushes - 2 dropped)")

    stream = h.setkey_request(h.TEST_KEY) + bytes(rec.seen)
    stream += bytes(-len(stream) % Q)                     # zeros: complete nothing new, start nothing
    model = rt.HuntingCell()                              # unkeyed, as the RTL comes up
    model.write(stream)
    want = model.read(1 << 24)

    work = args.keep or tempfile.mkdtemp(prefix="rt_cosim_")
    os.makedirs(work, exist_ok=True)
    req, resp, vvp_out = (os.path.join(work, f) for f in ("req.hex", "resp.hex", "tb.vvp"))
    with open(req, "w") as f:
        f.write("\n".join(f"{b:02x}" for b in stream) + "\n")
    t0 = time.time()
    subprocess.run(["iverilog", "-g2012", "-o", vvp_out, os.path.join(REPO, TB)]
                   + [os.path.join(REPO, p) for p in RTL], check=True)
    sim = subprocess.run(["vvp", vvp_out, f"+req={req}", f"+resp={resp}"], capture_output=True,
                         text=True, check=True)
    tb_line = [ln for ln in sim.stdout.splitlines() if ln.startswith("tern_tc_layer_rtl_tb")]
    with open(resp) as f:
        got = bytes(int(t, 16) for t in f.read().split())
    print(f"2. RTL under iverilog: {len(stream)} request bytes in, {len(got)} answer bytes out "
          f"({time.time() - t0:.1f} s); {tb_line[0] if tb_line else sim.stdout.strip()[-200:]}")
    same = got == want
    first = next((i for i, (u, v) in enumerate(zip(got, want)) if u != v), min(len(got), len(want)))
    print(f"3. model answers {len(want)} bytes, RTL {len(got)} bytes: "
          + ("identical" if same else f"DIFFER from byte {first}"))
    blind = h.RefCell()                                   # frames cut every 24 bytes, no hunt
    blind.write(stream)
    control = blind.read(1 << 24) != got
    print(f"4. negative control: h.RefCell, which cuts frames every 24 bytes, "
          + ("differs from the RTL on this stream" if control else "EQUALS the RTL: the stream tests nothing"))
    if not args.keep:
        shutil.rmtree(work, ignore_errors=True)
    ok = model_ok and same and control and len(got) > 0
    print(f"RESULT: {'PASS' if ok else 'FAIL'} - retransmit stream, model vs trinet_node_core.v")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
