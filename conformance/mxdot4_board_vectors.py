#!/usr/bin/env python3
"""The MXFP4/TNF4 block-dot cell's requests and their expected words.

Every count, seed and table comes from mxdot4_board_params.SPEC, which is generated from
specs/trinet/mxdot4_on_board_ax7203.t27. The element values the golden uses are not the
spec's tables: they are read from the two references and the spec's tables are checked
against them.

  MXFP4  conformance/mxfp_ref.py, decode(FORMATS["mxfp4"], code) for all 16 codes.
  TNF4   research/block/block_tnf.py, tnf_levels(TNF_LEVELS_BITS, TNF_LEVELS_ET). That file
         imports torch and transformers at the top, so the one function is lifted out of it
         with ast and run alone; the file itself is pinned by sha256 in the spec. The levels
         are normalised to a top of 1 and carry no codes; code k is the k-th level upward,
         code 7 (no level) reads as 0. Those two choices are the cell's, stated in the spec.

The golden is exact: S = sum of the 32 products in units of 2^-(2 * UNIT_SHIFT), an integer.

    python3 mxdot4_board_vectors.py --summary          counts per set, checked against the spec
    python3 mxdot4_board_vectors.py --write FILE       one hex line per request, for the testbenches
    python3 mxdot4_board_vectors.py --fraction-check N first N requests of each set, as Fractions
                                                       from the references' decoders and E8M0 scales
"""
import argparse
import ast
import hashlib
import os
import sys
import time
from fractions import Fraction

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
sys.path.insert(0, HERE)

from mxdot4_board_params import SPEC  # noqa: E402
import mxfp_ref  # noqa: E402

OP_MXFP4, OP_TNF4 = SPEC["OP_MXFP4"], SPEC["OP_TNF4"]
OPS = (OP_MXFP4, OP_TNF4)
OP_NAME = {OP_MXFP4: "mxfp4", OP_TNF4: "tnf4"}
UNIT_SHIFT = {OP_MXFP4: SPEC["E2M1_UNIT_SHIFT"], OP_TNF4: SPEC["TNF4_UNIT_SHIFT"]}
SPEC_TABLE = {OP_MXFP4: SPEC["E2M1_INT"], OP_TNF4: SPEC["TNF4_INT"]}
NCODES = 1 << SPEC["ELEM_BITS"]
SIGN = SPEC["SIGN_BIT"]
MASK64 = (1 << 64) - 1


def _sha(rel):
    return hashlib.sha256(open(os.path.join(ROOT, rel), "rb").read()).hexdigest()


def tnf_levels_from_file():
    """block_tnf.tnf_levels, compiled from its own source without importing its module."""
    src = open(os.path.join(ROOT, SPEC["TNF_LEVELS_FILE"])).read()
    fns = [n for n in ast.parse(src).body if isinstance(n, ast.FunctionDef) and n.name == "tnf_levels"]
    if len(fns) != 1:
        raise SystemExit(f"{SPEC['TNF_LEVELS_FILE']}: {len(fns)} definitions of tnf_levels")
    scope = {}
    exec(compile(ast.Module(body=fns, type_ignores=[]), SPEC["TNF_LEVELS_FILE"], "exec"), scope)
    return scope["tnf_levels"](SPEC["TNF_LEVELS_BITS"], SPEC["TNF_LEVELS_ET"])


def reference_tables():
    """{op: [signed element value in units of 2^-UNIT_SHIFT, for each 4-bit code]} and the
    element values as Fractions, both from the references; problems if the spec disagrees."""
    problems = []
    for rel, want in ((SPEC["MXFP_REF_FILE"], SPEC["MXFP_REF_SHA256"]),
                      (SPEC["TNF_LEVELS_FILE"], SPEC["TNF_LEVELS_SHA256"])):
        if _sha(rel) != want:
            problems.append(f"{rel}: sha256 differs from the spec")
    if os.path.realpath(mxfp_ref.__file__) != os.path.realpath(os.path.join(ROOT, SPEC["MXFP_REF_FILE"])):
        problems.append(f"imported mxfp_ref from {mxfp_ref.__file__}, not {SPEC['MXFP_REF_FILE']}")

    fmt = mxfp_ref.FORMATS["mxfp4"]
    frac = {OP_MXFP4: [], OP_TNF4: []}
    for code in range(NCODES):
        v = mxfp_ref.decode(fmt, code)
        if isinstance(v, mxfp_ref.Special):
            problems.append(f"mxfp4 code {code} decodes to {v}")
            v = Fraction(0)
        frac[OP_MXFP4].append(Fraction(v))

    levels = tnf_levels_from_file()
    top, lvl = SPEC["TOP_INT"], SPEC["TNF4_LEVELS"]
    if levels is None or len(levels) != lvl:
        problems.append(f"tnf_levels gives {levels}, spec has {lvl} levels")
        levels = [0.0] * lvl
    # Normalised to 1 in floats; each is k/TOP_INT for a small integer k, recovered exactly.
    raw = [Fraction(x).limit_denominator(4 * top) * top / (1 << UNIT_SHIFT[OP_TNF4]) for x in levels]
    for k, x in enumerate(levels):
        if abs(float(raw[k]) * (1 << UNIT_SHIFT[OP_TNF4]) / top - x) > 1e-12:
            problems.append(f"tnf level {k} = {x} is not a multiple of 1/{top}")
    for code in range(NCODES):
        mag = code & (SIGN - 1)
        v = raw[mag] if mag < lvl else Fraction(0)          # the hole: the cell's choice
        frac[OP_TNF4].append(-v if code & SIGN else v)

    ints = {}
    for op in OPS:
        u = 1 << UNIT_SHIFT[op]
        ints[op] = []
        for code, v in enumerate(frac[op]):
            n = v * u
            if n.denominator != 1:
                problems.append(f"{OP_NAME[op]} code {code}: {v} is not a multiple of 2^-{UNIT_SHIFT[op]}")
            ints[op].append(int(n))
        spec_signed = [(-1 if c & SIGN else 1) * SPEC_TABLE[op][c & (SIGN - 1)] for c in range(NCODES)]
        if ints[op] != spec_signed:
            problems.append(f"{OP_NAME[op]}: reference {ints[op]} != spec {spec_signed}")
    return ints, frac, problems


