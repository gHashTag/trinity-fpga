// SPDX-License-Identifier: Apache-2.0
// posit32_decode — Posit32 (n=32, es=2) -> FP32 decode with RNE rounding.
// Posit Standard 2022. useed = 2^(2^2) = 16. value = (-1)^S * 2^(4k + e) * (1+fraction).
// Fraction can be up to ~27 bits — exceeds FP32's 23-bit mantissa, so RNE rounding
// (guard/round/sticky, round-to-nearest-even) is applied. NaR = 0x80000000.
`default_nettype none
`timescale 1ns / 1ps

module posit32_decode (
    input  wire [31:0] posit_in,
    output reg  [31:0] fp32_out,
    output wire        is_zero,
    output wire        is_nar
);

    assign is_zero = (posit_in == 32'h00000000);
    assign is_nar  = (posit_in == 32'h80000000);

    wire        sign    = posit_in[31];
    wire [30:0] abs_val = sign ? (~posit_in[30:0] + 31'd1) : posit_in[30:0];

    // Regime: regime_sign = abs_val[30]. Count leading identical bits on 31-bit field.
    wire        regime_sign = abs_val[30];
    wire [30:0] regime_bits = regime_sign ? ~abs_val : abs_val;

    // LZC on 31 bits (0..30)
    reg  [4:0] lzc;
    always @(*) begin
        casez (regime_bits)
            31'b1??????????????????????????????: lzc = 5'd0;
            31'b01?????????????????????????????: lzc = 5'd1;
            31'b001????????????????????????????: lzc = 5'd2;
            31'b0001???????????????????????????: lzc = 5'd3;
            31'b00001??????????????????????????: lzc = 5'd4;
            31'b000001?????????????????????????: lzc = 5'd5;
            31'b0000001????????????????????????: lzc = 5'd6;
            31'b00000001???????????????????????: lzc = 5'd7;
            31'b000000001??????????????????????: lzc = 5'd8;
            31'b0000000001?????????????????????: lzc = 5'd9;
            31'b00000000001????????????????????: lzc = 5'd10;
            31'b000000000001????????????????????: lzc = 5'd11;
            31'b0000000000001???????????????????: lzc = 5'd12;
            31'b00000000000001??????????????????: lzc = 5'd13;
            31'b000000000000001?????????????????: lzc = 5'd14;
            31'b0000000000000001????????????????: lzc = 5'd15;
            31'b00000000000000001???????????????: lzc = 5'd16;
            31'b000000000000000001??????????????: lzc = 5'd17;
            31'b0000000000000000001?????????????: lzc = 5'd18;
            31'b00000000000000000001????????????: lzc = 5'd19;
            31'b000000000000000000001???????????: lzc = 5'd20;
            31'b0000000000000000000001??????????: lzc = 5'd21;
            31'b00000000000000000000001????????: lzc = 5'd22;
            31'b000000000000000000000001???????: lzc = 5'd23;
            31'b0000000000000000000000001??????: lzc = 5'd24;
            31'b00000000000000000000000001????: lzc = 5'd25;
            31'b000000000000000000000000001???: lzc = 5'd26;
            31'b0000000000000000000000000001??: lzc = 5'd27;
            31'b00000000000000000000000000001?: lzc = 5'd28;
            31'b000000000000000000000000000001: lzc = 5'd29;
            default:                            lzc = 5'd29;
        endcase
    end

    wire signed [5:0] regime_k = regime_sign ?
        ($signed({1'b0, lzc}) - 6'sd1) :
        -$signed({1'b0, lzc});

    wire [5:0] regime_total = (lzc < 5'd29) ? lzc + 5'd1 : lzc;

    // After regime + terminator: exponent (es=2) + fraction.
    wire [30:0] after_regime = abs_val << regime_total;
    wire [1:0]  e_field       = after_regime[30:29];
    wire [30:0] frac_field    = after_regime << 2;  // fraction left-aligned to bit 30

    // FP32 exponent = 4*k + e + 127 (9-bit signed, same as posit16).
    wire signed [8:0] four_k  = $signed(regime_k) * 9'sd4;
    wire signed [8:0] exp_raw = four_k + $signed({7'b0, e_field}) + 9'sd127;

    // RNE rounding: fraction up to 27 bits → extract 23-bit mantissa + guard/round/sticky.
    wire [22:0] mant_pre  = frac_field[30:8];   // top 23 bits of fraction
    wire        guard     = frac_field[7];        // guard bit
    wire        round_b   = frac_field[6];        // round bit
    wire        sticky    = |frac_field[5:0];     // sticky (OR of remaining)

    wire        round_up  = guard & (round_b | sticky | mant_pre[0]);
    wire [23:0] mant_rnd  = {1'b0, mant_pre} + (round_up ? 24'd1 : 24'd0);

    // Carry from rounding may increment exponent.
    wire        mant_carry = mant_rnd[23];
    wire [22:0] mant_final = mant_rnd[22:0];
    wire signed [8:0] exp_final = exp_raw + (mant_carry ? 9'sd1 : 9'sd0);

    always @(*) begin
        if (is_zero)
            fp32_out = 32'h00000000;
        else if (is_nar)
            fp32_out = 32'h7FC00000;  // NaR -> qNaN
        else if (exp_final > 9'sd254)
            fp32_out = {sign, 8'hFF, 23'h000000};  // overflow -> Inf
        else if (exp_final < 9'sd1)
            fp32_out = {sign, 8'h00, 23'h000000};  // underflow -> zero
        else
            fp32_out = {sign, exp_final[7:0], mant_final};
    end

endmodule

`default_nettype wire
