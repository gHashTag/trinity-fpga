`timescale 1ns/1ps
module tb_minifloat;
  reg clk = 0; always #1 clk = ~clk;
  reg [7:0] x; wire [31:0] fp;
  minifloat_decode dec (.mf_in(x), .fp32_out(fp));
  integer i;
  initial begin
    for (i = 0; i < (1<<8); i = i + 1) begin
      x = i[7:0]; #1; $display("%0d %08x", i, fp); #1;
    end
    $finish;
  end
endmodule
