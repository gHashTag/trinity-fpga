// SPDX-License-Identifier: Apache-2.0
// tt-trinity-corona / src/rtl/bf16_decode.v
// BFloat16 -> FP32 decode. Trivial: BF16 is the upper 16 bits of FP32.

`default_nettype none

module bf16_decode (
    input  wire [15:0] bf16_in,
    output wire [31:0] fp32_out,
    output wire        is_zero,
    output wire        is_inf,
    output wire        is_nan
);

    wire       sign = bf16_in[15];
    wire [7:0] exp  = bf16_in[14:7];
    wire [6:0] mant = bf16_in[6:0];

    assign fp32_out = {bf16_in, 16'b0};

    assign is_zero = (exp == 8'h00) && (mant == 7'h00);
    assign is_inf  = (exp == 8'hFF) && (mant == 7'h00);
    assign is_nan  = (exp == 8'hFF) && (mant != 7'h00);

    wire _unused = &{sign, 1'b0};

endmodule
