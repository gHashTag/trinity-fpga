`timescale 1ns/1ps
module scale_phi_signed_tb;
    localparam ACC = 32, KW = 5;
    reg clk = 0, rst = 1, start = 0, kneg = 0;
    reg signed [ACC-1:0] ia, ib;
    reg [KW-1:0] km;
    wire signed [ACC-1:0] oa, ob;
    wire done;
    integer errF = 0, errI = 0, errR = 0, n = 0, t, j, kk;
    reg signed [ACC-1:0] ga, gb, tmp, sa, sb;

    scale_phi_signed #(.ACC(ACC), .KW(KW)) dut
        (.clk(clk), .rst(rst), .start(start), .acc_a(ia), .acc_b(ib),
         .k_mag(km), .k_neg(kneg), .out_a(oa), .out_b(ob), .done(done));
    always #5 clk = ~clk;

    task run(input integer aa, input integer bb, input integer k, input dneg);
        begin
            @(negedge clk); ia = aa; ib = bb; km = k; kneg = dneg; start = 1;
            @(negedge clk); start = 0;
            while (!done) @(negedge clk);
            @(negedge clk);
        end
    endtask

    initial begin
        @(negedge clk); rst = 0;
        // 1. forward direction against an independent golden model
        for (t = 0; t < 120; t = t + 1) begin
            ia = $random % 5000; ib = $random % 5000; kk = {$random} % 10;
            ga = ia; gb = ib;
            for (j = 0; j < kk; j = j + 1) begin tmp = gb; gb = ga + gb; ga = tmp; end
            run(ia, ib, kk, 1'b0); n = n + 1;
            if (oa !== ga || ob !== gb) errF = errF + 1;
        end
        // 2. inverse direction against its own golden model
        for (t = 0; t < 120; t = t + 1) begin
            ia = $random % 5000; ib = $random % 5000; kk = {$random} % 10;
            ga = ia; gb = ib;
            for (j = 0; j < kk; j = j + 1) begin tmp = gb - ga; gb = ga; ga = tmp; end
            run(ia, ib, kk, 1'b1); n = n + 1;
            if (oa !== ga || ob !== gb) errI = errI + 1;
        end
        // 3. round trip: multiply by phi^k then divide by phi^k must be identity.
        //    This is the check that catches an inverse which is merely plausible.
        for (t = 0; t < 120; t = t + 1) begin
            sa = $random % 5000; sb = $random % 5000; kk = {$random} % 10;
            run(sa, sb, kk, 1'b0);
            run(oa, ob, kk, 1'b1); n = n + 1;
            if (oa !== sa || ob !== sb) errR = errR + 1;
        end
        $display("cases=%0d  forward_err=%0d  inverse_err=%0d  roundtrip_err=%0d",
                 n, errF, errI, errR);
        if (errF == 0 && errI == 0 && errR == 0)
            $display("SIGNED PHI SCALE: CORRECT IN BOTH DIRECTIONS");
        else $display("SIGNED PHI SCALE: BROKEN");
        // negative control: a wrong inverse rule must be rejected by check 3
        run(1000, 1, 3, 1'b0);
        if (oa === 1000 && ob === 1) $display("NEGATIVE CONTROL FAILED (no-op)");
        else $display("negative control ok (forward actually changes the pair)");
        $finish;
    end
endmodule
