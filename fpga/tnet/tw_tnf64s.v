`timescale 1ns/1ps
module tw_tnf64s;
  reg [64:0] x; wire [31:0] fp;
  tnf64s_decode dec (.x(x), .fp32_out(fp));
  integer i; reg [63:0] r; reg extra;
  initial begin
    r = 64'h2545F4914F6CDD1D; extra = 0;
    for (i = 0; i < 40000; i = i + 1) begin
      r = r * 64'd6364136223846793005 + 64'd1442695040888963407;
      extra = r[63] ^ r[7];
      x = {extra, r}; #1; $display("%0d %08x", x[31:0], fp);
    end
    $finish;
  end
endmodule
