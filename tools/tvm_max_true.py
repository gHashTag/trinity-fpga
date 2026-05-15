"""
tvm_max_true.py — TVM-VTA backend descriptor for the MAX-TRUE compute fabric.

Lane Q  · L-DPC22 · gHashTag/trinity-fpga#93
Author : Vasilev Dmitrii <admin@t27.ai>
Anchor : phi^2 + phi^-2 = 3 · DOI 10.5281/zenodo.19227877

NOTE: This file is a *software-only* backend descriptor.  It does NOT import
TVM at module-level so it remains importable in environments where TVM is not
installed.  All TVM-specific plumbing is guarded by optional imports and
clearly labelled.  A follow-up Lane Q-bis is required to validate against a
live TVM-VTA installation.

STATUS: descriptor + prototype ONLY — real TVM compile validation is deferred.

==============================================================================
MAX-TRUE fabric shape (authoritative constants)
==============================================================================
  Total cells     : 32  (GF16 ALU instances)
  Topology        : 2 × quad_mesh  (two 4×4 mesh quadrants)
  Banks           : 4   (SRAM banks, one per quadrant column)
  Tiles           : 4   (pipeline tiles per bank)
  Precision       : GF16  (4 bpw, galois-field arithmetic, weight ∈ {-1, 0, +1})
  Energy          : 1 nJ / op  (at 50 MHz clock)
  Peak throughput : 32 GF16 ops / cycle  (= 1.6 GOPS at 50 MHz)
==============================================================================
"""

# ---------------------------------------------------------------------------
# Fabric constants
# ---------------------------------------------------------------------------

FABRIC_NAME      = "MAX-TRUE"
TOTAL_CELLS      = 32          # GF16 ALU cells
QUAD_MESHES      = 2           # number of quad_mesh units
BANKS            = 4           # SRAM banks
TILES_PER_BANK   = 4           # pipeline tiles per bank
GF16_BPW         = 4           # bits per weight (GF16)
CLOCK_MHZ        = 50          # operating frequency
ENERGY_NJ_PER_OP = 1.0         # energy per GF16 MAC
PEAK_GOPS        = TOTAL_CELLS * CLOCK_MHZ * 1e6 / 1e9   # = 1.6 GOPS

# Derived banking map: cells are arranged as (quad, bank, tile)
# quad  ∈ [0, QUAD_MESHES)  → 0 or 1
# bank  ∈ [0, BANKS)        → 0..3
# tile  ∈ [0, TILES_PER_BANK)→ 0..3
# cell_id = quad * (BANKS * TILES_PER_BANK) + bank * TILES_PER_BANK + tile

def cell_id(quad: int, bank: int, tile: int) -> int:
    """Return flat cell index from (quad, bank, tile) coordinates."""
    assert 0 <= quad < QUAD_MESHES,    f"quad {quad} out of range"
    assert 0 <= bank < BANKS,          f"bank {bank} out of range"
    assert 0 <= tile < TILES_PER_BANK, f"tile {tile} out of range"
    return quad * (BANKS * TILES_PER_BANK) + bank * TILES_PER_BANK + tile


def cell_coords(cid: int) -> tuple:
    """Inverse of cell_id — returns (quad, bank, tile)."""
    assert 0 <= cid < TOTAL_CELLS
    quad = cid // (BANKS * TILES_PER_BANK)
    rem  = cid %  (BANKS * TILES_PER_BANK)
    bank = rem // TILES_PER_BANK
    tile = rem %  TILES_PER_BANK
    return quad, bank, tile


# ---------------------------------------------------------------------------
# GF16 ALU semantics
# ---------------------------------------------------------------------------

class GF16ALU:
    """
    Software model of a single GF16 ALU cell.

    GF16 encodes weights as signed 4-bit values in the range [-8, 7].
    BitNet uses the ternary subset {-1, 0, +1}.  The ALU supports:
      - dot4   : 4-element dot product (accumulate into int16 accumulator)
      - add    : scalar addition
      - scale  : multiply by a float scale factor (dequantisation)
      - load   : fill input register from SRAM bank
      - store  : write accumulator to SRAM bank

    Energy model (software approximation): each dot4 costs 1 nJ.
    """
    OPCODES = ("load", "dot4", "add", "scale", "store")

    def __init__(self, cell: int):
        self.cell = cell
        self.quad, self.bank, self.tile = cell_coords(cell)
        self.acc   = 0
        self.reg   = [0] * 4   # 4-element input register

    def load(self, values: list):
        assert len(values) == 4
        self.reg = list(values)

    def dot4(self, weights: list) -> int:
        assert len(weights) == 4
        result = sum(a * w for a, w in zip(self.reg, weights))
        self.acc += result
        return result

    def add(self, val: int):
        self.acc += val

    def scale(self, factor: float) -> float:
        return self.acc * factor

    def store(self) -> int:
        return self.acc


# ---------------------------------------------------------------------------
# Latency model
# ---------------------------------------------------------------------------

LATENCY_CYCLES = {
    "load"  : 2,   # SRAM read latency
    "dot4"  : 1,   # 1-cycle GF16 MAC array
    "add"   : 1,
    "scale" : 2,   # includes float normalisation
    "store" : 2,   # SRAM write latency
}

def estimate_latency(op_queue: list) -> int:
    """Return estimated total cycles for a linear op queue (no pipelining)."""
    return sum(LATENCY_CYCLES.get(op.get("opcode", ""), 1) for op in op_queue)


