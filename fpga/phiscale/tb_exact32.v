`timescale 1ns/1ps
// The theorem in silicon: the linear path of a ternary layer, exact.
// The accumulator pair is dumped as integers and compared against exact
// integer arithmetic in Z[phi]. Nothing here is a float.
module tb_exact32;
  localparam N = 32, W = 8, ACC = 24;
  reg clk = 0; always #1 clk = ~clk;
  reg  signed [N*W-1:0] x;
  reg         [2*N-1:0] w;
  wire signed [ACC-1:0] aa, bb;
  tern_node2 #(.N(N), .W(W), .ACC(ACC)) u (.clk(clk), .x(x), .w(w), .acc_a(aa), .acc_b(bb));
  integer i, j; reg [63:0] r;
  initial begin
    r = 64'h9E3779B97F4A7C15;
    for (i = 0; i < 6000; i = i + 1) begin
      @(negedge clk);
      for (j = 0; j < N; j = j + 1) begin
        r = r * 64'd6364136223846793005 + 64'd1442695040888963407;
        x[j*W +: W] = r[W-1:0];
        w[j*2 +: 2] = r[33:32];
      end
      @(posedge clk); #0.1;
      $display("%h %h %0d %0d", x, w, aa, bb);
    end
    $finish;
  end
endmodule
