// SPDX-License-Identifier: Apache-2.0
// binary16_decode.v — IEEE 754 binary16 (half, 1S+5E+10M, bias 15) -> FP32.
// Authored in-repo (not Corona-sourced). Standard IEEE decode:
//   zero   (exp=0,mant=0)    -> +/-0
//   denorm (exp=0,mant!=0)   -> value = mant * 2^-24, normalized
//   normal (1<=exp<=30)      -> (1.mant) * 2^(exp-15)
//   inf    (exp=31,mant=0)   -> +/-Inf
//   nan    (exp=31,mant!=0)  -> quiet NaN
// Denormal: p = MSB position of mant (0..9); value = mant*2^-24 =
//   (1.f) * 2^(p-24); fp32 exp_field = p-24+127 = p+103;
//   fp32 mant = (mant with MSB cleared) << (23-p).
`default_nettype none

module binary16_decode (
    input  wire [15:0] b16_in,
    output reg  [31:0] fp32_out,
    output wire        is_zero,
    output wire        is_inf,
    output wire        is_nan
);
    wire        sign = b16_in[15];
    wire [4:0]  exp  = b16_in[14:10];
    wire [9:0]  mant = b16_in[9:0];

    assign is_zero = (exp == 5'd0) && (mant == 10'd0);
    assign is_inf  = (exp == 5'h1F) && (mant == 10'd0);
    assign is_nan  = (exp == 5'h1F) && (mant != 10'd0);

    reg [7:0]  fp32_exp;
    reg [22:0] fp32_mant;
    integer p;

    always @(*) begin
        if (is_inf) begin
            fp32_exp  = 8'hFF;
            fp32_mant = 23'h000000;
        end else if (is_nan) begin
            fp32_exp  = 8'hFF;
            fp32_mant = {mant, 13'b0};   // propagate NaN payload (matches struct 'e')
        end else if (is_zero) begin
            fp32_exp  = 8'h00;
            fp32_mant = 23'h000000;
        end else if (exp == 5'd0) begin
            // denormal: find MSB position p of the 10-bit mant
            casez (mant)
                10'b1????_?????: p = 9;
                10'b01???_?????: p = 8;
                10'b001??_?????: p = 7;
                10'b0001?_?????: p = 6;
                10'b00001_?????: p = 5;
                10'b000001_????: p = 4;
                10'b0000001_???: p = 3;
                10'b00000001_??: p = 2;
                10'b000000001_?: p = 1;
                10'b0000000001:  p = 0;
                default:         p = 0;
            endcase
            fp32_exp  = p + 8'd103;
            fp32_mant = (mant ^ (10'd1 << p)) << (23 - p);
        end else begin
            // normal: fp32 exp = exp-15+127 = exp+112; mantissa << 13
            fp32_exp  = {3'b0, exp} + 8'd112;
            fp32_mant = {mant, 13'b0};
        end
    end

    always @(*) fp32_out = {sign, fp32_exp, fp32_mant};
endmodule

`default_nettype wire
