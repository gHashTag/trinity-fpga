// SPDX-License-Identifier: Apache-2.0
// tt-trinity-corona / src/rtl/fp6_e2m3_decode.v
// FP6 E2M3 -> FP32 decode (Blackwell tensor core format).
// Format: 1 sign + 2 exp (bias=1) + 3 mantissa. No Inf/NaN.

`default_nettype none

module fp6_e2m3_decode (
    input  wire [5:0]  fp6_in,
    output reg  [31:0] fp32_out,
    output wire        is_zero
);

    wire        sign = fp6_in[5];
    wire [1:0]  exp  = fp6_in[4:3];
    wire [2:0]  mant = fp6_in[2:0];

    assign is_zero = (exp == 2'd0) && (mant == 3'd0);

    reg [7:0]  fp32_exp;
    reg [22:0] fp32_mant;

    always @(*) begin
        if (is_zero) begin
            fp32_exp  = 8'h00;
            fp32_mant = 23'h000000;
        end else if (exp == 2'd0) begin
            // Subnormal: 2^(1-1) * 0.mmm = 0.mmm
            if (mant[2]) begin
                // 1xx: normalized 1.xx * 2^(-1). FP32 exp = -1+127 = 126
                fp32_exp  = 8'd126;
                fp32_mant = {mant[1:0], 21'b0};
            end else if (mant[1]) begin
                // 01x: normalized 1.x * 2^(-2). FP32 exp = -2+127 = 125
                fp32_exp  = 8'd125;
                fp32_mant = {mant[0], 22'b0};
            end else begin
                // 001: normalized 1.0 * 2^(-3). FP32 exp = -3+127 = 124
                fp32_exp  = 8'd124;
                fp32_mant = 23'b0;
            end
        end else begin
            // Normal: 2^(exp-1) * 1.mmm. FP32 exp = exp - 1 + 127 = exp + 126
            fp32_exp  = {6'b0, exp} + 8'd126;
            fp32_mant = {mant, 20'b0};
        end
    end

    always @(*) begin
        fp32_out = {sign, fp32_exp, fp32_mant};
    end

endmodule
