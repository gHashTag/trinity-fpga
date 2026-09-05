`default_nettype none
module h_phi_const8 (input wire clk, input wire rst_n, output wire [3:0] led);
  reg [63:0] lf = 64'h1234_5678_9ABC_DEF0;
  always @(posedge clk) lf <= !rst_n ? 64'h1234_5678_9ABC_DEF0 : {lf[62:0], lf[63]^lf[62]^lf[60]^lf[59]};
  wire signed [31:0] oa,ob; wire d;
  scale_phi_const #(.ACC(32),.K(8)) u (.clk(clk),.rst(!rst_n),.start(lf[0]),.in_a(lf[31:0]),.in_b(lf[63:32]),.out_a(oa),.out_b(ob),.done(d));
  assign led = oa[3:0] ^ ob[3:0];
endmodule
