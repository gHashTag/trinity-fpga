#!/usr/bin/env python3
"""tern_tc_batch_model.py -- BatchCell: reference model of the batched wire protocol.

A board-free reference model of the node under the design pinned by
specs/trinet/tern_tc_batch_ax7203.t27 (protocol-design; nothing here is built
into RTL, nothing here ran on hardware). BatchCell extends the harness's
RefCell with OP_SETX (0x03, upload one 8-byte x chunk of one plane inside a
standard 24-byte request frame) and OP_DOT6 (0x04, up to six 32-trit dots over
the x pinned at one chunk index, one 24-byte answer). OP_MAC32 and OP_SETKEY
keep RefCell semantics untouched. BatchHost is the host half: it builds the
frames, verifies every answer by the same standard the shipped harness uses
(status, nonce echo, node pin, tag over the preimage, y against an independent
golden oracle), and is written against the link interface so the same host
code will drive the real node or the RTL testbench unchanged.

Every constant the spec pins comes from conformance/tern_tc_batch_params.py
(generated from the spec); this file hardcodes nothing the spec fixes. The
one cryptographic rule under test is the spec's preimage rule: the DOT6 tag
MACs the 48 bytes of pinned x READ FROM RAM for that frame's dots, so a node
whose x RAM drifts after SETX (or corrupts a RAM write) cannot produce a
verifiable DOT6 receipt even though its SETX receipt verified -- the self-test
demonstrates both directions.

What this model does not settle, on purpose:
  * The byte-level AA-55 hunt and the flush-resync proof. RefCell-level models
    take 24-byte-aligned frames; that property is pinned in the spec and lives
    in the real parser (fpga/portable/trinet_node_core.v).
  * Out-of-range addressing (plane >= PLANES or chunk >= c_max): resolved by
    decision 1 of TERN_TC_BATCH_RTL_PLAN.md -- not refused. The address
    arithmetic is full width and the RAM's address port truncates, so such an
    address aliases to (plane*c_max + chunk) mod 2^addrbits, identically here
    and in silicon (fpga/portable/trinet_node_core.v). A bogus address harms
    only the host that issued it: the SETX tag still MACs the received bytes,
    the DOT6 tag still MACs what the RAM returned.
  * Timing, RAM cost, throughput. `tri fpga-cost`'s question, never a model's
    claim; the spec's projections are link arithmetic and stay in the spec.

Self-test (no board, no RTL):
    python3 tern_tc_batch_model.py --self-test

Author: Dmitrii Vasilev (@gHashTag)
"""
import argparse
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from trinet_mac32_conformance_ax7203 import (  # noqa: E402
    N_TRITS, STATUS_OK, golden_dot, pack_trits, siphash24,
)
from tern_tc_layer_ax7203 import (  # noqa: E402
    INT8_DIGITS, MAGIC_RESP, RESP_LEN, ST_NO_KEY, TEST_KEY,
    RefCell, balanced_ternary, install_key, parse,
)
from tern_tc_batch_params import SPEC  # noqa: E402

S = SPEC
REQ_LEN = S["REQ_LEN"]                  # 24; every request frame, SETX and DOT6 included
RESP_DOT6_LEN = S["RESP_DOT6_LEN"]      # 24; the six-dot answer
OP_SETX = S["OP_SETX"]                  # 0x03
OP_DOT6 = S["OP_DOT6"]                  # 0x04
PLANES = S["PLANES"]                    # 6
CHUNK_BYTES = S["SETX_CHUNK_BYTES"]     # 8
MASK_ALL = S["DOT6_MASK_ALL"]           # 0x3F
C_WIDE = S["C_DOWN"]                    # 27; widest pass -- the model's default RAM depth

# A public test key (the SipHash reference key). Never deploy it.


def signed(b):
    return b - 256 if b > 127 else b


# ---------------------------------------------------------------------------
# Frames and preimages, exactly as the spec pins them
# ---------------------------------------------------------------------------

def setx_request(nonce, plane, chunk, x8):
    """AA 55 | 03 | nonce4 | plane | chunk | x8 | 00 x7  (24 B)."""
    fr = (bytes([0xAA, 0x55, OP_SETX]) + nonce.to_bytes(4, "little")
          + bytes([plane, chunk]) + x8 + bytes(7))
    assert len(fr) == REQ_LEN, len(fr)
    return fr


