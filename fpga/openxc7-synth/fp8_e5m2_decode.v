// SPDX-License-Identifier: Apache-2.0
// tt-trinity-corona / src/rtl/fp8_e5m2_decode.v
// FP8 E5M2 -> FP32 decode per OCP MX spec / IEEE-like.
// Format: 1 sign + 5 exp (bias=15) + 2 mantissa. Has Inf and NaN.

`default_nettype none

module fp8_e5m2_decode (
    input  wire [7:0]  e5m2_in,
    output reg  [31:0] fp32_out,
    output wire        is_zero,
    output wire        is_inf,
    output wire        is_nan
);

    wire        sign = e5m2_in[7];
    wire [4:0]  exp  = e5m2_in[6:2];
    wire [1:0]  mant = e5m2_in[1:0];

    assign is_zero = (exp == 5'd0) && (mant == 2'd0);
    assign is_inf  = (exp == 5'h1F) && (mant == 2'd0);
    assign is_nan  = (exp == 5'h1F) && (mant != 2'd0);

    reg [7:0]  fp32_exp;
    reg [22:0] fp32_mant;

    always @(*) begin
        if (is_inf) begin
            fp32_exp  = 8'hFF;
            fp32_mant = 23'h000000;
        end else if (is_nan) begin
            fp32_exp  = 8'hFF;
            fp32_mant = 23'h400000;  // quiet NaN
        end else if (is_zero) begin
            fp32_exp  = 8'h00;
            fp32_mant = 23'h000000;
        end else if (exp == 5'd0) begin
            // Subnormal: value = (-1)^S * 2^(-14) * (0.mant)
            if (mant[1]) begin
                // mant=1x: 2^(-14)*0.5x -> normalized 2^(-15). FP32 exp = -15+127 = 112
                fp32_exp  = 8'd112;
                fp32_mant = {mant[0], 22'b0};
            end else begin
                // mant=01: 2^(-14)*0.25 -> normalized 2^(-16). FP32 exp = -16+127 = 111
                fp32_exp  = 8'd111;
                fp32_mant = 23'b0;
            end
        end else begin
            // Normal: value = (-1)^S * 2^(exp-15) * (1.mant)
            // FP32 exp = exp - 15 + 127 = exp + 112
            fp32_exp  = {3'b0, exp} + 8'd112;
            fp32_mant = {mant, 21'b0};
        end
    end

    always @(*) begin
        fp32_out = {sign, fp32_exp, fp32_mant};
    end

endmodule
