`timescale 1ns/1ps
// Depth in silicon: the claim that the gain through k phi-layers is exactly
// F_k*phi + F_(k-1) -- a pair of integers known in advance, so rescaling between
// layers never needs a multiplier at any depth.
//
// One phi_step_uni fed back on itself is k stacked layers: after k clocks the
// register holds phi^k applied to (1,0). The same module the paper measures.
module tb_depth;
  localparam K = 30, W = 32;
  reg clk = 0; always #1 clk = ~clk;
  reg  signed [W-1:0] a, b;
  wire signed [W-1:0] oa, ob;
  phi_step_uni #(.W(W)) s (.clk(clk), .a(a), .b(b), .oa(oa), .ob(ob));
  integer k;
  initial begin
    a = 1; b = 0;                 // the value 1, as the pair (1,0)
    for (k = 1; k <= K; k = k + 1) begin
      @(posedge clk); #0.1;
      $display("%0d %0d %0d", k, oa, ob);
      a = oa; b = ob;
    end
    $finish;
  end
endmodule
