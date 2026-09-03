// Correctness before area: a small circuit that computes the wrong thing is
// smaller still. The golden model is computed independently here, in integers,
// from the same definition the RTL claims to implement.
`timescale 1ns/1ps
`default_nettype none
module tern_layer_phi_tb;
    localparam integer N = 16, W = 8, ACC = 24, KW = 5;
    reg clk = 0, rst = 1, start = 0;
    reg signed [N*W-1:0] x;
    reg [2*N-1:0] w;
    reg [KW-1:0] k;
    wire signed [ACC-1:0] y_a, y_b;
    wire done;
    integer trial, i, errors = 0, checks = 0, guard;
    integer ga, gb, ta, tb_, s;
    reg signed [W-1:0] xi;

    always #5 clk = ~clk;

    tern_layer_phi #(.N(N), .W(W), .ACC(ACC), .KW(KW)) dut (
        .clk(clk), .rst(rst), .start(start), .x(x), .w(w), .k(k),
        .y_a(y_a), .y_b(y_b), .done(done));

    initial begin
        repeat (4) @(negedge clk);
        rst = 0;
        for (trial = 0; trial < 60; trial = trial + 1) begin
            s = 0;
            for (i = 0; i < N; i = i + 1) begin
                xi = $random;
                x[i*W +: W] = xi;
                w[i*2 +: 2] = $random & 2'b11;
                // weight 2'b01 = +phi, 2'b11 = -phi, else zero
                if (w[i*2 +: 2] == 2'b01) s = s + xi;
                else if (w[i*2 +: 2] == 2'b11) s = s - xi;
            end
            k = $random & 5'h7;

            // golden: accumulator is (0, s); applying phi k times is the
            // Fibonacci step (a,b) -> (b, a+b), computed here in plain integers.
            ga = 0; gb = s;
            for (i = 0; i < k; i = i + 1) begin
                ta = gb; tb_ = ga + gb; ga = ta; gb = tb_;
            end

            // Wait for the previous done to clear before pulsing, or the
            // loop below exits on a STALE done and samples the previous
            // trial's output -- which it did, freezing every result at the
            // first trial's value.
            // Driven on the NEGEDGE, as scale_phi_tb.v does. Driving stimulus
            // on the posedge races the flops that sample it: my first version
            // did that, saw nothing fire, and I briefly concluded the block was
            // broken. It is not -- its own bench passes 200/200. The harness
            // was wrong, again.
            guard = 0;
            while (done === 1'b1 && guard < 200) begin
                @(negedge clk); guard = guard + 1;
            end
            @(negedge clk); start = 1;
            @(negedge clk); start = 0;
            guard = 0;
            while (done !== 1'b1 && guard < 200) begin
                @(negedge clk); guard = guard + 1;
            end
            checks = checks + 1;
            if (y_a !== ga[ACC-1:0] || y_b !== gb[ACC-1:0]) begin
                errors = errors + 1;
                if (errors <= 3)
                    $display("  MISMATCH k=%0d sum=%0d : got (%0d,%0d) want (%0d,%0d)",
                             k, s, y_a, y_b, ga, gb);
            end
            repeat (2) @(negedge clk);
        end
        $display("  %0d checks, %0d errors", checks, errors);

        // A pass that cannot fail is not a pass: assert a deliberately wrong
        // expectation and confirm the comparison would have caught it.
        if (y_b === (gb[ACC-1:0] + 1))
            $display("  FAULT: the bench cannot distinguish a wrong answer");
        else
            $display("  negative control: a wrong expectation would be caught");
        $finish;
    end
endmodule
