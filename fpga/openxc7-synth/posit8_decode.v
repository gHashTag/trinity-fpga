// SPDX-License-Identifier: Apache-2.0
// tt-trinity-corona / src/rtl/posit8_decode.v
// Posit8(es=0) -> FP32 decode.
// Posit8: 1 sign + variable regime + 0 exponent + remaining fraction.
// useed = 2^(2^0) = 2. Value = (-1)^S * 2^k * (1 + fraction).

`default_nettype none

module posit8_decode (
    input  wire [7:0]  posit_in,
    output reg  [31:0] fp32_out,
    output wire        is_zero,
    output wire        is_nar
);

    assign is_zero = (posit_in == 8'h00);
    assign is_nar  = (posit_in == 8'h80);

    // Step 1: 2's complement if negative (sign bit = 1)
    wire       sign    = posit_in[7];
    wire [6:0] abs_val = sign ? (~posit_in[6:0] + 7'd1) : posit_in[6:0];

    // Step 2: Regime detection on abs_val[6:0]
    // Regime starts at bit 6. If bit6=1, count consecutive 1s (regime k = count-1).
    // If bit6=0, count consecutive 0s (regime k = -count).
    wire regime_sign = abs_val[6];

    // Count leading identical bits using a priority encoder
    // For regime_sign=1: count leading 1s -> invert first, then count leading 0s
    // For regime_sign=0: count leading 0s directly
    wire [6:0] regime_bits = regime_sign ? ~abs_val[6:0] : abs_val[6:0];

    // Leading zero count on 7 bits (returns 0-7)
    reg [2:0] lzc;
    always @(*) begin
        casez (regime_bits)
            7'b1??????: lzc = 3'd0;
            7'b01?????: lzc = 3'd1;
            7'b001????: lzc = 3'd2;
            7'b0001???: lzc = 3'd3;
            7'b00001??: lzc = 3'd4;
            7'b000001?: lzc = 3'd5;
            7'b0000001: lzc = 3'd6;
            7'b0000000: lzc = 3'd7;
            default:    lzc = 3'd1;
        endcase
    end

    // Regime value k
    // regime_sign=1: k = lzc - 1 (positive regime: run of 1s)
    // regime_sign=0: k = -lzc (negative regime: run of 0s)
    wire signed [3:0] regime_k = regime_sign ?
        $signed({1'b0, lzc}) - 4'sd1 :
        -$signed({1'b0, lzc});

    // Step 3: Extract fraction bits
    // Regime consumes lzc bits + 1 terminator (unless at word boundary)
    // Total regime+terminator length = lzc + (lzc < 7 ? 1 : 0)
    wire [2:0] regime_total = (lzc < 3'd7) ? lzc + 3'd1 : lzc;
    // Fraction starts after regime+terminator, from bit position (6 - regime_total)
    // Fraction bits available = 7 - regime_total
    wire [6:0] shifted = abs_val << regime_total;
    wire [5:0] fraction = shifted[6:1];  // shifted[0] dropped (beyond precision)

    // Step 4: Build FP32
    // For posit8(es=0): value = (-1)^S * 2^k * (1.fraction)
    // FP32 exponent = k + 127
    wire [8:0] fp32_exp_wide = {1'b0, 8'd127} + {{5{regime_k[3]}}, regime_k};
    wire [7:0] fp32_exp = fp32_exp_wide[7:0];

    always @(*) begin
        if (is_zero)
            fp32_out = 32'h00000000;
        else if (is_nar)
            fp32_out = 32'h7FC00000;  // NaN (quiet)
        else
            fp32_out = {sign, fp32_exp, fraction[5:0], 17'b0};
    end

    wire _unused = &{shifted[0], fp32_exp_wide[8]};

endmodule
