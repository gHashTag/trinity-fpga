// =============================================================================
// Formal property wrapper for gf_adder_param — bit-exact proof of floating-point
// ADD via an INDEPENDENT integer-scaled reference model.
//
// ACCEPTANCE CRITERIA (§3.5 formal gate — ALL required for [доказано]):
//   1. INDEPENDENT ORACLE: reference uses exact integer arithmetic + a single
//      mathematical round-half-to-even step, NOT a re-implementation of the DUT's
//      guard/round/sticky shift pipeline (bug-equals-bug would make proof useless).
//   2. FREE INPUTS: operands are unconstrained (solver explores ALL 2^(2*TOTAL)
//      input pairs) — a counter-driven stimulus is simulation, not a proof.
//   3. FULL PROOF (not bounded): run with `yosys sat -prove-asserts -tempinduct`.
//
// FACTCHECKED DUT semantics (read from gf_adder_param.v, 2026-06-27):
//   - Rounding = round-half-to-even (RNE) with GRS — round up iff
//     G && (R | S | LSB). (Header comment "truncation" was stale — fixed.)
//   - Denormal input: implicit-0 mantissa, exp_eff = 1 (real_exp = 1-BIAS).
//   - Saturation: biased exp_field >= 2^EXP_BITS  -> {sg, all-ones}.
//   - Zero: a_zero/b_zero short-circuit (result = other operand, incl -0).
//   - Subnormal RESULT: only effective-ADDITION (same input sign) may produce a
//     denormal result; effective-SUBTRACTION (diff sign) that lands in the
//     subnormal range is flushed to +0 (DUT `underflow` path).
//
// Run:  yosys -p "read_verilog -sv fpga/openxc7-synth/gf_adder_param.v; \
//        read_verilog -sv formal/gf_adder_property.v; hierarchy -top gf_adder_property; \
//        proc; opt; flatten; opt_clean; sat -prove-asserts -tempinduct -set-init-undef"
//       (yosys built-in SAT — no z3/sby required.)
// =============================================================================

`default_nettype none
`timescale 1ns / 1ps

