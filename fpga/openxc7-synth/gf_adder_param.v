`timescale 1ns / 1ps
// Parameterized GoldenFloat ADD — works for GF4 (1S+1E+2M) through GF16 (1S+6E+9M).
// Same algorithm as gf16_adder.v: align exp → effective add/sub → normalize → pack.
// Round-half-to-even (RNE) with GRS (G=bit2, R=bit1, S=bit0). AXI-Stream handshake identical to gf16_adder.
module gf_adder_param #(
    parameter EXP_BITS  = 6,
    parameter MANT_BITS = 8,
    parameter TOTAL     = 1 + EXP_BITS + MANT_BITS,  // total operand width
    parameter BIAS      = (1 << (EXP_BITS - 1)) - 1,
    // HAS_INF=1 only for formats where exp=all-ones is reserved as SPECIAL
    //   (Inf/NaN): currently GF16 (gf16.t27:25,35,131). For GF6/8/12/20
    //   exp=all-ones is a FINITE max_value (gf8.t27:115-119) -> HAS_INF=0,
    //   overflow saturates to max-finite.
    parameter HAS_INF   = 0
)(
    input  wire                    clk,
    input  wire                    rst,
    input  wire                    in_valid,
    input  wire [TOTAL-1:0]        in_a,
    input  wire [TOTAL-1:0]        in_b,
    output wire                    in_ready,
    output reg                     out_valid,
    output reg  [TOTAL-1:0]        out_y,
    input  wire                    out_ready
);
    // Field extraction
    wire                        sa = in_a[TOTAL-1];
    wire [EXP_BITS-1:0]         ea = in_a[TOTAL-2:MANT_BITS];
    wire [MANT_BITS-1:0]        ma = in_a[MANT_BITS-1:0];
    wire                        sb = in_b[TOTAL-1];
    wire [EXP_BITS-1:0]         eb = in_b[TOTAL-2:MANT_BITS];
    wire [MANT_BITS-1:0]        mb = in_b[MANT_BITS-1:0];

    // Zero detection: both +0 (all bits 0) and -0 (sign=1, exp=0, mant=0)
    wire                        a_zero = (ea == {EXP_BITS{1'b0}}) && (ma == {MANT_BITS{1'b0}});
    wire                        b_zero = (eb == {EXP_BITS{1'b0}}) && (mb == {MANT_BITS{1'b0}});

    // Denormal detection: exp_field==0 && mant!=0. (Dropped the bias>0 guard: per the
    // gf_ref.py golden, exp=0,mant!=0 is a DENORMAL for ALL widths including GF4 (bias=0) —
    // value = mant/2^MANT * 2^(1-bias). The old guard sent GF4 exp=0,mant!=0 to the normal
    // path with sh=ea-1=-1 => negative shift (undefined). No-op for BIAS>0 formats where the
    // guard was always true, so GF6/8/12/16 netlists are unchanged.)
    wire a_denorm = (ea == {EXP_BITS{1'b0}}) && (ma != {MANT_BITS{1'b0}});
    wire b_denorm = (eb == {EXP_BITS{1'b0}}) && (mb != {MANT_BITS{1'b0}});

    // NaN input detection (HAS_INF only — GF16): exp=all-ones && mant!=0.
    // Without this, NaN inputs fall into the normal path and produce Inf (overflow),
    // violating IEEE 754 (NaN+x = NaN). Caught by HW flash burst (fire #56).
    wire a_nan = (HAS_INF != 0) && (ea == {EXP_BITS{1'b1}}) && (ma != {MANT_BITS{1'b0}});
    wire b_nan = (HAS_INF != 0) && (eb == {EXP_BITS{1'b1}}) && (mb != {MANT_BITS{1'b0}});

    // Inf input detection (HAS_INF only — GF16): exp=all-ones && mant==0.
    // WV-22 fix: without this, an Inf operand fell into the normal path and
    // produced a FINITE saturated value instead of propagating Inf, violating
    // IEEE 754 (Inf+x=Inf, Inf+(-Inf)=NaN). NaN has priority over Inf below.
    // Proven against gf_ref.gf_add golden on all gf16 special inputs (0 mismatch).
    wire a_inf = (HAS_INF != 0) && (ea == {EXP_BITS{1'b1}}) && (ma == {MANT_BITS{1'b0}});
    wire b_inf = (HAS_INF != 0) && (eb == {EXP_BITS{1'b1}}) && (mb == {MANT_BITS{1'b0}});

    // Effective exponent: denormals use 1 (not 0) for alignment — their real_exp = 1-BIAS
    wire [EXP_BITS-1:0] ea_eff = a_denorm ? {{(EXP_BITS-1){1'b0}}, 1'b1} : ea;
    wire [EXP_BITS-1:0] eb_eff = b_denorm ? {{(EXP_BITS-1){1'b0}}, 1'b1} : eb;

    // Mantissa: denormals have NO implicit 1 ({0, ma} instead of {1, ma})
    wire [MANT_BITS:0]   ma_f = a_denorm ? {1'b0, ma} : {1'b1, ma};
    wire [MANT_BITS:0]   mb_f = b_denorm ? {1'b0, mb} : {1'b1, mb};

    wire a_larger = (ea_eff > eb_eff) || ((ea_eff == eb_eff) && (ma_f >= mb_f));
    wire [EXP_BITS:0] ediff = a_larger ?
        ({1'b0, ea_eff} - {1'b0, eb_eff}) : ({1'b0, eb_eff} - {1'b0, ea_eff});

    // Sticky: OR of all bits below G+R from the SMALLER operand (the shifted one)
    reg sticky_bit;
    integer j;
    always @(*) begin
        sticky_bit = 1'b0;
        for (j = 0; j <= MANT_BITS; j = j + 1)
            if (j < $signed(ediff) - 2)
                sticky_bit = sticky_bit | (a_larger ? mb_f[j] : ma_f[j]);
    end

    // Extend to MANT_BITS+4, align, preserve G+R+S
    wire [MANT_BITS+3:0] ma_ext = {ma_f, 3'b000};
    wire [MANT_BITS+3:0] mb_ext = {mb_f, 3'b000};
    wire [MANT_BITS+3:0] ma_al_raw = a_larger ? ma_ext : (ma_ext >> ediff);
    wire [MANT_BITS+3:0] mb_al_raw = a_larger ? (mb_ext >> ediff) : mb_ext;
    // Inject sticky into the SHIFTED operand's bit 0
    wire [MANT_BITS+3:0] ma_al = a_larger ? ma_ext : {ma_al_raw[MANT_BITS+3:1], ma_al_raw[0] | sticky_bit};
    wire [MANT_BITS+3:0] mb_al = a_larger ? {mb_al_raw[MANT_BITS+3:1], mb_al_raw[0] | sticky_bit} : mb_ext;

    wire [EXP_BITS-1:0]  er   = a_larger ? ea_eff : eb_eff;
    wire                 sr   = a_larger ? sa : sb;

    wire                  same_sign = (sa == sb);
    wire [MANT_BITS+4:0]  sum_add = {1'b0, ma_al} + {1'b0, mb_al};
    wire [MANT_BITS+4:0]  sum_sub = a_larger ?
        ({1'b0, ma_al} - {1'b0, mb_al}) :
        ({1'b0, mb_al} - {1'b0, ma_al});
    wire [MANT_BITS+4:0]  mant_raw = same_sign ? sum_add : sum_sub;

    reg  [TOTAL-1:0]      result_packed;
    reg  [MANT_BITS+4:0]  mw;
    reg  [EXP_BITS:0]     ew;
    reg                    sg;
    reg                    underflow;
    reg  [MANT_BITS+1:0]  mant_rounded;
    reg                    old_sticky;
    integer i;

    always @(*) begin
        // ----- zero-passthrough with IEEE zero-sign (gf16.t27:219, RNE) -----
        // (+/-0)+(+/-0): -0 only if BOTH operands are -0, else +0.
        // x + (+/-0) = x for nonzero x (passthrough preserves sign of x).
        if (a_zero && b_zero)
            result_packed = (sa && sb) ? {1'b1, {(TOTAL-1){1'b0}}} : {TOTAL{1'b0}};
        else if (a_zero)
            result_packed = in_b;
        else if (b_zero)
            result_packed = in_a;
        // NaN input → quiet NaN (IEEE 754: NaN propagates through ADD)
        else if (a_nan || b_nan)
            result_packed = {1'b0, {EXP_BITS{1'b1}}, {(MANT_BITS-1){1'b0}}, 1'b1};
        // Inf input (WV-22 fix, NaN already handled above so neither is NaN here):
        //   Inf + (-Inf) = NaN; Inf(+/-) + Inf(same) = Inf(same); Inf + finite = Inf.
        else if (a_inf && b_inf)
            result_packed = (sa != sb)
                ? {1'b0, {EXP_BITS{1'b1}}, {(MANT_BITS-1){1'b0}}, 1'b1}   // Inf+(-Inf)=qNaN
                : {sa,   {EXP_BITS{1'b1}}, {MANT_BITS{1'b0}}};              // +/-Inf
        else if (a_inf)
            result_packed = {sa, {EXP_BITS{1'b1}}, {MANT_BITS{1'b0}}};     // Inf + finite = Inf
        else if (b_inf)
            result_packed = {sb, {EXP_BITS{1'b1}}, {MANT_BITS{1'b0}}};     // finite + Inf = Inf
        else begin
            sg = sr; mw = mant_raw; ew = {1'b0, er}; underflow = 1'b0;
            // Add overflow (preserve sticky: capture old bit[0], OR into new sticky after >>1)
            if (same_sign && mw[MANT_BITS+4]) begin
                old_sticky = mw[0];
                mw = mw >> 1;
                mw[0] = mw[0] | old_sticky;
                ew = ew + 1;
            end
            // Subtraction normalize — stop at ew==0 (do NOT over-shift past the
            // denormal boundary; a subnormal result is packed as denormal below).
            if (!same_sign && mw != 0)
                for (i = 0; i < MANT_BITS+3; i = i + 1)
                    if (!mw[MANT_BITS+3] && ew != 0) begin
                        mw = mw << 1;
                        ew = ew - 1;
                    end
            // Subtraction subnormal result (ew==0): after normalize the denormal
            // mantissa sits one bit high; right-shift by 1 (sticky-preserving) to
            // align with the ew==0 denormal pack path. (er-independent: the offset
            // is GRS_width+1 regardless of exponent/MANT_BITS.)
            if (!same_sign && mw != 0 && ew == 0) begin
                old_sticky = mw[0];
                mw = mw >> 1;
                mw[0] = mw[0] | old_sticky;
            end
            // Round-half-to-even using G(bit2) R(bit1) S(bit0)
            if (mw[2] && (mw[1] || mw[0] || mw[3]))
                mant_rounded = mw[MANT_BITS+3:3] + 1;
            else
                mant_rounded = mw[MANT_BITS+3:3];
            if (mant_rounded[MANT_BITS+1]) begin
                mant_rounded = mant_rounded >> 1;
                ew = ew + 1;
            end
            // Denormal result detection (addition only, same_sign). Applies to ALL
            // widths incl. GF4 (BIAS=0): a same-sign sum whose leading bit sits below
            // the implicit position (mw[MANT_BITS+3]==0) with ew<=1 is a denormal result.
            if (same_sign && !mw[MANT_BITS+3] && ew <= 1'b1)
                ew = {EXP_BITS{1'b0}};  // force denormal packing
            // Pack
            if (mw == 0 || underflow)
                result_packed = {TOTAL{1'b0}};   // cancellation/zero -> +0 (sg=0)
            // OVERFLOW per spec (family-split):
            //  HAS_INF (gf16): exp=all-ones reserved -> overflow on carry-out
            //    OR ew_field==all-ones -> Inf {sg, all-ones-exp, 0...0}
            //  no-Inf (gf6/8/12/20): exp=all-ones is finite max -> overflow only
            //    on carry-out -> saturate {sg, all-ones-exp, all-ones-mant}
            else if (HAS_INF && (ew[EXP_BITS] || (ew[EXP_BITS-1:0] == {EXP_BITS{1'b1}})))
                result_packed = {sg, {EXP_BITS{1'b1}}, {MANT_BITS{1'b0}}};   // +/-Inf
            else if (!HAS_INF && ew[EXP_BITS])
                result_packed = {sg, {EXP_BITS{1'b1}}, {MANT_BITS{1'b1}}};   // max-finite
            else if (ew == {EXP_BITS{1'b0}})
                result_packed = {sg, {EXP_BITS{1'b0}}, mant_rounded[MANT_BITS-1:0]};
            else
                result_packed = {sg, ew[EXP_BITS-1:0], mant_rounded[MANT_BITS-1:0]};
        end
    end

    // AXI-Stream output register
    reg [TOTAL-1:0] out_reg;
    reg             out_valid_reg;

    always @(posedge clk or posedge rst) begin
        if (rst) begin
            out_reg       <= {TOTAL{1'b0}};
            out_valid_reg <= 1'b0;
        end else begin
            if (out_valid_reg && out_ready)
                out_valid_reg <= 1'b0;
            if (in_valid && in_ready) begin
                out_reg       <= result_packed;
                out_valid_reg <= 1'b1;
            end
        end
    end

    assign in_ready  = ~out_valid_reg | out_ready;
    assign out_valid = out_valid_reg;
    assign out_y     = out_reg;
endmodule
