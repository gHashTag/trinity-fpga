`timescale 1ns/1ps
module tw_takum16;
  reg clk = 0; always #1 clk = ~clk;
  reg [15:0] x; wire [31:0] fp;
  takum16_decode dec (.clk(clk), .takum16_in(x), .fp32_out(fp));
  integer i;
  initial begin
    for (i = 0; i < 65536; i = i + 1) begin
      @(negedge clk); x = i[15:0]; @(posedge clk); #0.1;
      $display("%0d %08x", x, fp);
    end
    $finish;
  end
endmodule
