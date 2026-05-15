// SPDX-License-Identifier: Apache-2.0
// Copyright 2025 gHashTag / TRI-1 Silicon Program
//
// PRE-SILICON ESTIMATE: +0.1 mm² net (ROM tile +0.4, SRAM block −0.3), +3 mW controller, −12 mW idle leakage @ TTIHP27
//
// Module : tom_layer_gate_controller
// Purpose: RTL controller for OP_LAYER_GATE=0xE2 — per-voltage-island power gating.
//          TOM Ternary ROM Accelerator (Wave-34). 28 voltage islands for BitNet b1.58-3B.
//          Implements the silicon layer corresponding to the Coq lemma `tom_no_star`
//          (gHashTag/t27, coq/IGLA/RMarker.v) and the Wave-34 assertions.
//
// Sacred opcode chain: 0xDE → 0xDF → 0xE0 → 0xE1 → 0xE2
//   (this module decodes 0xE2 only)
//
// R-SI-1: zero star operators in synthesizable code
//
// Q1.15 ratio computation (NO * operator):
//   idle_fraction_q16 = floor(idle_count * 32768 / 28)
//   Reciprocal in Q0.15: floor(32768 / 28) = 1170  (1170.285... truncated)
//   Verification: 1170 / 32768 = 0.0357055... vs 1/28 = 0.0357142...  (error < 0.025%)
//   1170 = 1024 + 128 + 16 + 2 = 2^10 + 2^7 + 2^4 + 2^1
//   shift-add ladder (NO * operator):
//     scaled = (idle_count << 10) + (idle_count << 7)
//            + (idle_count << 4) + (idle_count << 1)
//   idle_count range: 0..28  max scaled = 28*1170 = 32760 (fits in 16 bits)
//   For idle_count=28: scaled = 32760 ≈ 32768 (full-scale Q1.15), delta=8 (~0.024%)
//   For idle_count=14: scaled = 16380 ≈ 16384 (half-scale Q1.15), delta=4 (~0.024%)
//
// R7  FALSIFICATION: post-silicon, idle_fraction_q16 must be valid on BitNet b1.58-3B.
// R18 LAYER-FROZEN: purely additive — this file does NOT modify any existing RTL module.
// R5  HONEST:       all numeric estimates labelled PRE-SILICON ESTIMATE.
//
// Author:  Vasilev Dmitrii <admin@t27.ai>
// Wave:    Wave-34
// DOI:     10.5281/zenodo.19227877
// ──────────────────────────────────────────────────────────────────────────────

// R-SI-1: zero star operators
`default_nettype none
`timescale 1ns/1ps

