`default_nettype none
module b_raw5 (input wire clk, input wire rst_n, output wire [3:0] led);
  reg [63:0] lf = 64'h1234_5678_9ABC_DEF0;
  always @(posedge clk) lf <= !rst_n ? 64'h1234_5678_9ABC_DEF0 : {lf[62:0], lf[63]^lf[62]^lf[60]^lf[59]};
  wire [39:0] y;
  wire [159:0] wss = {3{lf[63:0]}};
  wire [127:0] cds = {lf[63:0], lf[63:0]} ^ {64'h0F0F_0F0F_0F0F_0F0F, lf[31:0], lf[63:32]};
  wire [255:0] act = {cds, cds} ^ {128'h0, lf[63:0], lf[63:0]};
  blk32_raw #(.WW(5)) u (.clk(clk),.rst_n(rst_n),.ws(wss),.acts(act),.e8m0(lf[39:32]),.emax(lf[47:40]),.y(y));
  wire [39:0] fz_y = y;
  assign led = fz_y[3:0] ^ fz_y[7:4] ^ fz_y[11:8] ^ fz_y[15:12] ^ fz_y[19:16] ^ fz_y[23:20] ^ fz_y[27:24] ^ fz_y[31:28] ^ fz_y[35:32] ^ fz_y[39:36];
endmodule
`default_nettype wire
