#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tnf_vectors_gen.py — deterministic conformance vectors for the TNF ladder, with
a digest manifest, for both ladder versions.

A conformance transcript from the board is only checkable if the vector file it
was run against can be reproduced bit for bit by a third party.  Two things make
that fail in practice, and both are avoided here:

  * `random.Random` is not a stable contract across interpreter versions.  This
    generator uses its own splitmix64, so the byte stream depends on nothing but
    the seed and the code in this file.
  * A repaired oracle changes vectors without changing their name.  Every file
    here carries its ladder version and vector-spec version in the name and in
    the header, and the manifest pins the SHA-256 of each file.

Usage
-----
    python3 tnf_vectors_gen.py --outdir vectors/tnf
    python3 tnf_vectors_gen.py --verify --outdir vectors/tnf
"""

import argparse
import hashlib
import os
from fractions import Fraction

from tnf_ref import (TNFFormat, encode, decode, tef_add, tef_mul, LADDERS,
                     is_special)
from tnf_ladder_versions import VECTOR_SPEC_VERSION

SEED = 0x546E4632303236  # "TNF2026"
N_PAIRS = 512             # per rung, per operation
MASK64 = (1 << 64) - 1


def splitmix64(state):
    """Stable 64-bit PRNG. Returns (value, next_state). No stdlib dependence."""
    state = (state + 0x9E3779B97F4A7C15) & MASK64
    z = state
    z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & MASK64
    z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & MASK64
    return (z ^ (z >> 31)), state


class Rng:
    def __init__(self, seed):
        self.s = seed & MASK64

    def next(self):
        v, self.s = splitmix64(self.s)
        return v

    def below(self, n):
        # Rejection sampling, so the mapping is uniform and reproducible.
        if n <= 0:
            raise ValueError(n)
        limit = MASK64 - (MASK64 % n)
        while True:
            v = self.next()
            if v <= limit:
                return v % n

    def bits(self, k):
        out = 0
        got = 0
        while got < k:
            out = (out << 64) | self.next()
            got += 64
        return out >> (got - k) if k else 0


def rung_seed(width, trits, mant, op):
    """Seed is derived from the rung itself, so adding a rung cannot shift the
    stream of an existing one."""
    h = hashlib.sha256(
        f"{VECTOR_SPEC_VERSION}|{width}|{trits}|{mant}|{op}".encode()
    ).digest()
    return int.from_bytes(h[:8], "big") ^ SEED


def sample_code(fmt: TNFFormat, rng: Rng) -> int:
    """A random finite code, plus a deliberate slice of edge rows."""
    roll = rng.below(16)
    if roll == 0:
        offset = 1                          # smallest finite exponent
    elif roll == 1:
        offset = fmt.offset_max - 1          # largest finite exponent
    elif roll == 2:
        offset = fmt.exp_offset              # balanced zero
    else:
        offset = 1 + rng.below(fmt.offset_max - 1)
    mroll = rng.below(8)
    if mroll == 0:
        m = 0                                # exact power of two
    elif mroll == 1:
        m = fmt.mant - 1                     # just below the next binade
    else:
        m = rng.bits(fmt.mant_bits) % fmt.mant
    sign = rng.below(2)
    return (sign << fmt.sign_shift) | (offset << fmt.exp_shift) | m


def vectors_for(fmt: TNFFormat, op: str, width: int):
    rng = Rng(rung_seed(width, fmt.exp_trits, fmt.mant_bits, op))
    fn = tef_add if op == "add" else tef_mul
    rows = []
    # Fixed head: zero, the two specials, and one exact case, before sampling.
    zero = 0
    inf = fmt.inf
    nan = fmt.inf | 1
    one = encode(fmt, Fraction(1))
    two = encode(fmt, Fraction(2))
    for a, b in [(zero, zero), (one, zero), (one, one), (one, two),
                 (two, one), (inf, one), (nan, one)]:
        rows.append((a, b, fn(fmt, a, b)))
    for _ in range(N_PAIRS):
        a = sample_code(fmt, rng)
        b = sample_code(fmt, rng)
        rows.append((a, b, fn(fmt, a, b)))
    return rows


def write_rung(outdir, ladder_version, width, fmt: TNFFormat):
    name = f"tnf{width}_{ladder_version}_{VECTOR_SPEC_VERSION}.vec"
    path = os.path.join(outdir, name)
    lines = [
        f"# {VECTOR_SPEC_VERSION}",
        f"# ladder_version={ladder_version}",
        f"# rung=TNF{width} exp_trits={fmt.exp_trits} mant_bits={fmt.mant_bits}",
        f"# width_rule_sum={1 + fmt.exp_trits + fmt.mant_bits} nominal_width={width}"
        f" satisfies={'yes' if 1 + fmt.exp_trits + fmt.mant_bits == width else 'no'}",
        f"# exp_bits={fmt.exp_bits} sign_shift={fmt.sign_shift}"
        f" offset_max={fmt.offset_max} exp_offset={fmt.exp_offset}",
        "# seed=splitmix64 derived per rung; see tnf_vectors_gen.py",
        "# columns: op a_hex b_hex expected_hex",
    ]
    for op in ("add", "mul"):
        for a, b, r in vectors_for(fmt, op, width):
            lines.append(f"{op} {a:x} {b:x} {r:x}")
    body = "\n".join(lines) + "\n"
    with open(path, "w") as fh:
        fh.write(body)
    return name, hashlib.sha256(body.encode()).hexdigest(), len(lines) - 7


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--outdir", default="vectors/tnf")
    ap.add_argument("--verify", action="store_true",
                    help="regenerate in memory and compare against the manifest")
    args = ap.parse_args()
    os.makedirs(args.outdir, exist_ok=True)

    manifest = [f"# TNF conformance vector manifest",
                f"# vector_spec_version={VECTOR_SPEC_VERSION}",
                f"# columns: sha256 file rows",]
    for ladder_version, lad in LADDERS.items():
        for width in sorted(lad):
            name, digest, rows = write_rung(args.outdir, ladder_version,
                                            width, lad[width])
            manifest.append(f"{digest}  {name}  {rows}")
    mpath = os.path.join(args.outdir, f"MANIFEST.{VECTOR_SPEC_VERSION}.sha256")
    new = "\n".join(manifest) + "\n"

    if args.verify and os.path.exists(mpath):
        old = open(mpath).read()
        if old == new:
            print(f"manifest unchanged: {mpath}")
        else:
            print("MANIFEST CHANGED — vectors are not reproducible as pinned")
            raise SystemExit(1)
    else:
        with open(mpath, "w") as fh:
            fh.write(new)
        print(f"wrote {mpath}")
    print(new, end="")


if __name__ == "__main__":
    main()
