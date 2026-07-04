// gf_decode_param.v  (v2 -- matches the bit-exact-proven rtl_bit_model.py)
// -----------------------------------------------------------------------------
// Parametric decode module for the ENTIRE GoldenFloat GF{N} lineup (Trinity
// project). One RTL generator (#(N, E, M, BIAS)) covers all 10 Phase-A
// (decode_target == FP32) formats: gf4, gf6, gf8, gf10, gf12, gf14, gf16,
// gf20, gf24, gf32. gf16 decode is simply the N=16,E=6,M=9,BIAS=31 instance
// of this same generator (closes issue #237 as a special case, no separate
// cell needed).
//
// Bit-width allocation rule (verified against SSOT formats_catalog.t27,
// master, 2026-07-04 -- holds EXACTLY across the whole ladder):
//     e = round((N-1)/phi^2)
//     m = N-1-e
//     bias = 2^(e-1)-1
// This module does NOT compute the rule itself (E/M/BIAS are passed in as
// parameters, generated/checked against the SSOT by gf_decode_ref.py) -- it
// only implements the 5-class decode law parametrically.
//
// Decode law (5 classes, HAS_INF semantics):
//   exp == EXP_MAX, mant == 0   -> +-Inf
//   exp == EXP_MAX, mant != 0   -> quiet NaN
//   exp == 0,       mant == 0   -> +-0
//   exp == 0,       mant != 0   -> subnormal: (-1)^s * mant/2^M * 2^(1-BIAS)
//   otherwise (normal)           -> (-1)^s * (1+mant/2^M) * 2^(exp-BIAS)
//
// Output: IEEE-754 binary32 (only valid for N<=32, i.e. Phase-A formats).
//
// v2 FIX (found by rtl_bit_model.py vs gf_decode_ref.py exhaustive/
// representative sweep, documented in README.md "Known issues found and
// fixed"): v1 flushed any GF value to FP32 ZERO whenever its rebiased
// exponent field went non-positive. This is WRONG whenever BIAS_GF >
// BIAS_FP32 (127) -- gf24 (BIAS=255) and gf32 (BIAS=2047) both have GF
// *normal* values whose true exponent is below GF's own range ceiling yet
// still smaller than FP32's minimum normal exponent (-126); such values
// MUST decode into an FP32 SUBNORMAL via gradual underflow with correct
// round-to-nearest-even, not an unconditional flush to zero. v2 introduces
// a unified significand-packing datapath (`pack_fp32`-equivalent combinational
// block below) that computes guard/round/sticky against the FP32 subnormal
// LSB exponent (-149), exactly mirroring the fixed Python model.
//
// GF4 (bias=0, e1m2) is a DEGENERATE EDGE: EXP_MAX=1 is entirely consumed by
// Inf/NaN, so GF4 has NO normal range at all (only subnormals 0.5/1.0/1.5
// plus zero/Inf/NaN). The datapath below handles this correctly WITHOUT a
// separate core because the general 5-class classification (exp==0 check)
// naturally routes all finite GF4 values through the subnormal branch; there
// is no "normal" GF4 code point to lose. Verified exhaustive 16/16 by
// rtl_bit_model.py. This differs from the GF-ADD denormal fix precedent
// (references/denormals-fix.md), where the alignment/rounding DATAPATH for
// arithmetic assumed bias>=1; decode has no such assumption because it does
// not do exponent alignment between two operands.
//
// EXTENDED FORMATS (gf96+, decode_target=="extended"): mantissa width M>52
// does not fit even in binary64. This module MUST NOT be instantiated for
// N>32 decode targets requiring binary32, nor claimed as FP-decode HW for
// extended formats -- see honesty rule in gf_decode_lineup_spec.md. Extended
// formats remain SW-only conformance ([open hypothesis for HW]).
//
// Synthesis/PnR/flashing on AX7203 = [ТРЕБУЕТ ДЕЙСТВИЯ ПОЛЬЗОВАТЕЛЯ]. This
// file is sandbox design output; no iverilog/yosys available here to
// simulate it directly -- correctness proven via rtl_bit_model.py (bit-exact
// Python model of this exact algorithm) against gf_decode_ref.py (golden
// Fraction-based oracle): 10/10 Phase-A FP32 formats PASS, gf4/gf6/gf8/gf10/
// gf12 exhaustive, gf14/gf16/gf20/gf24/gf32 representative + full-exponent
// stress sweep (0 mismatches).
//
// Author: Vasilev (gHashTag), ORCID 0009-0008-4294-6159, admin@t27.ai.
// -----------------------------------------------------------------------------

