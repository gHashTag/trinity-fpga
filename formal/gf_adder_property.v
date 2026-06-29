// =============================================================================
// Formal property wrapper for gf_adder_param — bit-exact proof of floating-point
// ADD via an INDEPENDENT integer-scaled reference model.
//
// PARAMETRIC: top-level params (EXP_BITS/MANT_BITS/HAS_INF) are overridden per
// task from formal/gf_adder_formal.sby `chparam`, so the SAME property proves
// every GF width gf4/gf6/gf8/gf12/gf16/gf20/gf24, not just the GF8 representative.
//
// ACCEPTANCE CRITERIA (§3.5 formal gate — ALL required for [доказано]):
//   1. INDEPENDENT ORACLE: reference scales each operand to an EXACT integer on
//      a common fine grid (unit = smallest denormal), sums exactly, then performs
//      a SINGLE mathematical round-half-to-even. It does NOT re-implement the
//      DUT's align/guard/round/sticky shift pipeline (bug==bug would void it).
//   2. FREE INPUTS: operands are unconstrained (solver explores ALL 2^(2*TOTAL)
//      input pairs) — a counter-driven stimulus is simulation, not a proof.
//   3. FULL PROOF: sby `mode prove` (z3) / yosys `sat -prove-asserts -tempinduct`.
//
// WIDTH SAFETY: the absolute-scaled magnitude can reach ~2^524 for gf24 (BIAS=255,
//   shift up to exp_max-1=510). Verilog `integer` is only 32-bit, so all scaled
//   arithmetic uses a WIDE `reg signed [ACC_W-1:0]` accumulator (ACC_W=600).
//   Yosys models wide regs exactly for SAT; this keeps the simple, manifestly
//   independent absolute-integer formulation valid across every width.
//
// FACTCHECKED DUT semantics (gf_adder_param.v, 2026-06-29):
//   - RNE with GRS: round up iff G && (R|S|LSB).
//   - Denormal input: implicit-0, exp_eff = 1 (real_exp = 1-BIAS).
//   - Zero: both-zero -> -0 only if BOTH -0 else +0; else pass the other operand.
//   - NaN input (HAS_INF): result = quiet NaN {0, all-ones-exp, 0..01}.
//   - Family-split OVERFLOW: HAS_INF -> Inf {sg,all-ones,0}; else max-finite
//     {sg,all-ones,all-ones}.
//   - Subnormal RESULT: exact integer multiple of the unit -> mantissa = scaled.
//
// Run (yosys built-in SAT):
//   yosys -p "read_verilog -sv fpga/openxc7-synth/gf_adder_param.v; \
//     read_verilog -sv formal/gf_adder_property.v; hierarchy -top gf_adder_property; \
//     chparam -set EXP_BITS 6 -set MANT_BITS 9 -set HAS_INF 1 gf_adder_property; \
//     proc; opt; flatten; opt_clean; sat -prove-asserts -tempinduct -set-init-undef"
// =============================================================================

`default_nettype none
`timescale 1ns / 1ps

