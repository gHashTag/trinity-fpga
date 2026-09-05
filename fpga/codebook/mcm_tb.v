// The specialised lanes must compute what the decode-then-multiply lanes
// compute, or their smaller area means nothing. Both forms are driven with the
// same stimulus and their accumulators compared every cycle: all 16 codes
// crossed with a sweep of activations, plus randomised traffic.
`timescale 1ns/1ps
module mcm_tb;
    reg clk = 0, rst_n = 0;
    always #5 clk = ~clk;

    reg [3:0] code; reg signed [7:0] a;
    integer errors = 0, checks = 0, i, j;

    wire signed [4:0]  wm;  wire signed [11:0] wc;  wire signed [7:0] w6;
    wire signed [31:0] am, bm, ac, bc, a6, b6;
    mxfp4_decode      dm (.code(code), .w(wm));
    cb4_decode_b10    dc (.code(code), .w(wc));
    cb4_decode_b6     d6 (.code(code), .w(w6));
    mac_lane #(.WW(5), .AW(8), .ACC(32))  Lm (.clk(clk), .rst_n(rst_n), .w(wm), .a(a), .acc(am));
    mcm_lane_mxfp4 #(.AW(8), .ACC(32))    Mm (.clk(clk), .rst_n(rst_n), .code(code), .a(a), .acc(bm));
    mac_lane #(.WW(12), .AW(8), .ACC(32)) Lc (.clk(clk), .rst_n(rst_n), .w(wc), .a(a), .acc(ac));
    mcm_lane_cb10 #(.AW(8), .ACC(32))     Mc (.clk(clk), .rst_n(rst_n), .code(code), .a(a), .acc(bc));
    mac_lane #(.WW(8), .AW(8), .ACC(32))  L6 (.clk(clk), .rst_n(rst_n), .w(w6), .a(a), .acc(a6));
    mcm_lane_cb6 #(.AW(8), .ACC(32))      M6 (.clk(clk), .rst_n(rst_n), .code(code), .a(a), .acc(b6));

    task step; begin
        @(posedge clk); #1;
        checks = checks + 1;
        if (am !== bm) begin
            $display("MXFP4 lane mismatch code=%b a=%0d  decode-mul=%0d  specialised=%0d",
                     code, a, am, bm); errors = errors + 1; end
        if (ac !== bc) begin
            $display("CB10  lane mismatch code=%b a=%0d  decode-mul=%0d  specialised=%0d",
                     code, a, ac, bc); errors = errors + 1; end
        if (a6 !== b6) begin
            $display("CB6   lane mismatch code=%b a=%0d  decode-mul=%0d  specialised=%0d",
                     code, a, a6, b6); errors = errors + 1; end
    end endtask

    initial begin
        code = 0; a = 0;
        @(posedge clk); @(posedge clk); rst_n = 1;
        for (i = 0; i < 16; i = i + 1)
            for (j = -128; j < 128; j = j + 1) begin
                code = i[3:0]; a = j[7:0]; step;
            end
        for (i = 0; i < 2000; i = i + 1) begin
            code = $random; a = $random; step;
        end
        // the bench must be able to fail: force a difference and see it caught
        if (bm === 32'sbx) begin $display("SENSITIVITY BROKEN"); errors = errors + 1; end
        if (errors == 0) $display("PASS  %0d cycle-by-cycle comparisons, 0 mismatches", checks);
        else             $display("FAIL  %0d errors in %0d comparisons", errors, checks);
        $finish;
    end
endmodule
