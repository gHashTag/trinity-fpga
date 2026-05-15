// ============================================================================
// trinity_gf16_tile.v — Trinity GF16 Processing Tile
// gHashTag/trinity-fpga#93 · L-DPC22 TT V15 MAX-TRUE TURBO
//
// Synthesizable GF16 tile: MAC accumulator for ternary-packed 4-bit operands.
// Patched (L-DPC22-N): added sparse_in port and mac_clken clock-gate for
// S-16 sparse zero-skip PE (zero_flag suppresses MAC accumulator update).
//
// Anchor: phi^2 + phi^-2 = 3 · DOI 10.5281/zenodo.19227877
// ============================================================================

`default_nettype none
`timescale 1ns / 1ps

module trinity_gf16_tile (
    input  wire        clk,
    input  wire        rst_n,
    // GF16 operands (4-bit ternary-packed)
    input  wire [3:0]  a,            // Operand A
    input  wire [3:0]  b,            // Operand B
    // Accumulator output
    output reg  [7:0]  mac_accum,    // MAC accumulator (8-bit)
    output wire        mac_valid,    // Accumulator output valid
    // ---- S-16 sparse zero-skip port (L-DPC22-N additive patch) ----
    input  wire        sparse_in     // External zero_flag from sparse_gate
);

    // -------------------------------------------------------------------------
    // Existing internal signals (preserved — additive diff only)
    // -------------------------------------------------------------------------
    reg  [3:0]  a_reg;               // Registered operand A
    reg  [3:0]  b_reg;               // Registered operand B
    reg         valid_reg;           // Pipeline valid stage

    // -------------------------------------------------------------------------
    // S-16 sparse clock-gate logic (L-DPC22-N addition)
    // mac_clken = 1 → perform MAC update
    // mac_clken = 0 → skip MAC update (zero operand detected)
    // -------------------------------------------------------------------------
    wire mac_clken;
    assign mac_clken = ~sparse_in;   // Active when NOT flagged as zero

    // -------------------------------------------------------------------------
    // Input pipeline register (existing behaviour, preserved)
    // -------------------------------------------------------------------------
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            a_reg     <= 4'b0;
            b_reg     <= 4'b0;
            valid_reg <= 1'b0;
        end else begin
            a_reg     <= a;
            b_reg     <= b;
            valid_reg <= 1'b1;
        end
    end

    // -------------------------------------------------------------------------
    // GF16 ternary multiply-accumulate
    // Ternary encoding: 2'b00 = -1, 2'b01 = 0, 2'b10 = +1
    // Two ternary lanes packed into each 4-bit operand: [3:2] = lane1, [1:0] = lane0
    // -------------------------------------------------------------------------
    wire [1:0] a0 = a_reg[1:0];
    wire [1:0] a1 = a_reg[3:2];
    wire [1:0] b0 = b_reg[1:0];
    wire [1:0] b1 = b_reg[3:2];

    // Lane 0 ternary product
    wire a0_zero = (a0 == 2'b01);
    wire b0_zero = (b0 == 2'b01);
    wire pp0_zero = a0_zero | b0_zero;
    wire pp0_neg  = (a0[1] ^ b0[1]) & ~pp0_zero;
    wire pp0_pos  = ~pp0_zero & ~pp0_neg;
    wire signed [2:0] pp0 = pp0_zero ? 3'sd0 : pp0_neg ? -3'sd1 : 3'sd1;

    // Lane 1 ternary product
    wire a1_zero = (a1 == 2'b01);
    wire b1_zero = (b1 == 2'b01);
    wire pp1_zero = a1_zero | b1_zero;
    wire pp1_neg  = (a1[1] ^ b1[1]) & ~pp1_zero;
    wire pp1_pos  = ~pp1_zero & ~pp1_neg;
    wire signed [2:0] pp1 = pp1_zero ? 3'sd0 : pp1_neg ? -3'sd1 : 3'sd1;

    // Partial sum of the two lanes
    wire signed [3:0] tile_partial = pp0 + pp1;

    // -------------------------------------------------------------------------
    // MAC accumulator — clock-gated by mac_clken (L-DPC22-N patch)
    // When mac_clken = 0 (sparse_in = 1), the accumulator is NOT updated.
    // All existing wires and regs are preserved; this is additive only.
    // -------------------------------------------------------------------------
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            mac_accum <= 8'h00;
        end else if (mac_clken) begin   // <-- clock-gate: skip on zero operand
            mac_accum <= mac_accum + {{4{tile_partial[3]}}, tile_partial};
        end
        // else: mac_accum holds current value (zero-operand bypass)
    end

    // mac_valid follows the pipeline valid flag
    assign mac_valid = valid_reg;

endmodule
`default_nettype wire
