#!/usr/bin/env python3
"""The batch protocol's request stream, replayed into the real node RTL under iverilog.

tern_tc_batch_runner.py rehearses against HuntingBatchCell, a Python model of
trinet_node_core.v's frame parser. This checks the model where it matters for
the batch ops: on a mixed SETX/DOT6 stream that loses bytes in both wires and
re-sends jobs under fresh nonces. It is the cosim step of
conformance/TERN_TC_BATCH_RTL_PLAN.md, pre-built red: run against the current
core (which has no SETX/DOT6) it must FAIL inside the first SETX answer — the
core answers every valid frame, so equality holds through the 19-byte setkey
ack and the y/status/nonce/node bytes of that answer (y can coincide: the
model echoes the chunk index, which is 0 for chunk 0, and the core's dot
result over the same operand bytes can be 0 too), but the tag never matches:
the model MACs the 20-byte SETX preimage, the core MACs the 26-byte MAC32
one. Observed: first difference at answer byte 30 = tag byte 0 of SETX #1;
the core emits 19 B per frame (4275 = 225 frames x 19) where the model owes
5085 (62x19 + 162x24 + 19). Run against the edited core it must PASS; no
flag changes the verdict.

  1. The rehearsal's smaller pass (wq) drives a keyed HuntingBatchCell through
     a link that drops request bytes (mid-SETX and mid-DOT6) and 44 answer
     bytes inside the DOT6 answer region; the exact request bytes that reach
     the cell are recorded. The run must credit every job and retransmit.
  2. setkey + that recorded stream (zero-padded to whole frames, which cannot
     start a frame) goes through formal/tern_tc_layer_rtl_tb.v with
     fpga/portable/trinet_node_core.v and trinet_siphash24.v, with
     +expect = the model's answer-stream length (the TB generalisation for
     mixed 19/24-byte answers; default remains frames*19).
  3. A fresh, unkeyed HuntingBatchCell gets the same bytes. Its answer stream
     must equal the RTL's, byte for byte — carrying the rehearsal's outcome
     from the model to the RTL.
  4. Negative control: BatchCell without the hunting mixin, which cuts frames
     every 24 bytes, must differ from the RTL on the same lossy stream, or the
     stream does not exercise the parser.

    python3 tern_tc_batch_rtl_cosim.py [--passes wq|both] [--keep DIR]

Needs iverilog and vvp on PATH. No board, no key file: the test key.
Author: Dmitrii Vasilev (@gHashTag)
"""
import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import tern_tc_layer_ax7203 as h  # noqa: E402
from tern_tc_retransmit import RxLoss, TxLoss  # noqa: E402
from tern_tc_batch_model import BatchCell  # noqa: E402
from tern_tc_batch_runner import (  # noqa: E402
    PLANES, TEST_KEY, HuntingBatchCell, rehearsal_passes, run,
)

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


class BlindBatchCell(BatchCell):
    """The negative control's cell: BatchCell with the aligned 24-byte framing
    only — no hunt, exactly RefCell's framing — and the model's out-of-range
    modeling assertion dropped per frame, the same garbage the hunting parser
    drops the same way (HuntingParser.write catches the same ValueError). The
    control's point is the framing, not the assertion."""

    def write(self, b):
        buf = bytearray()
        for c in b:
            buf.append(c)
            if len(buf) == 24:
                try:
                    self._answer(bytes(buf))
                except ValueError:
                    pass
                buf = bytearray()


def scan_ops(stream):
    """Hunt AA 55 and read the op byte, as the parser does: what reached the cell.

    Returns (counts, frames) where frames is [(op_byte, nonce_4bytes)] in stream
    order — every frame the parser assembles, real or phantom."""
    ops, frames, i, n = dict(setx=0, dot6=0, other=0), [], 0, len(stream)
    while i < n - 1:
        if stream[i] == 0xAA and stream[i + 1] == 0x55:
            if i + 2 < n:
                op = stream[i + 2]
                ops["setx" if op == 0x03 else "dot6" if op == 0x04 else "other"] += 1
                frames.append((op, bytes(stream[i + 3:i + 7])))
            i += 24                                   # a whole frame starts here
        else:
            i += 1                                    # hunting, byte by byte
    return ops, frames


def walk_answers(want, frames):
    """The precondition: every op-frame the parser found must own an answer.

    A phantom op-frame (re-assembled from misaligned bytes after a loss) whose
    plane/chunk lands out of range is DROPPED by the model's assertion but will
    be ANSWERED by the RTL (the plan's truncate-and-alias decision) — on such a
    stream the two can never be byte-equal, and this cosim must say so instead
    of reporting a mystery diff. The walk pins the stronger property: the model
    answered exactly the frames the parser found, each with the right length
    (19 B, or 24 for op 0x04), the A5 magic and the frame's nonce echoed at the
    shape's offset (bytes 3..6 standard, 8..11 for DOT6). Returns None when the
    stream is adjudicable, else the reason it is not."""
    pos = 19                                          # bytes 0..18: the setkey ack
    for op, nonce in frames:
        ln = 24 if op == 0x04 else 19
        ans = want[pos:pos + ln]
        if len(ans) < ln or ans[0] != 0xA5:
            return f"no answer for op {op:#04x} at answer byte {pos} (dropped by the model?)"
        off = 8 if op == 0x04 else 3
        if ans[off:off + 4] != nonce:
            return f"answer at byte {pos} does not echo its frame nonce"
        pos += ln
    if pos != len(want):
        return f"{len(want) - pos} answer bytes beyond the frames the parser found"
    return None


