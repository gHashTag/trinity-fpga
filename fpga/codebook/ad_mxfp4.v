`default_nettype none
module ad_mxfp4 (input wire clk, input wire rst_n, output wire [3:0] led);
  reg [63:0] lf = 64'h1234_5678_9ABC_DEF0;
  always @(posedge clk) lf <= !rst_n ? 64'h1234_5678_9ABC_DEF0 : {lf[62:0], lf[63]^lf[62]^lf[60]^lf[59]};
  wire [4:0] y;
  mxfp4_decode u (.code(lf[3:0]), .w(y));
  reg [4:0] q;
  always @(posedge clk) q <= !rst_n ? 5'b0 : y;
  wire [7:0] fz_q = {3'b000, q};
  assign led = fz_q[3:0] ^ fz_q[7:4];
endmodule
`default_nettype wire
