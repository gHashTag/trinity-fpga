`timescale 1ns/1ps
module tb_gf10;
  reg clk = 0; always #1 clk = ~clk;
  reg [9:0] x; wire [31:0] fp;
  gf10_decode dec (.gf10_in(x), .fp32_out(fp));
  integer i;
  initial begin
    for (i = 0; i < (1<<10); i = i + 1) begin
      x = i[9:0]; #1; $display("%0d %08x", i, fp); #1;
    end
    $finish;
  end
endmodule