REF_INT, REF_FRAC, _PROBLEMS = reference_tables()


class SplitMix64:
    def __init__(self, seed):
        self.s = seed & MASK64

    def next(self):
        self.s = (self.s + 0x9E3779B97F4A7C15) & MASK64
        z = self.s
        z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & MASK64
        z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & MASK64
        return z ^ (z >> 31)

    def below(self, n):
        return self.next() % n


def golden(op, sa, sb, a, b):
    """The result word: exact sum, exponent sum, NaN; layout from the spec."""
    if sa == SPEC["SCALE_NAN"] or sb == SPEC["SCALE_NAN"]:
        return SPEC["NAN_WORD"]
    t = REF_INT[op]
    s = sum(t[x] * t[y] for x, y in zip(a, b))
    if abs(s) > SPEC["SUM_MAX"]:
        raise SystemExit(f"sum {s} beyond SUM_MAX")
    return (s & (SPEC["SUM_LIMIT"] * 2 - 1)) | ((sa + sb) << SPEC["EXP_SHIFT"])


def word_value(op, w):
    """The word read back as a number (None for NaN), for the Fraction check and the host."""
    if w >> SPEC["NAN_BIT"] & 1:
        return None
    s = w & (SPEC["SUM_LIMIT"] * 2 - 1)
    if s >= SPEC["SUM_LIMIT"]:
        s -= SPEC["SUM_LIMIT"] * 2
    e = (w >> SPEC["EXP_SHIFT"]) & (SPEC["EXP_LIMIT"] - 1)
    return Fraction(s) * mxfp_ref.pow2(e - 2 * SPEC["SCALE_BIAS"] - 2 * UNIT_SHIFT[op])


def fraction_value(op, sa, sb, a, b):
    """The block dot product straight from the references' element values and E8M0 scales."""
    if sa == SPEC["SCALE_NAN"] or sb == SPEC["SCALE_NAN"]:
        return None
    f = REF_FRAC[op]
    return (sum(f[x] * f[y] for x, y in zip(a, b))
            * mxfp_ref.pow2(sa - SPEC["SCALE_BIAS"]) * mxfp_ref.pow2(sb - SPEC["SCALE_BIAS"]))


def _max_code(op):
    return max(range(SIGN), key=lambda c: REF_INT[op][c])


def pinned():
    n, zero = SPEC["BLOCK"], [0] * SPEC["BLOCK"]
    out = []
    for op in OPS:
        top = _max_code(op)
        neg = top | SIGN
        hole = SPEC["TNF4_HOLE_CODE"]
        rows = [
            (127, 127, zero, zero),
            (127, 127, [SIGN] * n, [SIGN] * n),                        # -0 times -0
            (127, 127, [top] * n, [top] * n),                          # +SUM_MAX
            (127, 127, [top] * n, [neg] * n),                          # -SUM_MAX
            (127, 127, [neg] * n, [neg] * n),                          # +SUM_MAX
            (127, 127, [top] * n, [top if i % 2 else neg for i in range(n)]),
            (127, 127, [top] + zero[1:], [top] + zero[1:]),            # lane 0 alone
            (127, 127, zero[:-1] + [top], zero[:-1] + [neg]),          # lane 31 alone
            (127, 127, [hole] * n, [7] * n),                           # TNF4's hole; E2M1's top
            (255, 127, [top] * n, [top] * n),                          # NaN scales
            (127, 255, [top] * n, [top] * n),
            (255, 255, zero, zero),
            (0, 0, [top] * n, [neg] * n),                              # smallest exponent
            (254, 254, [top] * n, [top] * n),                          # largest exponent
            (0, 254, [top] * n, [top] * n),
            (127, 127, [i % NCODES for i in range(n)], [(NCODES - 1 - i) % NCODES for i in range(n)]),
        ]
        out += [("pinned", op, sa, sb, a, b) for sa, sb, a, b in rows]
    return out


