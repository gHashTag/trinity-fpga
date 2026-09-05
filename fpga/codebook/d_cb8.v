`default_nettype none
module d_cb8 (input wire clk, input wire rst_n, output wire [3:0] led);
  reg [63:0] lf = 64'h1234_5678_9ABC_DEF0;
  always @(posedge clk) lf <= !rst_n ? 64'h1234_5678_9ABC_DEF0 : {lf[62:0], lf[63]^lf[62]^lf[60]^lf[59]};
  wire [9:0] y;
  cb4_decode_b8 u (.code(lf[3:0]), .w(y));
  reg [9:0] q;
  always @(posedge clk) q <= !rst_n ? 10'b0 : y;
  wire [11:0] fz_q = {2'b00, q};
  assign led = fz_q[3:0] ^ fz_q[7:4] ^ fz_q[11:8];
endmodule
`default_nettype wire
