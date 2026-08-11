`timescale 1ns/1ps
module tb_fp8f;
  reg [7:0] x; wire [31:0] a, b;
  fp8_e4m3_full d1 (.x(x), .fp32_out(a));
  fp8_e5m2_full d2 (.x(x), .fp32_out(b));
  integer i;
  initial begin
    for (i=0;i<256;i=i+1) begin x=i[7:0]; #1; $display("%0d %08x %08x", i, a, b); end
    $finish;
  end
endmodule
