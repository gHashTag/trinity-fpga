#!/usr/bin/env python3
"""igla-coder's tern_tc generating tokens, with every ternary dot product done on the AX7203 node.

Pre-registered in specs/trinet/tern_tc_generate_ax7203.t27; every number comes from the generated
tern_tc_generate_params.py. The layer harness, tern_tc_layer_ax7203.py, is imported and never
edited (its bytes are pinned): its run() sends the jobs, checks every receipt and rebuilds each row.
This runner only builds the jobs from the model's real activations, token by token.

WHAT RUNS WHERE, per generated token:
  board  every row of all 42 ternary matrices (wq wk wv wo gate up down, 6 layers) times the int8
         activation that feeds it: 16,896 rows, 32-trit chunks, 6 balanced-ternary digit planes per
         activation. Each chunk is one signed receipt, checked here.
  host   the embedding lookup, RMSNorms, the 8-bit absmax quantiser, RoPE, attention scores and
         softmax, SiLU, the fp32 tied head (8192 x 320) and the greedy argmax, in float32 as
         igla-coder-gpu/c_infer/tc_infer.c does them.
A chunk whose activation digit plane is all zero is not sent: its dot is 0 whatever the weights
are. Those chunks are counted and printed (SKIP_ZERO_X_CHUNKS in the spec).

The matvec result the host uses is (sum_k 3^k (T . d_k)) / s * g, an exact integer divided once.
tc_infer.c sums q/s in float instead, so the two can differ in the last bits. `--mode c` mirrors
tc_infer.c's float sum to check this file's forward pass against the C reference; the board run
uses the integer path, and its token ids must equal the CPU integer path's (CPU_INT_IDS).

    python3 tern_tc_generate_ax7203.py --self-test
    python3 tern_tc_generate_ax7203.py --cpu --mode c       # tc_infer.c's float matvec
    python3 tern_tc_generate_ax7203.py --cpu                # the integer path, no board
    python3 tern_tc_generate_ax7203.py --refcell            # every job through h.RefCell, no board
    python3 tern_tc_generate_ax7203.py --setkey --port /dev/cu.usbserial-110 --keys ../trinet-keys.txt

Author: Dmitrii Vasilev (@gHashTag)
"""
import argparse
import hashlib
import os
import subprocess
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import tern_tc_layer_ax7203 as h  # noqa: E402
from trinet_mac32_conformance_ax7203 import N_TRITS, pack_trits  # noqa: E402

F32 = np.float32
DIGITS = h.INT8_DIGITS


# ---------------------------------------------------------------------------
# Model file (TC02, the layout in tc_infer.c's header)
# ---------------------------------------------------------------------------

class TC02:
    def __init__(self, path):
        raw = open(os.path.expanduser(path), "rb").read()
        if raw[:4] != b"TC02":
            raise SystemExit(f"{path}: not a TC02 file")
        L, H, KV, D, FF, HD, V = (int(v) for v in np.frombuffer(raw, "<i4", 7, 4))
        self.n_layer, self.n_head, self.n_kv, self.d, self.ff, self.hd, self.vocab = L, H, KV, D, FF, HD, V
        off = 32

        def f32(n):
            nonlocal off
            a = np.frombuffer(raw, "<f4", n, off)
            off += 4 * n
            return a

        def i8(r, c):
            nonlocal off
            a = np.frombuffer(raw, "i1", r * c, off).reshape(r, c)
            off += r * c
            return a

        qd, kvd = H * HD, KV * HD
        self.embed = f32(V * D).reshape(V, D)
        self.layers = []
        for _ in range(L):
            ly = {"norm1": f32(D)}
            for k, r, c in (("wq", qd, D), ("wk", kvd, D), ("wv", kvd, D), ("wo", D, qd)):
                ly[k], ly["g" + k] = i8(r, c), f32(1)[0]
            ly["norm2"] = f32(D)
            for k, r, c in (("gate", FF, D), ("up", FF, D), ("down", D, FF)):
                ly[k], ly["g" + k] = i8(r, c), f32(1)[0]
            self.layers.append(ly)
        self.final_norm = f32(D)
        if off != len(raw):
            raise SystemExit(f"{path}: {len(raw) - off} bytes left over")


