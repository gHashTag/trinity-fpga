// SPDX-License-Identifier: Apache-2.0
// tt-trinity-corona / src/rtl/tf32_decode.v
// TF32 (TensorFloat-32) -> FP32 decode.
// Format: 1 sign + 8 exp + 10 mantissa = 19 bits (stored in lower 19 of 32).
// Decode is pure wiring: zero-extend mantissa from 10 to 23 bits.

`default_nettype none

module tf32_decode (
    input  wire [18:0] tf32_in,
    output wire [31:0] fp32_out,
    output wire        is_zero,
    output wire        is_inf,
    output wire        is_nan
);

    wire        sign = tf32_in[18];
    wire [7:0]  exp  = tf32_in[17:10];
    wire [9:0]  mant = tf32_in[9:0];

    assign fp32_out = {sign, exp, mant, 13'b0};
    assign is_zero  = (exp == 8'd0) && (mant == 10'd0);
    assign is_inf   = (exp == 8'hFF) && (mant == 10'd0);
    assign is_nan   = (exp == 8'hFF) && (mant != 10'd0);

endmodule
