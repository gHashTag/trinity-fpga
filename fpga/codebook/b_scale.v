`default_nettype none
module b_scale (input wire clk, input wire rst_n, output wire [3:0] led);
  reg [63:0] lf = 64'h1234_5678_9ABC_DEF0;
  always @(posedge clk) lf <= !rst_n ? 64'h1234_5678_9ABC_DEF0 : {lf[62:0], lf[63]^lf[62]^lf[60]^lf[59]};
  wire [39:0] y;
  reg signed [31:0] bv; always @(posedge clk) bv <= !rst_n ? 32'b0 : lf[31:0];
  blk_scale #(.ACC(32),.OUT(40)) u (.clk(clk),.rst_n(rst_n),.blk(bv),.e8m0(lf[39:32]),.emax(lf[47:40]),.y(y));
  wire [39:0] fz_y = y;
  assign led = fz_y[3:0] ^ fz_y[7:4] ^ fz_y[11:8] ^ fz_y[15:12] ^ fz_y[19:16] ^ fz_y[23:20] ^ fz_y[27:24] ^ fz_y[31:28] ^ fz_y[35:32] ^ fz_y[39:36];
endmodule
`default_nettype wire
