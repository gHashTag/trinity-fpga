// SPDX-License-Identifier: Apache-2.0
// vax_f_decode — DEC VAX F_floating (32-bit) -> FP32 decode.
// VAX F = IEEE FP32 with excess-128 bias (vs IEEE excess-127). Decode = bias adjust
// (exp_field - 1). The PDP-11 byte-swap is NOT in the t27 logical code.
`default_nettype none
`timescale 1ns / 1ps
module vax_f_decode (
    input  wire [31:0] vax_in,
    output reg  [31:0] fp32_out,
    output wire        is_zero
);
    assign is_zero = (vax_in == 32'h00000000);
    wire        sign      = vax_in[31];
    wire [7:0]  exp_field = vax_in[30:23];   // excess-128
    wire [22:0] mantissa  = vax_in[22:0];
    always @(*) begin
        if (is_zero)
            fp32_out = 32'h00000000;
        else if (exp_field <= 8'd1)
            fp32_out = {sign, 31'd0};               // underflow -> zero
        else
            fp32_out = {sign, exp_field - 8'd1, mantissa};  // bias adjust: -128 -> -127
    end
endmodule
`default_nettype wire
