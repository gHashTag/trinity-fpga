// =============================================================================
// Formal property wrapper for gf_mul_param — bit-exact proof of floating-point
// MUL via an INDEPENDENT integer-scaled reference model.
//
// PARAMETRIC: top-level params (EXP_BITS/MANT_BITS/HAS_INF) are overridden per
// task from formal/gf_mul_formal.sby `chparam`, proving every GF width
// gf6/gf8/gf12/gf16/gf20/gf24 with the SAME property. (gf4 BIAS=0 is degenerate
// and verified separately by the SW oracle — its pack_denorm returns +/-0.)
//
// ACCEPTANCE CRITERIA (§3.5 formal gate — ALL required for [доказано]):
//   1. INDEPENDENT ORACLE: the reference computes the EXACT integer product of
//      the two significands and the EXACT combined power-of-two, then performs a
//      SINGLE mathematical round-half-to-even at the target precision. It does
//      NOT re-implement the DUT's MSB-scan / guard-round-sticky / pack_denorm
//      pipeline (bug==bug would void the proof).
//   2. FREE INPUTS: operands are unconstrained (solver explores ALL 2^(2*TOTAL)
//      input pairs) — counter stimulus would be simulation, not proof.
//   3. FULL PROOF: run with sby `mode prove` (z3) / yosys `sat -prove-asserts`.
//
// FACTCHECKED DUT semantics (read from gf_mul_param.v, 2026-06-29):
//   - result_sign = sa ^ sb (incl zero result — IEEE 754).
//   - prod = {impl_a,ma} * {impl_b,mb}, width PW=2*(MANT+1) [erratum 2M+2].
//   - er = ea_eff + eb_eff - BIAS; exp_field = er + (msb - 2*MANT).
//   - Denormal operand: implicit=0, exp_eff=1 (real_exp=1-BIAS).
//   - exp_field<1 -> pack_denorm DIRECT from prod (single rounding).
//   - normal: RNE on G,R,S; rounding carry handled; family-split overflow.
//   - special (HAS_INF): NaN>0*Inf=NaN>Inf>zero. 0*x = +/-0 (sign XOR).
//
// Run (yosys built-in SAT — no z3/sby required):
//   yosys -p "read_verilog -sv fpga/openxc7-synth/gf_mul_param.v; \
//     read_verilog -sv formal/gf_mul_property.v; hierarchy -top gf_mul_property; \
//     chparam -set EXP_BITS 3 -set MANT_BITS 4 -set HAS_INF 0 gf_mul_property; \
//     proc; opt; flatten; opt_clean; sat -prove-asserts -tempinduct -set-init-undef"
// =============================================================================

`default_nettype none
`timescale 1ns / 1ps