def dot6_request(nonce, w8, chunk, mask):
    """AA 55 | 04 | nonce4 | w8 | chunk | mask | 00 x7  (24 B)."""
    fr = (bytes([0xAA, 0x55, OP_DOT6]) + nonce.to_bytes(4, "little")
          + w8 + bytes([chunk, mask]) + bytes(7))
    assert len(fr) == REQ_LEN, len(fr)
    return fr


def setx_preimage(nonce_b, plane, chunk, x8, y, node_id):
    """op nonce4 plane chunk x8 y node4 = 20 B: what the SETX tag MACs."""
    pre = (bytes([OP_SETX]) + nonce_b + bytes([plane, chunk]) + x8
           + bytes([y & 0xFF]) + node_id.to_bytes(4, "little"))
    assert len(pre) == S["PREIMAGE_SETX"], len(pre)
    return pre


def dot6_preimage(nonce_b, w8, chunk, mask, x48, ys6, node_id):
    """op nonce4 w8 chunk mask x48(6 planes read from RAM) y6 node4 = 73 B."""
    pre = (bytes([OP_DOT6]) + nonce_b + w8 + bytes([chunk, mask]) + x48
           + bytes(y & 0xFF for y in ys6) + node_id.to_bytes(4, "little"))
    assert len(pre) == S["PREIMAGE_DOT6"], len(pre)
    return pre


def setx_answer(nonce_b, chunk, status, node_id, tag):
    """The standard 19-B frame, y echoing the chunk index (parses by parse())."""
    return (bytes([MAGIC_RESP, chunk & 0xFF, status]) + nonce_b
            + node_id.to_bytes(4, "little") + tag.to_bytes(8, "little"))


def parse_dot6(raw):
    """A5 | y6 | status | nonce4 | node4 | tag8  (24 B)."""
    return {
        "ys": [signed(b) for b in raw[1:1 + PLANES]],
        "status": raw[1 + PLANES],
        "nonce": int.from_bytes(raw[2 + PLANES:6 + PLANES], "little"),
        "node_id": int.from_bytes(raw[6 + PLANES:10 + PLANES], "little"),
        "tag": int.from_bytes(raw[10 + PLANES:18 + PLANES], "little"),
    }


# ---------------------------------------------------------------------------
# The node: BatchCell
# ---------------------------------------------------------------------------

