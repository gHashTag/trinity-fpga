// SPDX-License-Identifier: Apache-2.0
// gf10_decode — GoldenFloat10 (1S+3E+6M, bias=3, HAS_INF=0) -> FP32 decode.
// Standard IEEE-like unpack; exp=all-ones (7) is finite max (no Inf/NaN).
// exp=0 -> zero / subnormal (2^(1-3) * 0.mant = 2^-2 * mant/64, normalized).
`default_nettype none
`timescale 1ns / 1ps

module gf10_decode (
    input  wire [9:0]  gf10_in,
    output reg  [31:0] fp32_out,
    output wire        is_zero
);

    wire        sign = gf10_in[9];
    wire [2:0]  exp  = gf10_in[8:6];
    wire [5:0]  mant = gf10_in[5:0];

    assign is_zero = (exp == 3'd0) && (mant == 6'd0);

    reg [7:0]  fp32_exp;
    reg [22:0] fp32_mant;

    always @(*) begin
        if (is_zero) begin
            fp32_exp  = 8'h00;
            fp32_mant = 23'h000000;
        end else if (exp == 3'd0) begin
            // Subnormal: value = 2^(1-3) * (0.mant) = 2^-2 * (mant/64). Normalize by leading 1.
            casez (mant)
                6'b1?????: begin fp32_exp = 8'd124; fp32_mant = {mant[4:0], 18'b0}; end  // 1.x * 2^-3
                6'b01????: begin fp32_exp = 8'd123; fp32_mant = {mant[3:0], 19'b0}; end
                6'b001???: begin fp32_exp = 8'd122; fp32_mant = {mant[2:0], 20'b0}; end
                6'b0001??: begin fp32_exp = 8'd121; fp32_mant = {mant[1:0], 21'b0}; end
                6'b00001?: begin fp32_exp = 8'd120; fp32_mant = {mant[0],   22'b0}; end
                default:   begin fp32_exp = 8'd119; fp32_mant = 23'b0;             end  // mant==1: 2^-8
            endcase
        end else begin
            // Normal (exp 1..7; exp=7 is finite max since has_inf=0):
            // value = 2^(exp-3) * (1.mant). FP32 exp = exp - 3 + 127 = exp + 124.
            fp32_exp  = {5'b0, exp} + 8'd124;
            fp32_mant = {mant, 17'b0};
        end
    end

    always @(*) begin
        fp32_out = {sign, fp32_exp, fp32_mant};
    end

endmodule

`default_nettype wire
