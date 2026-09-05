`default_nettype none
module d_cb10 (input wire clk, input wire rst_n, output wire [3:0] led);
  reg [63:0] lf = 64'h1234_5678_9ABC_DEF0;
  always @(posedge clk) lf <= !rst_n ? 64'h1234_5678_9ABC_DEF0 : {lf[62:0], lf[63]^lf[62]^lf[60]^lf[59]};
  wire [11:0] y;
  cb4_decode_b10 u (.code(lf[3:0]), .w(y));
  reg [11:0] q;
  always @(posedge clk) q <= !rst_n ? 12'b0 : y;
  wire [11:0] fz_q = q;
  assign led = fz_q[3:0] ^ fz_q[7:4] ^ fz_q[11:8];
endmodule
`default_nettype wire
