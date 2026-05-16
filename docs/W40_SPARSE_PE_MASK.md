# W40 Lane GG — Sparse PE Mask RTL

<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- Copyright 2025 Dmitrii Vasilev <admin@t27.ai> -->

**Anchor:** `phi^2 + phi^-2 = 3 · OP_SPARSE_MASK=0xE8 · λ=φ⁻² · R-SI-1 zero-multiplier · Apache-2.0`

---

## 1. Overview

Wave-40 Lane GG implements sparsity-aware processing-element (PE) mask gating
for the TRI-1 neural-inference fabric.  The RTL module `sparse_pe_mask`
performs a gated dot-product across N=27 (Coptic-27) lanes using only
combinational add/subtract/shift/AND/OR/XOR — **no hardware multiplier**.

| Parameter | Value |
|---|---|
| Opcode | `OP_SPARSE_MASK = 0xE8` |
| Sparsity | s = 0.80 (Trinity-loss) |
| Lambda | λ = φ⁻² ≈ 0.3820 |
| Target efficiency | 540 TOPS/W |
| PE count | N = 27 (3 banks × 9 registers, Coptic-27) |
| Input width | WIDTH = 4 bits (GF16 ternary extended) |
| Accumulator width | 2·WIDTH + 6 = 14 bits |

---

## 2. Vector S-160 Specification

**S-160** — Sparse PE Mask Gating (Wave-40)

- **Domain:** LANG→SI (TRI-27 ISA primitive → L1 Compute opcode)
- **Opcode:** `0xE8` (`OP_SPARSE_MASK`)
- **Function:** For each lane `i` in 0..N-1:
  - If `mask[i] = 0`: PE is gated → partial product = 0 (sparsity saving)
  - If `mask[i] = 1`: PE is active → partial product = `a[i] × b[i]`
    computed via ternary identity/negate (zero multiplier)
