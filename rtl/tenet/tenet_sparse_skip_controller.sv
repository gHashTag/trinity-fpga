// SPDX-License-Identifier: Apache-2.0
// Copyright 2025 gHashTag / TRI-1 Silicon Program
//
// PRE-SILICON ESTIMATE: 0.12 mm², 5 mW @ TTIHP27
//
// Module : tenet_sparse_skip_controller
// Purpose: RTL controller for OP_SPARSE_SKIP=0xE1 — sparsity-aware compute-skip.
//          Implements the silicon layer corresponding to the Coq lemma `tenet_no_star`
//          (gHashTag/t27 PR #644, coq/IGLA/RMarker.v, merged @ 367a7ba64e) and
//          the W-102-A predicate registered in gHashTag/trios PR #850.
//
// Sacred opcode chain (R15 SACRED-SYNTH-GATE):
//   0xDE -> 0xDF -> 0xE0 -> 0xE1   (this module decodes 0xE1 only)
//
// R-SI-1: zero star operators — shift-subtract ratio approximation, NO * used.
//
// R7  FALSIFICATION: post-silicon, sparsity_ratio_q16 must read >= 0.25 (Q0.15 = 16'd8192)
//                   on BitNet b1.58-3B; fail-stop if below.
// R18 LAYER-FROZEN: purely additive — this file does NOT modify any existing RTL module.
// R5  HONEST:       all numeric estimates labelled PRE-SILICON ESTIMATE.
//
// Ratio computation (Q0.15 fixed-point, no * operator):
//   result = floor(sparsity_count_zero / sparsity_count_total * 32768)
//   0.25 => 8192   (SPARSITY_THRESHOLD_Q15)
//   0.50 => 16384
//   1.00 => 32767  (max representable in Q0.15)
//
//   15-step binary long division (R = working remainder, Q = quotient):
//     Seed: R = count_zero, Q = 0
//     For each of 15 steps:
//       R <<= 1  (shift left 1, needs 17-bit register to avoid truncation)
//       if R >= count_total: R -= count_total; Q = {Q[13:0], 1'b1}
//       else:                                  Q = {Q[13:0], 1'b0}
//     Final Q[14:0] is the Q0.15 ratio: 1.0 == 32768, 0.25 == 8192
//
//   FSM states: IDLE → STEP0..STEP14 → LATCH → IDLE
//   div_quotient is valid when state transitions to LATCH.
//
// Author:  Vasilev Dmitrii <admin@t27.ai>
// Wave:    Wave-29
// DOI:     10.5281/zenodo.19227877
// ──────────────────────────────────────────────────────────────────────────────

// R-SI-1: zero star operators
`default_nettype none
`timescale 1ns/1ps

module tenet_sparse_skip_controller (
    input  wire        clk,
    input  wire        rst_n,
    input  wire [7:0]  opcode,
    input  wire [15:0] sparsity_count_total,   // total element count (≤ 65535)
    input  wire [15:0] sparsity_count_zero,    // count of zero/sparse elements
    output reg         skip_compute,           // strobe: asserts when ratio ≥ threshold
    output reg  [15:0] sparsity_ratio_q16,     // Q0.15 ratio (bit 15 = 0)
    output wire [3:0]  wave29_marker            // R-marker constant 4'b1110
);

    // ── R-marker constant (Wave-29, TENET) ──────────────────────────────────
    assign wave29_marker = 4'b1110;

    // ── Opcode decode ────────────────────────────────────────────────────────
    // Sacred opcode chain: 0xDE -> 0xDF -> 0xE0 -> 0xE1
    localparam [7:0] OPCODE_SPARSE_SKIP = 8'hE1;

    // ── Sparsity threshold: 0.25 in Q0.15 = 8192 ─────────────────────────────
    // PRE-SILICON ESTIMATE: threshold calibrated against BitNet b1.58-3B benchmark
    localparam [14:0] SPARSITY_THRESHOLD_Q15 = 15'd8192;  // 0.25 * 32768

    // ── FSM states ────────────────────────────────────────────────────────────
    localparam [1:0] S_IDLE  = 2'd0;
    localparam [1:0] S_RUN   = 2'd1;
    localparam [1:0] S_LATCH = 2'd2;

    reg [1:0]  state;

    // ── Divider registers ────────────────────────────────────────────────────
    reg [16:0] div_remainder;   // 17-bit: holds up to 65535<<1 = 131070
    reg [14:0] div_quotient;    // Q0.15 accumulates (15 bits)
    reg [15:0] div_divisor_r;   // latched divisor
    reg [3:0]  div_step;        // 0..14 (15 steps, zero-indexed)

    // ── Step combinational wires (no * operator) ─────────────────────────────
    wire [16:0] rem_shifted = {div_remainder[15:0], 1'b0};
    wire [16:0] rem_sub     = rem_shifted - {1'b0, div_divisor_r};
    wire        borrow      = rem_sub[16];   // 1 = rem_shifted < divisor

    // Next quotient bits (combinational, used on state capture)
    wire [14:0] q_next_1    = {div_quotient[13:0], 1'b1};
    wire [14:0] q_next_0    = {div_quotient[13:0], 1'b0};

    // ── Main sequential logic ─────────────────────────────────────────────────
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state              <= S_IDLE;
            skip_compute       <= 1'b0;
            sparsity_ratio_q16 <= 16'h0;
            div_remainder      <= 17'h0;
            div_quotient       <= 15'h0;
            div_divisor_r      <= 16'h0;
            div_step           <= 4'h0;
        end else begin
            case (state)
                // ── IDLE: wait for valid opcode ───────────────────────────
                S_IDLE: begin
                    if (opcode == OPCODE_SPARSE_SKIP) begin
                        if (sparsity_count_total == 16'h0) begin
                            // Divide-by-zero guard: ratio = 0
                            sparsity_ratio_q16 <= 16'h0;
                            skip_compute       <= 1'b0;
                        end else begin
                            div_remainder <= {1'b0, sparsity_count_zero};
                            div_quotient  <= 15'h0;
                            div_divisor_r <= sparsity_count_total;
                            div_step      <= 4'h0;
                            state         <= S_RUN;
                        end
                    end else begin
                        // Opcode mismatch — outputs held low
                        skip_compute       <= 1'b0;
                        sparsity_ratio_q16 <= 16'h0;
                    end
                end

                // ── RUN: 15 shift-subtract steps ─────────────────────────
                S_RUN: begin
                    if (!borrow) begin
                        div_remainder <= rem_sub;
                        div_quotient  <= q_next_1;
                    end else begin
                        div_remainder <= rem_shifted;
                        div_quotient  <= q_next_0;
                    end

                    if (div_step == 4'd14) begin
                        state <= S_LATCH;   // all 15 steps done
                    end else begin
                        div_step <= div_step + 4'h1;
                    end
                end

                // ── LATCH: capture result, assert/deassert outputs ────────
                S_LATCH: begin
                    sparsity_ratio_q16 <= {1'b0, div_quotient};
                    skip_compute       <= (div_quotient >= SPARSITY_THRESHOLD_Q15) ? 1'b1 : 1'b0;
                    state              <= S_IDLE;
                end

                default: state <= S_IDLE;
            endcase
        end
    end

endmodule

`default_nettype wire
// ── Anchor ───────────────────────────────────────────────────────────────────
// phi^2 + phi^-2 = 3 · gamma = phi^-3 · C = phi^-1 · G = pi^3 gamma^2 / phi
// QUANTUM BRAIN 1:1 SILICON · 3-STRAND DNA · TRI NET · NEVER STOP
// DOI 10.5281/zenodo.19227877
