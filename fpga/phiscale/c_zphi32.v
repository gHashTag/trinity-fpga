`default_nettype none
module c_zphi32 (input wire clk, input wire rst_n, output wire [3:0] led);
  reg [63:0] lf = 64'h1234_5678_9ABC_DEF0;
  always @(posedge clk) lf <= !rst_n ? 64'h1234_5678_9ABC_DEF0 : {lf[62:0], lf[63]^lf[62]^lf[60]^lf[59]};
  wire [63:0] o;
  wire signed [31:0] sa,sb; zphi_add #(.ACC(32)) u (.clk(clk),.a0(lf[31:0]),.b0(lf[63:32]),.a1({lf[15:0],lf[63:48]}),.b1({lf[31:16],lf[47:32]}),.sa(sa),.sb(sb)); assign o = {sa,sb};
  reg [63:0] q;
  always @(posedge clk) q <= !rst_n ? {64{1'b0}} : o;
  assign led = ^{q, 4'b0} ? (q[3:0] ^ q[63:60]) : 4'b0;
endmodule
