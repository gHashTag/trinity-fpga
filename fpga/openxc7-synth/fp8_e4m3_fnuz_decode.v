// SPDX-License-Identifier: Apache-2.0
// tt-trinity-corona / src/rtl/fp8_e4m3_fnuz_decode.v
// FP8 E4M3 FNUZ -> FP32 decode. AMD MI300 / CDNA3 variant.
// 1s+4e+3m, bias=8. 0x00=+0, 0x80=NaN. No inf. Has subnormals.

`default_nettype none

module fp8_e4m3_fnuz_decode (
    input  wire [7:0]  e4m3_in,
    output reg  [31:0] fp32_out,
    output wire        is_zero,
    output wire        is_nan
);

    wire        sign = e4m3_in[7];
    wire [3:0]  exp  = e4m3_in[6:3];
    wire [2:0]  mant = e4m3_in[2:0];

    assign is_zero = (e4m3_in == 8'h00);
    assign is_nan  = (e4m3_in == 8'h80);

    reg [7:0]  fp32_exp;
    reg [22:0] fp32_mant;

    always @(*) begin
        if (is_nan) begin
            fp32_exp  = 8'hFF;
            fp32_mant = 23'h400000;
        end else if (is_zero) begin
            fp32_exp  = 8'h00;
            fp32_mant = 23'h000000;
        end else if (exp == 4'd0) begin
            // Subnormal: value = (-1)^S * 2^(1-8) * (M/8) = (-1)^S * M * 2^(-10)
            if (mant[2]) begin
                fp32_exp  = 8'd119;           // 127-8 = 119
                fp32_mant = {mant[1:0], 21'b0};
            end else if (mant[1]) begin
                fp32_exp  = 8'd118;           // 127-9 = 118
                fp32_mant = {mant[0], 22'b0};
            end else begin
                fp32_exp  = 8'd117;           // 127-10 = 117
                fp32_mant = 23'b0;
            end
        end else begin
            // Normal: value = (-1)^S * 2^(E-8) * (1 + M/8)
            fp32_exp  = {4'b0, exp} + 8'd119;
            fp32_mant = {mant, 20'b0};
        end
    end

    always @(*) begin
        if (is_nan)
            fp32_out = 32'h7FC00000;
        else
            fp32_out = {sign, fp32_exp, fp32_mant};
    end

endmodule
