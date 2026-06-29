// =============================================================================
// Exhaustive simulation: independent integer-scaled reference vs gf_adder_param
// over ALL 2^(2*TOTAL) = 65536 GF8 input pairs. DUT is HW-exhaustive-proven
// correct on GF8 (matrix: 65536/65536 [доказано]) -> it is the ORACLE here.
// ref == DUT on all pairs  =>  reference model is VALIDATED (correct for GF8),
// so a later formal proof for GF12/GF16 is meaningful (a cex there would point
// at a real DUT bug or a width-specific ref issue, not at the ref model itself).
//
//   iverilog -g2012 -o /tmp/gf_ref_tb.vvp formal/gf_adder_ref_tb.v \
//             fpga/openxc7-synth/gf_adder_param.v && vvp /tmp/gf_ref_tb.vvp
// =============================================================================
`timescale 1ns / 1ps
`default_nettype none
module gf_adder_ref_tb;
`ifndef GF_EXP_BITS
`define GF_EXP_BITS 3
`endif
`ifndef GF_MANT_BITS
`define GF_MANT_BITS 4
`endif
`ifndef GF_HAS_INF
`define GF_HAS_INF 0
`endif
    localparam EXP_BITS  = `GF_EXP_BITS;
    localparam MANT_BITS = `GF_MANT_BITS;
    localparam HAS_INF   = `GF_HAS_INF;
    localparam TOTAL     = 1 + EXP_BITS + MANT_BITS;
    localparam BIAS      = (1 << (EXP_BITS - 1)) - 1;

    reg              clk = 1'b0;
    reg              rst = 1'b1;
    reg              in_valid = 1'b0;
    reg  [TOTAL-1:0] in_a, in_b;
    wire             in_ready, out_valid;
    wire [TOTAL-1:0] out_y;
    reg              out_ready = 1'b1;

    integer i, j, errors = 0, checked = 0;
    integer c_diff_flush = 0, c_diff_other = 0, c_same = 0;
    reg [TOTAL-1:0] expv;

    gf_adder_param #(.EXP_BITS(EXP_BITS), .MANT_BITS(MANT_BITS), .HAS_INF(HAS_INF)) dut (
        .clk(clk), .rst(rst), .in_valid(in_valid), .in_a(in_a), .in_b(in_b),
        .in_ready(in_ready), .out_valid(out_valid), .out_y(out_y), .out_ready(out_ready)
    );

    always #5 clk = ~clk;

    // ---- independent integer-scaled reference (same math as formal property) ----
    function [TOTAL-1:0] ref_fpadd;
        input [TOTAL-1:0] a, b;
        reg            ra, rb, az, bz, adn, bdn, sg, same_in;
        reg [EXP_BITS-1:0]  ea, eb;
        reg [MANT_BITS-1:0] ma, mb;
        integer sh_a, sh_b;
        reg  [543:0] base_a, base_b, mag;
        reg signed [543:0] sa_mag, sb_mag, ssum;
        integer lead, k, ii, exp_field, frac, gb, tailnz, lsb_bit;
        reg [EXP_BITS-1:0]  ef_r;
        reg [MANT_BITS-1:0] fr_r, mr_r;
        reg [TOTAL-1:0] res;
        begin
            ra = a[TOTAL-1];  ea = a[TOTAL-2:MANT_BITS];  ma = a[MANT_BITS-1:0];
            rb = b[TOTAL-1];  eb = b[TOTAL-2:MANT_BITS];  mb = b[MANT_BITS-1:0];
            az  = (ea == {EXP_BITS{1'b0}}) && (ma == {MANT_BITS{1'b0}});
            bz  = (eb == {EXP_BITS{1'b0}}) && (mb == {MANT_BITS{1'b0}});
            adn = (ea == {EXP_BITS{1'b0}}) && (ma != {MANT_BITS{1'b0}});
            bdn = (eb == {EXP_BITS{1'b0}}) && (mb != {MANT_BITS{1'b0}});
            same_in = (ra == rb);
            res = {TOTAL{1'b0}};
            // NaN input → quiet NaN (HAS_INF only — GF16). IEEE 754: NaN propagates.
            if (HAS_INF != 0 && ((ea == {EXP_BITS{1'b1}} && ma != 0) || (eb == {EXP_BITS{1'b1}} && mb != 0)))
                res = {1'b0, {EXP_BITS{1'b1}}, {(MANT_BITS-1){1'b0}}, 1'b1};
            else if (az && bz)    res = (ra && rb) ? {1'b1, {(TOTAL-1){1'b0}}} : {TOTAL{1'b0}};
            else if (az)     res = b;
            else if (bz)     res = a;
            else begin
                base_a = (adn ? 0 : (1 << MANT_BITS)) + ma;
                base_b = (bdn ? 0 : (1 << MANT_BITS)) + mb;
                sh_a   = (adn ? 1 : ea) - 1;
                sh_b   = (bdn ? 1 : eb) - 1;
                sa_mag = base_a << sh_a;
                sb_mag = base_b << sh_b;
                ssum   = (ra ? -sa_mag : sa_mag) + (rb ? -sb_mag : sb_mag);
                if (ssum == 0) res = {TOTAL{1'b0}};
                else begin
                    sg  = (ssum < 0);
                    mag = sg ? -ssum : ssum;
                    lead = 0;  for (ii = 0; ii < 544; ii = ii + 1) if ((mag >> ii) & 1) lead = ii;
                    exp_field = lead - MANT_BITS + 1;
                    if (exp_field >= 1) begin
                        k    = lead - MANT_BITS;
                        frac = (mag >> k) & ((1 << MANT_BITS) - 1);
                        gb       = (k >= 1) ? ((mag >> (k-1)) & 1) : 0;
                        tailnz   = (k >= 2) ? (((mag & ((544'd1 << (k-1)) - 1)) != 0) ? 1 : 0) : 0;
                        lsb_bit  = frac & 1;
                        if (gb && (tailnz || lsb_bit)) begin
                            frac = frac + 1;
                            if (frac == (1 << MANT_BITS)) begin frac = 0; exp_field = exp_field + 1; end
                        end
                    end
                    if (HAS_INF && (exp_field >= ((1 << EXP_BITS) - 1)))
                        res = {sg, {EXP_BITS{1'b1}}, {MANT_BITS{1'b0}}};   // Inf
                    else if (!HAS_INF && (exp_field >= (1 << EXP_BITS)))
                        res = {sg, {EXP_BITS{1'b1}}, {MANT_BITS{1'b1}}};   // max-finite
                    else if (exp_field <= 0) begin
                        // subnormal RESULT: exact (sum is an integer multiple of the
                        // unit), so mantissa = mag for BOTH add and sub. No flush.
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

    initial begin
        // reset
        in_valid = 1'b0; in_a = 0; in_b = 0;
        @(posedge clk); #1; rst = 1'b0;
        @(posedge clk); #1;

`ifndef GF_SAMPLE_N
        // exhaustive mode (narrow formats)
        for (i = 0; i < (1 << TOTAL); i = i + 1) begin
            for (j = 0; j < (1 << TOTAL); j = j + 1) begin
                in_a = i[TOTAL-1:0]; in_b = j[TOTAL-1:0]; in_valid = 1'b1;
                @(posedge clk); #1;            // accept edge: out_y = result(i,j)
                expv = ref_fpadd(i[TOTAL-1:0], j[TOTAL-1:0]);
                if (!out_valid || (out_y !== expv)) begin
                    errors = errors + 1;
                    if (i[TOTAL-1] != j[TOTAL-1]) begin
                        if ((out_y == {TOTAL{1'b0}}) || (out_y[TOTAL-1] && (out_y[TOTAL-2:0] == 0)))
                            c_diff_flush = c_diff_flush + 1;
                        else
                            c_diff_other = c_diff_other + 1;
                    end else begin
                        c_same = c_same + 1;
                    end
                    if (errors <= 12)
                        $display("MISMATCH a=%0d b=%0d dut=%0d ref=%0d", in_a, in_b, out_y, expv);
                end
                checked = checked + 1;
            end
        end
`else
        // random-sample mode (wide formats where exhaustive is infeasible)
        for (i = 0; i < `GF_SAMPLE_N; i = i + 1) begin
            in_a = $random; in_b = $random; in_valid = 1'b1;
            @(posedge clk); #1;
            expv = ref_fpadd(in_a, in_b);
            if (!out_valid || (out_y !== expv)) begin
                errors = errors + 1;
                if (in_a[TOTAL-1] != in_b[TOTAL-1]) begin
                    if ((out_y == {TOTAL{1'b0}}) || (out_y[TOTAL-1] && (out_y[TOTAL-2:0] == 0)))
                        c_diff_flush = c_diff_flush + 1;
                    else
                        c_diff_other = c_diff_other + 1;
                end else begin
                    c_same = c_same + 1;
                end
                if (errors <= 12)
                    $display("MISMATCH a=%0d b=%0d dut=%0d ref=%0d", in_a, in_b, out_y, expv);
            end
            checked = checked + 1;
        end
`endif
        in_valid = 1'b0;
        $display("RESULT checked=%0d errors=%0d", checked, errors);
        $display("CATEGORY diff_sign_DUT_flushed_to_pm0=%0d diff_sign_other=%0d same_sign=%0d",
                 c_diff_flush, c_diff_other, c_same);
        if (errors == 0) $display("REF_VALIDATED: independent reference == DUT on all %0d GF8 pairs", checked);
        $finish;
    end
endmodule
`default_nettype wire
