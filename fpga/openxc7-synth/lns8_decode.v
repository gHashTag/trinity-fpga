// SPDX-License-Identifier: Apache-2.0
// tt-trinity-corona / src/rtl/lns8_decode.v
// 8-bit LNS (base-2) -> 16-bit fixed-point decode (antilog).
// Format: 1 sign + 7-bit Q3.4 fixed-point logarithm.
// Output: 16-bit unsigned magnitude (Q8.8) + sign.

`default_nettype none

module lns8_decode (
    input  wire [7:0]  lns_in,
    output wire        sign_out,
    output reg  [15:0] magnitude,
    output wire        is_zero
);

    assign sign_out = lns_in[7];
    wire [6:0] log_val = lns_in[6:0];  // Q3.4: range 0.0000 to 7.9375

    // Zero is encoded as all-zeros (sign=0, log=0 maps to 2^0=1,
    // so we use a special case: lns_in == 8'h00 => zero)
    assign is_zero = (lns_in == 8'h00);

    // Antilog: magnitude = 2^(log_val / 16) in Q8.8 format.
    // Integer part of log_val[6:4] selects the power-of-2 octave.
    // Fractional part log_val[3:0] indexes a 16-entry LUT for interpolation.
    wire [2:0] int_part  = log_val[6:4];
    wire [3:0] frac_part = log_val[3:0];

    // 16-entry LUT: 2^(frac/16) scaled to Q0.8 (256 = 1.0)
    // Entry i = round(256 * 2^(i/16))
    reg [8:0] frac_lut;
    always @(*) begin
        case (frac_part)
            4'd0:  frac_lut = 9'd256;  // 2^(0/16) = 1.000
            4'd1:  frac_lut = 9'd267;  // 2^(1/16) = 1.044
            4'd2:  frac_lut = 9'd279;  // 2^(2/16) = 1.091
            4'd3:  frac_lut = 9'd292;  // 2^(3/16) = 1.141
            4'd4:  frac_lut = 9'd304;  // 2^(4/16) = 1.189
            4'd5:  frac_lut = 9'd318;  // 2^(5/16) = 1.242
            4'd6:  frac_lut = 9'd332;  // 2^(6/16) = 1.297
            4'd7:  frac_lut = 9'd347;  // 2^(7/16) = 1.354
            4'd8:  frac_lut = 9'd362;  // 2^(8/16) = 1.414 (sqrt2)
            4'd9:  frac_lut = 9'd378;  // 2^(9/16) = 1.476
            4'd10: frac_lut = 9'd395;  // 2^(10/16) = 1.542
            4'd11: frac_lut = 9'd412;  // 2^(11/16) = 1.610
            4'd12: frac_lut = 9'd431;  // 2^(12/16) = 1.682
            4'd13: frac_lut = 9'd450;  // 2^(13/16) = 1.758
            4'd14: frac_lut = 9'd470;  // 2^(14/16) = 1.834
            4'd15: frac_lut = 9'd490;  // 2^(15/16) = 1.915
        endcase
    end

    // Shift the fractional LUT value left by int_part to get final magnitude
    // magnitude = frac_lut << int_part (Q8.8 output)
    always @(*) begin
        if (is_zero)
            magnitude = 16'h0000;
        else
            magnitude = {7'b0, frac_lut} << int_part;
    end

endmodule
