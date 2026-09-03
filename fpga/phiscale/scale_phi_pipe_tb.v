// Correctness before area, and before any throughput claim.
//
// Driven on the NEGEDGE, as scale_phi_tb.v is: driving on the posedge races
// the flops that sample it, which cost a whole iteration once.
`timescale 1ns/1ps
`default_nettype none
module scale_phi_pipe_tb;
    localparam integer ACC = 16, KW = 4, K_MAX = 8;
    reg clk = 0, rst = 1, in_valid = 0;
    reg signed [ACC-1:0] ia, ib;
    reg [KW-1:0] k;
    wire signed [ACC-1:0] oa, ob;
    wire ov;
    integer t, i, errors = 0, checks = 0, ga, gb, ta, tb_;
    // expected results, delayed by the pipeline depth
    integer ea [0:63];
    integer eb [0:63];
    integer sent, recvd;

    always #5 clk = ~clk;

    scale_phi_pipe #(.ACC(ACC), .KW(KW), .K_MAX(K_MAX)) dut (
        .clk(clk), .rst(rst), .in_valid(in_valid), .acc_a(ia), .acc_b(ib), .k(k),
        .out_a(oa), .out_b(ob), .out_valid(ov));

    initial begin
        repeat (4) @(negedge clk);
        rst = 0;
        sent = 0; recvd = 0;
        // Feed one element every cycle -- the throughput claim under test.
        for (t = 0; t < 40; t = t + 1) begin
            ia = 0;
            ib = $random % 200;
            k  = $random & 4'h7;
            ga = 0; gb = ib;
            for (i = 0; i < k; i = i + 1) begin
                ta = gb; tb_ = ga + gb; ga = ta; gb = tb_;
            end
            ea[t] = ga; eb[t] = gb;
            // in_valid is raised with the FIRST data, not after it. Raising it
            // after the first negedge meant element 0 was never captured and
            // every result came out one index early -- the outputs were right
            // and the bench was reading them against the wrong expectation.
            in_valid = 1;
            @(negedge clk);
            sent = sent + 1;
        end
        // Dropped without waiting another edge: the loop's last iteration
        // already consumed the negedge that presented element 39, so one more
        // wait here accepts a 41st element that has no expectation.
        in_valid = 0;
        repeat (K_MAX + 4) @(negedge clk);
        $display("  %0d checks, %0d errors", checks, errors);
        // A pass that cannot fail is not a pass.
        if (ea[0] === eb[0] && ea[0] === 0)
            $display("  FAULT: the expectations are empty, so nothing was compared");
        if (errors == 0 && checks >= 35)
            $display("  one element per cycle, %0d accepted back to back", sent);
        $finish;
    end

    // Collect results as they emerge, one per cycle.
    always @(posedge clk) begin
        if (!rst && ov) begin
            checks = checks + 1;
            if (oa !== ea[recvd][ACC-1:0] || ob !== eb[recvd][ACC-1:0]) begin
                errors = errors + 1;
                if (errors <= 3)
                    $display("  MISMATCH #%0d: got (%0d,%0d) want (%0d,%0d)",
                             recvd, oa, ob, ea[recvd], eb[recvd]);
            end
            recvd = recvd + 1;
        end
    end
endmodule