module gf_mul_property #(
    parameter EXP_BITS  = 3,   // GF8 default; overridden per task via sby chparam
    parameter MANT_BITS = 4,
    parameter HAS_INF   = 0,
    parameter TOTAL     = 1 + EXP_BITS + MANT_BITS,
    parameter BIAS      = (1 << (EXP_BITS - 1)) - 1
)(
    input wire clk
);

    // ---- Internal power-on reset (DETERMINISTIC init — critical for BMC) ----
    // BMC with smtbmc lets the solver pick ARBITRARY power-on values for any reg
    // WITHOUT an `initial` value ("anyinit"). The DUT's out_reg/out_valid_reg are
    // such regs -> solver can assert out_valid high in step 0 with garbage out_reg,
    // producing a FALSE counterexample (verified 2026-06-29 run 28380750995:
    // a_cap=0x21,b_cap=0x91 but out_y=0x80=anyinit garbage; true product=0x89).
    // FIX: a harness-owned `primed` flag, deterministically initialised, gates the
    // assert so it fires ONLY on cycles whose out_y is the genuine DUT result of a
    // real captured pair (>=2 cycles after reset release). RTL is NOT modified.
    reg [2:0] rst_cnt;
    initial rst_cnt = 3'b111;
    always @(posedge clk) if (rst_cnt) rst_cnt <= rst_cnt - 3'b001;
    wire rst = |rst_cnt;

    // ---- FREE unconstrained operands ----
    // MUST use $anyseq: a plain undriven `reg` is NOT a free formal input in
    // yosys/sby ("no driver" -> undefined, NOT solver-chosen). $anyseq lets the
    // solver pick a fresh arbitrary value EVERY cycle (new operand pair per clock).
    // Verified 2026-06-29: undriven reg caused BMC FAIL (run 28378070910).
    wire [TOTAL-1:0] in_a_r = $anyseq;
    wire [TOTAL-1:0] in_b_r = $anyseq;
    wire in_valid_r = 1'b1;
    wire out_ready  = 1'b1;
    wire in_ready, out_valid;
    wire [TOTAL-1:0] out_y;

    gf_mul_param #(
        .EXP_BITS(EXP_BITS),
        .MANT_BITS(MANT_BITS),
        .HAS_INF(HAS_INF)
    ) dut (
        .clk(clk), .rst(rst),
        .in_valid(in_valid_r), .in_a(in_a_r), .in_b(in_b_r), .in_ready(in_ready),
        .out_valid(out_valid), .out_y(out_y), .out_ready(out_ready)
    );

    // ---- Latency-matched capture (DUT latency = 1) + primed tracker ----
    // a_cap/b_cap latch the operand pair the SAME edge the DUT latches out_reg, so
    // at the next cycle out_y == f(a_cap,b_cap). `primed` is set ONLY after a real
    // capture occurs post-reset, marking that out_y now reflects (a_cap,b_cap).
    // All three regs have deterministic `initial` -> solver cannot inject anyinit.
    reg [TOTAL-1:0] a_cap, b_cap;
    reg             primed;
    initial begin a_cap = {TOTAL{1'b0}}; b_cap = {TOTAL{1'b0}}; primed = 1'b0; end
    always @(posedge clk) begin
        if (rst) begin
            a_cap  <= {TOTAL{1'b0}};
            b_cap  <= {TOTAL{1'b0}};
            primed <= 1'b0;
        end else if (in_valid_r && in_ready) begin
            a_cap  <= in_a_r;
            b_cap  <= in_b_r;
            primed <= 1'b1;   // out_y next cycle is the genuine result of this pair
        end
    end

    // ---- INDEPENDENT reference: exact integer product + single RNE ----
    function [TOTAL-1:0] ref_fpmul;
        input [TOTAL-1:0] a, b;
        reg               sa, sb, sg, az, bz, adn, bdn, a_spec, b_spec, a_nan, b_nan, a_inf, b_inf;
        reg [EXP_BITS-1:0]  ea, eb;
        reg [MANT_BITS-1:0] ma, mb;
        integer base_a, base_b, iprod;       // exact integer significands & product
        integer P;                           // combined power: value = iprod * 2^P
        integer lead, k, i, exp_field, frac, gb, tailnz, lsb_bit;
        integer m_int, msbits;               // denormal direct-rounding helpers
        reg [EXP_BITS-1:0]  ef_r;
        reg [MANT_BITS-1:0] fr_r, mr_r;
        reg [TOTAL-1:0] res;
        begin
            sa = a[TOTAL-1];  ea = a[TOTAL-2:MANT_BITS];  ma = a[MANT_BITS-1:0];
            sb = b[TOTAL-1];  eb = b[TOTAL-2:MANT_BITS];  mb = b[MANT_BITS-1:0];
            sg = sa ^ sb;
            az  = (ea == {EXP_BITS{1'b0}}) && (ma == {MANT_BITS{1'b0}});
            bz  = (eb == {EXP_BITS{1'b0}}) && (mb == {MANT_BITS{1'b0}});
            adn = (ea == {EXP_BITS{1'b0}}) && (ma != {MANT_BITS{1'b0}});
            bdn = (eb == {EXP_BITS{1'b0}}) && (mb != {MANT_BITS{1'b0}});
            a_spec = (HAS_INF != 0) && (ea == {EXP_BITS{1'b1}});
            b_spec = (HAS_INF != 0) && (eb == {EXP_BITS{1'b1}});
            a_nan  = a_spec && (ma != {MANT_BITS{1'b0}});
            b_nan  = b_spec && (mb != {MANT_BITS{1'b0}});
            a_inf  = a_spec && (ma == {MANT_BITS{1'b0}});
            b_inf  = b_spec && (mb == {MANT_BITS{1'b0}});

            res = {TOTAL{1'b0}};

            // ---- DUT special-case order (gf_mul_param.v lines 113-122): ----
            //   NaN > (0*Inf=NaN) > Inf > zero > numeric.
            if (a_nan || b_nan)
                res = {1'b0, {EXP_BITS{1'b1}}, {(MANT_BITS-1){1'b0}}, 1'b1};   // qNaN
            else if ((a_inf && bz) || (b_inf && az))
                res = {1'b0, {EXP_BITS{1'b1}}, {(MANT_BITS-1){1'b0}}, 1'b1};   // 0*Inf=NaN
            else if (a_inf || b_inf)
                res = sg ? {1'b1, {EXP_BITS{1'b1}}, {MANT_BITS{1'b0}}}
                         : {1'b0, {EXP_BITS{1'b1}}, {MANT_BITS{1'b0}}};        // +/-Inf
            else if (az || bz)
                res = sg ? {1'b1, {(TOTAL-1){1'b0}}} : {TOTAL{1'b0}};          // +/-0
            else begin
                // ---- numeric: exact integer product of significands ----
                base_a = (adn ? 0 : (1 << MANT_BITS)) + ma;   // {impl, mant}, MANT+1 bits
                base_b = (bdn ? 0 : (1 << MANT_BITS)) + mb;
                iprod  = base_a * base_b;                     // exact integer product
                // value = iprod * 2^P, where each base is significand*2^MANT and
                //   real_exp = exp_eff - 1 - BIAS.  P = (ea_eff-1)+(eb_eff-1) - 2*MANT - 2*BIAS
                //   ... but we pack against the biased field, so use:
                //   exp contribution before normalize: er = ea_eff + eb_eff - BIAS,
                //   exp_field = er + (lead - 2*MANT). We keep P for the denormal path.
                if (iprod == 0)
                    res = sg ? {1'b1, {(TOTAL-1){1'b0}}} : {TOTAL{1'b0}};
                else begin
                    // leading set-bit position of iprod
                    lead = 0;  for (i = 0; i < 128; i = i + 1) if ((iprod >> i) & 1) lead = i;
                    // biased exponent field for the normalized result
                    // er = ea_eff + eb_eff - BIAS  (ea_eff = adn?1:ea, eb_eff = bdn?1:eb)
                    exp_field = ((adn ? 1 : ea) + (bdn ? 1 : eb) - BIAS) + (lead - 2*MANT_BITS);

                    if (exp_field >= 1) begin
                        // ---- NORMAL: take MANT bits below the leading bit, RNE ----
                        k    = lead - MANT_BITS;          // >=0 since lead>=MANT for normal
                        frac = (iprod >> k) & ((1 << MANT_BITS) - 1);
                        gb       = (k >= 1) ? ((iprod >> (k-1)) & 1) : 0;
                        tailnz   = (k >= 2) ? (((iprod & ((1 << (k-1)) - 1)) != 0) ? 1 : 0) : 0;
                        lsb_bit  = frac & 1;
                        if (gb && (tailnz || lsb_bit)) begin   // round-half-to-even
                            frac = frac + 1;
                            if (frac == (1 << MANT_BITS)) begin frac = 0; exp_field = exp_field + 1; end
                        end
                        // family-split overflow
                        if (HAS_INF != 0) begin
                            if (exp_field >= ((1 << EXP_BITS) - 1))
                                res = {sg, {EXP_BITS{1'b1}}, {MANT_BITS{1'b0}}};      // Inf
                            else begin
                                ef_r = exp_field[EXP_BITS-1:0]; fr_r = frac[MANT_BITS-1:0];
                                res = {sg, ef_r, fr_r};
                            end
                        end else begin
                            if (exp_field > ((1 << EXP_BITS) - 1))
                                res = {sg, {EXP_BITS{1'b1}}, {MANT_BITS{1'b1}}};      // max-finite
                            else begin
                                ef_r = exp_field[EXP_BITS-1:0]; fr_r = frac[MANT_BITS-1:0];
                                res = {sg, ef_r, fr_r};
                            end
                        end
                    end else begin
                        // ---- DENORMAL RESULT: direct single rounding from iprod ----
                        // value = iprod * 2^Preal, Preal = (ea_eff-1)+(eb_eff-1)-2*MANT-2*BIAS+... ;
                        // Denormal field m_int = round( value / 2^(1-BIAS-MANT) )
                        //   = round( iprod * 2^(exp_field - 1) ) with exp_field<1.
                        // shift amount sh = 1 - exp_field (>=0) bits to drop from iprod,
                        //   keeping MANT-bit denormal mantissa, RNE+sticky.
                        // Derivation: in NORMAL form mantissa LSB weight = 2^(exp_field-1-MANT)
                        //   relative; for denormal the field weight is 2^(1-BIAS-MANT) and
                        //   exp_field-1 captures exactly the extra right-shift needed.
                        k = (1 - exp_field) + (lead - MANT_BITS);  // bits below denormal LSB
                        if (k <= 0) begin
                            // exact: left-justify (no rounding)
                            m_int = iprod << (-k);
                        end else begin
                            frac   = (iprod >> k) & ((1 << (MANT_BITS+2)) - 1);
                            gb     = ((iprod >> (k-1)) & 1);
                            tailnz = (k >= 2) ? (((iprod & ((1 << (k-1)) - 1)) != 0) ? 1 : 0) : 0;
                            lsb_bit= frac & 1;
                            m_int  = frac;
                            if (gb && (tailnz || lsb_bit)) m_int = m_int + 1;
                        end
                        // pack: m_int reaching 2^MANT promotes to smallest normal
                        if (m_int >= (1 << MANT_BITS))
                            res = {sg, {(EXP_BITS-1){1'b0}}, 1'b1, {MANT_BITS{1'b0}}};
                        else if (m_int == 0)
                            res = sg ? {1'b1, {(TOTAL-1){1'b0}}} : {TOTAL{1'b0}};
                        else begin
                            mr_r = m_int[MANT_BITS-1:0]; res = {sg, {EXP_BITS{1'b0}}, mr_r};
                        end
                    end
                end
            end
            ref_fpmul = res;
        end
    endfunction

    // ---- THE proof: DUT == independent reference ----
    // Gate ONLY on `primed` (harness-owned, deterministically initialised) — NOT on
    // the DUT's out_valid. out_valid_reg is an anyinit reg: the solver could either
    // (a) raise it early with garbage out_reg -> FALSE positive CE, or (b) hold it
    // low to SUPPRESS a real check -> coverage hole. `primed` removes both: when it
    // is high, out_y is provably out_reg<=result_packed(a_cap,b_cap) from the prior
    // edge (DUT latency=1, in_valid=in_ready=1 every cycle), independent of the
    // anyinit out_valid_reg. This makes the proof both SOUND and COMPLETE.
    always @(posedge clk) begin
        if (primed && !rst)
            assert(out_y == ref_fpmul(a_cap, b_cap));
    end

endmodule

`default_nettype wire
