`timescale 1ns/1ps
module tb_spec;
  reg [35:0] a; wire [31:0] fa;
  tnf32s_decode d32 (.x(a), .fp32_out(fa));
  integer i; reg [63:0] r;
  initial begin
    r = 64'h2545F4914F6CDD1D;
    for (i = 0; i < 40000; i = i + 1) begin
      r = r * 64'd6364136223846793005 + 64'd1442695040888963407;
      a = r[35:0]; #1; $display("%0d %08x", a, fa);
    end
    $finish;
  end
endmodule
