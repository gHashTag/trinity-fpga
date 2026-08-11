`timescale 1ns/1ps
module tb_bnf;
  reg [16:0] x; wire [31:0] fp;
  bnf16s_decode dec (.x(x), .fp32_out(fp));
  integer i;
  initial begin
    for (i=0;i<131072;i=i+1) begin x=i[16:0]; #1; $display("%0d %08x", i, fp); end
    $finish;
  end
endmodule
