`default_nettype none
module ln_h32 (input wire clk, input wire rst_n, output wire [3:0] led);
  reg [63:0] lf = 64'h1234_5678_9ABC_DEF0;
  always @(posedge clk) lf <= !rst_n ? 64'h1234_5678_9ABC_DEF0 : {lf[62:0], lf[63]^lf[62]^lf[60]^lf[59]};
  wire [31:0] y;
  assign y = lf[31:0];
  reg [31:0] q;
  always @(posedge clk) q <= !rst_n ? 32'b0 : y;
  wire [31:0] fz_q = q;
  assign led = fz_q[3:0] ^ fz_q[7:4] ^ fz_q[11:8] ^ fz_q[15:12] ^ fz_q[19:16] ^ fz_q[23:20] ^ fz_q[27:24] ^ fz_q[31:28];
endmodule
`default_nettype wire
