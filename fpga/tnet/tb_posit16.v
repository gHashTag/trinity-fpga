`timescale 1ns/1ps
module tb_posit16;
  reg clk = 0; always #1 clk = ~clk;
  reg [15:0] x; wire [31:0] fp;
  posit16_decode dec (.posit_in(x), .fp32_out(fp), .is_zero(), .is_nar());
  integer i;
  initial begin
    for (i = 0; i < (1<<16); i = i + 1) begin
      x = i[15:0]; #1; $display("%0d %08x", i, fp); #1;
    end
    $finish;
  end
endmodule