def edge(rng):
    out = []
    for op in OPS:
        for k in range(SPEC["EDGE_PER_OP"]):
            ps = [(k + 7 * i) % SPEC["EDGE_PER_OP"] for i in range(SPEC["BLOCK"])]
            out.append(("edge", op, rng.below(255), rng.below(255),
                        [p >> SPEC["ELEM_BITS"] for p in ps], [p & (NCODES - 1) for p in ps]))
    return out


def rand_block(rng):
    return [rng.below(NCODES) for _ in range(SPEC["BLOCK"])]


def scales(rng):
    return [("scales", op, j >> 8, j & 255, rand_block(rng), rand_block(rng))
            for op in OPS for j in range(SPEC["SCALE_PAIRS_PER_OP"])]


def uniform(rng):
    return [("uniform", op, rng.below(256), rng.below(256), rand_block(rng), rand_block(rng))
            for op in OPS for _ in range(SPEC["RANDOM_UNIFORM_PER_OP"])]


def top(rng):
    out = []
    for op in OPS:
        big = sorted(range(SIGN), key=lambda c: REF_INT[op][c])[-2:]
        for _ in range(SPEC["RANDOM_TOP_PER_OP"]):
            blk = [[big[rng.below(2)] | (SIGN * rng.below(2)) for _ in range(SPEC["BLOCK"])] for _ in range(2)]
            out.append(("top", op, rng.below(255), rng.below(255), blk[0], blk[1]))
    return out


def requests(log=print):
    """[(set, op, sa, sb, a codes, b codes, expected word)], in the order they are sent."""
    if _PROBLEMS:
        raise SystemExit("reference check failed:\n  " + "\n  ".join(_PROBLEMS))
    rng = SplitMix64(SPEC["RANDOM_SEED"])
    t0 = time.monotonic()
    rows = pinned() + edge(rng) + scales(rng) + uniform(rng) + top(rng)
    out = [(name, op, sa, sb, a, b, golden(op, sa, sb, a, b)) for name, op, sa, sb, a, b in rows]
    if len(out) != SPEC["TOTAL_REQUESTS"]:
        raise SystemExit(f"{len(out)} requests, spec says {SPEC['TOTAL_REQUESTS']}")
    log(f"# {len(out)} requests, element values from {SPEC['MXFP_REF_FILE']} and "
        f"{SPEC['TNF_LEVELS_FILE']} in {time.monotonic() - t0:.1f} s")
    return out


def pack(codes):
    """32 codes as 16 bytes, element 2j in the low nibble of byte j."""
    return bytes(codes[2 * j] | (codes[2 * j + 1] << 4) for j in range(SPEC["BLOCK_BYTES"]))


def hex_line(op, sa, sb, a, b, want):
    """{op, sa, sb, A[127:0], B[127:0], expected[23:0]}: element i of A at A[4i+3:4i]."""
    av = int.from_bytes(pack(a), "little")
    bv = int.from_bytes(pack(b), "little")
    return f"{op:02x}{sa:02x}{sb:02x}{av:032x}{bv:032x}{want:06x}"


def summary(reqs):
    per = {}
    for name, op, *_ in reqs:
        per[(name, OP_NAME[op])] = per.get((name, OP_NAME[op]), 0) + 1
    for (name, op), n in sorted(per.items()):
        print(f"{name:8s} {op:5s} {n}")
    nan = sum(1 for r in reqs if r[6] == SPEC["NAN_WORD"])
    sums = [r[6] & (SPEC["SUM_LIMIT"] * 2 - 1) for r in reqs if r[6] != SPEC["NAN_WORD"]]
    sums = [s - SPEC["SUM_LIMIT"] * 2 if s >= SPEC["SUM_LIMIT"] else s for s in sums]
    print(f"total {len(reqs)}  NaN words {nan}  sum range {min(sums)}..{max(sums)}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--summary", action="store_true")
    ap.add_argument("--write", metavar="FILE")
    ap.add_argument("--fraction-check", type=int, metavar="N", default=0)
    args = ap.parse_args()
    reqs = requests()
    if args.summary:
        summary(reqs)
    if args.write:
        h = hashlib.sha256()
        with open(args.write, "w") as f:
            for _name, op, sa, sb, a, b, want in reqs:
                line = hex_line(op, sa, sb, a, b, want) + "\n"
                f.write(line)
                h.update(line.encode())
        print(f"wrote {args.write} ({len(reqs)} lines) sha256 {h.hexdigest()}")
    if args.fraction_check:
        seen, bad, n = {}, 0, 0
        for name, op, sa, sb, a, b, want in reqs:
            key = (name, op)
            if seen.get(key, 0) >= args.fraction_check:
                continue
            seen[key] = seen.get(key, 0) + 1
            n += 1
            if word_value(op, want) != fraction_value(op, sa, sb, a, b):
                bad += 1
                if bad <= 10:
                    print(f"FRACTION MISMATCH {name} {OP_NAME[op]} sa {sa} sb {sb}: word {want:06x}")
        print(f"FRACTION: {n - bad}/{n} words equal the references' block value")
        return 1 if bad else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