class BatchCell(RefCell):
    """RefCell plus the two batch ops, fault-injectable like its parent.

    RAM is PLANES x c_max chunks of 8 bytes, addressed (plane, chunk). Faults
    (each on the fault_at-th matching frame, counted per op):
      setx_write_flip -- store a corrupted byte but receipt the received ones
      ram_drift       -- flip a byte of stored x after an honest SETX write
      lie             -- a wrong y byte on a DOT6, honestly signed
      damage          -- one flipped bit in a DOT6 answer's tag
      nonce           -- a nonce this run never issued
      replay          -- an earlier DOT6 answer served again
      drop            -- a swallowed DOT6 answer
    wrong_key (parent's) applies to batch answers too.
    """

    def __init__(self, node_id=0x5452494E, key=None, c_max=C_WIDE,
                 fault=None, fault_at=0, fault_plane=2):
        super().__init__(node_id=node_id, key=key, fault=fault, fault_at=fault_at)
        self.c_max, self.fault_plane = c_max, fault_plane
        # Physical depth is 2^addrbits words, not PLANES*c_max: the address
        # port truncates to addrbits, so an out-of-range (plane, chunk) lands
        # in the slack beyond the used region, never off the end of the RAM.
        # The RTL array is sized the same way; never-written words read zero.
        self.xram = bytearray((1 << (PLANES * c_max - 1).bit_length())
                              * CHUNK_BYTES)
        self.n_setx = self.n_dot6 = 0
        self.first_dot6 = None

    def _alias(self, plane, chunk):
        """Where the RAM's truncated address port lands a (plane, chunk).

        Decision 1 of TERN_TC_BATCH_RTL_PLAN.md: out-of-range addressing is
        not refused. The address arithmetic is full width and the port is
        $clog2(PLANES*c_max) bits wide, so the word addressed is
        (plane*c_max + chunk) mod 2^addrbits -- same word here and in silicon.
        """
        abits = (PLANES * self.c_max - 1).bit_length()   # the RAM address-port width
        return (plane * self.c_max + chunk) & ((1 << abits) - 1)

    def _x(self, plane, chunk):
        off = self._alias(plane, chunk) * CHUNK_BYTES
        return bytes(self.xram[off:off + CHUNK_BYTES])

    def _answer(self, fr):
        if fr[2] == OP_SETX:
            self._answer_setx(fr)
        elif fr[2] == OP_DOT6:
            self._answer_dot6(fr)
        else:
            super()._answer(fr)                    # MAC32 / SETKEY unchanged

    def _answer_setx(self, fr):
        nonce_b, plane, chunk, x8 = fr[3:7], fr[7], fr[8], fr[9:17]
        hit = self.n_setx == self.fault_at
        self.n_setx += 1
        off = self._alias(plane, chunk) * CHUNK_BYTES
        self.xram[off:off + CHUNK_BYTES] = x8
        if hit and self.fault == "setx_write_flip":
            self.xram[off] ^= 0x01                 # RAM holds other than what was sent
        if hit and self.fault == "ram_drift":
            self.xram[off] ^= 0x01                 # drift after the honest write
        sign_key = self._sign_key()
        tag = siphash24(setx_preimage(nonce_b, plane, chunk, x8,
                                      chunk, self.node_id), sign_key)
        resp = setx_answer(nonce_b, chunk,
                           STATUS_OK if self.key is not None else ST_NO_KEY,
                           self.node_id, tag)
        self.out += resp

    def _answer_dot6(self, fr):
        nonce_b, w8, chunk, mask = fr[3:7], fr[7:15], fr[15], fr[16]
        hit = self.n_dot6 == self.fault_at
        self.n_dot6 += 1
        xs = [self._x(p, chunk) for p in range(PLANES)]        # read from RAM, in plane order
        ys = [golden_dot(w8, xs[p]) if mask >> p & 1 else 0
              for p in range(PLANES)]
        if hit and self.fault == "lie":
            ys[self.fault_plane] += 2
        if hit and self.fault == "nonce":
            nonce_b = (int.from_bytes(nonce_b, "little")
                       ^ 0x40000000).to_bytes(4, "little")
        sign_key = self._sign_key()
        tag = siphash24(dot6_preimage(nonce_b, w8, chunk, mask,
                                      b"".join(xs), ys, self.node_id), sign_key)
        resp = (bytes([MAGIC_RESP]) + bytes(y & 0xFF for y in ys)
                + bytes([STATUS_OK if self.key is not None else ST_NO_KEY])
                + nonce_b + self.node_id.to_bytes(4, "little")
                + tag.to_bytes(8, "little"))
        if hit and self.fault == "damage":
            resp = resp[:17] + bytes([resp[17] ^ 0x10]) + resp[18:]
        if hit and self.fault == "replay" and self.first_dot6 is not None:
            resp = self.first_dot6          # serve an earlier answer instead
        if hit and self.fault == "drop":
            return
        if self.first_dot6 is None:
            self.first_dot6 = resp
        self.out += resp

    def _sign_key(self):
        if self.fault == "wrong_key":
            return bytes(16 - i for i in range(16))
        return self.key if self.key is not None else bytes(16)


# ---------------------------------------------------------------------------
# The host: BatchHost
# ---------------------------------------------------------------------------

