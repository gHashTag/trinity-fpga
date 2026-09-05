`default_nettype none
`timescale 1ns / 1ps
// minifloat_decode — E3M4 8-bit minifloat → IEEE-754 binary32.
// Bit layout: [7] sign, [6:4] exponent (3 bits), [3:0] mantissa (4 bits).
// Bias = 2^(3-1)-1 = 3.
// Classes: exp=0,m=0→zero; exp=0,m≠0→subnormal; exp=7,m=0→Inf; exp=7,m≠0→NaN.
module minifloat_decode (
    input  wire [7:0]  mf_in,
    output reg  [31:0] fp32_out,
    output wire        is_nan_o,
    output wire        is_inf_o,
    output wire        is_zero_o
);
    wire       sign  = mf_in[7];
    wire [2:0] exp_in = mf_in[6:4];
    wire [3:0] mant  = mf_in[3:0];

    wire is_exp_zero = (exp_in == 3'd0);
    wire is_exp_max  = (exp_in == 3'd7);
    wire is_mant_zero = (mant == 4'd0);

    assign is_zero_o = is_exp_zero && is_mant_zero;
    assign is_inf_o  = is_exp_max  && is_mant_zero;
    assign is_nan_o  = is_exp_max  && !is_mant_zero;

    wire cls_subnormal = is_exp_zero && !is_mant_zero;
    wire cls_normal    = !is_exp_zero && !is_exp_max;

    // Normal: value = (-1)^s × (1 + m/16) × 2^(e-3)
    // Subnormal: value = (-1)^s × (m/16) × 2^(1-3) = (-1)^s × m × 2^(-7)
    wire [7:0] norm_biased = {5'b0, exp_in} + 8'd124; // (e-3)+127 = e+124
    wire [22:0] norm_mant  = {mant, 19'b0};           // 4 bits → 23 bits

    // Subnormal: true_exp = 1 - 3 = -2, biased = 125
    // value = m/16 × 2^(-2) = m × 2^(-6)
    // Normalize m (4-bit): find leading 1
    function [2:0] clz4;
        input [3:0] v;
        begin
            casez (v)
                4'b1???: clz4 = 0;
                4'b01??: clz4 = 1;
                4'b001?: clz4 = 2;
                4'b0001: clz4 = 3;
                default: clz4 = 4;
            endcase
        end
    endfunction

    wire [2:0] sub_lzc = clz4(mant);
    // Subnormal renormalization: shift mant to create implicit 1
    // value = m × 2^(-6), normalize m → m_norm × 2^(3-lzc) × 2^(-6) = m_norm × 2^(-3-lzc)
    // biased_exp = 127 - 3 - lzc = 124 - lzc
    wire [7:0] sub_biased = 8'd124 - {5'b0, sub_lzc};
    wire [3:0] sub_shifted = mant << (sub_lzc + 1);
    wire [22:0] sub_mant = {sub_shifted, 19'b0};

    always @(*) begin
        if (is_exp_max && !is_mant_zero)
            fp32_out = 32'h7FC00001; // qNaN
        else if (is_exp_max && is_mant_zero)
            fp32_out = sign ? 32'hFF800000 : 32'h7F800000; // ±Inf
        else if (is_exp_zero && is_mant_zero)
            fp32_out = {sign, 31'b0}; // ±0
        else if (cls_normal)
            fp32_out = {sign, norm_biased, norm_mant};
        else begin // subnormal
            if (sub_biased >= 8'd127)
                fp32_out = {sign, sub_biased, sub_mant}; // became normal after renorm
            else if (sub_biased <= 8'd0)
                fp32_out = {sign, 31'b0}; // flush to zero (too small)
            else
                fp32_out = {sign, sub_biased, sub_mant};
        end
    end
endmodule
`default_nettype none
