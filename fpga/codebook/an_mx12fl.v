`default_nettype none
module an_mx12fl (input wire clk, input wire rst_n, output wire [3:0] led);
  reg [63:0] lf = 64'h1234_5678_9ABC_DEF0;
  always @(posedge clk) lf <= !rst_n ? 64'h1234_5678_9ABC_DEF0 : {lf[62:0], lf[63]^lf[62]^lf[60]^lf[59]};
  wire [31:0] y;
  wire signed [4:0] wv;
  mx_u12_flat d (.code(lf[3:0]), .w(wv));
  mac_lane #(.WW(5),.AW(8),.ACC(32)) u (.clk(clk),.rst_n(rst_n),.w(wv),.a(lf[23:16]),.acc(y));
  wire [31:0] fz_y = y;
  assign led = fz_y[3:0] ^ fz_y[7:4] ^ fz_y[11:8] ^ fz_y[15:12] ^ fz_y[19:16] ^ fz_y[23:20] ^ fz_y[27:24] ^ fz_y[31:28];
endmodule
`default_nettype wire
