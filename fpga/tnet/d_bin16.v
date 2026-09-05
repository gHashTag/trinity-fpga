`default_nettype none
module d_bin16 (input wire clk, input wire rst_n, output wire [7:0] led);
  reg [63:0] lf = 64'h1234_5678_9ABC_DEF0;
  always @(posedge clk) lf <= !rst_n ? 64'h1234_5678_9ABC_DEF0 : {lf[62:0], lf[63]^lf[62]^lf[60]^lf[59]};
  wire [31:0] fp;
  binary16_decode dec (.b16_in(lf[15:0]), .fp32_out(fp), .is_zero(), .is_inf(), .is_nan());
  reg [31:0] q;
  always @(posedge clk) q <= !rst_n ? 32'b0 : fp;
  assign led = q[7:0] ^ q[31:24];
endmodule
