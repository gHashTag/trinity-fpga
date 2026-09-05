`timescale 1ns/1ps
module tb_t8;
  reg [9:0] x; wire [31:0] fp;
  tnf8s_decode dec (.x(x), .fp32_out(fp));
  integer i;
  initial begin
    for (i=0;i<1024;i=i+1) begin x=i[9:0]; #1; $display("%0d %08x", i, fp); end
    $finish;
  end
endmodule
