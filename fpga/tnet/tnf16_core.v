`default_nettype none
//=============================================================================
// tnf16_core -- TNF16 add and mul, bit-exact to conformance/tnf_ref.py
// TNFFormat(4, 11), ladder v2-spec: tef_add / tef_mul.
//
// Word: sign [SS], offset [SS-1:M] (7 bits), mantissa [M-1:0]. Offset 0 is zero,
// offset OFFSET_MAX is the special row (any operand there gives CANON_NAN),
// offsets above it are ordinary finite values, as the reference decodes them.
//
// Stage for stage the same algorithm as conformance/tnf16_rtl_model.py, which
// equals the reference on every board request (tnf16_board_vectors.py
// --model-check). Add keeps GUARD_BITS guard bits and ORs every bit shifted out
// into bit 0; the spec says why, and what 2 guard bits cost.
//
// Constants come from fpga/tnet/tnf16_board_params.v, generated from
// specs/trinet/tnf16_on_board_ax7203.t27; list that file first.
//
// Six register stages from in_valid to out_valid; one request per clock.
//   1 decode, order add operands by magnitude, mul partial products
//   2 align the smaller add operand (sticky jam), sum the partial products
//   3 add or subtract; normalise the product
//   4 leading-one position of the sum
//   5 normalise the sum; pick add or mul fields
//   6 round to nearest even, carry, overflow, underflow
//=============================================================================
module tnf16_core (
    input  wire        clk,
    input  wire        rst,
    input  wire        in_valid,
    input  wire [7:0]  in_op,
    input  wire [`TNF16_WORD_BITS-1:0] in_a,
    input  wire [`TNF16_WORD_BITS-1:0] in_b,
    output reg         out_valid,
    output reg         out_badop,
    output reg  [`TNF16_WORD_BITS-1:0] out_y
);
    localparam integer M    = `TNF16_MANT_BITS;       // 11
    localparam integer OB   = `TNF16_OFF_BITS;        // 7
    localparam integer W    = `TNF16_WORD_BITS;       // 19
    localparam integer SS   = `TNF16_SIGN_SHIFT;      // 18
    localparam integer OMAX = `TNF16_OFFSET_MAX;      // 80
    localparam integer EOFF = `TNF16_EXP_OFFSET;      // 40
    localparam integer G    = `TNF16_GUARD_BITS;      // 3
    localparam integer AW   = M + 1 + G;              // 15: aligned operand
    localparam integer DW   = AW + 1;                 // 16: sum
    localparam integer PW   = 2 * (M + 1);            // 24: product
    localparam integer LO   = (M + 1) / 2;            // 6: low partial-product slice
    localparam integer KW   = 2 * OB;                 // 14: magnitude key width - 4
    localparam integer FW   = 10;                     // signed result offset
    localparam [OB-1:0] OMAX_B = `TNF16_OFFSET_MAX;

    wire [7:0] OP_ADD = `TNF16_OP_ADD;
    wire [7:0] OP_MUL = `TNF16_OP_MUL;
    wire [W-1:0] NAN  = `TNF16_CANON_NAN;

    //------------------------------------------------------------------ 1
    wire          sa = in_a[SS],        sb = in_b[SS];
    wire [OB-1:0] oa = in_a[SS-1:M],    ob = in_b[SS-1:M];
    wire [M-1:0]  ma = in_a[M-1:0],     mb = in_b[M-1:0];
    wire za = (oa == {OB{1'b0}});
    wire zb = (ob == {OB{1'b0}});
    wire [OB+M-1:0] ka = za ? {(OB+M){1'b0}} : {oa, ma};
    wire [OB+M-1:0] kb = zb ? {(OB+M){1'b0}} : {ob, mb};
    wire a_big = (ka >= kb);
    // Offset 0 is zero whatever its mantissa bits say: its significand is 0.
    wire [M:0]    ga   = za ? {(M+1){1'b0}} : {1'b1, ma};
    wire [M:0]    gb   = zb ? {(M+1){1'b0}} : {1'b1, mb};
    wire          c_sl = a_big ? sa : sb;
    wire          c_ss = a_big ? sb : sa;
    wire [OB-1:0] c_ol = a_big ? oa : ob;
    wire [OB-1:0] c_os = a_big ? ob : oa;
    wire [M:0]    c_gl = a_big ? ga : gb;
    wire [M:0]    c_gs = a_big ? gb : ga;
    wire [M:0]    siga = {1'b1, ma};
    wire [M:0]    sigb = {1'b1, mb};

    reg          s1_v, s1_special, s1_sl, s1_eff_sub, s1_mzero, s1_msign;
    reg [7:0]    s1_op;
    reg [OB-1:0] s1_ol, s1_d;
    reg [M:0]    s1_gl, s1_gs;
    reg [OB:0]   s1_osum;
    reg [M+LO:0]     s1_pp_lo;       // siga * sigb[LO-1:0]
    reg [2*M+1-LO:0] s1_pp_hi;       // siga * sigb[M:LO]

    always @(posedge clk) begin
        s1_v       <= in_valid & ~rst;
        s1_op      <= in_op;
        s1_special <= (oa == OMAX_B) | (ob == OMAX_B);
        s1_sl      <= c_sl;
        s1_eff_sub <= c_sl ^ c_ss;
        s1_ol      <= c_ol;
        s1_d       <= c_ol - c_os;
        s1_gl      <= c_gl;
        s1_gs      <= c_gs;
        s1_mzero   <= za | zb;
        s1_msign   <= sa ^ sb;
        s1_osum    <= {1'b0, oa} + {1'b0, ob};
        s1_pp_lo   <= siga * sigb[LO-1:0];
        s1_pp_hi   <= siga * sigb[M:LO];
    end

    //------------------------------------------------------------------ 2
    wire [AW-1:0] full_s   = {s1_gs, {G{1'b0}}};
    wire          d_out    = (s1_d >= AW);
    wire [AW-1:0] lostmask = d_out ? {AW{1'b1}} : ~({AW{1'b1}} << s1_d);
    wire [AW-1:0] shifted  = d_out ? {AW{1'b0}} : (full_s >> s1_d);
    wire          lost     = |(full_s & lostmask);

    reg          s2_v, s2_special, s2_sl, s2_eff_sub, s2_mzero, s2_msign;
    reg [7:0]    s2_op;
    reg [OB-1:0] s2_ol;
    reg [AW-1:0] s2_al, s2_as;
    reg [OB:0]   s2_osum;
    reg [PW-1:0] s2_prod;

    always @(posedge clk) begin
        s2_v       <= s1_v & ~rst;
        s2_op      <= s1_op;
        s2_special <= s1_special;
        s2_sl      <= s1_sl;
        s2_eff_sub <= s1_eff_sub;
        s2_ol      <= s1_ol;
        s2_al      <= {s1_gl, {G{1'b0}}};
        s2_as      <= shifted | {{(AW-1){1'b0}}, lost};
        s2_mzero   <= s1_mzero;
        s2_msign   <= s1_msign;
        s2_osum    <= s1_osum;
        s2_prod    <= {{(PW-M-1-LO){1'b0}}, s1_pp_lo} + ({{(LO-1){1'b0}}, s1_pp_hi} << LO);
    end

    //------------------------------------------------------------------ 3
    wire [DW-1:0] sum = s2_eff_sub ? ({1'b0, s2_al} - {1'b0, s2_as})
                                   : ({1'b0, s2_al} + {1'b0, s2_as});
    wire          ptop  = s2_prod[PW-1];
    wire [PW-1:0] pnorm = ptop ? s2_prod : {s2_prod[PW-2:0], 1'b0};
    // |x| = prod * 2^(oa + ob - 2*(EOFF + M)): offset = ptop + oa + ob - EOFF.
    // Underflow (offset < 1) needs k = 2*M + EOFF - oa - ob >= 2*M; then
    // |x| <= 2^-EOFF iff prod <= 2^k.
    wire [FW-1:0] k_m = (2 * M + EOFF) - {{(FW-OB-1){1'b0}}, s2_osum};
    wire          ufz_m = ($signed(k_m) >= PW)
                        | (($signed(k_m) == PW - 1) && (s2_prod <= ({{(PW-1){1'b0}}, 1'b1} << (PW - 1))))
                        | (($signed(k_m) == PW - 2) && (s2_prod <= ({{(PW-1){1'b0}}, 1'b1} << (PW - 2))));

    reg          s3_v, s3_special, s3_sl, s3_mzero, s3_msign;
    reg [7:0]    s3_op;
    reg [OB-1:0] s3_ol;
    reg [DW-1:0] s3_sum;
    reg [M-1:0]  s3_mmant;
    reg          s3_mrbit, s3_msticky, s3_mufz;
    reg [FW-1:0] s3_moff;

    always @(posedge clk) begin
        s3_v       <= s2_v & ~rst;
        s3_op      <= s2_op;
        s3_special <= s2_special;
        s3_sl      <= s2_sl;
        s3_ol      <= s2_ol;
        s3_sum     <= sum;
        s3_mzero   <= s2_mzero;
        s3_msign   <= s2_msign;
        s3_mmant   <= pnorm[PW-2:PW-1-M];
        s3_mrbit   <= pnorm[PW-2-M];
        s3_msticky <= |pnorm[PW-3-M:0];
        s3_moff    <= {{(FW-1){1'b0}}, ptop} + {{(FW-OB-1){1'b0}}, s2_osum} - EOFF;
        s3_mufz    <= ufz_m;
    end

    //------------------------------------------------------------------ 4
    reg [3:0] lead;
    integer li;
    always @* begin
        lead = 4'd0;
        for (li = 0; li < DW; li = li + 1)
            if (s3_sum[li]) lead = li[3:0];
    end

    reg          s4_v, s4_special, s4_sl, s4_mzero, s4_msign;
    reg [7:0]    s4_op;
    reg [OB-1:0] s4_ol;
    reg [DW-1:0] s4_sum;
    reg [3:0]    s4_p;
    reg [M-1:0]  s4_mmant;
    reg          s4_mrbit, s4_msticky, s4_mufz;
    reg [FW-1:0] s4_moff;

    always @(posedge clk) begin
        s4_v       <= s3_v & ~rst;
        s4_op      <= s3_op;
        s4_special <= s3_special;
        s4_sl      <= s3_sl;
        s4_ol      <= s3_ol;
        s4_sum     <= s3_sum;
        s4_p       <= lead;
        s4_mzero   <= s3_mzero;
        s4_msign   <= s3_msign;
        s4_mmant   <= s3_mmant;
        s4_mrbit   <= s3_mrbit;
        s4_msticky <= s3_msticky;
        s4_moff    <= s3_moff;
        s4_mufz    <= s3_mufz;
    end

    //------------------------------------------------------------------ 5
    wire [DW-1:0] anorm   = s4_sum << ((DW - 1) - s4_p);
    wire          azero   = (s4_sum == {DW{1'b0}});
    wire [FW-1:0] aoff    = {{(FW-4){1'b0}}, s4_p} + {{(FW-OB){1'b0}}, s4_ol} - (AW - 1);
    // |x| = sum * 2^(ol - EOFF - M - G); it is <= 2^-EOFF iff sum <= 2^(AW-1-ol).
    wire          aufz    = (s4_ol <= AW - 1)
                          && (s4_sum <= ({{(DW-1){1'b0}}, 1'b1} << ((AW - 1) - s4_ol)));
    wire          is_add  = (s4_op == OP_ADD);
    wire          is_mul  = (s4_op == OP_MUL);

    reg          s5_v, s5_badop, s5_special, s5_zero, s5_sign;
    reg [FW-1:0] s5_off;
    reg [M-1:0]  s5_mant;
    reg          s5_rbit, s5_sticky, s5_ufz;

    always @(posedge clk) begin
        s5_v       <= s4_v & ~rst;
        s5_badop   <= ~(is_add | is_mul);
        s5_special <= s4_special;
        s5_zero    <= is_add ? azero : s4_mzero;
        s5_sign    <= is_add ? s4_sl : s4_msign;
        s5_off     <= is_add ? aoff : s4_moff;
        s5_mant    <= is_add ? anorm[DW-2:DW-1-M] : s4_mmant;
        s5_rbit    <= is_add ? anorm[DW-2-M] : s4_mrbit;
        s5_sticky  <= is_add ? (|anorm[DW-3-M:0]) : s4_msticky;
        s5_ufz     <= is_add ? aufz : s4_mufz;
    end

    //------------------------------------------------------------------ 6
    wire          up    = s5_rbit & (s5_sticky | s5_mant[0]);
    wire [M:0]    mr    = {1'b0, s5_mant} + {{M{1'b0}}, up};
    wire [FW-1:0] off2  = s5_off + {{(FW-1){1'b0}}, mr[M]};
    wire [W-1:0]  inf   = {s5_sign, OMAX_B, {M{1'b0}}};
    reg  [W-1:0]  y;
    always @* begin
        if (s5_badop)                       y = {W{1'b0}};
        else if (s5_special)                y = NAN;
        else if (s5_zero)                   y = {W{1'b0}};
        else if ($signed(s5_off) >= OMAX)   y = inf;
        else if ($signed(s5_off) < 1)       y = {s5_sign, {(OB-1){1'b0}}, ~s5_ufz, {M{1'b0}}};
        else if ($signed(off2) >= OMAX)     y = inf;
        else                                y = {s5_sign, off2[OB-1:0], mr[M-1:0]};
    end

    always @(posedge clk) begin
        out_valid <= s5_v & ~rst;
        out_badop <= s5_badop;
        out_y     <= y;
    end
endmodule
`default_nettype wire
