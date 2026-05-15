"""
compile_prototype.py — Prototype BitNet-to-MAX-TRUE compiler.

Lane Q  · L-DPC22 · gHashTag/trinity-fpga#93
Author : Vasilev Dmitrii <admin@t27.ai>
Anchor : phi^2 + phi^-2 = 3 · DOI 10.5281/zenodo.19227877

This script:
  1. Defines a 3-layer toy BitNet MLP (embed / attn / ffn) with ternary weights
     {-1, 0, +1} drawn from a fixed seed (seed=0xBEEF).
  2. Compiles the model to a MAX-TRUE op queue (software simulation, no TVM).
  3. Loads tools/golden_ops_queue.json and compares op-by-op.
  4. Prints MATCH / MISMATCH counts and exits non-zero on any mismatch.

STATUS: pure prototype — real TVM-VTA install required for G-51 final validation
        (deferred to Lane Q-bis).

Usage:
    python3 tools/compile_prototype.py
    python3 tools/compile_prototype.py --dump   # also write /tmp/op_queue.json
"""

import json
import random
import sys
import os
import argparse
from pathlib import Path

# ---------------------------------------------------------------------------
# Fabric constants (must agree with tvm_max_true.py)
# ---------------------------------------------------------------------------
TOTAL_CELLS      = 32
BANKS            = 4
TILES_PER_BANK   = 4
CLOCK_MHZ        = 50
ENERGY_NJ_PER_OP = 1.0

# ---------------------------------------------------------------------------
# BitNet model definition
# ---------------------------------------------------------------------------
# Three layers with small dimensions so the op queue is human-readable:
#   embed : in=8,  out=8
#   attn  : in=8,  out=8
#   ffn   : in=8,  out=8
# With in_dim=8 and dot4 width=4, each output neuron needs 2 dot4 ops → chunk=2.
# Ops per neuron = load + (dot4 + load) * (chunks-1) + dot4 + scale + store
#               = 1 + (1+1)*1 + 1 + 1 + 1 = 6
# Ops per layer  = 8 neurons * 6 = 48  → within ≤30 limit per layer we shrink.

SEED    = 0xBEEF
IN_DIM  = 4   # 4 inputs → 1 dot4 per neuron → 4 ops/neuron * 4 neurons = 16 ≤ 30
OUT_DIM = 4

LAYERS = [
    {"name": "embed", "in_dim": IN_DIM, "out_dim": OUT_DIM,
     "base_src": 0x000, "base_dst": 0x100, "lane": 0},
    {"name": "attn",  "in_dim": IN_DIM, "out_dim": OUT_DIM,
     "base_src": 0x100, "base_dst": 0x200, "lane": 1},
    {"name": "ffn",   "in_dim": IN_DIM, "out_dim": OUT_DIM,
     "base_src": 0x200, "base_dst": 0x300, "lane": 2},
]

# ---------------------------------------------------------------------------
# Weight generation
# ---------------------------------------------------------------------------

def ternary_weights(rng: random.Random, n: int) -> list:
    """Draw n ternary weights {-1, 0, +1} from rng."""
    return [rng.choice([-1, 0, 1]) for _ in range(n)]


def build_model(seed: int) -> dict:
    """Return dict of layer_name → weight matrix (list of lists)."""
    rng = random.Random(seed)
    model = {}
    for layer in LAYERS:
        rows = layer["out_dim"]
        cols = layer["in_dim"]
        matrix = [ternary_weights(rng, cols) for _ in range(rows)]
        model[layer["name"]] = matrix
    return model


# ---------------------------------------------------------------------------
# Compiler: BitNet layer → MAX-TRUE op queue
# ---------------------------------------------------------------------------

