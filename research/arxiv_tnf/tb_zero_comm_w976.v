`timescale 1ns/1ps
// W976: reproduce, in simulation, the two clauses the die reports false.
// The spec's own tests use FIXED constants; the die drives LIVE operands that
// change every beat. This drives the same varying operands the wrapper does.
module tb;
  reg clk = 0, rst_n = 0;
  always #5 clk = ~clk;

  localparam [31:0] Z   = 32'd0;
  localparam [31:0] ONE = 32'd20480;   // the spec's own "1"
  localparam [31:0] TWO = 32'd86016;   // the spec's own "2"

  reg [31:0] live = 32'd0, live2 = 32'd0;
  wire [31:0] r_zero, r_c1, r_c2;
  wire y_z, y1, y2;

  GftSignedMac u_z  (.clk(clk), .rst_n(rst_n), .en(1'b1),
                     .a1(Z),    .b1(live), .a2(Z),    .b2(live2), .ready(y_z), .result(r_zero));
  GftSignedMac u_c1 (.clk(clk), .rst_n(rst_n), .en(1'b1),
                     .a1(live), .b1(TWO),  .a2(live2), .b2(ONE),  .ready(y1),  .result(r_c1));
  GftSignedMac u_c2 (.clk(clk), .rst_n(rst_n), .en(1'b1),
                     .a1(TWO),  .b1(live), .a2(ONE),   .b2(live2), .ready(y2), .result(r_c2));

  integer i, zbad = 0, cbad = 0, n = 0;
  initial begin
    #20 rst_n = 1;
    for (i = 0; i < 64; i = i + 1) begin
      live  = i;
      live2 = i * 7;
      repeat (40) @(posedge clk);
      n = n + 1;
      if (r_zero !== 32'd0) begin
        zbad = zbad + 1;
        if (zbad <= 4) $display("[ZERO]  live=%0d live2=%0d -> %0d  (must be 0)", live, live2, r_zero);
      end
      if (r_c1 !== r_c2) begin
        cbad = cbad + 1;
        if (cbad <= 4) $display("[COMM]  live=%0d live2=%0d -> c1=%0d c2=%0d", live, live2, r_c1, r_c2);
      end
    end
    $display("");
    $display("points=%0d  ZERO violations=%0d  COMM violations=%0d", n, zbad, cbad);
    $finish;
  end
endmodule