class BatchHost:
    """Builds frames, verifies answers by the shipped harness's standard.

    Works against any link-shaped object (BatchCell now; a serial port or the
    RTL testbench's response stream later, unchanged).
    """

    def __init__(self, key):
        self.key, self.node_pin, self.nonce_seen = key, None, set()

    def install_key(self, link):
        return install_key(link, self.key, log=lambda *_: None)

    def setx(self, link, nonce, plane, chunk, x8):
        link.write(setx_request(nonce, plane, chunk, x8))
        raw = link.read(RESP_LEN)
        if len(raw) < RESP_LEN or raw[0] != MAGIC_RESP:
            return False, "short", None
        r = parse(raw)
        if r["status"] != STATUS_OK:
            return False, "status", r
        if r["nonce"] != nonce:
            return False, "nonce", r
        if r["nonce"] in self.nonce_seen:
            return False, "duplicate", r
        self.nonce_seen.add(r["nonce"])
        if self.node_pin is None:
            self.node_pin = r["node_id"]
        if r["node_id"] != self.node_pin:
            return False, "node", r
        pre = setx_preimage(nonce.to_bytes(4, "little"), plane, chunk, x8,
                            r["y"], r["node_id"])
        if r["tag"] != siphash24(pre, self.key):
            return False, "tag", r
        if r["y"] != chunk:
            return False, "echo", r                  # y must echo the chunk index
        return True, "ok", r

    def dot6(self, link, nonce, w8, chunk, mask, x_by_plane):
        """x_by_plane: the PLANES chunks the host believes are pinned at `chunk`."""
        link.write(dot6_request(nonce, w8, chunk, mask))
        raw = link.read(RESP_DOT6_LEN)
        if len(raw) < RESP_DOT6_LEN or raw[0] != MAGIC_RESP:
            return False, "short", None
        r = parse_dot6(raw)
        if r["status"] != STATUS_OK:
            return False, "status", r
        if r["nonce"] != nonce:
            return False, "nonce", r
        if r["nonce"] in self.nonce_seen:
            return False, "duplicate", r
        self.nonce_seen.add(r["nonce"])
        if self.node_pin is None:
            self.node_pin = r["node_id"]
        if r["node_id"] != self.node_pin:
            return False, "node", r
        expect = [golden_dot(w8, x_by_plane[p]) if mask >> p & 1 else 0
                  for p in range(PLANES)]
        pre = dot6_preimage(nonce.to_bytes(4, "little"), w8, chunk, mask,
                            b"".join(x_by_plane), r["ys"], r["node_id"])
        tag_ok = r["tag"] == siphash24(pre, self.key)
        if tag_ok and r["ys"] == expect:
            return True, "ok", r
        if tag_ok:
            return False, "lie", r                   # wrong answer, honestly signed
        if r["ys"] != expect:
            return False, "damage", r                # fits neither: RAM drift lands here
        return False, "tag", r


# ---------------------------------------------------------------------------
# A mini matrix pass end to end: same values, same receipt standard, fewer frames
# ---------------------------------------------------------------------------

def mini_pass(cell, host, rng, rows_n=8, in_dim=320):
    """One int8 activation vector through rows_n ternary rows, batched.

    Today this is rows_n x PLANES x C MAC32 jobs; batched it is PLANES x C
    SETX uploads plus rows_n x C DOT6 frames. Returns (exact_rows, frames_now,
    frames_batched) -- counts of THIS run only; the whole-run projections are
    pinned in the spec, not measured here.
    """
    C = in_dim // N_TRITS
    q = [rng.randint(-127, 127) for _ in range(in_dim)]
    digs = [balanced_ternary(v) for v in q]
    plane_trits = [[d[k] for d in digs] for k in range(PLANES)]
    x8 = [[pack_trits(plane_trits[p][c * N_TRITS:(c + 1) * N_TRITS])
           for c in range(C)] for p in range(PLANES)]
    rows = [[rng.choice((-1, 0, 1)) for _ in range(in_dim)] for _ in range(rows_n)]
    w8 = [[pack_trits(row[c * N_TRITS:(c + 1) * N_TRITS]) for c in range(C)]
          for row in rows]
    oracle = [sum(w * v for w, v in zip(row, q)) for row in rows]

    nonce = S["FIRST_JOB_NONCE"]
    for p in range(PLANES):                          # upload once, use rows_n times
        for c in range(C):
            ok, kind, _ = host.setx(cell, nonce, p, c, x8[p][c])
            assert ok, kind
            nonce += 1
    acc = [0] * rows_n
    for r in range(rows_n):
        for c in range(C):
            pinned = [x8[p][c] for p in range(PLANES)]
            ok, kind, res = host.dot6(cell, nonce, w8[r][c], c, MASK_ALL, pinned)
            assert ok, kind
            acc[r] += sum(3 ** p * y for p, y in enumerate(res["ys"]))
            nonce += 1
    exact = sum(a == o for a, o in zip(acc, oracle))
    return exact, rows_n * PLANES * C, PLANES * C + rows_n * C


# ---------------------------------------------------------------------------
# Self-test: every check, each fault shown able to fail
# ---------------------------------------------------------------------------