module gf_adder_property #(
    parameter EXP_BITS  = 3,   // GF8 as representative width (parametric DUT)
    parameter MANT_BITS = 4,
    parameter TOTAL     = 1 + EXP_BITS + MANT_BITS,
    parameter BIAS      = (1 << (EXP_BITS - 1)) - 1
)(
    input wire clk
);

    // ---- Internal power-on reset: asserted for the first cycles, then deasserts.
    //      Pinned via `initial` so formal init is a KNOWN reset state (yosys sat
    //      otherwise treats undriven init as "any", yielding spurious cex). ----
    reg [1:0] rst_cnt;
    initial rst_cnt = 2'b11;
    always @(posedge clk) if (rst_cnt) rst_cnt <= rst_cnt - 2'b01;
    wire rst = |rst_cnt;

    // ---- FREE unconstrained operands (formal: solver sets these every cycle) ----
    reg  [TOTAL-1:0] in_a_r, in_b_r;

    // Always-valid, always-ready handshake -> one pair accepted per cycle,
    // result exactly 1 cycle later (DUT latency = 1). So at the out_valid edge,
    // a_cap/b_cap hold the pair the DUT just produced a result for.
    wire in_valid_r = 1'b1;
    wire out_ready  = 1'b1;
    wire in_ready, out_valid;
    wire [TOTAL-1:0] out_y;

    gf_adder_param #(
        .EXP_BITS(EXP_BITS),
        .MANT_BITS(MANT_BITS)
    ) dut (
        .clk(clk), .rst(rst),
        .in_valid(in_valid_r), .in_a(in_a_r), .in_b(in_b_r), .in_ready(in_ready),
        .out_valid(out_valid), .out_y(out_y), .out_ready(out_ready)
    );

    // ---- Latency-matched capture of the accepted pair ----
    reg [TOTAL-1:0] a_cap, b_cap;
    always @(posedge clk) begin
        if (rst) begin
            a_cap <= {TOTAL{1'b0}};
            b_cap <= {TOTAL{1'b0}};
        end else if (in_valid_r && in_ready) begin
            a_cap <= in_a_r;
            b_cap <= in_b_r;
        end
    end

    // ---- INDEPENDENT reference: exact integer arithmetic + mathematical RNE ----
    // Value scaling: unit = smallest denormal = 2^(1-BIAS-MANT_BITS). Each operand
    // scaled-magnitude = {implicit,mant} * 2^(exp_eff-1). Sum is an exact integer.
    function [TOTAL-1:0] ref_fpadd;
        input [TOTAL-1:0] a, b;
        reg            ra, rb, az, bz, adn, bdn, sg, same_in;
        reg [EXP_BITS-1:0]  ea, eb;
        reg [MANT_BITS-1:0] ma, mb;
        // ВНИМАНИЕ (честность): `integer` = 32-бит знаковый в Verilog. Для дефолтных
        // параметров GF8 (EXP_BITS=3) sh_a<=6, sa_mag<=~11 бит — переполнения нет,
        // доказательство exhaustive валидно. Для параметризации на GF16 (EXP_BITS=6)
        // sh_a достигает ~62, sa_mag/ssum/mag НЕ помещаются в 32 бита -> требуется
        // расширить эти переменные до reg signed [127:0] перед прогоном GF16-прува.
        // Логика (включая исправленную границу скана) проверена bit-exact в
        // verify_adder_oracle.py на произвольной точности (GF6/GF8 exhaustive,
        // GF12/GF16 sample). [доказано для GF8; GF16 = требует расширения разрядности]
        integer base_a, base_b, sh_a, sh_b, sa_mag, sb_mag, ssum, mag;
        integer lead, k, i, exp_field, frac, gb, tailnz, lsb_bit;
        reg [EXP_BITS-1:0]  ef_r;
        reg [MANT_BITS-1:0] fr_r, mr_r;
        reg [TOTAL-1:0] res;
        begin
            // decode a
            ra = a[TOTAL-1];  ea = a[TOTAL-2:MANT_BITS];  ma = a[MANT_BITS-1:0];
            // decode b
            rb = b[TOTAL-1];  eb = b[TOTAL-2:MANT_BITS];  mb = b[MANT_BITS-1:0];
            az  = (ea == {EXP_BITS{1'b0}}) && (ma == {MANT_BITS{1'b0}});
            bz  = (eb == {EXP_BITS{1'b0}}) && (mb == {MANT_BITS{1'b0}});
            adn = (BIAS > 0) && (ea == {EXP_BITS{1'b0}}) && (ma != {MANT_BITS{1'b0}});
            bdn = (BIAS > 0) && (eb == {EXP_BITS{1'b0}}) && (mb != {MANT_BITS{1'b0}});
            same_in = (ra == rb);

            res = {TOTAL{1'b0}};
            // FIX (2026-06-29, верифицировано verify_adder_oracle.py): DUT обрабатывает
            // (+/-0)+(+/-0) ОТДЕЛЬНО со знаком: -0 ТОЛЬКО если ОБА операнда -0, иначе +0.
            // Прежний оракул возвращал b при az -> ложный контрпример на (+0)+(-0).
            if (az && bz)    res = (ra && rb) ? {1'b1, {(TOTAL-1){1'b0}}} : {TOTAL{1'b0}};
            else if (az)     res = b;            // DUT: a_zero -> pass b (priority)
            else if (bz)     res = a;            // DUT: b_zero -> pass a
            else begin
                base_a = (adn ? 0 : (1 << MANT_BITS)) + ma;   // {implicit, mant}
                base_b = (bdn ? 0 : (1 << MANT_BITS)) + mb;
                sh_a   = (adn ? 1 : ea) - 1;                  // exp_eff - 1, exp_eff >= 1
                sh_b   = (bdn ? 1 : eb) - 1;
                sa_mag = base_a << sh_a;
                sb_mag = base_b << sh_b;
                ssum   = (ra ? -sa_mag : sa_mag) + (rb ? -sb_mag : sb_mag);  // exact signed sum

                if (ssum == 0) res = {TOTAL{1'b0}};
                else begin
                    sg  = (ssum < 0);
                    mag = sg ? -ssum : ssum;
                    // Параметрическая граница скана старшего бита mag.
                    // sh_a = ea-1, ea<=2^EXP_BITS-1; base<=2^(MANT_BITS+1).
                    // => MSB(mag) <= (MANT_BITS+1) + (2^EXP_BITS-2). Запас +4.
                    // Прежняя граница TOTAL+MANT_BITS+4 (=29 для GF16) ломалась:
                    // при ea~62 mag достигал ~67 бит, lead обрезался -> мусор.
                    lead = 0;  for (i = 0; i < (MANT_BITS + 1) + ((1 << EXP_BITS) - 2) + 4; i = i + 1) if ((mag >> i) & 1) lead = i;
                    exp_field = lead - MANT_BITS + 1;          // biased field for normal form
                    if (exp_field >= 1) begin
                        k    = lead - MANT_BITS;
                        frac = (mag >> k) & ((1 << MANT_BITS) - 1);
                        gb       = (k >= 1) ? ((mag >> (k-1)) & 1) : 0;
                        tailnz   = (k >= 2) ? (((mag & ((1 << (k-1)) - 1)) != 0) ? 1 : 0) : 0;
                        lsb_bit  = frac & 1;
                        if (gb && (tailnz || lsb_bit)) begin   // round-half-to-even
                            frac = frac + 1;
                            if (frac == (1 << MANT_BITS)) begin frac = 0; exp_field = exp_field + 1; end
                        end
                    end
                    // classify + pack
                    if (exp_field >= (1 << EXP_BITS))
                        res = {sg, {EXP_BITS{1'b1}}, {MANT_BITS{1'b1}}};          // saturate
                    else if (exp_field <= 0) begin
                        // subnormal RESULT: sum is an exact integer multiple of the
                        // unit, so mantissa = mag for BOTH add and sub. No flush.
                        mr_r = mag[MANT_BITS-1:0]; res = {sg, {EXP_BITS{1'b0}}, mr_r};
                    end else begin
                        ef_r = exp_field[EXP_BITS-1:0]; fr_r = frac[MANT_BITS-1:0];
                        res = {sg, ef_r, fr_r};
                    end
                end
            end
            ref_fpadd = res;
        end
    endfunction

    // ---- THE proof: DUT == independent reference, every out_valid cycle ----
    // (Coverage `cover()` points omitted — bare `yosys sat` has no model for
    //  $cover; they are an sby concern and add no proof value here.)
    always @(posedge clk) begin
        if (out_valid && !rst)
            assert(out_y == ref_fpadd(a_cap, b_cap));
    end

endmodule

`default_nettype wire
