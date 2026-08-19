// tekum8 decode: code -> (sign, exponent, significand), in binary fabric.
//
// The first tekum hardware in this repository, built from the oracle that was
// itself built from the paper (conformance/tekum_true_ref.py, arXiv:2512.10964
// Definitions 7 and 8). The scope is the DECODER, deliberately: it is where
// everything tekum-specific lives -- the anchor subtraction, the balanced-trit
// extraction, the regime-dependent variable fields, the base-3 significand
// scaling -- and it is small enough to verify EXHAUSTIVELY, all 6559 finite
// codes against the oracle. An adder would bolt ordinary float machinery onto
// these outputs; shipping one without exhaustive verification is how wrong
// numbers happened before.
//
// What base 3 costs in a binary fabric, structurally:
//   * eight compare-subtract stages to extract balanced trits (a binary format
//     slices wires instead),
//   * variable-width field muxes for the tapered exponent and fraction,
//   * a shift-add ladder to scale the fraction by 3^(5-p).
//
// Significand is emitted as (1 + f) * 3^5, an integer in [122, 364]: f is a
// multiple of 3^-p, so scaling by 3^5 clears every denominator.
`default_nettype none
module tekum8_decode (
    input  wire signed [13:0] v,        // code, |v| <= 3280
    output wire               is_zero,
    output wire               is_inf,
    output wire               is_nar,
    output wire               sgn,       // 1 = negative
    output wire signed [9:0]  e,         // exponent, in [-365, 365]
    output wire        [8:0]  sig        // (1+f)*3^5, in [122, 364]
);
    localparam signed [13:0] VMAX = 14'sd3280;
    localparam signed [12:0] ANCH = 13'sd1640;      // (9^4-1)/4

    assign is_zero = (v == 0);
    assign is_inf  = (v ==  VMAX);
    assign is_nar  = (v == -VMAX);
    assign sgn     = v[13];

    wire [12:0] av = sgn ? (~v[12:0] + 13'd1) : v[12:0];
    wire signed [12:0] a0 = $signed({1'b0, av[11:0]}) - ANCH;   // in [-1639, 1639]

    // Balanced-trit extraction, most significant first. Digit k is +1 when the
    // remainder exceeds (3^k - 1)/2, -1 below the negative of it, else 0 -- the
    // canonical balanced-ternary window.
    function signed [1:0] trit_of;
        input signed [12:0] rem;
        input signed [12:0] half;   // (3^k - 1) / 2
        begin
            trit_of = (rem > half) ? 2'sd1 : (rem < -half) ? -2'sd1 : 2'sd0;
        end
    endfunction

    wire signed [12:0] P7 = 13'sd2187, H7 = 13'sd1093;
    wire signed [12:0] P6 = 13'sd729,  H6 = 13'sd364;
    wire signed [12:0] P5 = 13'sd243,  H5 = 13'sd121;
    wire signed [12:0] P4 = 13'sd81,   H4 = 13'sd40;
    wire signed [12:0] P3 = 13'sd27,   H3 = 13'sd13;
    wire signed [12:0] P2 = 13'sd9,    H2 = 13'sd4;
    wire signed [12:0] P1 = 13'sd3,    H1 = 13'sd1;
    wire signed [12:0] P0 = 13'sd1,    H0 = 13'sd0;

    wire signed [1:0] t7 = trit_of(a0, H7); wire signed [12:0] a1 = a0 - t7 * P7;
    wire signed [1:0] t6 = trit_of(a1, H6); wire signed [12:0] a2 = a1 - t6 * P6;
    wire signed [1:0] t5 = trit_of(a2, H5); wire signed [12:0] a3 = a2 - t5 * P5;
    wire signed [1:0] t4 = trit_of(a3, H4); wire signed [12:0] a4 = a3 - t4 * P4;
    wire signed [1:0] t3 = trit_of(a4, H3); wire signed [12:0] a5 = a4 - t3 * P3;
    wire signed [1:0] t2 = trit_of(a5, H2); wire signed [12:0] a6 = a5 - t2 * P2;
    wire signed [1:0] t1 = trit_of(a6, H1); wire signed [12:0] a7 = a6 - t1 * P1;
    wire signed [1:0] t0 = trit_of(a7, H0);

    // Regime from the top three trits; c = max(0, |r| - 2); p = 5 - c.
    // A concatenation is UNSIGNED in Verilog, and one unsigned operand makes
    // the whole expression unsigned: t6 = -1 zero-extended to 3, and 9+9+1
    // read back as -13. Caught by the exhaustive bench on code -3278; every
    // sign-extension concat below is wrapped in $signed for the same reason.
    wire signed [4:0] r = t7 * 5'sd9 + t6 * 5'sd3 + $signed({{3{t5[1]}}, t5});
    wire [4:0] rabs = r[4] ? (~r + 5'd1) : r[4:0];
    wire [2:0] c = (rabs > 5'd2) ? (rabs[2:0] - 3'd2) : 3'd0;

    // Characteristic prefix values E_c and fraction suffix values F_p, muxed by
    // the regime-dependent widths -- the tapered cost, paid in muxes.
    wire signed [8:0] E1 = $signed({{7{t4[1]}}, t4});
    wire signed [8:0] E2 = E1 * 9'sd3 + $signed({{7{t3[1]}}, t3});
    wire signed [8:0] E3 = E2 * 9'sd3 + $signed({{7{t2[1]}}, t2});
    wire signed [8:0] E4 = E3 * 9'sd3 + $signed({{7{t1[1]}}, t1});
    wire signed [8:0] E5 = E4 * 9'sd3 + $signed({{7{t0[1]}}, t0});
    reg signed [8:0] E;
    always @* case (c)
        3'd0: E = 9'sd0;
        3'd1: E = E1;
        3'd2: E = E2;
        3'd3: E = E3;
        3'd4: E = E4;
        default: E = E5;
    endcase

    wire signed [8:0] F1 = $signed({{7{t0[1]}}, t0});
    wire signed [8:0] F2 = $signed({{7{t1[1]}}, t1}) * 9'sd3 + F1;
    wire signed [8:0] F3 = $signed({{7{t2[1]}}, t2}) * 9'sd9 + F2;
    wire signed [8:0] F4 = $signed({{7{t3[1]}}, t3}) * 9'sd27 + F3;
    wire signed [8:0] F5 = $signed({{7{t4[1]}}, t4}) * 9'sd81 + F4;
    wire [2:0] p = 3'd5 - c;
    reg signed [8:0] F;
    always @* case (p)
        3'd0: F = 9'sd0;
        3'd1: F = F1;
        3'd2: F = F2;
        3'd3: F = F3;
        3'd4: F = F4;
        default: F = F5;
    endcase

    // Bias, signed by the regime.
    reg [7:0] bmag;
    always @* case (rabs)
        5'd0: bmag = 8'd0;   5'd1: bmag = 8'd1;   5'd2: bmag = 8'd2;
        5'd3: bmag = 8'd4;   5'd4: bmag = 8'd10;  5'd5: bmag = 8'd28;
        5'd6: bmag = 8'd82;  default: bmag = 8'd244;
    endcase
    wire signed [9:0] b = r[4] ? -$signed({2'b00, bmag}) : $signed({2'b00, bmag});
    assign e = $signed({E[8], E}) + b;

    // sig = 3^5 + F * 3^(5-p): the base-3 scaling ladder, muxed by p.
    reg signed [9:0] fs;
    always @* case (p)
        3'd0: fs = 10'sd0;
        3'd1: fs = F * 10'sd81;
        3'd2: fs = F * 10'sd27;
        3'd3: fs = F * 10'sd9;
        3'd4: fs = F * 10'sd3;
        default: fs = $signed({F[8], F});
    endcase
    assign sig = 9'd243 + fs[8:0];
endmodule
`default_nettype wire