module gf_adder_property #(
    parameter EXP_BITS  = 3,   // GF8 default; overridden per task via sby chparam
    parameter MANT_BITS = 4,
    parameter HAS_INF   = 0,
    parameter TOTAL     = 1 + EXP_BITS + MANT_BITS,
    parameter BIAS      = (1 << (EXP_BITS - 1)) - 1,
    parameter ACC_W     = 600  // wide enough for gf24 absolute scale (~2^524)
)(
    input wire clk
);

    // -----------------------------------------------------------------------------
    // ROOT-CAUSE REWRITE 2026-06-30 — $anyconst time-invariant operands (mirror of
    // gf_mul_property.v). HISTORY: four harness iterations (anyinit primed,
    // async-reset rst_prev, registered-operand sampling, primed_d) each removed ONE
    // boundary-cycle false CE, but smtbmc kept finding the next, because the property
    // compared a LATENT anyinit-capable out_y against a COMBINATIONAL oracle of a
    // separately-captured pair, hand-aligned in phase. Any 1-cycle residue => spurious
    // CE. FIX (kills the whole class): drive the DUT with $anyconst operands invariant
    // across the trace. With out_ready=1/in_ready=1/in_valid=1 the DUT writes
    // out_reg <= result_packed(a,b) every cycle, so out_reg is STABLE at the correct
    // value once reset+settle pass — no sample skew, no capture, no anyinit residue.
    // RTL is UNCHANGED. (Independent gf_ref golden and silicon — adder family Tier E —
    // confirm the RTL; every formal FAIL here was a harness timing artifact.)
    // -----------------------------------------------------------------------------
    reg [2:0] rst_cnt;
    initial rst_cnt = 3'b011;            // reset asserted while rst_cnt != 0
    always @(posedge clk) if (rst_cnt) rst_cnt <= rst_cnt - 3'b001;
    wire rst = |rst_cnt;

    // ---- TIME-INVARIANT free operands ($anyconst): solver explores all pairs ----
    wire [TOTAL-1:0] a_op;
    wire [TOTAL-1:0] b_op;
    assign a_op = $anyconst;
    assign b_op = $anyconst;

    wire             in_valid = 1'b1;
    wire             out_ready = 1'b1;
    wire             in_ready, out_valid;
    wire [TOTAL-1:0] out_y;

    gf_adder_param #(
        .EXP_BITS(EXP_BITS),
        .MANT_BITS(MANT_BITS),
        .HAS_INF(HAS_INF)
    ) dut (
        .clk(clk), .rst(rst),
        .in_valid(in_valid), .in_a(a_op), .in_b(b_op), .in_ready(in_ready),
        .out_valid(out_valid), .out_y(out_y), .out_ready(out_ready)
    );

    // ---- `primed` margin: assert only after reset boundary + first stable write ----
    reg [2:0] settle;
    initial settle = 3'b000;
    always @(posedge clk) begin
        if (rst) settle <= 3'b000;
        else if (~&settle) settle <= settle + 3'b001;
    end
    wire primed = (~rst) && (&settle);   // high once settle saturates after reset

    // ---- INDEPENDENT reference: exact integer arithmetic + mathematical RNE ----
    function [TOTAL-1:0] ref_fpadd;
        input [TOTAL-1:0] a, b;
        reg               ra, rb, az, bz, adn, bdn;
        reg               a_spec, b_spec, a_nan, b_nan;
        reg [EXP_BITS-1:0]  ea, eb;
        reg [MANT_BITS-1:0] ma, mb;
        reg [TOTAL-1:0] res;
        begin
            ra = a[TOTAL-1];  ea = a[TOTAL-2:MANT_BITS];  ma = a[MANT_BITS-1:0];
            rb = b[TOTAL-1];  eb = b[TOTAL-2:MANT_BITS];  mb = b[MANT_BITS-1:0];
            az  = (ea == {EXP_BITS{1'b0}}) && (ma == {MANT_BITS{1'b0}});
            bz  = (eb == {EXP_BITS{1'b0}}) && (mb == {MANT_BITS{1'b0}});
            adn = (ea == {EXP_BITS{1'b0}}) && (ma != {MANT_BITS{1'b0}});
            bdn = (eb == {EXP_BITS{1'b0}}) && (mb != {MANT_BITS{1'b0}});
            a_spec = (HAS_INF != 0) && (ea == {EXP_BITS{1'b1}});
            b_spec = (HAS_INF != 0) && (eb == {EXP_BITS{1'b1}});
            a_nan  = a_spec && (ma != {MANT_BITS{1'b0}});
            b_nan  = b_spec && (mb != {MANT_BITS{1'b0}});

            // ---- DUT special-case order (gf_adder_param.v 106-114): ----
            //   both-zero -> a_zero -> b_zero -> NaN -> numeric.
            //   The DUT does NOT short-circuit Inf inputs in ADD; an all-ones-exp
            //   finite-mant=0 operand goes numeric and naturally saturates -> Inf.
            res = {TOTAL{1'b0}};
            if (az && bz)
                res = (ra && rb) ? {1'b1, {(TOTAL-1){1'b0}}} : {TOTAL{1'b0}};
            else if (az)        res = b;
            else if (bz)        res = a;
            else if (a_nan || b_nan)
                res = {1'b0, {EXP_BITS{1'b1}}, {(MANT_BITS-1){1'b0}}, 1'b1}; // qNaN
            else
                res = ref_numeric_add(ra, rb, ea, eb, ma, mb, adn, bdn);
            ref_fpadd = res;
        end
    endfunction

    // ---- numeric core: exact wide-integer scaled sum + single RNE ----
    //   Common grid: unit = smallest denormal = 2^(1-BIAS-MANT). Each operand's
    //   scaled magnitude = {impl,mant} << (exp_eff-1)  (integer, exact).
    //   The wide accumulator holds the exact signed sum; one RNE rounds the
    //   normalized result. Subnormal results are exact multiples of the unit.
    function [TOTAL-1:0] ref_numeric_add;
        input             ra, rb;
        input [EXP_BITS-1:0]  ea, eb;
        input [MANT_BITS-1:0] ma, mb;
        input             adn, bdn;
        integer base_a, base_b, sh_a, sh_b;
        reg signed [ACC_W-1:0] sa_mag, sb_mag, ssum, mag;
        integer lead, k, i, exp_field, gb, tailnz, lsb_bit;
        reg [MANT_BITS:0] frac;     // MANT+1 to catch rounding carry
        reg sg;
        reg [EXP_BITS-1:0]  ef_r;
        reg [MANT_BITS-1:0] fr_r, mr_r;
        reg [TOTAL-1:0] res;
        begin
            // NOTE: операнды уже декодированы и спец-случаи (zero/NaN/Inf) обработаны
            // в ref_fpadd; сюда приходит только числовое ядро. Разрешение merge-конфликта
            // 29.06: взята версия ветки (wide ACC_W-аккумулятор + полная HAS_INF-ветка),
            // т.к. она корректна для широких форматов (gf20/gf24 ~2^524) и gf16 Inf/NaN;
            // inline-вариант main использовал 32-bit integer + lead-loop<24 (узко).
            base_a = (adn ? 0 : (1 << MANT_BITS)) + ma;   // {implicit, mant}
            base_b = (bdn ? 0 : (1 << MANT_BITS)) + mb;
            sh_a   = (adn ? 1 : ea) - 1;                  // exp_eff - 1 (>= 0)
            sh_b   = (bdn ? 1 : eb) - 1;
            sa_mag = $signed({{(ACC_W-32){1'b0}}, base_a[31:0]}) <<< sh_a;
            sb_mag = $signed({{(ACC_W-32){1'b0}}, base_b[31:0]}) <<< sh_b;
            ssum   = (ra ? -sa_mag : sa_mag) + (rb ? -sb_mag : sb_mag); // exact signed sum

            res = {TOTAL{1'b0}};
            if (ssum == 0) res = {TOTAL{1'b0}};
            else begin
                sg  = (ssum < 0);
                mag = sg ? -ssum : ssum;
                lead = 0;  for (i = 0; i < ACC_W; i = i + 1) if (mag[i]) lead = i;
                exp_field = lead - MANT_BITS + 1;          // biased field for normal form
                frac = {(MANT_BITS+1){1'b0}};
                if (exp_field >= 1) begin
                    k        = lead - MANT_BITS;
                    frac     = (mag >> k) & ((1 << MANT_BITS) - 1);
                    gb       = (k >= 1) ? ((mag >> (k-1)) & 1) : 0;
                    tailnz   = 0;
                    if (k >= 2)
                        for (i = 0; i < ACC_W; i = i + 1)
                            if (i < k-1 && mag[i]) tailnz = 1;
                    lsb_bit  = frac & 1;
                    if (gb && (tailnz || lsb_bit)) begin   // round-half-to-even
                        frac = frac + 1'b1;
                        if (frac == (1 << MANT_BITS)) begin frac = 0; exp_field = exp_field + 1; end
                    end
                end
                // ---- classify + pack (family-split overflow / subnormal) ----
                if (HAS_INF != 0) begin
                    if (exp_field >= ((1 << EXP_BITS) - 1))
                        res = {sg, {EXP_BITS{1'b1}}, {MANT_BITS{1'b0}}};      // +/-Inf
                    else if (exp_field <= 0) begin
                        mr_r = mag[MANT_BITS-1:0]; res = {sg, {EXP_BITS{1'b0}}, mr_r};
                    end else begin
                        ef_r = exp_field[EXP_BITS-1:0]; fr_r = frac[MANT_BITS-1:0];
                        res = {sg, ef_r, fr_r};
                    end
                end else begin
                    if (exp_field > ((1 << EXP_BITS) - 1))
                        res = {sg, {EXP_BITS{1'b1}}, {MANT_BITS{1'b1}}};      // max-finite
                    else if (exp_field <= 0) begin
                        mr_r = mag[MANT_BITS-1:0]; res = {sg, {EXP_BITS{1'b0}}, mr_r};
                    end else begin
                        ef_r = exp_field[EXP_BITS-1:0]; fr_r = frac[MANT_BITS-1:0];
                        res = {sg, ef_r, fr_r};
                    end
                end
            end
            ref_numeric_add = res;
        end
    endfunction

    // ---- THE proof: DUT == independent reference ----
    // With $anyconst operands out_reg is stable at result_packed(a_op,b_op) once
    // `primed` rises (reset boundary + first stable write passed). No phase capture
    // is needed: assert directly against a_op/b_op.
    always @(posedge clk) begin
        if (primed)
            assert(out_y == ref_fpadd(a_op, b_op));
    end

endmodule

`default_nettype wire