def main():
    a = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    a.add_argument("--passes", choices=("wq", "both"), default="wq",
                   help="the wq pass (default) or the full rehearsal pair")
    a.add_argument("--keep", metavar="DIR", help="keep req.hex, resp.hex and the build here")
    args = a.parse_args()
    for tool in ("iverilog", "vvp"):
        if shutil.which(tool) is None:
            print(f"{tool} not on PATH; nothing run")
            return 2

    pss = rehearsal_passes()
    if args.passes == "wq":
        pss = pss[:1]
    n_setx = sum(PLANES * p["C"] for p in pss)
    n_dot6 = sum(p["R"] * p["C"] for p in pss)

    # One request byte lost mid-SETX upload, one mid-DOT6 (after the 24-B setkey
    # frame); 44 answer bytes lost inside the DOT6 answer region. The runner's
    # self-test already proved recovery over this shape of loss. For the full
    # pair the first drop sits 6 bytes later, so the misaligned re-assembly
    # forms no phantom op-frame outside the model's RAM (the model drops those,
    # the RTL will answer them — see walk_answers); the walk below fails loudly
    # if a change ever breaks that property, so the offset is verified, not
    # trusted.
    tx_drops = [24 + (n_setx // 2) * 24 + 11 + (6 if args.passes == "both" else 0),
                24 + n_setx * 24 + (n_dot6 // 3) * 24 + 23]
    rx_holes = [(n_setx * h.RESP_LEN + 8, 44)]

    rec = Recorder(HuntingBatchCell(key=TEST_KEY))
    link = RxLoss(TxLoss(rec, tx_drops), rx_holes)
    results, budget = run(link, pss, key=TEST_KEY, log=lambda s: None)
    model_ok = (all(r["exact"] == r["rows"] for r in results)
                and budget.retransmits > 0 and budget.resyncs > 0)
    print(f"1. model run: {['%s %d/%d rows' % (r['per_pass']['name'], r['exact'], r['rows']) for r in results]}"
          f"; {budget.summary()}")
    print(f"   request bytes that reached the cell: {len(rec.seen)}")

    ops, frames = scan_ops(rec.seen)
    print(f"   frames that reached the cell: {ops['setx']} SETX, {ops['dot6']} DOT6, "
          f"{ops['other']} other (setkey/retransmit/garbage)")

    stream = h.setkey_request(TEST_KEY) + bytes(rec.seen)
    stream += bytes(-len(stream) % 24)                # zeros: complete nothing new, start nothing
    model = HuntingBatchCell()                        # fresh, unkeyed, as the RTL comes up
    model.write(stream)
    want = model.read(1 << 24)
    reason = walk_answers(want, frames)
    adjudicable = reason is None
    print(f"   model answer stream: {len(want)} bytes; adjudicable: "
          + ("yes — every parsed frame owns its answer" if adjudicable else f"NO — {reason}"))
    if not adjudicable:
        print("   the model drops out-of-range phantom frames the RTL will answer "
              "(plan's aliasing decision); this stream cannot be adjudicated byte-for-byte")

    work = args.keep or tempfile.mkdtemp(prefix="batch_cosim_")
    os.makedirs(work, exist_ok=True)
    req, resp, vvp_out = (os.path.join(work, f) for f in ("req.hex", "resp.hex", "tb.vvp"))
    with open(req, "w") as f:
        f.write("\n".join(f"{b:02x}" for b in stream) + "\n")
    t0 = time.time()
    subprocess.run(["iverilog", "-g2012", "-o", vvp_out, os.path.join(REPO, TB)]
                   + [os.path.join(REPO, p) for p in RTL], check=True)
    sim = subprocess.run(["vvp", vvp_out, f"+req={req}", f"+resp={resp}",
                          f"+expect={len(want)}"], capture_output=True, text=True, check=True)
    tb_line = [ln for ln in sim.stdout.splitlines() if ln.startswith("tern_tc_layer_rtl_tb")]
    with open(resp) as f:
        got = bytes(int(t, 16) for t in f.read().split())
    print(f"2. RTL under iverilog: {len(stream)} request bytes in, {len(got)} answer bytes "
          f"out ({time.time() - t0:.1f} s); {tb_line[-1] if tb_line else sim.stdout.strip()[-200:]}")
    same = got == want
    first = next((i for i, (u, v) in enumerate(zip(got, want)) if u != v), min(len(got), len(want)))
    print(f"3. model answers {len(want)} bytes, RTL {len(got)} bytes: "
          + ("identical" if same else f"DIFFER from byte {first}"))
    blind = BlindBatchCell(key=TEST_KEY)              # frames cut every 24 bytes, no hunt
    blind.write(stream)
    control = blind.read(1 << 24) != got
    print(f"4. negative control: BatchCell without the hunting parser "
          + ("differs from the RTL on this stream" if control else "EQUALS the RTL: the stream tests nothing"))
    if not args.keep:
        shutil.rmtree(work, ignore_errors=True)
    ok = model_ok and adjudicable and same and control and len(got) > 0
    if not same and ops["setx"] + ops["dot6"] > 0:
        print("   note: the current core has no SETX/DOT6 ops — a difference at a SETX answer "
              "is the expected red until the RTL edit lands (TERN_TC_BATCH_RTL_PLAN.md)")
    print(f"RESULT: {'PASS' if ok else 'FAIL'} - batch stream, model vs trinet_node_core.v")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