# ---------------------------------------------------------------------------
# Dataflow mapping: BitNet layer → MAX-TRUE op schedule
# ---------------------------------------------------------------------------

def bitnet_layer_to_ops(layer_name: str, in_dim: int, out_dim: int,
                        lane_id: int = 0, base_src: int = 0,
                        base_dst: int = 256) -> list:
    """
    Produce a symbolic op queue for one BitNet linear layer on MAX-TRUE.

    Each output neuron maps to one (bank, tile) pair (round-robin across cells).
    Inputs are loaded in chunks of 4 (matching the GF16 dot4 width).

    Args:
        layer_name: human-readable label ("embed", "attn", "ffn")
        in_dim    : input feature dimension
        out_dim   : output feature dimension
        lane_id   : TVM-VTA lane assignment
        base_src  : SRAM address for activations
        base_dst  : SRAM address for output

    Returns:
        list of dicts with keys (opcode, src, dst, lane)
    """
    ops = []
    chunks = (in_dim + 3) // 4  # number of dot4 operations per output neuron

    for out_idx in range(out_dim):
        cell = out_idx % TOTAL_CELLS
        # load activation chunk 0 to prime the register
        ops.append({
            "opcode": "load",
            "src"   : f"sram[{base_src}+{out_idx * chunks * 4}]",
            "dst"   : f"cell{cell}.reg",
            "lane"  : lane_id,
        })
        for chunk in range(chunks):
            ops.append({
                "opcode": "dot4",
                "src"   : f"cell{cell}.reg",
                "dst"   : f"cell{cell}.acc",
                "lane"  : lane_id,
            })
            if chunk < chunks - 1:
                ops.append({
                    "opcode": "load",
                    "src"   : f"sram[{base_src}+{(out_idx*chunks + chunk + 1)*4}]",
                    "dst"   : f"cell{cell}.reg",
                    "lane"  : lane_id,
                })
        ops.append({
            "opcode": "scale",
            "src"   : f"cell{cell}.acc",
            "dst"   : f"cell{cell}.acc",
            "lane"  : lane_id,
        })
        ops.append({
            "opcode": "store",
            "src"   : f"cell{cell}.acc",
            "dst"   : f"sram[{base_dst}+{out_idx}]",
            "lane"  : lane_id,
        })

    return ops


# ---------------------------------------------------------------------------
# TVM-VTA backend registration stubs (guarded import)
# ---------------------------------------------------------------------------

def register_max_true_target():
    """
    Register the MAX-TRUE target with TVM if TVM is installed.
    Returns True on success, False if TVM is not available.

    This stub documents the intended TVM target attributes; actual registration
    requires TVM >= 0.14 with VTA support compiled in.
    """
    try:
        import tvm                           # noqa: F401  (optional)
        from tvm import target as tvm_target # noqa: F401
        # In a real TVM integration:
        # tvm.target.Target.register("max_true", {
        #     "kind"       : "vta",
        #     "num_cells"  : TOTAL_CELLS,
        #     "banks"      : BANKS,
        #     "tiles"      : TILES_PER_BANK,
        #     "bpw"        : GF16_BPW,
        #     "clock_mhz"  : CLOCK_MHZ,
        #     "energy_nj"  : ENERGY_NJ_PER_OP,
        # })
        print("[tvm_max_true] TVM found — target registration would proceed here.")
        print("[tvm_max_true] Lane Q-bis required for actual compile validation.")
        return True
    except ImportError:
        print("[tvm_max_true] TVM not installed — running in descriptor-only mode.")
        return False


# ---------------------------------------------------------------------------
# Banking policy: op → cell assignment
# ---------------------------------------------------------------------------

def assign_cells(ops: list) -> list:
    """
    Assign each store/dot4 op to a physical cell using round-robin policy.
    Returns ops with 'cell_id' field populated.
    """
    counter = 0
    result = []
    for op in ops:
        op = dict(op)
        if op["opcode"] in ("dot4", "store"):
            op["cell_id"] = counter % TOTAL_CELLS
            counter += 1
        result.append(op)
    return result


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

def _self_test():
    """Basic sanity checks for the descriptor module."""
    # Check fabric geometry
    assert TOTAL_CELLS == QUAD_MESHES * BANKS * TILES_PER_BANK, "cell count mismatch"
    assert cell_id(0, 0, 0) == 0
    assert cell_id(1, 3, 3) == TOTAL_CELLS - 1
    assert cell_coords(0) == (0, 0, 0)
    assert cell_coords(TOTAL_CELLS - 1) == (1, 3, 3)

    # Check round-trip
    for cid in range(TOTAL_CELLS):
        assert cell_id(*cell_coords(cid)) == cid

    # Check latency model
    dummy_ops = [{"opcode": "load"}, {"opcode": "dot4"}, {"opcode": "store"}]
    assert estimate_latency(dummy_ops) == 5

    # Check TVM registration stub
    register_max_true_target()

    print("[tvm_max_true] self-test PASSED — descriptor is internally consistent.")
    print(f"  Fabric : {FABRIC_NAME} {TOTAL_CELLS} cells / {BANKS} banks / "
          f"{TILES_PER_BANK} tiles / GF{2**GF16_BPW} / "
          f"{ENERGY_NJ_PER_OP} nJ/op @ {CLOCK_MHZ} MHz")


if __name__ == "__main__":
    _self_test()