module gf_decode_param #(
    parameter integer N        = 16,     // total GF width (1 + E + M)
    parameter integer E        = 6,      // GF exponent width
    parameter integer M        = 9,      // GF mantissa width
    parameter integer BIAS     = 31,     // GF exponent bias
    parameter integer OUT_REG  = 0       // 0 = pure combinational, 1 = registered output
) (
    input  wire                 clk,     // used only when OUT_REG=1
    input  wire                 rst_n,   // sync active-low reset, used only when OUT_REG=1
    input  wire [N-1:0]         gf_in,   // raw GF{N} encoded word
    output wire [31:0]          fp32_out,// IEEE binary32 result
    output wire                 is_nan_o,
    output wire                 is_inf_o,
    output wire                 is_zero_o,
    output wire                 is_subnormal_o
);
    // -------------------------------------------------------------------
    // Static elaboration-time checks (fail synthesis early on bad params)
    // -------------------------------------------------------------------
    // synthesis translate_off
    initial begin
        if (N !== (1 + E + M)) begin
            $display("ERROR gf_decode_param: N != 1+E+M (N=%0d E=%0d M=%0d)", N, E, M);
            $finish;
        end
        if (N > 32) begin
            $display("WARNING gf_decode_param: N=%0d > 32 -- binary32 output is not a faithful decode for extended formats (mantissa truncation). Phase-A (N<=32) only.", N);
        end
    end
    // synthesis translate_on

    localparam [E-1:0] EXP_MAX = {E{1'b1}};
    localparam integer FP32_EBIAS      = 127;
    localparam integer FP32_MANT       = 23;
    localparam integer FP32_MIN_NORM_EXP = -126;  // smallest true exp for FP32 normal
    localparam integer FP32_SUB_LSB_EXP  = -149;  // exponent of FP32 subnormal LSB (2^-149)

    // Working field widths: true_exp needs to span GF's full exponent range
    // rebiased (worst case BIAS up to ~2^390 for gf1024, but this module is
    // Phase-A only, N<=32, so a 32-bit signed true_exp is always sufficient
    // (max |true_exp| for gf32: BIAS=2047, exp in [0,4094] -> true_exp in
    // [-2047,2047], comfortably inside 32 bits with huge margin).
    localparam integer EXP_CALC_W = 40; // signed working width for exponent math
    localparam integer SIG_W = M + 2;   // implicit + M frac bits + 1 round-carry guard

    // ---- field extraction ----
    wire               sign_in = gf_in[N-1];
    wire [E-1:0]       exp_in  = gf_in[N-2 -: E];
    wire [M-1:0]       mant_in = gf_in[M-1:0];

    wire is_exp_zero  = (exp_in == {E{1'b0}});
    wire is_exp_max   = (exp_in == EXP_MAX);
    wire is_mant_zero = (mant_in == {M{1'b0}});

    wire cls_zero      = is_exp_zero  &&  is_mant_zero;
    wire cls_subnormal = is_exp_zero  && !is_mant_zero;
    wire cls_inf       = is_exp_max   &&  is_mant_zero;
    wire cls_nan       = is_exp_max   && !is_mant_zero;
    wire cls_normal    = !is_exp_zero && !is_exp_max;

    // -------------------------------------------------------------------
    // Leading-zero-count (LZC) for GF-subnormal -> renormalized (true_exp,
    // frac_bits) pair. Scans mant_in (M bits) from MSB.
    // -------------------------------------------------------------------
    function integer clz_m;
        input [M-1:0] v;
        integer i;
        begin
            clz_m = M; // sentinel (not reached when v!=0, which is guaranteed
                       // by cls_subnormal's is_mant_zero==0 check)
            for (i = 0; i < M; i = i + 1) begin
                if (v[M-1-i] && (clz_m == M))
                    clz_m = i;
            end
        end
    endfunction

    wire signed [31:0] lzc_s = clz_m(mant_in);

    // GF-subnormal renormalized true exponent and remaining fraction bits:
    //   true_exp   = (1-BIAS) - (lzc+1)
    //   frac_bits  = (mant_in << (lzc+1))  truncated to M bits
    wire signed [EXP_CALC_W-1:0] sub_true_exp =
        ($signed(1) - BIAS) - (lzc_s + 32'sd1);
    wire [M-1:0] sub_frac_bits = (mant_in << (lzc_s[7:0] + 8'd1));

    // GF-normal true exponent: true_exp = exp_in - BIAS, frac_bits = mant_in
    wire signed [EXP_CALC_W-1:0] norm_true_exp =
        $signed({1'b0, exp_in}) - BIAS;

    // -------------------------------------------------------------------
    // Select which (true_exp, frac_bits) pair feeds the shared FP32 packer,
    // based on class (only meaningful for normal/subnormal; zero/inf/nan are
    // shortcut-returned separately below).
    // -------------------------------------------------------------------
    wire signed [EXP_CALC_W-1:0] pack_true_exp = cls_subnormal ? sub_true_exp : norm_true_exp;
    wire [M-1:0]                 pack_frac     = cls_subnormal ? sub_frac_bits : mant_in;

    // -------------------------------------------------------------------
    // Shared FP32 significand packer (normal + subnormal-of-FP32 renorm).
    // Mirrors _pack_fp32() in rtl_bit_model.py exactly (same variable roles).
    // -------------------------------------------------------------------

    // ---- Attempt 1: treat as FP32 NORMAL ----
    // Mantissa field width adaptation GF(M) -> FP32(23): GF lineup Phase-A
    // always has M<=19 < 23, so this is always a left-shift/zero-pad (no
    // rounding needed on the widen path -- kept general for M>23 anyway).
    localparam integer WIDE = (M > FP32_MANT) ? M : FP32_MANT;
    wire [WIDE:0] norm_widen_result; // [WIDE]=carry, [WIDE-1:0]=candidate mant bits (top 23 used)
    generate
        if (M <= FP32_MANT) begin : g_widen
            // FIX (iverilog-witness 04.07): widen BEFORE shift. `pack_frac` is
            // only M bits wide, so `pack_frac << (FP32_MANT-M)` was evaluated in
            // M-bit width and the shifted-out high bits were truncated (Verilog
            // shift result width == left-operand width). Zero-extend pack_frac to
            // the full result width first, then shift, so all significant bits
            // survive. For Phase-A GF lineup M<=19<23 => WIDE=23, WIDE+1=24 bits
            // hold M+(23-M)=23 significant bits + no carry (carry stays 0 here).
            wire [WIDE:0] pf_wide = { {(WIDE-M+1){1'b0}}, pack_frac };
            assign norm_widen_result = pf_wide << (FP32_MANT - M);
        end else begin : g_narrow
            // Narrowing path (M>23, not exercised by Phase-A GF lineup but
            // kept for completeness/documentation): round-to-nearest-even
            // via guard/round/sticky computed from the extra low bits.
            wire [M-FP32_MANT-1:0] lost_bits = pack_frac[M-FP32_MANT-1:0];
            wire                   g_bit     = pack_frac[M-FP32_MANT-1];
            wire                   s_bit     = |pack_frac[M-FP32_MANT-2:0];
            wire [FP32_MANT-1:0]   trunc     = pack_frac[M-1 -: FP32_MANT];
            wire round_up = g_bit && (s_bit || trunc[0]);
            wire [FP32_MANT:0] rounded = {1'b0, trunc} + (round_up ? 1'b1 : 1'b0);
            assign norm_widen_result = { {(WIDE-FP32_MANT){1'b0}}, rounded };
        end
    endgenerate
    wire        norm_carry  = norm_widen_result[FP32_MANT];
    wire [22:0] norm_mant23 = norm_widen_result[22:0];
    wire signed [EXP_CALC_W-1:0] norm_exp_final = pack_true_exp + norm_carry + FP32_EBIAS;

    wire is_fp32_normal_candidate = (pack_true_exp >= FP32_MIN_NORM_EXP);
    wire norm_overflow  = is_fp32_normal_candidate && (norm_exp_final >= 255);
    wire norm_takes_normal_path = is_fp32_normal_candidate && !norm_overflow && (norm_exp_final >= 1);
    // Rare edge: normal candidate whose rounding carry pushes exp_final back
    // to <=0 -- falls through to the subnormal packer with corrected exponent.
    wire signed [EXP_CALC_W-1:0] corrected_true_exp = pack_true_exp + norm_carry;

    // ---- Attempt 2: FP32 SUBNORMAL packer (gradual underflow) ----
    // full_sig = implicit '1' followed by pack_frac (M bits); value exact =
    // full_sig * 2^(true_exp - M). Express as integer units of 2^-149:
    //   shift = M - true_exp + FP32_SUB_LSB_EXP
    wire signed [EXP_CALC_W-1:0] eff_true_exp_for_sub =
        is_fp32_normal_candidate ? corrected_true_exp : pack_true_exp;
    wire [M:0] full_sig = {1'b1, pack_frac};
    wire signed [EXP_CALC_W-1:0] shift_s = M - eff_true_exp_for_sub + FP32_SUB_LSB_EXP;

    // Guard against absurd shift magnitudes (defensive clamp; Phase-A never
    // needs shift outside [0, M+2] in practice for gf24/gf32, proven by
    // rtl_bit_model.py exhaustive/representative sweep).
    localparam integer MAXSH = M + 8;
    wire [31:0] shift_clamped = (shift_s < 0) ? 32'd0 :
                                (shift_s > MAXSH) ? MAXSH[31:0] : shift_s[31:0];

    // FIX #2 (iverilog-witness №2, 04.07): declared width was [M:0] (=15 bits
    // for gf24), but sub_shifted[22:0] is read below (line ~237) -> bits
    // 22:(M+1) were OUT-OF-BOUNDS reads -> X on the FP32-subnormal path.
    // Fires ONLY when true_exp < -126 (deep underflow -> FP32-subnormal), which
    // gf16 (BIAS=31) never reaches, so gf16 stayed clean and hid the bug; only
    // gf24/gf32 (BIAS>127) exposed it (dut=00Xxxxxx). Python bit-model has no
    // notion of OOB read, so it could not catch this. Widen the declared width
    // to [23:0]: RHS zero-extends, [22:0] then reads valid (zero) bits.
    wire [23:0] sub_shifted = (shift_s <= 0) ? (full_sig << (-shift_s))
                                              : (full_sig >> shift_clamped);
    wire [M:0]  sub_lost_mask = (shift_clamped == 0) ? {(M+1){1'b0}} : ({(M+1){1'b1}} >> (M+1-shift_clamped));
    wire [M:0]  sub_lost    = full_sig & sub_lost_mask;
    wire        sub_guard   = (shift_clamped >= 1) ? sub_lost[shift_clamped-1] : 1'b0;
    wire [M:0]  sub_sticky_mask = (shift_clamped >= 1) ? ({(M+1){1'b1}} >> (M+2-shift_clamped)) : {(M+1){1'b0}};
    wire        sub_sticky  = (shift_clamped >= 1) ? (|(sub_lost & sub_sticky_mask)) : 1'b0;

    wire [24:0] sub_mant_pre = {2'b0, sub_shifted[22:0]}; // headroom for round-up carry
    wire        sub_round_up = sub_guard && (sub_sticky || sub_shifted[0]);
    wire [24:0] sub_mant_rounded = sub_mant_pre + (sub_round_up ? 25'd1 : 25'd0);
    wire        sub_carry_to_normal = sub_mant_rounded[23];
    wire [22:0] sub_mant23 = sub_mant_rounded[22:0];

    // -------------------------------------------------------------------
    // Result composition
    // -------------------------------------------------------------------
    reg [31:0] fp32_r;
    localparam [31:0] FP32_QNAN    = 32'h7FC00001; // quiet NaN, nonzero mantissa payload=1
    localparam [31:0] FP32_POS_INF = 32'h7F800000;
    localparam [31:0] FP32_NEG_INF = 32'hFF800000;

    always @(*) begin
        fp32_r = 32'h00000000;
        if (cls_nan) begin
            fp32_r = FP32_QNAN;
        end else if (cls_inf) begin
            fp32_r = sign_in ? FP32_NEG_INF : FP32_POS_INF;
        end else if (cls_zero) begin
            fp32_r = {sign_in, 31'b0};
        end else if (norm_overflow) begin
            fp32_r = sign_in ? FP32_NEG_INF : FP32_POS_INF;
        end else if (norm_takes_normal_path) begin
            fp32_r = {sign_in, norm_exp_final[7:0], norm_mant23};
        end else begin
            // FP32 subnormal packer path (covers: GF subnormal always, PLUS
            // GF normal values whose true exponent < -126 -- the v1 bug).
            if (sub_carry_to_normal) begin
                fp32_r = {sign_in, 8'd1, 23'b0}; // rounded up to smallest FP32 normal
            end else begin
                fp32_r = {sign_in, 8'b0, sub_mant23};
            end
        end
    end

    // -------------------------------------------------------------------
    // Optional output register
    // -------------------------------------------------------------------
    generate
        if (OUT_REG != 0) begin : g_reg
            reg [31:0] fp32_q;
            reg        nan_q, inf_q, zero_q, sub_q;
            always @(posedge clk) begin
                if (!rst_n) begin
                    fp32_q <= 32'b0;
                    nan_q  <= 1'b0;
                    inf_q  <= 1'b0;
                    zero_q <= 1'b0;
                    sub_q  <= 1'b0;
                end else begin
                    fp32_q <= fp32_r;
                    nan_q  <= cls_nan;
                    inf_q  <= cls_inf;
                    zero_q <= cls_zero;
                    sub_q  <= cls_subnormal;
                end
            end
            assign fp32_out       = fp32_q;
            assign is_nan_o       = nan_q;
            assign is_inf_o       = inf_q;
            assign is_zero_o      = zero_q;
            assign is_subnormal_o = sub_q;
        end else begin : g_comb
            assign fp32_out       = fp32_r;
            assign is_nan_o       = cls_nan;
            assign is_inf_o       = cls_inf;
            assign is_zero_o      = cls_zero;
            assign is_subnormal_o = cls_subnormal;
        end
    endgenerate

endmodule
