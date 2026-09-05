#!/usr/bin/env python3
"""Cost of top-aligned scaling against a window fixed about unity.

Backs Corollary cor:topaligned. A scale set from the block or tensor maximum
carries the largest magnitude into the top representable binade, so the visited
binade indices are -(b-1)...0 -- entirely at or below unity. The TNF exponent
window is fixed symmetrically about unity, offsets 0...3^Et-1 with the top row
reserved for the special value and the bottom for zero, leaving representable
indices -(Delta-1)...+(Delta-1) with Delta = (3^Et-1)/2.

Two quantities are computed and both go into the paper:
  (1) how often the top-aligned admissible width exceeds the centred one, and
  (2) the asymptotic budget recovered by centring the scale instead.

Nothing here is a hardware claim. Status: [proved -- enumeration].
"""
import json
import math
import pathlib

EPS = 1e-12


def width_centred(b):
    """Theorem thm:optimal: covers b binades when the span is centred."""
    return math.ceil(math.log(b + 1, 3) - EPS)


def width_top_aligned(b):
    """Proposition prop:uncentred with max|e| = b-1, i.e. 3^Et >= 2b+1."""
    return math.ceil(math.log(2 * b + 1, 3) - EPS)


def main():
    span = range(1, 201)
    worse = [b for b in span if width_top_aligned(b) > width_centred(b)]
    never_below = all(width_top_aligned(b) >= width_centred(b) for b in span)

    usable = {}
    for et in range(2, 9):
        delta = (3 ** et - 1) // 2
        usable[et] = {
            "delta": delta,
            "window_rows": 2 * delta - 1,
            "reachable_rows": delta,
            "usable_pct": round(100.0 * delta / (2 * delta - 1), 1),
        }

    recovered = math.log(2, 3)
    out = {
        "status": "[proved -- enumeration]",
        "b_range": [1, 200],
        "n_needing_extra_trit": len(worse),
        "first_needing_extra_trit": worse[:14],
        "top_aligned_never_below_centred": never_below,
        "trits_recovered_by_centring": round(recovered, 4),
        "usable_fraction_by_exponent_width": usable,
    }
    dest = pathlib.Path(__file__).resolve().parent / "tnf_topaligned_cost.json"
    dest.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")

    print(f"needing an extra trit, b=1..200: {len(worse)}")
    print(f"never below the centred width: {never_below}")
    print(f"trits recovered by centring:   {recovered:.4f}")
    for et, row in usable.items():
        print(f"  Et={et}: {row['reachable_rows']}/{row['window_rows']} "
              f"= {row['usable_pct']}% of the window reachable")


if __name__ == "__main__":
    main()
