// SPDX-License-Identifier: Apache-2.0
// gf14_decode — GoldenFloat14 (1S+5E+8M, bias=15, HAS_INF=0) -> FP32 decode.
// Standard IEEE-like unpack. exp=all-ones (31) is a finite max (no Inf/NaN — has_inf=0).
// exp=0 -> zero / subnormal (2^-14 * 0.mant, normalized). Decode to FP32 is exact.
`default_nettype none
`timescale 1ns / 1ps

module gf14_decode (
    input  wire [13:0] gf14_in,
    output reg  [31:0] fp32_out,
    output wire        is_zero
);

    wire        sign = gf14_in[13];
    wire [4:0]  exp  = gf14_in[12:8];
    wire [7:0]  mant = gf14_in[7:0];

    assign is_zero = (exp == 5'd0) && (mant == 8'd0);

    reg [7:0]  fp32_exp;
    reg [22:0] fp32_mant;

    always @(*) begin
        if (is_zero) begin
            fp32_exp  = 8'h00;
            fp32_mant = 23'h000000;
        end else if (exp == 5'd0) begin
            // Subnormal: value = (-1)^S * 2^(1-15) * (0.mant) = 2^-14 * (mant/256).
            // Normalize by leading-one position (8-bit mantissa).
            casez (mant)
                8'b1???????: begin fp32_exp = 8'd112; fp32_mant = {mant[6:0], 16'b0}; end  // 1.x * 2^-15
                8'b01??????: begin fp32_exp = 8'd111; fp32_mant = {mant[5:0], 17'b0}; end
                8'b001?????: begin fp32_exp = 8'd110; fp32_mant = {mant[4:0], 18'b0}; end
                8'b0001????: begin fp32_exp = 8'd109; fp32_mant = {mant[3:0], 19'b0}; end
                8'b00001???: begin fp32_exp = 8'd108; fp32_mant = {mant[2:0], 20'b0}; end
                8'b000001??: begin fp32_exp = 8'd107; fp32_mant = {mant[1:0], 21'b0}; end
                8'b0000001?: begin fp32_exp = 8'd106; fp32_mant = {mant[0],   22'b0}; end
                default:      begin fp32_exp = 8'd105; fp32_mant = 23'b0;             end  // mant==1: 1.0 * 2^-22
            endcase
        end else begin
            // Normal (exp 1..31; exp=31 is finite max since has_inf=0):
            // value = (-1)^S * 2^(exp-15) * (1.mant). FP32 exp = exp - 15 + 127 = exp + 112.
            fp32_exp  = {3'b0, exp} + 8'd112;
            fp32_mant = {mant, 15'b0};
        end
    end

    always @(*) begin
        fp32_out = {sign, fp32_exp, fp32_mant};
    end

endmodule

`default_nettype wire