def self_test():
    ok = True

    def check(cond, what):
        nonlocal ok
        print(f"  {'ok  ' if cond else 'FAIL'} {what}")
        ok = ok and cond

    print("self-test (no board, no RTL)")
    check(REQ_LEN == 24 and OP_SETX == 3 and OP_DOT6 == 4 and PLANES == 6,
          "constants come from the spec's params (24/3/4/6)")
    check(PLANES == INT8_DIGITS,
          "the design's plane count is tern_tc's int8 digit-plane count")

    rng = random.Random(0xB47C)
    x8 = [pack_trits([rng.choice((-1, 0, 1)) for _ in range(N_TRITS)])
          for _ in range(PLANES * 3)]
    check(all(len(setx_request(0x10000, p, c, x8[p * 3 + c])) == REQ_LEN
              for p in range(PLANES) for c in range(3)),
          "SETX frames ride the standard 24-byte request shape")
    check(all(len(dot6_request(0x10000, x8[0], c, MASK_ALL)) == REQ_LEN
              for c in range(3)),
          "DOT6 frames ride the standard 24-byte request shape")
    check(len(setx_answer((0).to_bytes(4, "little"), 7, 1, 0x5452494E, 0)) == RESP_LEN,
          "SETX answers the standard 19-byte frame")

    cell, host = BatchCell(key=TEST_KEY), BatchHost(TEST_KEY)
    check(host.install_key(cell) == 0x5452494E, "setkey works through BatchCell")
    pinned = [[pack_trits([rng.choice((-1, 0, 1)) for _ in range(N_TRITS)])
               for _ in range(3)] for _ in range(PLANES)]
    nonce = S["FIRST_JOB_NONCE"]
    good = True
    for p in range(PLANES):
        for c in range(3):
            okk, kind, _ = host.setx(cell, nonce, p, c, pinned[p][c])
            good = good and okk
            nonce += 1
    w_trits = [rng.choice((-1, 0, 1)) for _ in range(N_TRITS)]
    w8 = pack_trits(w_trits)
    w8_t0z = pack_trits([0] + w_trits[1:])     # trit 0 zero: a drifted trit 0 cannot move y
    w8_t0p = pack_trits([1] + w_trits[1:])     # trit 0 +1: a drifted trit 0 moves y
    ys_want = [golden_dot(w8, pinned[p][1]) for p in range(PLANES)]
    okk, kind, res = host.dot6(cell, nonce, w8, 1, MASK_ALL, [pinned[p][1]
                                                              for p in range(PLANES)])
    check(good and okk and res["ys"] == ys_want,
          f"honest cell: 6 SETX receipts verify, one DOT6 returns the six golden dots")

    okk, kind, res = host.dot6(cell, nonce + 1, w8, 1, 0b010101,
                               [pinned[p][1] for p in range(PLANES)])
    check(okk and res["ys"][1::2] == [0, 0, 0]
          and res["ys"][0] == ys_want[0] and res["ys"][2] == ys_want[2]
          and res["ys"][4] == ys_want[4],
          "a plane mask computes and returns only the planes it names")
    okk, kind, res = host.dot6(cell, nonce + 2, w8, 2, 0,
                               [pinned[p][2] for p in range(PLANES)])
    check(okk and res["ys"] == [0] * PLANES,
          "mask 0 computes nothing but still receipts the RAM it read (an x readback probe)")

    cell, host = BatchCell(key=TEST_KEY), BatchHost(TEST_KEY)
    exact, frames_now, frames_b = mini_pass(cell, host, random.Random(0x51))
    check(exact == 8, "mini pass (8 rows x 320): every row dot bit-exact vs the int8 oracle")
    check(frames_now == 480 and frames_b == 140,
          f"mini pass frame count: {frames_b} batched vs {frames_now} today"
          f" (SETX amortizes over rows)")

    def one_dot6_with(fault, fault_at, chunk=1, mask=MASK_ALL, w=w8,
                      setx_must_pass=True):
        c2, h2 = BatchCell(key=TEST_KEY, fault=fault, fault_at=fault_at,
                           fault_plane=2), BatchHost(TEST_KEY)
        setx_kinds = []
        for p in range(PLANES):
            okk, kind, _ = h2.setx(c2, 0x10000 + p, p, chunk, pinned[p][chunk])
            setx_kinds.append(kind)
            if setx_must_pass:
                assert okk, kind
        return h2.dot6(c2, 0x20000, w, chunk, mask,
                       [pinned[p][chunk] for p in range(PLANES)]), setx_kinds

    cases = [
        ("lie", "lie", "a wrong y byte with a valid tag"),
        ("damage", "tag", "one flipped tag bit"),
        ("nonce", "nonce", "a nonce this run never issued"),
        ("drop", "short", "a dropped answer"),
    ]
    for fault, kind, what in cases:
        (okk, got, _), _sk = one_dot6_with(fault, fault_at=0)
        check(not okk and got == kind,
              f"DOT6 rejects {what} (counted as '{got}')")

    (okk, got, _), sk = one_dot6_with("wrong_key", fault_at=0, setx_must_pass=False)
    check(all(k == "tag" for k in sk) and not okk and got == "tag",
          f"a cell signing with another key: even its SETX receipts refuse"
          f" (all '{sk[0]}'), DOT6 too (counted as '{got}')")

    (okz, gotz, _), _sk = one_dot6_with("ram_drift", fault_at=0, w=w8_t0z)
    check(not okz and gotz == "tag",
          f"RAM drift with a w whose trit 0 is zero: y cannot see it, the tag does"
          f" (counted as '{gotz}')")
    (okp, gotp, _), _sk = one_dot6_with("ram_drift", fault_at=0, w=w8_t0p)
    check(not okp and gotp == "damage",
          f"RAM drift that also moves the dot: fits neither (counted as '{gotp}')")

    c2, h2 = BatchCell(key=TEST_KEY, fault="replay", fault_at=1), BatchHost(TEST_KEY)
    for p in range(PLANES):
        assert h2.setx(c2, 0x10000 + p, p, 1, pinned[p][1])[0]
    ok1, _, _ = h2.dot6(c2, 0x20000, w8, 1, MASK_ALL, [pinned[p][1] for p in range(PLANES)])
    ok2, got, _ = h2.dot6(c2, 0x20001, w8, 1, MASK_ALL, [pinned[p][1] for p in range(PLANES)])
    check(ok1 and not ok2 and got == "nonce",
          f"DOT6 rejects a replayed earlier answer (counted as '{got}'; a windowed"
          f" host would call it 'duplicate')")

    c2, h2 = BatchCell(key=TEST_KEY, fault="setx_write_flip", fault_at=2 * 1 + 1,
                       fault_plane=2), BatchHost(TEST_KEY)
    setx_ok = all(h2.setx(c2, 0x10000 + p, p, 1, pinned[p][1])[0]
                  for p in range(PLANES))
    okk, got, _ = h2.dot6(c2, 0x20000, w8, 1, MASK_ALL,
                          [pinned[p][1] for p in range(PLANES)])
    check(setx_ok and not okk,
          f"a corrupted RAM write passes its SETX receipt (verified {setx_ok})"
          f" and is caught by DOT6 (counted as '{got}')")

    cell, host = BatchCell(key=None), BatchHost(TEST_KEY)
    okk, kind, _ = host.setx(cell, 0x10000, 0, 0, pinned[0][0])
    check(not okk and kind == "status",
          "an unkeyed cell signs nothing (status 0x04), SETX gets no credit")
    cell, host = BatchCell(key=None), BatchHost(TEST_KEY)
    check(host.install_key(cell) is not None,
          "setkey installs through BatchCell")
    check(host.install_key(cell) is not None,
          "a second setkey is refused (0x03) and the first key holds")
    for p in range(PLANES):
        assert host.setx(cell, 0x10000 + p, p, 0, pinned[p][0])[0]
    okk, kind, res = host.dot6(cell, 0x20000, w8, 0, MASK_ALL,
                               [pinned[p][0] for p in range(PLANES)])
    check(okk and res["ys"] == [golden_dot(w8, pinned[p][0]) for p in range(PLANES)],
          "after setkey (and a refused second one), DOT6 still verifies under the first key")
    print(f"self-test: {'PASS' if ok else 'FAIL'}")
    return ok


def main():
    a = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    a.add_argument("--self-test", action="store_true")
    args = a.parse_args()
    if args.self_test:
        return 0 if self_test() else 1
    print(__doc__)
    return 0


if __name__ == "__main__":
    sys.exit(main())
