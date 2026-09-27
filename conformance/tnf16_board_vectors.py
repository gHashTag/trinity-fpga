#!/usr/bin/env python3
"""The TNF16 board cell's requests and their expected words.

Every count, seed and range comes from tnf16_board_params.SPEC, which is generated from
specs/trinet/tnf16_on_board_ax7203.t27. Expected words come from tnf_ref.tef_add / tef_mul,
TNFFormat(EXP_TRITS, MANT_BITS); nothing here computes TNF arithmetic itself.

    python3 tnf16_board_vectors.py --summary           counts per set, checked against the spec
    python3 tnf16_board_vectors.py --write FILE        one "op a b expected" hex line per request
    python3 tnf16_board_vectors.py --model-check       tnf16_rtl_model against the reference, all requests
"""
import argparse
import hashlib
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from tnf16_board_params import SPEC  # noqa: E402
import tnf_ref  # noqa: E402

FMT = tnf_ref.TNFFormat(SPEC["EXP_TRITS"], SPEC["MANT_BITS"])
OP_ADD, OP_MUL = SPEC["OP_ADD"], SPEC["OP_MUL"]
OPS = (OP_ADD, OP_MUL)
MASK64 = (1 << 64) - 1


def check_reference():
    """The reference and format the spec names, not whatever is importable."""
    problems = []
    for rel, want in ((SPEC["REF_FILE"], SPEC["REF_SHA256"]),
                      (SPEC["REF_VERSIONS_FILE"], SPEC["REF_VERSIONS_SHA256"])):
        path = os.path.join(HERE, "..", rel)
        got = hashlib.sha256(open(path, "rb").read()).hexdigest()
        if got != want:
            problems.append(f"{rel}: sha256 {got} != spec")
    if os.path.realpath(tnf_ref.__file__) != os.path.realpath(os.path.join(HERE, "..", SPEC["REF_FILE"])):
        problems.append(f"imported tnf_ref from {tnf_ref.__file__}, not {SPEC['REF_FILE']}")
    if tnf_ref.VECTOR_SPEC_VERSION != SPEC["VEC_SPEC_VERSION"]:
        problems.append(f"tnf_ref VECTOR_SPEC_VERSION {tnf_ref.VECTOR_SPEC_VERSION} != spec")
    derived = dict(OFFSET_MAX=FMT.offset_max, EXP_OFFSET=FMT.exp_offset, OFF_BITS=FMT.exp_bits,
                   SIGN_SHIFT=FMT.sign_shift, EXP_SHIFT=FMT.exp_shift, POS_INF=FMT.inf,
                   MANT_SCALE=FMT.mant,
                   CANON_NAN=(FMT.offset_max << FMT.exp_shift) | 1,
                   ONE=tnf_ref.encode(FMT, 1))
    for k, v in derived.items():
        if SPEC[k] != v:
            problems.append(f"{k}: spec {SPEC[k]} != reference {v}")
    return problems


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

    def between(self, lo, hi):
        return lo + self.below(hi - lo + 1)


def word(sign, off, mant):
    return (sign << SPEC["SIGN_SHIFT"]) | (off << SPEC["EXP_SHIFT"]) | mant


def pinned():
    path = os.path.join(HERE, "..", SPEC["VEC_FILE"])
    raw = open(path, "rb").read()
    if hashlib.sha256(raw).hexdigest() != SPEC["VEC_SHA256"]:
        raise SystemExit(f"{SPEC['VEC_FILE']}: sha256 differs from the spec")
    out = []
    for line in raw.decode().splitlines():
        if not line or line.startswith("#"):
            continue
        op, a, b, want = line.split()
        out.append((OP_ADD if op == "add" else OP_MUL, int(a, 16), int(b, 16), int(want, 16)))
    return out


def edge():
    codes = [word(s, o, m) for s in (0, 1) for o in SPEC["EDGE_OFFSETS"] for m in SPEC["EDGE_MANTS"]]
    return [(op, a, b) for op in OPS for a in codes for b in codes]


