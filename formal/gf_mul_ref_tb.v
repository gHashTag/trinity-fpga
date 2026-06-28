// =============================================================================
// Independent iverilog oracle (#2) for gf_mul_param — integer reference.
// Computes the spec-correct GF MUL result via exact integer arithmetic (NOT a
// transcription of the DUT bit-loops) and compares to the DUT on exhaustive
// (narrow) / random-sample (wide) input pairs.
//   spec: RNE, gradual-underflow single-rounding from exact prod,
//         HAS_INF family-split overflow (Inf / max-finite), IEEE Inf/NaN/zero.
// =============================================================================
`timescale 1ns/1ps
`default_nettype none
module gf_mul_ref_tb;
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
    reg [TOTAL-1:0] expv;

    gf_mul_param #(.EXP_BITS(EXP_BITS), .MANT_BITS(MANT_BITS), .HAS_INF(HAS_INF)) dut (
        .clk(clk), .rst(rst), .in_valid(in_valid), .in_a(in_a), .in_b(in_b),
        .in_ready(in_ready), .out_valid(out_valid), .out_y(out_y), .out_ready(out_ready)
    );
    always #5 clk = ~clk;

    // pack a denormal mantissa integer D (handles carry->smallest-normal, 0->±0)
    function [TOTAL-1:0] pack_den;
        input sgn; input integer D;
        begin
            if (D >= (1 << MANT_BITS))
                pack_den = {sgn, {{(EXP_BITS-1){1'b0}}, 1'b1}, {MANT_BITS{1'b0}}};  // smallest normal
            else if (D == 0)
                pack_den = sgn ? {1'b1, {(TOTAL-1){1'b0}}} : {TOTAL{1'b0}};
            else
                pack_den = {sgn, {EXP_BITS{1'b0}}, D[MANT_BITS-1:0]};
        end
    endfunction

    function [TOTAL-1:0] ref_mul;
        input [TOTAL-1:0] a, b;
        reg ra, rb, sgn;
        reg [EXP_BITS-1:0] ea, eb;
        reg [MANT_BITS-1:0] ma, mb;
        reg az, bz, adn, bdn, asp, bsp, ainf, binf, anan, bnan;
        integer ea_eff, eb_eff, sig_a, sig_b, prod, msb, exp_field;
        integer p_sh, sh, D, gd, st, lsbf, k;
        integer mf, g2, r2, s2, mant_rnd;
        reg [TOTAL-1:0] res;
        begin
            ra=a[TOTAL-1]; ea=a[TOTAL-2:MANT_BITS]; ma=a[MANT_BITS-1:0];
            rb=b[TOTAL-1]; eb=b[TOTAL-2:MANT_BITS]; mb=b[MANT_BITS-1:0];
            az=(ea==0)&&(ma==0); bz=(eb==0)&&(mb==0);
            adn=(BIAS>0)&&(ea==0)&&(ma!=0); bdn=(BIAS>0)&&(eb==0)&&(mb!=0);
            asp=(HAS_INF!=0)&&(ea=={EXP_BITS{1'b1}}); bsp=(HAS_INF!=0)&&(eb=={EXP_BITS{1'b1}});
            ainf=asp&&(ma==0); binf=bsp&&(mb==0); anan=asp&&(ma!=0); bnan=bsp&&(mb!=0);
            sgn = ra^rb;
            ea_eff = adn?1:ea;  eb_eff = bdn?1:eb;
            sig_a = (adn?0:(1<<MANT_BITS))+ma;
            sig_b = (bdn?0:(1<<MANT_BITS))+mb;
            res = {TOTAL{1'b0}};
            // special order: NaN > 0*Inf=NaN > Inf > zero > finite
            if (anan||bnan)
                res = {1'b0,{EXP_BITS{1'b1}},{{(MANT_BITS-1){1'b0}},1'b1}};          // quiet NaN
            else if ((ainf&&bz)||(binf&&az))
                res = {1'b0,{EXP_BITS{1'b1}},{{(MANT_BITS-1){1'b0}},1'b1}};          // 0*Inf = NaN
            else if (ainf||binf)
                res = sgn ? {1'b1,{EXP_BITS{1'b1}},{MANT_BITS{1'b0}}} : {1'b0,{EXP_BITS{1'b1}},{MANT_BITS{1'b0}}};
            else if (az||bz)
                res = sgn ? {1'b1,{(TOTAL-1){1'b0}}} : {TOTAL{1'b0}};
            else begin
                prod = sig_a * sig_b;                            // exact, <= 2*(MANT+1) bits
                msb = 0; for (k=0;k<2*MANT_BITS+2;k=k+1) if ((prod>>k)&1) msb=k;
                if (prod == 0)
                    res = sgn ? {1'b1,{(TOTAL-1){1'b0}}} : {TOTAL{1'b0}};
                else begin
                    exp_field = (ea_eff+eb_eff-BIAS) + (msb - 2*MANT_BITS);   // biased
                    if (exp_field < 1) begin
                        // subnormal result: gradual underflow, single RNE from exact prod
                        p_sh = (ea_eff+eb_eff-BIAS) - MANT_BITS - 1;          // = er - MANT - 1
                        if (BIAS==0)
                            res = sgn ? {1'b1,{(TOTAL-1){1'b0}}} : {TOTAL{1'b0}};
                        else if (p_sh >= 0)
                            res = pack_den(sgn, prod << p_sh);
                        else begin
                            sh = -p_sh;
                            if (sh >= msb+3)
                                res = sgn ? {1'b1,{(TOTAL-1){1'b0}}} : {TOTAL{1'b0}};
                            else begin
                                gd = (sh>=1) ? ((prod>>(sh-1))&1) : 0;
                                st = 0; for (k=0;k<sh-1;k=k+1) st = st | ((prod>>k)&1);
                                D  = prod >> sh;
                                lsbf = D & 1;
                                if (gd && (st||lsbf)) D = D + 1;
                                res = pack_den(sgn, D);
                            end
                        end
                    end else begin
                        // normal: mantissa = {1, prod[msb-1:msb-MANT]}, RNE(G,R,S)
                        mf = 0;
                        for (k=0;k<=MANT_BITS;k=k+1)
                            if (msb-MANT_BITS+k >= 0) mf = mf | (((prod>>(msb-MANT_BITS+k))&1) << k);
                        g2 = (msb-MANT_BITS-1>=0) ? ((prod>>(msb-MANT_BITS-1))&1) : 0;
                        r2 = (msb-MANT_BITS-2>=0) ? ((prod>>(msb-MANT_BITS-2))&1) : 0;
                        s2 = 0; for (k=0;k<msb-MANT_BITS-2;k=k+1) s2 = s2 | ((prod>>k)&1);
                        mant_rnd = (g2 && (r2||s2||(mf&1))) ? mf+1 : mf;       // integer, no wrap
                        if (mant_rnd >= (1<<(MANT_BITS+1))) begin              // rounding carry -> 2.0
                            mant_rnd = mant_rnd >> 1;
                            exp_field = exp_field + 1;
                        end
                        // overflow family-split
                        if (HAS_INF!=0) begin
                            if (exp_field >= (1<<EXP_BITS)-1)
                                res = sgn ? {1'b1,{EXP_BITS{1'b1}},{MANT_BITS{1'b0}}} : {1'b0,{EXP_BITS{1'b1}},{MANT_BITS{1'b0}}};
                            else
                                res = {sgn, exp_field[EXP_BITS-1:0], mant_rnd[MANT_BITS-1:0]};
                        end else begin
                            if (exp_field > (1<<EXP_BITS)-1)
                                res = {sgn, {EXP_BITS{1'b1}}, {MANT_BITS{1'b1}}};
                            else
                                res = {sgn, exp_field[EXP_BITS-1:0], mant_rnd[MANT_BITS-1:0]};
                        end
                    end
                end
            end
            ref_mul = res;
        end
    endfunction

    initial begin
        in_valid=1'b0; in_a=0; in_b=0;
        @(posedge clk); #1; rst=1'b0;
        @(posedge clk); #1;
`ifndef GF_SAMPLE_N
        for (i=0; i<(1<<TOTAL); i=i+1) begin
            for (j=0; j<(1<<TOTAL); j=j+1) begin
                in_a=i[TOTAL-1:0]; in_b=j[TOTAL-1:0]; in_valid=1'b1;
                @(posedge clk); #1;
                expv = ref_mul(i[TOTAL-1:0], j[TOTAL-1:0]);
                if (!out_valid || (out_y !== expv)) begin
                    errors=errors+1;
                    if (errors<=12) $display("MISMATCH a=%0d b=%0d dut=%0d ref=%0d", in_a, in_b, out_y, expv);
                end
                checked=checked+1;
            end
        end
`else
        for (i=0; i<`GF_SAMPLE_N; i=i+1) begin
            in_a=$random; in_b=$random; in_valid=1'b1;
            @(posedge clk); #1;
            expv = ref_mul(in_a, in_b);
            if (!out_valid || (out_y !== expv)) begin
                errors=errors+1;
                if (errors<=12) $display("MISMATCH a=%0d b=%0d dut=%0d ref=%0d", in_a, in_b, out_y, expv);
            end
            checked=checked+1;
        end
`endif
        in_valid=1'b0;
        $display("RESULT checked=%0d errors=%0d", checked, errors);
        if (errors==0) $display("MUL_REF_VALIDATED: independent integer-ref == DUT on %0d pairs (HAS_INF=%0d)", checked, HAS_INF);
        $finish;
    end
endmodule
`default_nettype wire
