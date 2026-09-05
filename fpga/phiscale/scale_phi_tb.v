// Does the circuit actually compute phi^k, or is it merely small?
// Reference: (a,b) -> (b, a+b) applied k times, which by phi^2 = phi + 1 is
// exactly multiplication by phi^k in Z[phi].  Checked against a golden model
// computed independently in the testbench.
`timescale 1ns/1ps
module scale_phi_tb;
    localparam ACC = 32, KW = 5;
    reg clk = 0, rst = 1, start = 0;
    reg signed [ACC-1:0] ia, ib;
    reg [KW-1:0] k;
    wire signed [ACC-1:0] oa, ob;
    wire done;
    integer errors = 0, checks = 0;
    integer t, kk, j;
    reg signed [ACC-1:0] ga, gb, tmp;

    scale_phi #(.ACC(ACC), .KW(KW)) dut
        (.clk(clk), .rst(rst), .start(start), .acc_a(ia), .acc_b(ib), .k(k),
         .out_a(oa), .out_b(ob), .done(done));

    always #5 clk = ~clk;

    initial begin
        @(negedge clk); rst = 0;
        for (t = 0; t < 200; t = t + 1) begin
            ia = $random % 10000;
            ib = $random % 10000;
            kk = {$random} % 12;
            // golden model, computed here and not by the DUT
            ga = ia; gb = ib;
            for (j = 0; j < kk; j = j + 1) begin
                tmp = gb; gb = ga + gb; ga = tmp;
            end
            @(negedge clk); k = kk; start = 1;
            @(negedge clk); start = 0;
            while (!done) @(negedge clk);
            checks = checks + 1;
            if (oa !== ga || ob !== gb) begin
                errors = errors + 1;
                if (errors < 4)
                    $display("MISMATCH k=%0d in=(%0d,%0d) got=(%0d,%0d) want=(%0d,%0d)",
                             kk, ia, ib, oa, ob, ga, gb);
            end
            @(negedge clk);
        end
        $display("checks=%0d errors=%0d", checks, errors);
        if (errors == 0) $display("PHI SCALE PATH: CORRECT");
        else             $display("PHI SCALE PATH: BROKEN");
        // negative control: a deliberately wrong expectation must be caught
        ga = 12345; gb = 999;
        if (ga === oa && gb === ob) $display("NEGATIVE CONTROL FAILED");
        else $display("negative control ok (tb can detect a mismatch)");
        $finish;
    end
endmodule
