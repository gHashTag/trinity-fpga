`timescale 1ps/1ps
module tb_top;
  reg p = 0; always #2500 p = ~p;   // 200 MHz crystal; the probe halves it to 100 MHz
  wire n; wire tx; wire [3:0] led; assign n = ~p;
  bench007_probe_ax7203 dut(.clk200_p(p), .clk200_n(n), .uart_tx(tx), .led(led));
  defparam dut.meter.GATE = 40000; defparam dut.meter.BAUD_DIV = 8;
  integer k, len = 0, lines = 0; reg [7:0] b; reg [8*40-1:0] s;
  initial forever begin
    @(negedge tx); repeat (24) @(posedge p);
    for (k = 0; k < 8; k = k + 1) begin b[k] = tx; repeat (16) @(posedge p); end
    s = {s[8*39-1:0], b}; len = len + 1;
    if (b == 8'h0A) begin
      $display("%s", s[8*34-1:16]); lines = lines + 1; len = 0;
      // seq >= 1: C must be 40000 ref cycles (10 ns) / 14.534 ns = 27521.7 +- 1 -> 27521..27523
      if (s[8*34-1-8*3 -: 64] != "00000000") begin
        if (s[8*34-1-8*12 -: 64] < "00006B81" || s[8*34-1-8*12 -: 64] > "00006B83") begin
          $display("FAIL C field %s", s[8*34-1-8*12 -: 64]); $fatal(1);
        end
      end
    end
  end
  initial begin #(10000.0*40000*4); if (lines < 3) $fatal(1, "no lines"); $display("PASS top smoke, lines=%0d", lines); $finish; end
endmodule