# ---------------------------------------------------------------------------
# float32 pieces, in tc_infer.c's order of operations
# ---------------------------------------------------------------------------

def seqsum(a, axis=-1):
    """Left-to-right float32 sum, as a C loop without -ffast-math adds."""
    return np.cumsum(a, axis=axis, dtype=F32).take(-1, axis=axis)


def rms_norm(x, w):
    s = F32(1) / np.sqrt(seqsum(x * x) / F32(x.size) + F32(1e-6))
    return (x * s) * w


def quantize(x):
    """bitlinear_input: pf-RMSNorm, then 8-bit absmax. Returns (q as int64, s)."""
    r = F32(1) / np.sqrt(seqsum(x * x) / F32(x.size) + F32(1e-6))
    v = x * r
    s = F32(127) / max(F32(np.max(np.abs(v))), F32(1e-5))
    t = (v * s).astype(np.float64)                       # exact; lroundf = half away from zero
    q = np.sign(t) * np.floor(np.abs(t) + 0.5)
    return np.clip(q, -128, 127).astype(np.int64), s


def rope(vec, pos, hd):
    half = hd // 2
    i = np.arange(half)
    freq = F32(1) / np.power(F32(10000), (2 * i).astype(F32) / F32(hd))
    ang = F32(pos) * freq
    cs, sn = np.cos(ang), np.sin(ang)
    a, b = vec[:half].copy(), vec[half:].copy()
    vec[:half] = a * cs - b * sn
    vec[half:] = a * sn + b * cs


def softmax(x):
    e = np.exp(x - np.max(x))
    return e / seqsum(e)


def silu(x):
    return x / (F32(1) + np.exp(-x))


# ---------------------------------------------------------------------------
# Integer dot backends
# ---------------------------------------------------------------------------

def digit_planes(q):
    """q (int, |q| <= 364) -> planes[k][j] in {-1,0,1} with q = sum_k 3^k planes[k]."""
    out = np.zeros((DIGITS, q.size), dtype=np.int8)
    q = q.copy()
    for k in range(DIGITS):
        r = q % 3
        d = np.where(r == 2, -1, r)
        out[k] = d
        q = (q - d) // 3
    if np.any(q):
        raise ValueError("value out of range for balanced-ternary digits")
    return out


