`default_nettype none
module c_zeck16 (input wire clk, input wire rst_n, output wire [3:0] led);
  reg [63:0] lf = 64'h1234_5678_9ABC_DEF0;
  always @(posedge clk) lf <= !rst_n ? 64'h1234_5678_9ABC_DEF0 : {lf[62:0], lf[63]^lf[62]^lf[60]^lf[59]};
  wire [22:0] o;
  zeck_reenc16 u (.clk(clk),.x(lf[15:0]),.z(o));
  reg [22:0] q;
  always @(posedge clk) q <= !rst_n ? {23{1'b0}} : o;
  assign led = ^{q, 4'b0} ? (q[3:0] ^ q[22:19]) : 4'b0;
endmodule
