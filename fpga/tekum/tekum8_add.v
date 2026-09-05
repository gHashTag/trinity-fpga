// THE VERILOG LESSON, PAID THREE TIMES IN ONE DAY: concatenations and
// bit-selects are UNSIGNED, and one unsigned operand makes the whole
// expression unsigned. In this file it hid inside function ARGUMENTS:
// pow3(13 + {{2{mm[3]}}, mm}) computed pow3(72) instead of pow3(8) for
// mm = -5, and 796 of 3600 additions rounded on a garbage grid step. The
// python model of the same algorithm was correct on every failing pair,
// which is what localised the fault to translation rather than design.
//
// tekum8 add: two codes in, the nearest code to their exact sum out.
//
// Exact until the single rounding at the end:
//   * alignment keeps the smaller operand at full precision (units of 3^-13 of
//     the significand scale), so RES is the exact sum for any d <= 13;
//   * for d >= 14 the smaller operand is provably below half of the coarsest
//     grid step, so the result IS the larger operand's code, passed through;
//   * cancellation deeper than one window is impossible for d >= 2 (the low
//     operand is less than a ninth of the high one), so the normalisation
//     window m spans only [-6, +1];
//   * no rounding tie can occur: every grid step in RES units is an odd power
//     of three and 2*num is even, so round-half-up is exact round-to-nearest.
`default_nettype none
module tekum8_add (
    input  wire signed [13:0] va,
    input  wire signed [13:0] vb,
    output reg  signed [13:0] vsum
);
    wire za, ia, na, sa; wire signed [9:0] ea; wire [8:0] ga;
    wire zb, ib, nb, sb; wire signed [9:0] eb; wire [8:0] gb;
    tekum8_decode da(.v(va), .is_zero(za), .is_inf(ia), .is_nar(na),
                     .sgn(sa), .e(ea), .sig(ga));
    tekum8_decode db(.v(vb), .is_zero(zb), .is_inf(ib), .is_nar(nb),
                     .sgn(sb), .e(eb), .sig(gb));

    wire a_hi = (ea > eb) || ((ea == eb) && (ga >= gb));
    wire              hs = a_hi ? sa : sb;
    wire signed [9:0] he = a_hi ? ea : eb;
    wire [8:0]        hg = a_hi ? ga : gb;
    wire signed [9:0] le = a_hi ? eb : ea;
    wire [8:0]        lg = a_hi ? gb : ga;
    wire sub = (a_hi ? sb : sa) ^ hs;

    wire [9:0] d10 = he - le;
    wire       far = (d10 > 10'd13);
    wire [3:0] d   = far ? 4'd14 : d10[3:0];

    reg [30:0] lo_al;
    always @* case (d)
        4'd0:  lo_al = lg * 31'd1594323;  4'd1:  lo_al = lg * 31'd531441;
        4'd2:  lo_al = lg * 31'd177147;   4'd3:  lo_al = lg * 31'd59049;
        4'd4:  lo_al = lg * 31'd19683;    4'd5:  lo_al = lg * 31'd6561;
        4'd6:  lo_al = lg * 31'd2187;     4'd7:  lo_al = lg * 31'd729;
        4'd8:  lo_al = lg * 31'd243;      4'd9:  lo_al = lg * 31'd81;
        4'd10: lo_al = lg * 31'd27;       4'd11: lo_al = lg * 31'd9;
        4'd12: lo_al = lg * 31'd3;        4'd13: lo_al = lg * 31'd1;
        default: lo_al = 31'd0;
    endcase
    wire [30:0] hi_sc = hg * 31'd1594323;
    wire [31:0] res = sub ? ({1'b0, hi_sc} - {1'b0, lo_al})
                          : ({1'b0, hi_sc} + {1'b0, lo_al});

    // Normalisation window m in [-6, +1]: 2*res in [3^18 * 3^m, 3^19 * 3^m).
    wire [32:0] r2 = {res, 1'b0};
    reg signed [3:0] m;
    always @* begin
        if      (r2 >= 33'd1162261467) m =  4'sd1;   // 3^19
        else if (r2 >= 33'd387420489)  m =  4'sd0;   // 3^18
        else if (r2 >= 33'd129140163)  m = -4'sd1;
        else if (r2 >= 33'd43046721)   m = -4'sd2;
        else if (r2 >= 33'd14348907)   m = -4'sd3;
        else if (r2 >= 33'd4782969)    m = -4'sd4;
        else if (r2 >= 33'd1594323)    m = -4'sd5;
        else                           m = -4'sd6;
    end
    wire signed [9:0] e1 = he + $signed({{6{m[3]}}, m});

    // Regime window of a candidate exponent -> fraction width p.
    function [2:0] p_of;
        input signed [9:0] ex;
        reg [9:0] ea_;
        begin
            ea_ = ex[9] ? (~ex + 10'd1) : ex[9:0];
            if      (ea_ <= 10'd2)   p_of = 3'd5;
            else if (ea_ <= 10'd5)   p_of = 3'd4;
            else if (ea_ <= 10'd14)  p_of = 3'd3;
            else if (ea_ <= 10'd41)  p_of = 3'd2;
            else if (ea_ <= 10'd122) p_of = 3'd1;
            else                     p_of = 3'd0;
        end
    endfunction

    // One rounding attempt at exponent (he + mm): F = round(num / s),
    // round-half-up via floor((2*num + s) / (2*s)) with a floor correction for
    // negative numerators (Verilog constant division truncates toward zero).
    function signed [9:0] round_F;
        input [31:0] resv;
        input signed [3:0] mm;
        input [2:0] pp;
        reg signed [34:0] anchor, num, num2, den, q;
        reg [5:0] sexp;
        reg signed [34:0] s;
        begin
            // anchor = 243 * 3^(13+mm); s = 3^(18-pp+mm)
            anchor = 35'sd243 * pow3(7'sd13 + $signed({{3{mm[3]}}, mm}));
            s = pow3(7'sd18 - $signed({4'b0000, pp}) + $signed({{3{mm[3]}}, mm}));
            num  = $signed({3'b000, resv}) - anchor;
            num2 = (num <<< 1) + s;
            den  = (s <<< 1);
            q = num2 / den;
            if ((num2 % den != 0) && (num2 < 0)) q = q - 1;
            round_F = q[9:0];
        end
    endfunction

    function signed [34:0] pow3;
        input signed [6:0] k;      // 0..15 needed
        begin
            case (k)
                7'sd0: pow3 = 35'sd1;        7'sd1: pow3 = 35'sd3;
                7'sd2: pow3 = 35'sd9;        7'sd3: pow3 = 35'sd27;
                7'sd4: pow3 = 35'sd81;       7'sd5: pow3 = 35'sd243;
                7'sd6: pow3 = 35'sd729;      7'sd7: pow3 = 35'sd2187;
                7'sd8: pow3 = 35'sd6561;     7'sd9: pow3 = 35'sd19683;
                7'sd10: pow3 = 35'sd59049;   7'sd11: pow3 = 35'sd177147;
                7'sd12: pow3 = 35'sd531441;  7'sd13: pow3 = 35'sd1594323;
                7'sd14: pow3 = 35'sd4782969; 7'sd15: pow3 = 35'sd14348907;
                // The grid-step exponent 18 - p + m reaches 19 (p = 0, m = 1).
                // The first version of this table stopped at 15 and the DEFAULT
                // silently served 3^15 for every larger request, so rounding
                // ran on a garbage step for wide-regime results: 154 of 3600
                // additions wrong, all in the p <= 2 windows.
                7'sd16: pow3 = 35'sd43046721;
                7'sd17: pow3 = 35'sd129140163;
                7'sd18: pow3 = 35'sd387420489;
                default: pow3 = 35'sd1162261467;
            endcase
        end
    endfunction

    function signed [9:0] fmax_of;
        input [2:0] pp;
        begin
            case (pp)
                3'd0: fmax_of = 10'sd0;    3'd1: fmax_of = 10'sd1;
                3'd2: fmax_of = 10'sd4;    3'd3: fmax_of = 10'sd13;
                3'd4: fmax_of = 10'sd40;   default: fmax_of = 10'sd121;
            endcase
        end
    endfunction

    // Rounding, with the window boundary done exactly.
    //
    // Inside a window no tie can occur (odd step, even 2*num). AT a window
    // boundary the proof breaks: adjacent windows differ 3x in grid step, so
    // the gap between the last code below and the first code above is even in
    // shared units and its midpoint IS representable -- measured: 3213 + -3215
    // lands exactly on one. So when the in-window rounding hits the window's
    // edge code, the true nearest may be across the boundary: build both
    // candidates, compare exact distances in res units, and break a tie toward
    // the LARGER value, which is what the oracle's nearest-code search does.
    wire [2:0] p1 = p_of(e1);
    wire signed [9:0] F1 = round_F(res, m, p1);
    wire signed [9:0] fm1 = fmax_of(p1);

    wire signed [9:0] FA = (F1 >= fm1) ? fm1 : (F1 <= -fm1) ? -fm1 : F1;

    // Candidate values in res units: (243 + F*3^(5-p)) * 3^(13 + e - he).
    function signed [36:0] cand_val;
        input signed [9:0] ec;
        input [2:0] pc;
        input signed [9:0] Fc;
        input signed [9:0] he_;
        reg signed [36:0] sigc;
        begin
            sigc = 37'sd243 + Fc * pow3(7'sd5 - $signed({4'b0000, pc}));
            cand_val = sigc * pow3(7'sd13 + ec - he_);
        end
    endfunction

    wire signed [36:0] vA = cand_val(e1, p1, FA, he);
    wire signed [36:0] resw = $signed({5'b00000, res});

    // The cross-boundary competitor sits on the side of the residual. This is
    // what F's sign alone cannot say: at p=0 the window's single code is both
    // edge codes at once (fmax = 0), so F1 >= fmax and F1 <= -fmax both hold.
    wire edge_up = (F1 >=  fm1) && (resw > vA);
    wire edge_dn = (F1 <= -fm1) && (resw < vA);
    wire signed [9:0] eB = edge_up ? (e1 + 10'sd1) : (e1 - 10'sd1);
    wire b_valid = (edge_up || edge_dn) && (eB >= -10'sd365) && (eB <= 10'sd365);
    wire [2:0] pB = p_of(eB);
    wire signed [9:0] FB = edge_up ? -fmax_of(pB) : fmax_of(pB);

    wire signed [36:0] vB = b_valid ? cand_val(eB, pB, FB, he) : vA;
    wire signed [36:0] dA = (resw > vA) ? (resw - vA) : (vA - resw);
    wire signed [36:0] dB = (resw > vB) ? (resw - vB) : (vB - resw);

    // B is the larger-magnitude candidate exactly when we crossed upward.
    wire tie_pick_B = (dB == dA) && b_valid && (edge_up ^ hs);
    wire pick_B = b_valid && ((dB < dA) || tie_pick_B);

    wire signed [9:0] e2 = pick_B ? eB : e1;
    wire [2:0]        p2 = pick_B ? pB : p1;
    wire signed [9:0] F2 = pick_B ? FB : FA;

    // Re-encode through the shared field encoder.
    wire signed [13:0] venc;
    tekum8_encode_fields ef(.sgn(hs), .e(e2), .p(p2), .F(F2), .v(venc));

    localparam signed [13:0] VMAXF = 14'sd3279;   // largest finite code
    always @* begin
        if (na || nb || (ia && ib))            vsum = -14'sd3280;  // NaR
        else if (ia || ib)                     vsum = 14'sd3280;   // inf
        else if (za && zb)                     vsum = 14'sd0;
        else if (za)                           vsum = vb;
        else if (zb)                           vsum = va;
        else if (res == 0)                     vsum = 14'sd0;
        else if (far)                          vsum = a_hi ? va : vb;
        else if (e2 > 10'sd365)                vsum = hs ? -VMAXF : VMAXF;
        else                                   vsum = venc;
    end
endmodule

// The encoder's field-composition tail, factored so the adder can feed a
// fraction directly: a = r*3^5 + E*3^p + F, |v| = a + anchor.
module tekum8_encode_fields (
    input  wire              sgn,
    input  wire signed [9:0] e,
    input  wire [2:0]        p,
    input  wire signed [9:0] F,
    output wire signed [13:0] v
);
    wire [9:0] eabs = e[9] ? (~e + 10'd1) : e[9:0];
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
    wire signed [8:0] En = $signed(E[8:0]);
    reg signed [12:0] Ew;
    always @* case (p)
        3'd0: Ew = En * 13'sd1;   3'd1: Ew = En * 13'sd3;
        3'd2: Ew = En * 13'sd9;   3'd3: Ew = En * 13'sd27;
        3'd4: Ew = En * 13'sd81;  default: Ew = 13'sd0;
    endcase
    wire signed [12:0] a = r * 13'sd243 + Ew + $signed({{3{F[9]}}, F});
    wire [12:0] mag = a[12:0] + 13'd1640;
    assign v = sgn ? -$signed({1'b0, mag}) : $signed({1'b0, mag});
endmodule
`default_nettype wire