def pack_chunks(t):
    """t: (..., n) trits, n a multiple of 32 -> list over chunks of 8-byte pack_trits encodings."""
    codes = np.where(t == 1, 1, np.where(t == -1, 2, 0)).astype(np.uint8)
    codes = codes.reshape(*t.shape[:-1], -1, N_TRITS // 4, 4)
    by = codes[..., 0] | codes[..., 1] << 2 | codes[..., 2] << 4 | codes[..., 3] << 6
    return by


class CpuDots:
    """Integer dots on the host. Also counts what the board would be sent, chunk by chunk."""
    name = "cpu"

    def __init__(self):
        self.jobs = self.skipped = self.rows = self.calls = 0

    def dots(self, groups, tag):
        self.calls += 1
        for _name, W, q in groups:
            nz = digit_planes(q).reshape(DIGITS, -1, N_TRITS).any(axis=2)
            self.jobs += W.shape[0] * int(nz.sum())
            self.skipped += W.shape[0] * int((~nz).sum())
            self.rows += W.shape[0]
        return [W.astype(np.int64) @ q for _name, W, q in groups]


class Abort(Exception):
    pass


class BoardDots:
    """Each call: one h.run() over the jobs of a group of matrices that share an activation."""
    name = "board"

    def __init__(self, model, link, key, window, first_nonce, skip_zero, log=print):
        self.link, self.key, self.window, self.skip, self.log = link, key, window, skip_zero, log
        self.next_nonce = first_nonce
        self.tot = dict(jobs=0, skipped=0, accepted=0, rows=0, exact=0, calls=0, seconds=0.0,
                        max_pause=0.0)
        self.node = None
        self.wpack = {}
        for li, ly in enumerate(model.layers):
            for k in h.KINDS:
                self.wpack[f"L{li}/{k}"] = [[bytes(c) for c in row] for row in pack_chunks(ly[k])]
        self.captured = {}
        orig = h._per_matrix

        def spy(rows_ref, acc, complete):             # the harness passes its row sums here
            self.captured = dict(acc=dict(acc), complete=dict(complete))
            return orig(rows_ref, acc, complete)
        h._per_matrix = spy

    def dots(self, groups, tag):
        jobs, rows_ref, bases, refs, skipped = [], [], [], [], 0
        for name, W, q in groups:
            ref = W.astype(np.int64) @ q
            planes = digit_planes(q)
            xb = pack_chunks(planes)                           # (DIGITS, chunks, 8)
            nz = planes.reshape(DIGITS, -1, N_TRITS).any(axis=2)
            xs = [[bytes(c) for c in xb[k]] for k in range(DIGITS)]
            live = [(3 ** k, xs[k], [c for c in range(nz.shape[1]) if nz[k, c] or not self.skip])
                    for k in range(DIGITS)]
            skipped += W.shape[0] * int((~nz).sum()) if self.skip else 0
            wb = self.wpack[name]
            bases.append(len(rows_ref))
            refs.append(ref)
            for r in range(W.shape[0]):
                rid = len(rows_ref)
                rows_ref.append((name, 0, r, int(ref[r])))
                wr = wb[r]
                for weight, xk, cs in live:
                    for c in cs:
                        jobs.append((wr[c], xk[c], rid, weight))
        if self.next_nonce + len(jobs) >= 1 << 32:
            raise Abort("nonce space exhausted")
        h.FIRST_JOB_NONCE = self.next_nonce                    # run() reads the module global
        self.captured = {}
        t0 = time.time()
        res = h.run(self.link, jobs, rows_ref, self.key, self.window)
        dt = time.time() - t0
        self.next_nonce += len(jobs)
        c = res["counts"]
        t = self.tot
        t["jobs"] += len(jobs)
        t["skipped"] += skipped
        t["accepted"] += c["accepted"]
        t["rows"] += len(rows_ref)
        t["exact"] += res["exact"]
        t["calls"] += 1
        t["seconds"] += dt
        t["max_pause"] = max(t["max_pause"], res["max_pause"])
        if res["node"] is not None:
            if self.node is None:
                self.node = res["node"]
            elif res["node"] != self.node:
                raise Abort(f"{tag}: node id {res['node']:#010x} != {self.node:#010x}")
        ok = c["accepted"] == len(jobs) and res["exact"] == len(rows_ref)
        self.log(f"  {tag:<16} jobs {len(jobs):7d}  skipped {skipped:6d}  receipts {c['accepted']:7d}/"
                 f"{len(jobs):<7d} rows {res['exact']:5d}/{len(rows_ref):<5d} {dt:6.1f} s"
                 + ("" if ok else "  FAIL"))
        if not ok:
            bad = {k: v for k, v in c.items() if k != "accepted" and v}
            for m in res["first_bad"]:
                self.log(f"    ! {m}")
            raise Abort(f"{tag}: rejected {bad}")
        acc = self.captured["acc"]
        out = []
        for b, ref in zip(bases, refs):
            got = np.array([acc[b + r] for r in range(ref.size)], dtype=np.int64)
            out.append(got)                                    # the board's sums, not ref
        return out


# ---------------------------------------------------------------------------
# Forward pass (tc_infer.c's forward(), one token)
# ---------------------------------------------------------------------------

class Generator:
    def __init__(self, model, backend, mode="int"):
        m = self.m = model
        self.backend, self.mode = backend, mode
        self.kcache = [[] for _ in range(m.n_layer)]
        self.vcache = [[] for _ in range(m.n_layer)]

    def linear(self, x, specs, tag):
        """specs: [(name, W, g)] sharing input x. Returns float32 outputs."""
        q, s = quantize(x)
        if self.mode == "c":                                   # tc_infer.c: sum of q/s in float
            xf = (q.astype(F32) / s).astype(F32)
            return [seqsum(W.astype(F32) * xf, axis=1) * g for _n, W, g in specs]
        sums = self.backend.dots([(n, W, q) for n, W, _g in specs], tag)
        return [(d.astype(F32) / s) * g for d, (_n, _W, g) in zip(sums, specs)]

    def forward(self, token, pos, tag=""):
        m = self.m
        H, KV, HD = m.n_head, m.n_kv, m.hd
        x = m.embed[token].astype(F32).copy()
        for li, ly in enumerate(m.layers):
            L = f"L{li}"
            xn = rms_norm(x, ly["norm1"])
            q, k, v = self.linear(xn, [(f"{L}/wq", ly["wq"], ly["gwq"]), (f"{L}/wk", ly["wk"], ly["gwk"]),
                                       (f"{L}/wv", ly["wv"], ly["gwv"])], f"{tag}{L}/qkv")
            for hh in range(H):
                rope(q[hh * HD:(hh + 1) * HD], pos, HD)
            for hh in range(KV):
                rope(k[hh * HD:(hh + 1) * HD], pos, HD)
            self.kcache[li].append(k)
            self.vcache[li].append(v)
            K, Vv = np.stack(self.kcache[li]), np.stack(self.vcache[li])
            xo = np.zeros(H * HD, dtype=F32)
            per = H // KV
            for hh in range(H):
                kv = hh // per
                qh = q[hh * HD:(hh + 1) * HD]
                att = softmax(seqsum(K[:, kv * HD:(kv + 1) * HD] * qh, axis=1) / np.sqrt(F32(HD)))
                xo[hh * HD:(hh + 1) * HD] = seqsum(att[:, None] * Vv[:, kv * HD:(kv + 1) * HD], axis=0)
            (o,) = self.linear(xo, [(f"{L}/wo", ly["wo"], ly["gwo"])], f"{tag}{L}/wo")
            x = x + o
            xn = rms_norm(x, ly["norm2"])
            g, u = self.linear(xn, [(f"{L}/gate", ly["gate"], ly["ggate"]),
                                    (f"{L}/up", ly["up"], ly["gup"])], f"{tag}{L}/gate+up")
            (d,) = self.linear(silu(g) * u, [(f"{L}/down", ly["down"], ly["gdown"])], f"{tag}{L}/down")
            x = x + d
        xn = rms_norm(x, m.final_norm)
        return seqsum(m.embed * xn, axis=1)

    def greedy(self, start, n, stop, log=print):
        ids, token, self.margins = [], start, []
        for pos in range(n):
            t0 = time.time()
            logits = self.forward(token, pos, tag=f"t{pos} ")
            token = int(np.argmax(logits))
            ids.append(token)
            top2 = np.partition(logits, -2)[-2:]
            self.margins.append(float(top2[1] - top2[0]))
            log(f"token {pos}: id {token}  ({time.time() - t0:.1f} s)")
            if token == stop:
                break
        return ids


# ---------------------------------------------------------------------------
# Self-test (no board)
# ---------------------------------------------------------------------------

def sha256_file(path):
    with open(os.path.expanduser(path) if path.startswith("~") else os.path.join(REPO, path), "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def git_blob_sha(abs_path, want_sha):
    """The commit whose blob at abs_path hashes to want_sha, or None.

    The fire-2 pin doctrine: the C reference of record may have moved on disk
    since the run was pinned, and the pin stays honest while the pinned bytes
    are reachable in the file's git history. This mirrors gitBlobSha in
    tern_tc_generate_from_spec.mjs, the doctrine's reference implementation —
    same git calls, same early stop on the first matching commit."""
    try:
        top = subprocess.run(["git", "-C", os.path.dirname(abs_path), "rev-parse", "--show-toplevel"],
                             capture_output=True, text=True, check=True).stdout.strip()
        rel = os.path.relpath(abs_path, top)
        commits = subprocess.run(["git", "-C", top, "log", "--all", "--format=%H", "--", rel],
                                 capture_output=True, text=True, check=True).stdout.split()
        for c in commits:
            blob = subprocess.run(["git", "-C", top, "show", f"{c}:{rel}"],
                                  capture_output=True, check=True).stdout
            if hashlib.sha256(blob).hexdigest() == want_sha:
                return c
    except (subprocess.CalledProcessError, OSError):
        pass
    return None


def pins_ok(SPEC, SPEC_FILE, SPEC_SHA256, log=print):
    """Every pinned input is checked before anything runs.

    SPEC, the harness, MAC32 and the model stay strict: those bytes are read at
    run time. The C reference is never read at run time (--mode c is a Python
    float-sum mirror; the greedy ids are recorded constants), so its pin is
    satisfied on disk or by the pinned bytes being reachable in the file's git
    history — the fire-2 doctrine the three generation generators already
    implement; the six wrappers share this one check."""
    ok = True
    for rel, want, strict in ((SPEC_FILE, SPEC_SHA256, True),
                              (SPEC["HARNESS_FILE"], SPEC["HARNESS_SHA256"], True),
                              (SPEC["MAC32_FILE"], SPEC["MAC32_SHA256"], True),
                              (SPEC["MODEL"], SPEC["MODEL_SHA256"], True),
                              (SPEC["C_REF_FILE"], SPEC["C_REF_SHA256"], False)):
        got = sha256_file(rel)
        if got == want:
            continue
        abs_path = os.path.expanduser(rel) if rel.startswith("~") else os.path.join(REPO, rel)
        if not strict and git_blob_sha(abs_path, want):
            continue
        log(f"PIN MISMATCH {rel}: {got[:16]} != {want[:16]}"
            + ("" if strict else " and the pinned bytes are not in the file's git history")
            + "; nothing run")
        ok = False
    return ok


def preflight(SPEC, model, log=print):
    """The CPU integer path must reproduce what the spec fixed before any byte goes to the board."""
    cpu = CpuDots()
    gen = Generator(model, cpu, "int")
    ids = gen.greedy(SPEC["START_TOKEN"], SPEC["N_TOKENS"], SPEC["STOP_TOKEN"], log=lambda s: None)
    got = dict(ids=ids, jobs=cpu.jobs, skipped=cpu.skipped, rows=cpu.rows, calls=cpu.calls,
               margin=int(1000 * min(gen.margins)))
    want = dict(ids=SPEC["CPU_INT_IDS"], jobs=SPEC["JOBS_EXPECTED"], skipped=SPEC["SKIPPED_EXPECTED"],
                rows=SPEC["ROWS_EXPECTED"], calls=SPEC["CALLS_EXPECTED"], margin=SPEC["MIN_MARGIN_MILLI"])
    bad = {k: (got[k], want[k]) for k in want if got[k] != want[k]}
    log(f"preflight (CPU integer path): ids {' '.join(map(str, ids))}; jobs {cpu.jobs}, skipped "
        f"{cpu.skipped}, rows {cpu.rows}, calls {cpu.calls}, smallest logit margin {min(gen.margins):.4f}"
        + ("" if not bad else f"; DIFFERS from the spec: {bad}"))
    return not bad


def self_test(SPEC, model):
    ok = True

    def check(cond, msg):
        nonlocal ok
        print(f"  [{'ok ' if cond else 'FAIL'}] {msg}")
        ok &= bool(cond)

    rng = np.random.default_rng(7)
    t = rng.integers(-1, 2, size=(5, 64)).astype(np.int8)
    pk = pack_chunks(t)
    check(all(bytes(pk[i, c]) == pack_trits([int(v) for v in t[i, c * 32:(c + 1) * 32]])
              for i in range(5) for c in range(2)), "numpy chunk packing equals pack_trits")
    qs = np.arange(-128, 128)
    pl = digit_planes(qs)
    check(all([int(v) for v in pl[:, i]] == h.balanced_ternary(int(qs[i])) for i in range(qs.size)),
          "digit planes equal the harness's balanced_ternary for q in [-128, 127]")
    n = SPEC["N_TOKENS"]
    c_ids = Generator(model, CpuDots(), "c").greedy(SPEC["START_TOKEN"], n, SPEC["STOP_TOKEN"], log=lambda s: None)
    check(c_ids == SPEC["C_GREEDY_IDS"], f"--mode c ids {c_ids} equal tc_infer.c's {SPEC['C_GREEDY_IDS']}")
    check(preflight(SPEC, model, log=lambda s: print("  " + s)),
          "integer path ids, job, skip, row and call counts and the smallest margin equal the spec's")

    # The board path over the harness's reference cell: one real call (layer 0 q/k/v of token 0).
    ly = model.layers[0]
    xn = rms_norm(model.embed[SPEC["START_TOKEN"]].astype(F32), ly["norm1"])
    q, _s = quantize(xn)
    groups = [("L0/wq", ly["wq"], q), ("L0/wk", ly["wk"], q), ("L0/wv", ly["wv"], q)]
    want = CpuDots().dots(groups, "")
    quiet = []
    b = BoardDots(model, h.RefCell(key=h.TEST_KEY), h.TEST_KEY, SPEC["WINDOW"], SPEC["FIRST_JOB_NONCE"],
                  bool(SPEC["SKIP_ZERO_X_CHUNKS"]), log=quiet.append)
    got = b.dots(groups, "L0/qkv")
    check(all(np.array_equal(g, w) for g, w in zip(got, want)) and b.tot["accepted"] == b.tot["jobs"],
          f"reference cell, L0 q/k/v: {b.tot['accepted']}/{b.tot['jobs']} receipts, "
          f"{b.tot['exact']}/{b.tot['rows']} rows, {b.tot['skipped']} chunks skipped, sums equal the CPU's")
    got2 = b.dots(groups, "L0/qkv again")
    check(b.next_nonce == SPEC["FIRST_JOB_NONCE"] + b.tot["jobs"] and all(np.array_equal(g, w) for g, w in zip(got2, want)),
          "a second call continues the nonces and still agrees")
    small = groups[1:2]                                        # wk: 64 rows, up to 3840 jobs
    for fault in ("lie", "damage", "nonce", "impersonate", "wrong_key", "drop"):
        bf = BoardDots(model, h.RefCell(key=h.TEST_KEY, fault=fault, fault_at=1000), h.TEST_KEY,
                       SPEC["WINDOW"], SPEC["FIRST_JOB_NONCE"], True, log=lambda s: None)
        try:
            bf.dots(small, "fault")
            check(False, f"fault '{fault}' at job 1000 was not caught")
        except Abort as e:
            check(True, f"fault '{fault}' at job 1000 stops the run ({str(e)[:60]})")

    # The fire-2 pin doctrine, as the wrapper now implements it: the C reference of
    # record is satisfied on disk or by bytes reachable in its git history; the
    # strict four never fall back. Checked here because pins_ok already passed in
    # main() — the positive path is live, so the negative path needs its own probe.
    from tern_tc_generate_params import SPEC_FILE, SPEC_SHA256
    c_ref_abs = os.path.expanduser(SPEC["C_REF_FILE"]) if SPEC["C_REF_FILE"].startswith("~") \
        else os.path.join(REPO, SPEC["C_REF_FILE"])
    check(git_blob_sha(c_ref_abs, "0" * 64) is None,
          "git history refuses a sha no commit ever had")
    if sha256_file(SPEC["C_REF_FILE"]) != SPEC["C_REF_SHA256"]:
        check(git_blob_sha(c_ref_abs, SPEC["C_REF_SHA256"]) is not None,
              "the pinned C reference bytes are reachable in the file's git history")
    bad = dict(SPEC)
    bad["C_REF_SHA256"] = "0" * 64
    refused = []
    check(pins_ok(bad, SPEC_FILE, SPEC_SHA256, log=refused.append) is False
          and any("git history" in m for m in refused),
          "a C_REF sha nothing ever had fails pins_ok and names the git history")
    check(pins_ok(SPEC, SPEC_FILE, SPEC_SHA256, log=lambda s: None),
          "the live pins satisfy pins_ok (on disk or via git history)")
    return ok


# ---------------------------------------------------------------------------

def main():
    from tern_tc_generate_params import SPEC, SPEC_FILE, SPEC_SHA256
    a = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    a.add_argument("--self-test", action="store_true")
    a.add_argument("--cpu", action="store_true", help="integer dots on the host, no board")
    a.add_argument("--refcell", action="store_true",
                   help="the full board path against the harness's Python model of the node (rehearsal)")
    a.add_argument("--mode", choices=("int", "c"), default="int")
    a.add_argument("--port", default="/dev/cu.usbserial-110")
    a.add_argument("--keys", default="../trinet-keys.txt")
    a.add_argument("--node", default="node0")
    a.add_argument("--setkey", action="store_true")
    a.add_argument("--tokens", type=int, default=SPEC["N_TOKENS"])
    args = a.parse_args()
    if not pins_ok(SPEC, SPEC_FILE, SPEC_SHA256):
        return 2
    model = TC02(SPEC["MODEL"])
    print(f"model {SPEC['MODEL']}: {model.n_layer} layers, d {model.d}, ff {model.ff}, vocab {model.vocab}")
    if args.self_test:
        return 0 if self_test(SPEC, model) else 1
    if args.cpu or args.mode == "c":
        ids = Generator(model, CpuDots(), args.mode).greedy(SPEC["START_TOKEN"], args.tokens, SPEC["STOP_TOKEN"])
        print("ids " + " ".join(map(str, ids)))
        return 0
    if args.tokens != SPEC["N_TOKENS"]:
        print(f"the board run is pre-registered for {SPEC['N_TOKENS']} tokens; nothing run")
        return 2
    if not preflight(SPEC, model):
        print("the CPU path no longer matches the pre-registration; nothing sent to the board")
        return 2
    if args.refcell:
        key, link = h.TEST_KEY, h.RefCell(key=h.TEST_KEY)
        what = "reference-cell receipts "           # a Python model of the node, not the board
    else:
        key = h.load_key(args.keys, args.node)
        link = h.SerialLink(args.port, SPEC["BAUD"])
        if args.setkey and h.install_key(link, key) is None:
            return 1
        what = "receipts verified (tag) "
    board = BoardDots(model, link, key, SPEC["WINDOW"], SPEC["FIRST_JOB_NONCE"], bool(SPEC["SKIP_ZERO_X_CHUNKS"]))
    t0 = time.time()
    try:
        ids = Generator(model, board, "int").greedy(SPEC["START_TOKEN"], SPEC["N_TOKENS"], SPEC["STOP_TOKEN"])
        err = None
    except Abort as e:
        ids, err = None, str(e)
    el = time.time() - t0
    t = board.tot
    print("-" * 66)
    print(f"calls                   : {t['calls']} of {SPEC['CALLS_EXPECTED']} (4 per layer per token)")
    print(f"jobs sent               : {t['jobs']} of {SPEC['JOBS_EXPECTED']} "
          f"(+ {t['skipped']} chunks skipped: activation digit plane all zero)")
    print(f"{what}: {t['accepted']}/{t['jobs']}"
          + (f" under node {board.node:#010x}" if board.node is not None else ""))
    print(f"rows bit-exact          : {t['exact']}/{t['rows']}  (int8 activations from the model's own forward pass)")
    print(f"elapsed                 : {el:.1f} s ({t['accepted'] / max(t['seconds'], 1e-9):.0f} answers/s in run())")
    print(f"longest host pause      : {1000 * t['max_pause']:.1f} ms")
    print("-" * 66)
    if err:
        print(f"RESULT: FAIL - {err}. No token from this run is cited.")
        return 1
    print("ids " + ("refcell" if args.refcell else "board  ") + ": " + " ".join(map(str, ids)))
    print("CPU_INT_IDS: " + " ".join(map(str, SPEC["CPU_INT_IDS"])))
    print("C ids      : " + " ".join(map(str, SPEC["C_GREEDY_IDS"])))
    full = (ids == SPEC["CPU_INT_IDS"] and t["accepted"] == t["jobs"] == SPEC["JOBS_EXPECTED"]
            and t["exact"] == t["rows"] == SPEC["ROWS_EXPECTED"])
    if full and args.refcell:
        print(f"RESULT: REHEARSAL OK - {len(ids)} tokens through the reference cell; the board was not used.")
        return 0
    if full:
        print(f"RESULT: PASS - {len(ids)} tokens generated with every ternary dot product computed on the")
        print("        AX7203 and every receipt verified under the key; ids equal the CPU integer path.")
        return 0
    print("RESULT: FAIL - ids or counts differ from the pre-registration.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
