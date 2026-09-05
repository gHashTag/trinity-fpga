// SPDX-License-Identifier: Apache-2.0
// ibm_hfp32_decode — IBM hexadecimal floating-point (32-bit) -> FP32 decode.
// Format: 1 sign + 7 exp (excess-64, base-16) + 24 fraction (hex 0.MMMMMM).
// Value = (-1)^S × 16^(E-64) × fraction/2^24 = (-1)^S × 2^(4*(E-64)-24) × fraction.
// Normalize: leading-1 detection + barrel shift to 23-bit FP32 mantissa.
`default_nettype none
`timescale 1ns / 1ps

module ibm_hfp32_decode (
    input  wire [31:0] ibm_in,
    output reg  [31:0] fp32_out,
    output wire        is_zero
);
    wire        sign       = ibm_in[31];
    wire [6:0]  exp_field  = ibm_in[30:24];  // excess-64
    wire [23:0] fraction   = ibm_in[23:0];
    assign is_zero = (exp_field == 7'd0) && (fraction == 24'd0);

    reg [4:0] lead;  // leading-1 position (0..23)
    always @(*) begin
        if      (fraction[23]) lead = 5'd23;
        else if (fraction[22]) lead = 5'd22;
        else if (fraction[21]) lead = 5'd21;
        else if (fraction[20]) lead = 5'd20;
        else if (fraction[19]) lead = 5'd19;
        else if (fraction[18]) lead = 5'd18;
        else if (fraction[17]) lead = 5'd17;
        else if (fraction[16]) lead = 5'd16;
        else if (fraction[15]) lead = 5'd15;
        else if (fraction[14]) lead = 5'd14;
        else if (fraction[13]) lead = 5'd13;
        else if (fraction[12]) lead = 5'd12;
        else if (fraction[11]) lead = 5'd11;
        else if (fraction[10]) lead = 5'd10;
        else if (fraction[9])  lead = 5'd9;
        else if (fraction[8])  lead = 5'd8;
        else if (fraction[7])  lead = 5'd7;
        else if (fraction[6])  lead = 5'd6;
        else if (fraction[5])  lead = 5'd5;
        else if (fraction[4])  lead = 5'd4;
        else if (fraction[3])  lead = 5'd3;
        else if (fraction[2])  lead = 5'd2;
        else if (fraction[1])  lead = 5'd1;
        else                   lead = 5'd0;
    end

    // FP32 exponent = 4*(E-64) - 24 + lead + 127
    wire signed [10:0] exp_calc = $signed({4'd0, exp_field}) - 11'sd64;  // E-64
    wire signed [10:0] exp_base2 = (exp_calc <<< 2) - 11'sd24;             // 4*(E-64) - 24
    wire signed [10:0] exp_final = exp_base2 + {{6'd0}, lead} + 11'sd127;

    // Mantissa: fraction shifted left by (23-lead), mask to 23 bits
    wire [23:0] frac_shifted = fraction << (5'd23 - lead);
    wire [22:0] mant = frac_shifted[22:0];

    always @(*) begin
        if (is_zero || fraction == 24'd0)
            fp32_out = {sign, 31'd0};  // zero (or unnormalized zero mantissa)
        else if (exp_final > 11'sd254)
            fp32_out = {sign, 8'hFF, 23'd0};  // overflow -> Inf
        else if (exp_final < 11'sd1)
            fp32_out = {sign, 31'd0};  // underflow -> zero
        else
            fp32_out = {sign, exp_final[7:0], mant};
    end

endmodule

`default_nettype wire