def compile_layer(layer: dict) -> list:
    """
    Emit the canonical op sequence for one BitNet layer on MAX-TRUE.

    For in_dim=4 (dot4 width=4), each output neuron produces exactly:
      load, dot4, scale, store  (4 ops)
    Total per layer = out_dim * 4.

    This matches the golden reference exactly.
    """
    ops = []
    name      = layer["name"]
    in_dim    = layer["in_dim"]
    out_dim   = layer["out_dim"]
    base_src  = layer["base_src"]
    base_dst  = layer["base_dst"]
    lane      = layer["lane"]

    chunks = (in_dim + 3) // 4  # = 1 when in_dim == 4

    for out_idx in range(out_dim):
        cell = out_idx % TOTAL_CELLS

        # Initial load of the full 4-element activation vector
        ops.append({
            "opcode": "load",
            "src"   : f"sram[0x{base_src:03x}+{out_idx * chunks * 4}]",
            "dst"   : f"cell{cell}.reg",
            "lane"  : lane,
            "layer" : name,
        })

        for chunk_idx in range(chunks):
            ops.append({
                "opcode": "dot4",
                "src"   : f"cell{cell}.reg",
                "dst"   : f"cell{cell}.acc",
                "lane"  : lane,
                "layer" : name,
            })
            # If more chunks remain, load the next 4 activations
            if chunk_idx < chunks - 1:
                ops.append({
                    "opcode": "load",
                    "src"   : f"sram[0x{base_src:03x}+{(out_idx * chunks + chunk_idx + 1) * 4}]",
                    "dst"   : f"cell{cell}.reg",
                    "lane"  : lane,
                    "layer" : name,
                })

        ops.append({
            "opcode": "scale",
            "src"   : f"cell{cell}.acc",
            "dst"   : f"cell{cell}.acc",
            "lane"  : lane,
            "layer" : name,
        })
        ops.append({
            "opcode": "store",
            "src"   : f"cell{cell}.acc",
            "dst"   : f"sram[0x{base_dst:03x}+{out_idx}]",
            "lane"  : lane,
            "layer" : name,
        })

    return ops


def compile_model() -> list:
    """Compile all three layers and return the flat op queue."""
    all_ops = []
    for layer in LAYERS:
        all_ops.extend(compile_layer(layer))
    return all_ops


# ---------------------------------------------------------------------------
# Comparison
# ---------------------------------------------------------------------------

def compare_queues(generated: list, golden: list) -> tuple:
    """
    Compare two op queues element-by-element.
    Returns (match_count, mismatch_count, details).
    """
    match_count    = 0
    mismatch_count = 0
    details        = []

    max_len = max(len(generated), len(golden))
    for i in range(max_len):
        if i >= len(generated):
            mismatch_count += 1
            details.append(f"[{i}] MISSING in generated — golden: {golden[i]}")
        elif i >= len(golden):
            mismatch_count += 1
            details.append(f"[{i}] EXTRA in generated: {generated[i]}")
        else:
            g_op = generated[i]
            r_op = golden[i]
            # Compare only the canonical fields present in the golden reference
            match = all(g_op.get(k) == r_op.get(k) for k in r_op)
            if match:
                match_count += 1
            else:
                mismatch_count += 1
                details.append(f"[{i}] MISMATCH\n     generated: {g_op}\n     golden   : {r_op}")

    return match_count, mismatch_count, details


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="MAX-TRUE BitNet prototype compiler")
    parser.add_argument("--dump", action="store_true",
                        help="Write generated queue to /tmp/op_queue.json")
    args = parser.parse_args()

    # Locate golden reference relative to this script
    script_dir  = Path(__file__).parent
    golden_path = script_dir / "golden_ops_queue.json"

    if not golden_path.exists():
        print(f"ERROR: golden reference not found at {golden_path}", file=sys.stderr)
        sys.exit(2)

    with open(golden_path) as f:
        golden_data = json.load(f)

    golden_ops = golden_data.get("ops", [])

    # Compile
    print("=== MAX-TRUE BitNet Prototype Compiler ===")
    print(f"Seed: 0x{SEED:04X}  |  Layers: {[l['name'] for l in LAYERS]}")
    print(f"Fabric: {TOTAL_CELLS} cells / {BANKS} banks / {TILES_PER_BANK} tiles")
    print()

    generated_ops = compile_model()

    print(f"Generated ops : {len(generated_ops)}")
    print(f"Golden ops    : {len(golden_ops)}")
    print()

    # Optionally dump
    if args.dump:
        out_path = "/tmp/op_queue.json"
        with open(out_path, "w") as f:
            json.dump({"ops": generated_ops}, f, indent=2)
        print(f"Dumped to {out_path}")
        print()

    # Compare
    match_count, mismatch_count, details = compare_queues(generated_ops, golden_ops)

    if details:
        print("--- DIFF DETAILS ---")
        for d in details:
            print(d)
        print()

    unique_opcodes = sorted({op["opcode"] for op in generated_ops})
    print(f"Unique opcodes : {unique_opcodes}")
    print(f"MATCH count    : {match_count}")
    print(f"MISMATCH count : {mismatch_count}")
    print()

    if mismatch_count == 0:
        print("RESULT: MATCH — generated op queue matches golden reference.")
        print()
        print("NOTE: This is an internal prototype-vs-golden consistency check.")
        print("      Real TVM-VTA install validation is deferred to Lane Q-bis.")
        sys.exit(0)
    else:
        print("RESULT: MISMATCH — op queue does NOT match golden reference.")
        sys.exit(1)


if __name__ == "__main__":
    main()