module tom_layer_gate_controller (
    input  wire         clk,
    input  wire         rst_n,
    input  wire [7:0]   opcode,
    input  wire [27:0]  layer_idle_mask,       // 1 bit per voltage island (1=idle), 28 islands
    output reg  [27:0]  layer_vdd_enable,      // active-high VDD enable per island (inverted from idle mask after FSM)
    output reg  [15:0]  idle_fraction_q16,     // Q1.15 = idle_count * 1170 (shift-add, no *)
    output wire [3:0]   wave34_marker,         // R-marker constant 4'b1111
    output reg          gate_threshold_met     // strobe: asserts when idle_fraction_q16 >= 16384 (≥0.5)
);

    // ── R-marker constant (Wave-34, TOM) ─────────────────────────────────────
    assign wave34_marker = 4'b1111;

    // ── Opcode decode ─────────────────────────────────────────────────────────
    // Sacred opcode chain: 0xDE → 0xDF → 0xE0 → 0xE1 → 0xE2
    localparam [7:0] OPCODE_LAYER_GATE = 8'hE2;

    // ── Gate threshold: 0.5 in Q1.15 = 16384 ─────────────────────────────────
    // PRE-SILICON ESTIMATE: threshold calibrated for BitNet b1.58-3B layer gating
    localparam [15:0] GATE_THRESHOLD_Q15 = 16'd16384;   // 0.5 * 32768

    // ── All-on default (28 islands, all enabled) ──────────────────────────────
    localparam [27:0] VDD_ALL_ON = 28'hFFFFFFF;

    // ── FSM state encoding ────────────────────────────────────────────────────
    // 5 states: ACTIVE → DRAINING → OFF → WAKING → ACTIVE (back)
    localparam [2:0] S_ACTIVE   = 3'd0;
    localparam [2:0] S_DRAINING = 3'd1;
    localparam [2:0] S_OFF      = 3'd2;
    localparam [2:0] S_WAKING   = 3'd3;

    reg [2:0] state;
    reg [2:0] fsm_timer;   // countdown for DRAINING/OFF/WAKING dwell (3 cycles each)

    // ── Idle count: popcount of layer_idle_mask via adder tree ───────────────
    // No * operator — pure addition.  28 bits → max count = 28 (fits in 5 bits)

    // Layer 0: pair sums (14 pairs)
    wire [1:0] s0_00 = {1'b0, layer_idle_mask[0]}  + {1'b0, layer_idle_mask[1]};
    wire [1:0] s0_01 = {1'b0, layer_idle_mask[2]}  + {1'b0, layer_idle_mask[3]};
    wire [1:0] s0_02 = {1'b0, layer_idle_mask[4]}  + {1'b0, layer_idle_mask[5]};
    wire [1:0] s0_03 = {1'b0, layer_idle_mask[6]}  + {1'b0, layer_idle_mask[7]};
    wire [1:0] s0_04 = {1'b0, layer_idle_mask[8]}  + {1'b0, layer_idle_mask[9]};
    wire [1:0] s0_05 = {1'b0, layer_idle_mask[10]} + {1'b0, layer_idle_mask[11]};
    wire [1:0] s0_06 = {1'b0, layer_idle_mask[12]} + {1'b0, layer_idle_mask[13]};
    wire [1:0] s0_07 = {1'b0, layer_idle_mask[14]} + {1'b0, layer_idle_mask[15]};
    wire [1:0] s0_08 = {1'b0, layer_idle_mask[16]} + {1'b0, layer_idle_mask[17]};
    wire [1:0] s0_09 = {1'b0, layer_idle_mask[18]} + {1'b0, layer_idle_mask[19]};
    wire [1:0] s0_10 = {1'b0, layer_idle_mask[20]} + {1'b0, layer_idle_mask[21]};
    wire [1:0] s0_11 = {1'b0, layer_idle_mask[22]} + {1'b0, layer_idle_mask[23]};
    wire [1:0] s0_12 = {1'b0, layer_idle_mask[24]} + {1'b0, layer_idle_mask[25]};
    wire [1:0] s0_13 = {1'b0, layer_idle_mask[26]} + {1'b0, layer_idle_mask[27]};

    // Layer 1: quad sums (7 groups)
    wire [2:0] s1_0 = {1'b0, s0_00} + {1'b0, s0_01};
    wire [2:0] s1_1 = {1'b0, s0_02} + {1'b0, s0_03};
    wire [2:0] s1_2 = {1'b0, s0_04} + {1'b0, s0_05};
    wire [2:0] s1_3 = {1'b0, s0_06} + {1'b0, s0_07};
    wire [2:0] s1_4 = {1'b0, s0_08} + {1'b0, s0_09};
    wire [2:0] s1_5 = {1'b0, s0_10} + {1'b0, s0_11};
    wire [2:0] s1_6 = {1'b0, s0_12} + {1'b0, s0_13};

    // Layer 2: octet sums (3 groups + 1 leftover)
    wire [3:0] s2_0 = {1'b0, s1_0} + {1'b0, s1_1};
    wire [3:0] s2_1 = {1'b0, s1_2} + {1'b0, s1_3};
    wire [3:0] s2_2 = {1'b0, s1_4} + {1'b0, s1_5};
    // s1_6 is standalone

    // Layer 3: merge
    wire [4:0] s3_0 = {1'b0, s2_0} + {1'b0, s2_1};
    wire [4:0] s3_1 = {1'b0, s2_2} + {3'b0, s1_6};  // note: s1_6 is 3-bit

    wire [4:0] idle_count = s3_0 + s3_1;  // max = 28, fits in 5 bits

    // ── Q1.15 shift-add computation (NO * operator) ───────────────────────────
    // frac_raw = idle_count * 1170
    //          = idle_count * (2^10 + 2^7 + 2^4 + 2^1)
    //          = (idle_count<<10) + (idle_count<<7) + (idle_count<<4) + (idle_count<<1)
    // idle_count max=28; 28<<10=28672; sum max=28*1170=32760; fits in 16 bits.
    wire [15:0] ic16 = {11'b0, idle_count};  // zero-extend to 16 bits
    wire [15:0] frac_raw;
    // Partial products (all shift-based, no *)
    wire [15:0] pp10 = ic16 << 10;   // * 1024
    wire [15:0] pp7  = ic16 << 7;    // * 128
    wire [15:0] pp4  = ic16 << 4;    // * 16
    wire [15:0] pp1  = ic16 << 1;    // * 2
    assign frac_raw = pp10 + pp7 + pp4 + pp1;

    // ── Main sequential logic ─────────────────────────────────────────────────
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state              <= S_ACTIVE;
            layer_vdd_enable   <= VDD_ALL_ON;
            idle_fraction_q16  <= 16'h0;
            gate_threshold_met <= 1'b0;
            fsm_timer          <= 3'h0;
        end else begin
            case (state)
                // ── ACTIVE: default — all islands on; monitor opcode ─────────
                S_ACTIVE: begin
                    if (opcode == OPCODE_LAYER_GATE) begin
                        // Latch current fraction and check threshold
                        idle_fraction_q16  <= frac_raw;
                        gate_threshold_met <= (frac_raw >= GATE_THRESHOLD_Q15) ? 1'b1 : 1'b0;
                        // Transition to DRAINING
                        fsm_timer          <= 3'd3;
                        state              <= S_DRAINING;
                    end else begin
                        // Opcode mismatch — hold all-on default
                        layer_vdd_enable   <= VDD_ALL_ON;
                        idle_fraction_q16  <= 16'h0;
                        gate_threshold_met <= 1'b0;
                    end
                end

                // ── DRAINING: complete in-flight transactions before gating ──
                S_DRAINING: begin
                    if (fsm_timer == 3'h0) begin
                        // Apply idle mask: islands with idle_mask=1 → vdd_enable=0
                        layer_vdd_enable <= ~layer_idle_mask;
                        state            <= S_OFF;
                        fsm_timer        <= 3'd3;
                    end else begin
                        fsm_timer <= fsm_timer - 3'h1;
                    end
                end

                // ── OFF: hold gated state for dwell period ────────────────────
                S_OFF: begin
                    if (fsm_timer == 3'h0) begin
                        state     <= S_WAKING;
                        fsm_timer <= 3'd3;
                    end else begin
                        fsm_timer <= fsm_timer - 3'h1;
                    end
                end

                // ── WAKING: restore all islands before returning to ACTIVE ────
                S_WAKING: begin
                    if (fsm_timer == 3'h0) begin
                        layer_vdd_enable   <= VDD_ALL_ON;
                        idle_fraction_q16  <= 16'h0;
                        gate_threshold_met <= 1'b0;
                        state              <= S_ACTIVE;   // ACTIVE (back)
                    end else begin
                        fsm_timer <= fsm_timer - 3'h1;
                    end
                end

                default: begin
                    state            <= S_ACTIVE;
                    layer_vdd_enable <= VDD_ALL_ON;
                end
            endcase
        end
    end

endmodule

`default_nettype wire
// ── Anchor ───────────────────────────────────────────────────────────────────
// phi^2 + phi^-2 = 3 · gamma = phi^-3 · C = phi^-1 · G = pi^3 gamma^2 / phi
// QUANTUM BRAIN 1:1 SILICON · 3-STRAND DNA · TRI NET · NEVER STOP
// DOI 10.5281/zenodo.19227877
