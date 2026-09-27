`default_nettype none
`timescale 1ns / 1ps
//=============================================================================
// mxdot4_core -- the exact dot product of two 32-element MX blocks, with
// MXFP4 (E2M1) or TNF4 elements and E8M0 scales.
//
// Spec: specs/trinet/mxdot4_on_board_ax7203.t27. Every constant is a
// `MXDOT4_* macro from fpga/tnet/mxdot4_board_params.v, generated from it;
// list that file first.
//
// An element is 4 bits: bit 3 the sign, bits 2..0 a magnitude code. The code's
// value in units of 2^-UNIT_SHIFT is an entry of the format's table, the only
// thing that differs between the two formats; MXFP4 and TNF4 go through the
// same lanes, adders and word. The sum is exact: 32 products of at most 12 x 12,
// so 14 signed bits hold any block, and no rounding happens anywhere.
//
//   out_y = NAN_WORD                     if in_sa or in_sb is SCALE_NAN
//         = {1'b0, sa + sb, S}           S = sum of the 32 signed products
//
// FORMATS picks which tables are built: 1 MXFP4 only, 2 TNF4 only, 3 both, the
// op choosing. The one-format builds are the cost comparison; the board runs 3.
// An op the build does not have gets out_badop and out_y = 0.
//
// Three stages, `MXDOT4_CORE_STAGES: decode and multiply per lane; eight sums
// of four; the sum of eight and the word.
//=============================================================================
module mxdot4_core #(
    parameter integer FORMATS = 3
) (
    input  wire         clk,
    input  wire         rst,
    input  wire         in_valid,
    input  wire [7:0]   in_op,
    input  wire [7:0]   in_sa,
    input  wire [7:0]   in_sb,
    input  wire [`MXDOT4_BLOCK*`MXDOT4_ELEM_BITS-1:0] in_a,
    input  wire [`MXDOT4_BLOCK*`MXDOT4_ELEM_BITS-1:0] in_b,
    output reg          out_valid,
    output reg          out_badop,
    output reg  [`MXDOT4_WORD_BITS-1:0] out_y
);
    localparam integer N  = `MXDOT4_BLOCK;
    localparam integer EB = `MXDOT4_ELEM_BITS;
    localparam integer SB = `MXDOT4_SUM_BITS;
    localparam integer XB = `MXDOT4_EXP_BITS;
    localparam integer PB = 9;          // one signed product, |p| <= 144
    localparam integer QB = 11;         // a sum of four, |q| <= 576
    localparam [31:0] E2M1 = `MXDOT4_E2M1_TABLE;
    localparam [31:0] TNF4 = `MXDOT4_TNF4_TABLE;
    localparam [7:0]  SCALE_NAN = `MXDOT4_SCALE_NAN;

    function [3:0] level(input [31:0] tab, input [2:0] code);
        level = tab[{code, 2'b00} +: 4];
    endfunction

    wire has_mx  = FORMATS[0];
    wire has_tnf = FORMATS[1];
    wire is_mx   = in_op == `MXDOT4_OP_MXFP4;
    wire is_tnf  = in_op == `MXDOT4_OP_TNF4;
    wire ok      = (has_mx && is_mx) || (has_tnf && is_tnf);
    // With one format built the table is a constant and the op never reaches a lane.
    wire use_tnf = (FORMATS == 2) ? 1'b1 : (FORMATS == 1) ? 1'b0 : is_tnf;

    //-------------------------------------------------------------------------
    // Stage 1: per lane, magnitude x magnitude, then the sign.
    //-------------------------------------------------------------------------
    reg signed [PB-1:0] p1 [0:N-1];
    reg                 v1, bad1, nan1;
    reg [XB-1:0]        e1;

    integer i;
    always @(posedge clk) begin
        for (i = 0; i < N; i = i + 1) begin : lane
            reg [3:0] ea, eb;
            reg [3:0] ma, mb;
            reg [7:0] m;
            ea = in_a[EB*i +: EB];
            eb = in_b[EB*i +: EB];
            ma = use_tnf ? level(TNF4, ea[2:0]) : level(E2M1, ea[2:0]);
            mb = use_tnf ? level(TNF4, eb[2:0]) : level(E2M1, eb[2:0]);
            m  = ma * mb;
            p1[i] <= (ea[3] ^ eb[3]) ? -$signed({1'b0, m}) : $signed({1'b0, m});
        end
        bad1 <= ~ok;
        nan1 <= (in_sa == SCALE_NAN) || (in_sb == SCALE_NAN);
        e1   <= {1'b0, in_sa} + {1'b0, in_sb};
    end

    //-------------------------------------------------------------------------
    // Stage 2: eight sums of four lanes.
    //-------------------------------------------------------------------------
    reg signed [QB-1:0] q2 [0:N/4-1];
    reg                 v2, bad2, nan2;
    reg [XB-1:0]        e2;

    integer j;
    always @(posedge clk) begin
        for (j = 0; j < N / 4; j = j + 1)
            q2[j] <= p1[4*j] + p1[4*j+1] + p1[4*j+2] + p1[4*j+3];
        bad2 <= bad1; nan2 <= nan1; e2 <= e1;
    end

    //-------------------------------------------------------------------------
    // Stage 3: the sum of eight and the word.
    //-------------------------------------------------------------------------
    reg signed [SB-1:0] s3;
    integer k;
    always @(*) begin
        s3 = {SB{1'b0}};
        for (k = 0; k < N / 4; k = k + 1) s3 = s3 + q2[k];
    end

    always @(posedge clk) begin
        out_badop <= bad2;
        out_y     <= bad2 ? {`MXDOT4_WORD_BITS{1'b0}}
                   : nan2 ? `MXDOT4_NAN_WORD
                   : {1'b0, e2, s3};
    end

    always @(posedge clk or posedge rst) begin
        if (rst) begin
            v1 <= 1'b0; v2 <= 1'b0; out_valid <= 1'b0;
        end else begin
            v1 <= in_valid; v2 <= v1; out_valid <= v2;
        end
    end
endmodule
`default_nettype wire
