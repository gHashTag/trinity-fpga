`timescale 1ns/1ps
`default_nettype none
module zphi_to_scalar_tb;
    localparam integer ACC = 16, W = 8, SH = 4;
    reg clk = 0, rst = 1, in_valid = 0;
    reg signed [ACC-1:0] a, b;
    wire signed [W-1:0] y;
    wire ov;
    integer t, errors = 0, checks = 0, want, got, sat;
    always #5 clk = ~clk;
    zphi_to_scalar #(.ACC(ACC), .W(W), .SH(SH)) dut (
        .clk(clk), .rst(rst), .in_valid(in_valid), .a(a), .b(b), .y(y), .out_valid(ov));
    initial begin
        repeat (4) @(negedge clk);
        rst = 0;
        for (t = 0; t < 200; t = t + 1) begin
            a = $random % 400;
            b = $random % 400;
            in_valid = 1;
            @(negedge clk);
            // golden: a + b*207/128, arithmetic-shifted, saturated
            want = a + ((b * 207) >>> 7);
            want = want >>> SH;
            if (want > 127) want = 127;
            if (want < -128) want = -128;
            @(posedge clk); @(posedge clk);
            #1;
            checks = checks + 1;
            if (y !== want[W-1:0]) begin
                errors = errors + 1;
                if (errors <= 3)
                    $display("  MISMATCH a=%0d b=%0d: got %0d want %0d", a, b, y, want);
            end
        end
        in_valid = 0;
        $display("  %0d checks, %0d errors", checks, errors);
        // saturation must actually be exercised, or the branch is untested
        a = 32000; b = 32000; @(negedge clk); @(posedge clk); @(posedge clk); #1;
        $display("  saturation: a=b=32000 -> %0d (must be 127)", y);
        $finish;
    end
endmodule
