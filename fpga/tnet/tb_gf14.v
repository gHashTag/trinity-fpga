`timescale 1ns/1ps
module tb_gf14;
  reg clk = 0; always #1 clk = ~clk;
  reg [13:0] x; wire [31:0] fp;
  gf14_decode dec (.gf14_in(x), .fp32_out(fp));
  integer i;
  initial begin
    for (i = 0; i < (1<<14); i = i + 1) begin
      x = i[13:0]; #1; $display("%0d %08x", i, fp); #1;
    end
    $finish;
  end
endmodule
