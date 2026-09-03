// Correctness before area. Loads one row through the narrow port, runs it, and
// compares against a golden model computed independently in integers.
// Driven on the negedge, as every bench in this directory is.
`timescale 1ns/1ps
`default_nettype none
module tern_layer_mem_tb;
    localparam integer N = 16, W = 8, ACC = 16, KW = 4, K_MAX = 8, SH = 4, ROWS = 4;
    reg clk = 0, rst = 1, start = 0, ld_en = 0, ld_commit = 0;
    reg [1:0] row = 0, ld_row = 0;
    reg [3:0] ld_lane = 0;
    reg signed [W-1:0] ld_x = 0;
    reg [1:0] ld_w = 0;
    reg [KW-1:0] k = 0;
    wire signed [W-1:0] y;
    wire ov;
    integer i, s, ga, gb, ta, tb_, want, errors = 0, checks = 0, guard;
    reg signed [W-1:0] xs [0:N-1];
    reg [1:0] ws [0:N-1];

    always #5 clk = ~clk;

    tern_layer_mem #(.N(N), .W(W), .ACC(ACC), .KW(KW), .K_MAX(K_MAX), .SH(SH),
                     .ROWS(ROWS), .ARM(0)) dut (
        .clk(clk), .rst(rst), .start(start), .row(row), .k(k), .alpha(16'd0),
        .ld_en(ld_en), .ld_row(ld_row), .ld_lane(ld_lane), .ld_x(ld_x),
        .ld_w(ld_w), .ld_commit(ld_commit), .y(y), .out_valid(ov));

    initial begin
        repeat (4) @(negedge clk);
        rst = 0;
        for (s = 0; s < 6; s = s + 1) begin
            // load one row, lane by lane
            for (i = 0; i < N; i = i + 1) begin
                xs[i] = $random % 60;
                ws[i] = $random & 2'b11;
                @(negedge clk);
                ld_en = 1; ld_lane = i[3:0]; ld_x = xs[i]; ld_w = ws[i];
            end
            @(negedge clk); ld_en = 0; ld_row = 0; ld_commit = 1;
            @(negedge clk); ld_commit = 0;

            k = s[KW-1:0] & 4'h7;
            // golden
            gb = 0;
            for (i = 0; i < N; i = i + 1) begin
                if (ws[i] == 2'b01) gb = gb + xs[i];
                else if (ws[i] == 2'b11) gb = gb - xs[i];
            end
            ga = 0;
            for (i = 0; i < k; i = i + 1) begin ta = gb; tb_ = ga + gb; ga = ta; gb = tb_; end
            want = ga + ((gb * 207) >>> 7);
            want = want >>> SH;
            if (want > 127) want = 127;
            if (want < -128) want = -128;

            @(negedge clk); row = 0; start = 1;
            @(negedge clk); start = 0;
            guard = 0;
            while (ov !== 1'b1 && guard < 60) begin @(negedge clk); guard = guard + 1; end
            checks = checks + 1;
            if (y !== want[W-1:0]) begin
                errors = errors + 1;
                if (errors <= 3) $display("  MISMATCH k=%0d: got %0d want %0d", k, y, want);
            end
            repeat (3) @(negedge clk);
        end
        $display("  %0d checks, %0d errors", checks, errors);
        $finish;
    end
endmodule
