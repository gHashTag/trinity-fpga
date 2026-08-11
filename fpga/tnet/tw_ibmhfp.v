`timescale 1ns/1ps
module tw_ibmhfp;
  reg [31:0] x; wire [31:0] fp;
  ibm_hfp32_decode dec (.ibm_in(x), .fp32_out(fp));
  integer i; reg [63:0] r;
  initial begin
    r = 64'h2545F4914F6CDD1D;
    for (i = 0; i < 40000; i = i + 1) begin
      r = r * 64'd6364136223846793005 + 64'd1442695040888963407;
      x = r[31:0]; #1; $display("%0d %08x", x, fp);
    end
    $finish;
  end
endmodule
