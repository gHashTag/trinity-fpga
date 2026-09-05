`timescale 1ns/1ps
module tb_tnf16;
  reg clk = 0; always #1 clk = ~clk;
  reg [15:0] x; wire [31:0] fp;
  tnf16_decode dec (.x(x), .fp32_out(fp));
  integer i;
  initial begin
    for (i = 0; i < (1<<16); i = i + 1) begin
      x = i[15:0]; #1; $display("%0d %08x", i, fp); #1;
    end
    $finish;
  end
endmodule
