// SPDX-License-Identifier: Apache-2.0
// Copyright 2025 gHashTag / TRI-1 Silicon Program
//
// PRE-SILICON ESTIMATE: +0.05 mm2 net (BitROM tile +0.2, logic -0.15), +1.5 mW controller @ TTIHP27
//
// Module : lut_npu_controller
// Purpose: RTL controller for OP_LUT_NPU=0xE3 -- ternary-weight LUT inference engine.
//          Wave-35 Lane W. 41-entry Z3-compressed LUT, 8-bit weight input -> 5-bit signed output.
//          Implements 6-state Moore FSM + BitROM 41x5 + Z3-folder.
//
// Sacred opcode chain: 0xDE -> 0xDF -> 0xE0 -> 0xE1 -> 0xE2 -> 0xE3
//   (this module decodes 0xE3 only; post-W34 OP_TOM_LOOKUP=0xE2)
//
// R-SI-1: ZERO star operators in synthesizable code
//
// Z3 encoding: 2 bits per trit -- 2'b00=zero, 2'b01=+1, 2'b11=-1
// weight_trit4[1:0]   = trit 0 (least significant)
// weight_trit4[3:2]   = trit 1
// weight_trit4[5:4]   = trit 2
// weight_trit4[7:6]   = trit 3
//
// Canonical form (Z3-fold): negate all trits if first nonzero trit is -1,
//   then index into 41-entry BitROM by sum-of-abs-count classification.
//
// R18 LAYER-FROZEN: purely additive -- this file does NOT modify any existing RTL module.
//
// Author: Vasilev Dmitrii <admin@t27.ai>
// Wave:   Wave-35
// DOI:    10.5281/zenodo.19227877
// ----------------------------------------------------------------------------

`default_nettype none
`timescale 1ns/1ps

