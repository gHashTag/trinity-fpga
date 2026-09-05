// SPDX-License-Identifier: Apache-2.0
// posit16_decode — Posit16 (n=16, es=2) -> FP32 decode.
// Posit Standard 2022. useed = 2^(2^es) = 16. value = (-1)^S * 16^k * 2^e * (1+fraction)
//   = (-1)^S * 2^(4k + e) * (1 + fraction). NaR = 0x8000; zero = 0x0000.
// Decode to FP32 is EXACT for in-range values: exponent (4k+e) is integral and the
// fraction (<=13 bits) fits FP32's 23-bit mantissa, so no rounding is needed.
`default_nettype none
`timescale 1ns / 1ps

module posit16_decode (
    input  wire [15:0] posit_in,
    output reg  [31:0] fp32_out,
    output wire        is_zero,
    output wire        is_nar
);

    assign is_zero = (posit_in == 16'h0000);
    assign is_nar  = (posit_in == 16'h8000);

    // Step 1: sign + 2's complement of the 15-bit magnitude if negative.
    wire        sign    = posit_in[15];
    wire [14:0] abs_val = sign ? (~posit_in[14:0] + 15'd1) : posit_in[14:0];

    // Step 2: regime. regime_sign = abs_val[14]. Count leading identical bits.
    //         regime_bits flips so the regime run becomes leading 0s, then LZC.
    wire        regime_sign = abs_val[14];
    wire [14:0] regime_bits = regime_sign ? ~abs_val : abs_val;

    // LZC on 15 bits (0..14): position of the first 1 (the terminator of the run).
    reg  [3:0] lzc;
    always @(*) begin
        casez (regime_bits)
            15'b1??????????????: lzc = 4'd0;
            15'b01?????????????: lzc = 4'd1;
            15'b001????????????: lzc = 4'd2;
            15'b0001???????????: lzc = 4'd3;
            15'b00001??????????: lzc = 4'd4;
            15'b000001?????????: lzc = 4'd5;
            15'b0000001????????: lzc = 4'd6;
            15'b00000001???????: lzc = 4'd7;
            15'b000000001??????: lzc = 4'd8;
            15'b0000000001?????: lzc = 4'd9;
            15'b00000000001????: lzc = 4'd10;
            15'b000000000001???: lzc = 4'd11;
            15'b0000000000001??: lzc = 4'd12;
            15'b00000000000001?: lzc = 4'd13;
            15'b000000000000001: lzc = 4'd14;
            default:             lzc = 4'd14;   // all-zero regime_bits (all-1 field): k=+14
        endcase
    end

    // Regime value k (signed): regime_sign=1 -> k=lzc-1 (positive run of 1s);
    //                         regime_sign=0 -> k=-lzc (negative run of 0s).
    wire signed [5:0] regime_k = regime_sign ?
        ($signed({2'b00, lzc}) - 6'sd1) :
        -$signed({2'b00, lzc});

    // Step 3: regime + terminator length (cap so we don't overflow the field).
    wire [4:0] regime_total = (lzc < 4'd14) ? {1'b0, lzc} + 5'd1 : {1'b0, lzc};

    // Step 4: exponent (es=2) and fraction. Shift regime+terminator out; the top 2
    //         bits are the exponent, the rest is the fraction (left-aligned).
    wire [14:0] after_regime = abs_val << regime_total;   // top = exp, then fraction
    wire [1:0]  e_field       = after_regime[14:13];
    wire [14:0] frac_field    = after_regime << 2;        // fraction left-aligned to bit 14

    // Step 5: FP32 exponent = 4*k + e + 127 (useed=16 -> 4 bits of exp per regime k).
    //         Compute in 9-bit signed: 4*k (up to 52) + 127 lands at ~179, which OVERFLOWS
    //         signed-8-bit at 128 (that overflow mis-flushed valid values like 3.0 to zero
    //         and 0.5 to Inf on the first silicon run — bug, not algorithm).
    wire signed [8:0] four_k  = $signed(regime_k) * 9'sd4;
    wire signed [8:0] exp_raw = four_k + $signed({7'b0, e_field}) + 9'sd127;

    // Step 6: assemble FP32 (clamp out-of-range exponents to Inf / zero).
    always @(*) begin
        if (is_zero)
            fp32_out = 32'h00000000;
        else if (is_nar)
            fp32_out = 32'h7FC00000;                       // NaR -> qNaN
        else if (exp_raw > 9'sd254)
            fp32_out = {sign, 8'hFF, 23'h000000};          // overflow -> Inf
        else if (exp_raw < 9'sd1)
            fp32_out = {sign, 8'h00, 23'h000000};          // underflow -> zero (flush)
        else
            fp32_out = {sign, exp_raw[7:0], frac_field[14:0], 8'b0};  // fraction MSB at mant[22]
    end

endmodule

`default_nettype wire
