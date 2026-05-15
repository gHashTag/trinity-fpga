// SPDX-License-Identifier: Apache-2.0
// Copyright 2026 gHashTag / TRI-1 Silicon Program
//
// PRE-SILICON ESTIMATE: +0.04 mm2 net (FSM + V_dd LUT), +1.2 mW controller @ IRDS22FDX
//
// Module : avs_controller
// Purpose: RTL controller for OP_AVS_RECONF=0xE4 -- AVS-48 island reconfiguration FSM.
//          Wave-36 Lane W. 48-island voltage stack, 4 V_dd operating points,
//          per-island enable mask, ≤ 4-cycle reconfig latency.
//
// Sacred opcode chain: 0xDE -> 0xDF -> 0xE0 -> 0xE1 -> 0xE2 -> 0xE3 -> 0xE4
//   (this module decodes 0xE4 only; post-W35 OP_LUT_NPU=0xE3)
//
// R-SI-1: ZERO star operators in synthesizable code.
//         No `*`, no `/`, no `%` -- all arithmetic by `+`/shift/mask only.
//
// Topology:
//   - N_ISLANDS = 48 = 3 strands × 16 islands
//   - V_island base = 0.45 V (V_TOTAL = 21.6 V)
//   - 4 V_dd operating points encoded by V_DD_FIELD_WIDTH_BITS = 2:
//       2'b00 = 0.40 V  (low-power)
//       2'b01 = 0.45 V  (nominal)
//       2'b10 = 0.50 V  (boost)
//       2'b11 = 0.55 V  (turbo)
//   - Reconfig latency: ≤ 4 cycles from valid_in to ack_out (W-105-B)
//
// W-105 predicate witnesses (R7 falsifiers in trios assertions/wave36_avs.json):
//   - W-105-A: BitNet b1.58-3B island_utilisation ≥ 0.80   (Rust witness, tt-trinity-max-true#25)
//   - W-105-B: avs_reconfig_latency_cycles ≤ 4              (this module, structural)
//   - W-105-C: avs_v_dd_field_width_bits exact 2            (this module, V_DD_FIELD_WIDTH)
//   - W-105-D: avs_island_count exact 48                    (this module, N_ISLANDS)
//
// R18 LAYER-FROZEN: purely additive -- this file does NOT modify any existing RTL module.
//
// Author: Vasilev Dmitrii <admin@t27.ai>
// Wave:   Wave-36
// DOI:    10.5281/zenodo.19227877
// ----------------------------------------------------------------------------

`default_nettype none
`timescale 1ns/1ps

module avs_controller #(
    parameter integer N_ISLANDS              = 48,
    parameter integer V_DD_FIELD_WIDTH_BITS  = 2
) (
    input  wire                                   clk,
    input  wire                                   rst_n,
    input  wire                                   valid_in,
    input  wire [7:0]                             opcode,          // 0xE4 = OP_AVS_RECONF
    input  wire [V_DD_FIELD_WIDTH_BITS-1:0]       v_dd_target,     // 4 levels
    input  wire [N_ISLANDS-1:0]                   island_mask_in,  // 48-bit enable mask
    output reg  [V_DD_FIELD_WIDTH_BITS-1:0]       v_dd_active,
    output reg  [N_ISLANDS-1:0]                   island_enable,
    output reg                                    ack_out,
    output reg                                    valid_out
);

    // Sacred opcode
    localparam [7:0] OP_AVS_RECONF = 8'hE4;

    // FSM states (Moore, 4 states -> ≤ 4-cycle latency W-105-B)
    localparam [1:0]
        S_IDLE    = 2'd0,
        S_DECODE  = 2'd1,
        S_APPLY   = 2'd2,
        S_ACK     = 2'd3;

    reg [1:0] state, next_state;

    // Internal registers
    reg [V_DD_FIELD_WIDTH_BITS-1:0] v_dd_latched;
    reg [N_ISLANDS-1:0]             mask_latched;

    // -----------------------------------------------------------------------
    // FSM combinational next-state logic
    // -----------------------------------------------------------------------
    always @* begin
        next_state = state;
        case (state)
            S_IDLE   : next_state = (valid_in && (opcode == OP_AVS_RECONF)) ? S_DECODE : S_IDLE;
            S_DECODE : next_state = S_APPLY;
            S_APPLY  : next_state = S_ACK;
            S_ACK    : next_state = S_IDLE;
            default  : next_state = S_IDLE;
        endcase
    end

    // -----------------------------------------------------------------------
    // FSM sequential state update + datapath
    // -----------------------------------------------------------------------
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state         <= S_IDLE;
            v_dd_active   <= 2'b01;     // boot at nominal 0.45 V
            v_dd_latched  <= 2'b01;
            island_enable <= {N_ISLANDS{1'b1}};
            mask_latched  <= {N_ISLANDS{1'b1}};
            ack_out       <= 1'b0;
            valid_out     <= 1'b0;
        end else begin
            state <= next_state;

            // Default per-cycle outputs
            ack_out   <= 1'b0;
            valid_out <= 1'b0;

            case (state)
                S_IDLE: begin
                    if (valid_in && (opcode == OP_AVS_RECONF)) begin
                        v_dd_latched <= v_dd_target;
                        mask_latched <= island_mask_in;
                    end
                end
                S_DECODE: begin
                    // R-SI-1: pure mask-and-latch, no arithmetic ops
                    // Decode complete -- pass through to apply
                end
                S_APPLY: begin
                    v_dd_active   <= v_dd_latched;
                    island_enable <= mask_latched;
                end
                S_ACK: begin
                    ack_out   <= 1'b1;
                    valid_out <= 1'b1;
                end
                default: begin
                    // Defensive: no action
                end
            endcase
        end
    end

    // -----------------------------------------------------------------------
    // Structural assertions (W-105-C, W-105-D)
    // -----------------------------------------------------------------------
    initial begin
        // W-105-C: V_dd field width is exactly 2 bits
        if (V_DD_FIELD_WIDTH_BITS != 2) begin
            $display("W-105-C FAIL: V_DD_FIELD_WIDTH_BITS=%0d != 2", V_DD_FIELD_WIDTH_BITS);
            $fatal(1);
        end
        // W-105-D: AVS island count is exactly 48
        if (N_ISLANDS != 48) begin
            $display("W-105-D FAIL: N_ISLANDS=%0d != 48", N_ISLANDS);
            $fatal(1);
        end
        // Trinity alignment: N_ISLANDS divisible by 3 (no `%` -- use mask test)
        // 48 = 0b110000, divisible by 3 iff (sum_of_bits_at_3k) - (sum_of_bits_at_3k+1) - 2*(sum_at_3k+2) is 0 mod 3
        // Cheaper: check explicit equality to 48.
        // Already covered above.
    end

endmodule

`default_nettype wire
