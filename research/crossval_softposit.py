#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Cross-validate the posit packs against SoftPosit, the posit reference implementation.

The catalogue's posit packs had no recorded witness. SoftPosit (Cerlane Leong,
gitlab.com/cerlane/SoftPosit) is the reference implementation for the Posit Standard,
which makes it for posit what libtakum was for takum: an implementation from outside
this corpus entirely.

**The comparand has to be chosen carefully, and the obvious choice is wrong.**
SoftPosit's `posit8_t`/`posit16_t`/`posit32_t` are the *legacy* fixed-es types --
posit(8,0), posit(16,1), posit(32,2) from the pre-standard draft. The Posit Standard
2022 fixes **es = 2 at every width**, which is what these packs declare. Comparing the
packs against `convertP8ToDouble` produces 3 agreements out of 255 and looks like a
catastrophe; it is a catastrophe of comparand, not of pack.

The right entry point is the `positX` family: `convertPX2ToDouble`, es = 2 at arbitrary
width, with the n-bit code left-aligned in a 32-bit container. The tell that settles it
without argument is maxpos -- posit(8,0) tops out at 2^6 = 64, posit(8,2) at 2^24 =
16,777,216, and the packs say 16,777,216.

    build:
      c++ -O2 -x c++ -Isource/include -Isource/8086-SSE -Ibuild/Linux-x86_64-GCC \\
          bridge.c source/c_convertPosit32ToDec.c -o spx

    python3 research/crossval_softposit.py --ref-dir <dir with spx8/spx16/spx32 tsv>
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys

SCRATCH = ("/private/tmp/claude-501/-Users-playom-trinity-fpga/"
           "3a885a60-490c-4733-abfd-86bfa298080d/scratchpad")


def load_ref(path: str) -> dict[int, float]:
    out = {}
    for line in open(path, encoding="utf-8"):
        if not line.strip():
            continue
        a, b = line.split("\t")
        out[int(a)] = float(b)
    return out


def compare(pack_path: str, ref: dict[int, float], label: str) -> int:
    pack = json.load(open(pack_path, encoding="utf-8"))
    vectors = pack["vectors"]
    bit_key = next(k for k in vectors[0] if k.endswith("_bits_int"))

    same = differ = nar = 0
    worst = []
    for e in vectors:
        raw = e[bit_key]
        stored = e.get("decoded_f64")
        x = ref.get(raw)
        if x is None:
            continue
        # SoftPosit's positX returns INFINITY for the NaR code; the packs use null.
        if math.isinf(x) or stored is None:
            nar += 1
            continue
        if stored == x:
            same += 1
        else:
            differ += 1
            rel = abs((stored - x) / x) if x else float("inf")
            worst.append((rel, raw, stored, x))

    print(f"{label:<9} {len(vectors):>4} vectors   bit-identical {same:>4}   "
          f"differing {differ:>3}   NaR {nar}")
    worst.sort(reverse=True)
    for rel, raw, stored, x in worst[:4]:
        print(f"    raw {raw}  pack {stored!r}  SoftPosit {x!r}  rel {rel:.3g}")
    return differ


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref-dir", default=SCRATCH)
    args = ap.parse_args()

    print("posit packs vs SoftPosit positX, es = 2 (Posit Standard 2022)\n")
    bad = 0
    checked = 0
    for w in (8, 16, 32):
        ref_path = os.path.join(args.ref_dir, f"spx{w}.tsv")
        pack_path = os.path.join(args.ref_dir, f"posit{w}.json")
        if not (os.path.exists(ref_path) and os.path.exists(pack_path)):
            print(f"posit{w:<4} skipped -- reference dump or pack not present")
            continue
        checked += 1
        bad += compare(pack_path, load_ref(ref_path), f"posit{w}")

    if not checked:
        print("\nNothing was compared. This script does not report success when it "
              "has read nothing.")
        return 2

    print(f"""
posit8 is exhaustive over its whole code space; posit16 and posit32 are the packs'
curated vectors. Zero differences means the packs implement Posit Standard 2022 as the
reference implementation does.

posit64 is NOT covered. SoftPosit's positX family uses a 32-bit container, so es = 2 at
width 64 is out of its reach, and `posit64_t` is the legacy es = 0 type. That pack
remains without an independent witness and the record should say so rather than imply
the family was done.""")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
