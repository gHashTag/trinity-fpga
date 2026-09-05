`default_nettype none
module c_zeck32 (input wire clk, input wire rst_n, output wire [3:0] led);
  reg [63:0] lf = 64'h1234_5678_9ABC_DEF0;
  always @(posedge clk) lf <= !rst_n ? 64'h1234_5678_9ABC_DEF0 : {lf[62:0], lf[63]^lf[62]^lf[60]^lf[59]};
  wire [45:0] o;
  zeck_reenc32 u (.clk(clk),.x(lf[31:0]),.z(o));
  reg [45:0] q;
  always @(posedge clk) q <= !rst_n ? {46{1'b0}} : o;
  assign led = ^{q, 4'b0} ? (q[3:0] ^ q[45:42]) : 4'b0;
endmodule
