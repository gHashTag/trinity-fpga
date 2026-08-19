// tekum8 encode: (sign, exponent, significand) -> code.
//
// The inverse of tekum8_decode, and the other half of the codec. The regime is
// a priority comparator over the exponent windows, which the anchor makes
// contiguous and non-overlapping:
//
//   |r|: 0    1    2    3      4       5        6         7
//   |e|: 0    1    2    3..5   6..14   15..41   42..122   123..365
//
// The significand arrives as (1+f)*3^5 and must sit on the p-trit grid of its
// regime -- true for anything a decode produced, which is what the exhaustive
// round-trip verifies. Rounding OFF-grid values onto it is the adder's job,
// deliberately not this module's.
`default_nettype none
module tekum8_encode (
    input  wire              sgn,
    input  wire signed [9:0] e,          // in [-365, 365]
    input  wire        [8:0] sig,        // (1+f)*3^5, in [122, 364]
    output wire signed [13:0] v
);
    wire [9:0] eabs = e[9] ? (~e + 10'd1) : e[9:0];

    // Regime magnitude from the window, then signed by e.
    reg [2:0] rmag;
    always @* begin
        if      (eabs == 10'd0)   rmag = 3'd0;
        else if (eabs == 10'd1)   rmag = 3'd1;
        else if (eabs == 10'd2)   rmag = 3'd2;
        else if (eabs <= 10'd5)   rmag = 3'd3;
        else if (eabs <= 10'd14)  rmag = 3'd4;
        else if (eabs <= 10'd41)  rmag = 3'd5;
        else if (eabs <= 10'd122) rmag = 3'd6;
        else                      rmag = 3'd7;
    end
    wire signed [4:0] r = e[9] ? -$signed({2'b00, rmag}) : $signed({2'b00, rmag});

    reg [7:0] bmag;
    always @* case (rmag)
        3'd0: bmag = 8'd0;   3'd1: bmag = 8'd1;   3'd2: bmag = 8'd2;
        3'd3: bmag = 8'd4;   3'd4: bmag = 8'd10;  3'd5: bmag = 8'd28;
        3'd6: bmag = 8'd82;  default: bmag = 8'd244;
    endcase
    wire signed [9:0] b = e[9] ? -$signed({2'b00, bmag}) : $signed({2'b00, bmag});
    wire signed [9:0] E = e - b;

    wire [2:0] c = (rmag > 3'd2) ? (rmag - 3'd2) : 3'd0;
    wire [2:0] p = 3'd5 - c;

    // F = (sig - 243) / 3^(5-p); exact for on-grid significands. Constant
    // division synthesises to multiply-shift and rounds toward zero, which is
    // exact on multiples.
    wire signed [9:0] fs = $signed({1'b0, sig}) - 10'sd243;
    reg signed [9:0] F;
    always @* case (p)
        3'd0: F = 10'sd0;
        3'd1: F = fs / 10'sd81;
        3'd2: F = fs / 10'sd27;
        3'd3: F = fs / 10'sd9;
        3'd4: F = fs / 10'sd3;
        default: F = fs;
    endcase

    // a = r*3^5 + E*3^p + F, then |v| = a + anchor.
    // A bit-select is UNSIGNED in Verilog, exactly as a concatenation is:
    // E[8:0] read -65 back as 447 and every negative characteristic shifted
    // the code by +512. Same bug family the decoder had; same cure.
    wire signed [8:0] En = $signed(E[8:0]);
    reg signed [12:0] Ew;
    always @* case (p)
        3'd0: Ew = En * 13'sd1;
        3'd1: Ew = En * 13'sd3;
        3'd2: Ew = En * 13'sd9;
        3'd3: Ew = En * 13'sd27;
        3'd4: Ew = En * 13'sd81;
        default: Ew = 13'sd0;             // c = 0: no exponent trits
    endcase
    wire signed [12:0] a = r * 13'sd243 + Ew + $signed({{3{F[9]}}, F});
    wire [12:0] mag = a[12:0] + 13'd1640;
    assign v = sgn ? -$signed({1'b0, mag}) : $signed({1'b0, mag});
endmodule
`default_nettype wire