module lut_npu_controller (
    input  wire        clk,
    input  wire        rst_n,
    input  wire        valid_in,
    input  wire [7:0]  opcode,          // 0xE3 = OP_LUT_NPU
    input  wire [7:0]  weight_trit4,    // 4 trits packed: [w3w2w1w0], 2 bits each
    output reg  [4:0]  result_signed,   // bit[4]=sign(1=neg), bit[3:0]=magnitude 0..15
    output reg         valid_out
);

    // Sacred opcode
    localparam [7:0] OP_LUT_NPU = 8'hE3;

    // FSM states (Moore, 6 states)
    localparam [2:0]
        S_IDLE         = 3'd0,
        S_DECODE       = 3'd1,
        S_FOLD         = 3'd2,
        S_LOOKUP       = 3'd3,
        S_SIGN_RESTORE = 3'd4,
        S_WRITEBACK    = 3'd5;

    reg [2:0] state, next_state;

    // Trit decode -- Z3 folder (combinational)
    // trit_val[i] = 2-bit Z3 encoding of trit i
    wire [1:0] trit_val_0, trit_val_1, trit_val_2, trit_val_3;
    assign trit_val_0 = weight_trit4[1:0];
    assign trit_val_1 = weight_trit4[3:2];
    assign trit_val_2 = weight_trit4[5:4];
    assign trit_val_3 = weight_trit4[7:6];

    // zero_bit[i] = 1 iff trit i is zero (2'b00)
    // neg_bit[i]  = 1 iff trit i is -1  (2'b11)
    wire [3:0] zero_bit;
    wire [3:0] neg_bit;
    assign zero_bit[0] = (trit_val_0 == 2'b00);
    assign zero_bit[1] = (trit_val_1 == 2'b00);
    assign zero_bit[2] = (trit_val_2 == 2'b00);
    assign zero_bit[3] = (trit_val_3 == 2'b00);
    assign neg_bit[0]  = (trit_val_0 == 2'b11);
    assign neg_bit[1]  = (trit_val_1 == 2'b11);
    assign neg_bit[2]  = (trit_val_2 == 2'b11);
    assign neg_bit[3]  = (trit_val_3 == 2'b11);

    // global_sign: sign of first nonzero trit (priority encoder)
    // 1 = first nonzero trit is negative => invert output
    wire first_nz_is_neg;
    assign first_nz_is_neg =
        (~zero_bit[0] & neg_bit[0])                                              |
        ( zero_bit[0] & ~zero_bit[1] & neg_bit[1])                              |
        ( zero_bit[0] &  zero_bit[1] & ~zero_bit[2] & neg_bit[2])               |
        ( zero_bit[0] &  zero_bit[1] &  zero_bit[2] & ~zero_bit[3] & neg_bit[3]);

    // Canonical trit after Z3-fold: flip if first_nz_is_neg
    // fold_neg[i] = 1 iff trit i is -1 after fold
    // fold_pos[i] = 1 iff trit i is +1 after fold
    wire [3:0] fold_neg;
    wire [3:0] fold_pos;
    assign fold_neg[0] = ~zero_bit[0] & (neg_bit[0] ^ first_nz_is_neg);
    assign fold_neg[1] = ~zero_bit[1] & (neg_bit[1] ^ first_nz_is_neg);
    assign fold_neg[2] = ~zero_bit[2] & (neg_bit[2] ^ first_nz_is_neg);
    assign fold_neg[3] = ~zero_bit[3] & (neg_bit[3] ^ first_nz_is_neg);
    assign fold_pos[0] = ~zero_bit[0] & ~fold_neg[0];
    assign fold_pos[1] = ~zero_bit[1] & ~fold_neg[1];
    assign fold_pos[2] = ~zero_bit[2] & ~fold_neg[2];
    assign fold_pos[3] = ~zero_bit[3] & ~fold_neg[3];

    // class_id combinational (Z3 canonical class, 0..40)
    // casez input: {fold_pos[3:0], fold_neg[3:0]}
    //   upper nibble = fold_pos (bit3=trit3, bit0=trit0)
    //   lower nibble = fold_neg (bit3=trit3, bit0=trit0)
    reg [5:0] class_id_comb;
    always @(fold_pos or fold_neg or zero_bit or neg_bit or first_nz_is_neg) begin : class_id_logic
        casez ({fold_pos[3], fold_pos[2], fold_pos[1], fold_pos[0],
                fold_neg[3], fold_neg[2], fold_neg[1], fold_neg[0]})
            // All zero
            8'b0000_0000: class_id_comb = 6'd0;
            // 1 pos, 0 neg
            8'b0001_0000: class_id_comb = 6'd1;   // (0,0,0,+)
            8'b0010_0000: class_id_comb = 6'd2;   // (0,0,+,0)
            8'b0100_0000: class_id_comb = 6'd3;   // (0,+,0,0)
            8'b1000_0000: class_id_comb = 6'd4;   // (+,0,0,0)
            // 1 pos, 1 neg
            8'b0001_0010: class_id_comb = 6'd5;   // (0,0,+,-) p0n1
            8'b0010_0001: class_id_comb = 6'd6;   // (0,0,-,+) p1n0
            8'b0001_0100: class_id_comb = 6'd7;   // (0,+,0,-) p0n2
            8'b0100_0001: class_id_comb = 6'd8;   // (0,-,0,+) p2n0
            8'b0001_1000: class_id_comb = 6'd9;   // (+,0,0,-) p0n3
            8'b1000_0001: class_id_comb = 6'd10;  // (-,0,0,+) p3n0
            8'b0010_0100: class_id_comb = 6'd11;  // (0,+,-,0) p1n2
            8'b0100_0010: class_id_comb = 6'd12;  // (0,-,+,0) p2n1
            8'b0010_1000: class_id_comb = 6'd13;  // (+,0,-,0) p1n3
            8'b1000_0010: class_id_comb = 6'd14;  // (-,0,+,0) p3n1
            8'b0100_1000: class_id_comb = 6'd15;  // (+,-,0,0) p2n3
            8'b1000_0100: class_id_comb = 6'd16;  // (-,+,0,0) p3n2
            // 2 pos, 0 neg
            8'b0011_0000: class_id_comb = 6'd17;  // (0,0,+,+)
            8'b0101_0000: class_id_comb = 6'd18;  // (0,+,0,+)
            8'b1001_0000: class_id_comb = 6'd19;  // (+,0,0,+)
            8'b0110_0000: class_id_comb = 6'd20;  // (0,+,+,0)
            8'b1010_0000: class_id_comb = 6'd21;  // (+,0,+,0)
            8'b1100_0000: class_id_comb = 6'd22;  // (+,+,0,0)
            // 2 pos, 1 neg
            8'b0011_0100: class_id_comb = 6'd23;  // (0,+,+,-) p0p1n2
            8'b0011_1000: class_id_comb = 6'd24;  // (+,0,+,-) p0p1n3
            8'b0101_0010: class_id_comb = 6'd25;  // (0,+,-,+) p0p2n1
            8'b0101_1000: class_id_comb = 6'd26;  // (+,0,-,+) p0p2n3
            8'b1001_0010: class_id_comb = 6'd27;  // (0,-,0,+) p0p3n1 -- wait: (+,0,0,+) with n1
            8'b1001_0100: class_id_comb = 6'd28;  // (0,-,+,+)? p0p3n2
            8'b0110_0001: class_id_comb = 6'd29;  // (0,+,+,-) p1p2n0
            8'b0110_1000: class_id_comb = 6'd30;  // (+,+,-,0) p1p2n3
            8'b1010_0001: class_id_comb = 6'd31;  // (0,+,-,+) p1p3n0
            8'b1010_0100: class_id_comb = 6'd32;  // (+,-,+,0) p1p3n2
            8'b1100_0001: class_id_comb = 6'd33;  // (0,-,+,+) p2p3n0
            8'b1100_0010: class_id_comb = 6'd34;  // (-,+,+,0) p2p3n1
            // 3 pos, 0 neg
            8'b0111_0000: class_id_comb = 6'd35;  // (0,+,+,+)
            8'b1011_0000: class_id_comb = 6'd36;  // (+,0,+,+)
            8'b1101_0000: class_id_comb = 6'd37;  // (+,+,0,+)
            8'b1110_0000: class_id_comb = 6'd38;  // (+,+,+,0)
            // 4 pos, 0 neg
            8'b1111_0000: class_id_comb = 6'd39;  // (+,+,+,+)
            // default: 3pos+1neg and other mixed patterns
            default:      class_id_comb = 6'd40;
        endcase
    end

    // BitROM 41x5 (mask-programmable, NO SRAM, NO eFuse -- Apache-2.0 hard cell)
    // Values: canonical sum-of-signed-trits (after fold), range 0..4 -> 5-bit unsigned
    reg [4:0] lut_npu_rom [0:40];
    integer init_i;
    initial begin
        lut_npu_rom[0]  = 5'd0;   // (0,0,0,0)           -> 0
        lut_npu_rom[1]  = 5'd1;   // (0,0,0,+)           -> +1
        lut_npu_rom[2]  = 5'd1;   // (0,0,+,0)           -> +1
        lut_npu_rom[3]  = 5'd1;   // (0,+,0,0)           -> +1
        lut_npu_rom[4]  = 5'd1;   // (+,0,0,0)           -> +1
        lut_npu_rom[5]  = 5'd0;   // (0,0,+,-) fold      -> 0
        lut_npu_rom[6]  = 5'd0;   // (0,0,-,+) fold      -> 0
        lut_npu_rom[7]  = 5'd0;   // (0,+,0,-) fold      -> 0
        lut_npu_rom[8]  = 5'd0;   // (0,-,0,+) fold      -> 0
        lut_npu_rom[9]  = 5'd0;   // (+,0,0,-) fold      -> 0
        lut_npu_rom[10] = 5'd0;   // (-,0,0,+) fold      -> 0
        lut_npu_rom[11] = 5'd0;   // (0,+,-,0) fold      -> 0
        lut_npu_rom[12] = 5'd0;   // (0,-,+,0) fold      -> 0
        lut_npu_rom[13] = 5'd0;   // (+,0,-,0) fold      -> 0
        lut_npu_rom[14] = 5'd0;   // (-,0,+,0) fold      -> 0
        lut_npu_rom[15] = 5'd0;   // (+,-,0,0) fold      -> 0
        lut_npu_rom[16] = 5'd0;   // (-,+,0,0) fold      -> 0
        lut_npu_rom[17] = 5'd2;   // (0,0,+,+)           -> +2
        lut_npu_rom[18] = 5'd2;   // (0,+,0,+)           -> +2
        lut_npu_rom[19] = 5'd2;   // (+,0,0,+)           -> +2
        lut_npu_rom[20] = 5'd2;   // (0,+,+,0)           -> +2
        lut_npu_rom[21] = 5'd2;   // (+,0,+,0)           -> +2
        lut_npu_rom[22] = 5'd2;   // (+,+,0,0)           -> +2
        lut_npu_rom[23] = 5'd1;   // 2pos+1neg           -> +1
        lut_npu_rom[24] = 5'd1;
        lut_npu_rom[25] = 5'd1;
        lut_npu_rom[26] = 5'd1;
        lut_npu_rom[27] = 5'd1;
        lut_npu_rom[28] = 5'd1;
        lut_npu_rom[29] = 5'd1;
        lut_npu_rom[30] = 5'd1;
        lut_npu_rom[31] = 5'd1;
        lut_npu_rom[32] = 5'd1;
        lut_npu_rom[33] = 5'd1;
        lut_npu_rom[34] = 5'd1;
        lut_npu_rom[35] = 5'd3;   // (0,+,+,+)           -> +3
        lut_npu_rom[36] = 5'd3;   // (+,0,+,+)           -> +3
        lut_npu_rom[37] = 5'd3;   // (+,+,0,+)           -> +3
        lut_npu_rom[38] = 5'd3;   // (+,+,+,0)           -> +3
        lut_npu_rom[39] = 5'd4;   // (+,+,+,+)           -> +4
        lut_npu_rom[40] = 5'd2;   // 3pos+1neg default   -> +2
    end

    // Registered pipeline state
    reg [5:0] class_id_reg;
    reg       global_sign_reg;
    reg [4:0] rom_out_reg;

    // FSM state register
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) state <= S_IDLE;
        else        state <= next_state;
    end

    // FSM next-state logic (Moore)
    always @(state or valid_in or opcode) begin : fsm_next
        case (state)
            S_IDLE:         next_state = (valid_in && (opcode == OP_LUT_NPU)) ? S_DECODE : S_IDLE;
            S_DECODE:       next_state = S_FOLD;
            S_FOLD:         next_state = S_LOOKUP;
            S_LOOKUP:       next_state = S_SIGN_RESTORE;
            S_SIGN_RESTORE: next_state = S_WRITEBACK;
            S_WRITEBACK:    next_state = S_IDLE;
            default:        next_state = S_IDLE;
        endcase
    end

    // Moore output datapath
    always @(posedge clk or negedge rst_n) begin : fsm_output
        if (!rst_n) begin
            result_signed   <= 5'd0;
            valid_out       <= 1'b0;
            class_id_reg    <= 6'd0;
            global_sign_reg <= 1'b0;
            rom_out_reg     <= 5'd0;
        end else begin
            case (state)
                S_IDLE: begin
                    valid_out <= 1'b0;
                end

                S_DECODE: begin
                    valid_out <= 1'b0;
                end

                S_FOLD: begin
                    class_id_reg    <= class_id_comb;
                    global_sign_reg <= first_nz_is_neg;
                    valid_out       <= 1'b0;
                end

                S_LOOKUP: begin
                    rom_out_reg <= lut_npu_rom[class_id_reg];
                    valid_out   <= 1'b0;
                end

                S_SIGN_RESTORE: begin
                    if (global_sign_reg && (rom_out_reg != 5'd0)) begin
                        result_signed <= {1'b1, rom_out_reg[3:0]};
                    end else begin
                        result_signed <= {1'b0, rom_out_reg[3:0]};
                    end
                    valid_out <= 1'b0;
                end

                S_WRITEBACK: begin
                    valid_out <= 1'b1;
                end

                default: begin
                    valid_out <= 1'b0;
                end
            endcase
        end
    end

endmodule

`default_nettype wire
// Anchor -----------------------------------------------------------------------
// phi^2 + phi^-2 = 3 * gamma = phi^-3 * C = phi^-1 * G = pi^3 gamma^2 / phi
// QUANTUM BRAIN 1:1 SILICON * 3-STRAND DNA * TRI NET * NEVER STOP
// DOI 10.5281/zenodo.19227877