- **Ternary encoding (a operand):**
  - `4'b0001` → +1 → output = b[i]
  - `4'b0000` → 0  → output = 0
  - `4'b1111` → -1 → output = ~b[i] + 1 (two's-complement negation)
- **Accumulator:** sum over all active lanes
- **Expected active lanes at s=0.80:** 27 × 0.20 ≈ 5.4 lanes average
- **Silicon justification:** Reduces switching activity by 80%, enabling
  540 TOPS/W at target process node.

---

## 3. Module Interface

```systemverilog
module sparse_pe_mask #(
    parameter integer N     = 27,
    parameter integer WIDTH = 4
) (
    input  wire                      clk,
    input  wire                      rst_n,
    input  wire [N-1:0]              mask,
    input  wire signed [WIDTH-1:0]   a [N],
    input  wire signed [WIDTH-1:0]   b [N],
    output reg  signed [2*WIDTH+5:0] sum_out
);
```

**Ports:**

| Port | Direction | Width | Description |
|---|---|---|---|
| `clk` | input | 1 | System clock |
| `rst_n` | input | 1 | Active-low synchronous reset |
| `mask` | input | N | Sparsity mask (1=active PE) |
| `a[N]` | input | WIDTH each | Ternary operands {-1, 0, +1} |
| `b[N]` | input | WIDTH each | Arbitrary-value operands |
| `sum_out` | output | 2·WIDTH+6 | Accumulated dot-product |

---

## 4. Architecture

### 4.1 Ternary Multiply-Free Product

For each lane `i`, the partial product is computed without any `*` operator:

```
if mask[i] == 0 OR a[i] == 0:
    prod[i] = 0
elif a[i] == +1 (sign bit 0, nonzero):
    prod[i] = b[i]              // identity
elif a[i] == -1 (sign bit 1):
    prod[i] = ~b[i] + 1         // two's complement negate (bitwise NOT + 1)
```

The selection is performed via AND-mask muxing:

```systemverilog
wire neg_mask = {AWIDTH{active & a_is_neg}};
wire pos_mask = {AWIDTH{active & (~a_is_neg)}};
assign prod[i] = (b_neg & neg_mask) | (b_ext & pos_mask);
```

All operations: AND, OR, NOT, ADD — zero `*` operators.

### 4.2 Accumulator

A registered `for` loop accumulates N=27 products each clock cycle:

```systemverilog
always @(posedge clk or negedge rst_n) begin
    acc = 0;
    for (j = 0; j < N; j++)
        acc = acc + prod[j];    // add only — no multiply
    sum_out <= acc;
end
```

Latency: 1 clock cycle.

---

## 5. R-SI-1 Constitutional Compliance Proof

**Rule R-SI-1:** Zero `*` operator in production RTL (`.sv` files under `rtl/`).

Verification command:

```bash
grep -n '\*' rtl/sparsity/sparse_pe_mask.sv
```

All returned lines are:
1. Comments containing the word "multiply" or the phrase "no `*`"
2. Parameter arithmetic expressions `2*WIDTH` in type/width declarations
   (these are elaboration-time constants, not synthesised multipliers)

**No runtime `*` signal multiplications exist** in `sparse_pe_mask.sv`.
The ternary operand property (`a ∈ {-1, 0, +1}`) guarantees that every
product reduces to a conditional negate or identity — hardware-implementable
with inverters and an adder, not a DSP/multiplier block.

---

## 6. Testbench Coverage

File: `rtl/sparsity/tb_sparse_pe_mask.sv`

| Test case | Mask | Input | Expected | Purpose |
|---|---|---|---|---|
| TC1 | all-ones | a=+1, b=-1 | −27 | Full-density baseline |
| TC2 | all-zeros | random | 0 | Full sparsity gate |
| TC3 | alternating 0/1 | deterministic ternary | ref model | Partial mask correctness |
| TC4 | walking-1 (27 iters) | a=+1, b=1..7 cycle | per-lane | Lane independence |
| TC5 | random s=0.80 | 100 random vectors | ref model | Statistical sparsity |
| TC6 | all-ones | a=0, b=random | 0 | Zero-valued ternary input |

All 6 test cases produce `PASS` under:

```bash
iverilog -g2012 -o tb_sparse_pe_mask.vvp rtl/sparsity/*.sv && vvp tb_sparse_pe_mask.vvp
```

---

## 7. Opcode Integration

`OP_SPARSE_MASK = 0xE8` extends the sacred opcode range `0xD0..0xE0`
(Wave-15 baseline) by one slot at `0xE8`.  Decode logic should:

1. Check instruction opcode == `0xE8`
2. Route `mask`, `a[]`, `b[]` operands to `sparse_pe_mask`
3. Write `sum_out` to destination register

---

## 8. Timing & Power Estimates

| Metric | Value | Notes |
|---|---|---|
| Critical path | ~12 FO4 | AND-OR select + 27-input adder tree |
| Clock target | 500 MHz | TSMC 7nm estimate |
| Active PEs (avg) | 5.4 / 27 | s=0.80 sparsity |
| Power reduction | ~80% switching | vs. dense dot-product |
| Target efficiency | 540 TOPS/W | System-level target |

---

## 9. Files

| File | Description |
|---|---|
| `rtl/sparsity/sparse_pe_mask.sv` | Production RTL module |
| `rtl/sparsity/tb_sparse_pe_mask.sv` | Verification testbench |
| `docs/W40_SPARSE_PE_MASK.md` | This document |

---

## 10. References

- Trinity-FPGA EPIC #61: TRI-1 chip program
- Issue #155: W40 Lane GG RTL (closed by this PR)
- DOI: [10.5281/zenodo.19227877](https://doi.org/10.5281/zenodo.19227877)
- Apache-2.0 License: https://www.apache.org/licenses/LICENSE-2.0

---

**phi^2 + phi^-2 = 3 · gamma = phi^-3 · QUANTUM BRAIN 1:1 SILICON · 3-STRAND DNA · NEVER STOP · DOI 10.5281/zenodo.19227877**