def uniform(rng):
    top = 1 << SPEC["WORD_BITS"]
    return [(op, rng.below(top), rng.below(top))
            for op in OPS for _ in range(SPEC["RANDOM_UNIFORM_PER_OP"])]


def near(rng):
    lo, hi, gap = 1, SPEC["OFFSET_MAX"] - 1, SPEC["NEAR_ADD_MAX_GAP"]
    mant = SPEC["MANT_SCALE"]
    bands = SPEC["NEAR_MUL_SUM_BANDS"]
    out = []

    def rand_word(off):
        return word(rng.below(2), off, rng.below(mant))

    for _ in range(SPEC["RANDOM_NEAR_PER_OP"]):
        oa = rng.between(lo, hi)
        while True:
            ob = oa + rng.between(-gap, gap)
            if lo <= ob <= hi:
                break
        out.append((OP_ADD, rand_word(oa), rand_word(ob)))
    for _ in range(SPEC["RANDOM_NEAR_PER_OP"]):
        band = rng.below(len(bands) // 2)
        s = rng.between(bands[2 * band], bands[2 * band + 1])
        oa = rng.between(max(lo, s - hi), min(hi, s - lo))
        out.append((OP_MUL, rand_word(oa), rand_word(s - oa)))
    return out


def golden(op, a, b):
    return tnf_ref.tef_add(FMT, a, b) if op == OP_ADD else tnf_ref.tef_mul(FMT, a, b)


def requests(log=print):
    """[(set, op, a, b, expected)], in the order they are sent. Pinned rows keep their own
    expected word, and it must equal the reference's."""
    problems = check_reference()
    if problems:
        raise SystemExit("reference check failed:\n  " + "\n  ".join(problems))
    rng = SplitMix64(SPEC["RANDOM_SEED"])
    t0 = time.monotonic()
    out = []
    for op, a, b, want in pinned():
        ref = golden(op, a, b)
        if ref != want:
            raise SystemExit(f"pinned row op {op} {a:05x} {b:05x}: file {want:05x}, reference {ref:05x}")
        out.append(("pinned", op, a, b, want))
    for name, rows in (("edge", edge()), ("uniform", uniform(rng)), ("near", near(rng))):
        out += [(name, op, a, b, golden(op, a, b)) for op, a, b in rows]
    if len(out) != SPEC["TOTAL_REQUESTS"]:
        raise SystemExit(f"{len(out)} requests, spec says {SPEC['TOTAL_REQUESTS']}")
    log(f"# {len(out)} requests, expected words from {SPEC['REF_FILE']} in {time.monotonic() - t0:.1f} s")
    return out


def summary(reqs):
    per = {}
    for name, op, *_ in reqs:
        per[(name, op)] = per.get((name, op), 0) + 1
    for (name, op), n in sorted(per.items()):
        print(f"{name:8s} {'add' if op == OP_ADD else 'mul'} {n}")
    print(f"total {len(reqs)}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--summary", action="store_true")
    ap.add_argument("--write", metavar="FILE")
    ap.add_argument("--model-check", action="store_true")
    args = ap.parse_args()
    reqs = requests()
    if args.summary:
        summary(reqs)
    if args.write:
        with open(args.write, "w") as f:
            for _name, op, a, b, want in reqs:
                f.write(f"{op:x} {a:05x} {b:05x} {want:05x}\n")
        print(f"wrote {args.write}")
    if args.model_check:
        import tnf16_rtl_model as model
        bad = 0
        for name, op, a, b, want in reqs:
            got = model.compute(op, a, b)
            if got != want:
                bad += 1
                if bad <= 20:
                    print(f"MODEL MISMATCH {name} op {op} a {a:05x} b {b:05x}: model {got:05x} reference {want:05x}")
        print(f"MODEL: {len(reqs) - bad}/{len(reqs)} equal to the reference")
        return 1 if bad else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
