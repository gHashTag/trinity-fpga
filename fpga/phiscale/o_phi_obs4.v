`default_nettype none
module o_phi_obs4 (input wire clk, input wire rst_n, output wire [3:0] led);
  reg [63:0] lf = 64'h1234_5678_9ABC_DEF0;
  always @(posedge clk) lf <= !rst_n ? 64'h1234_5678_9ABC_DEF0 : {lf[62:0], lf[63]^lf[62]^lf[60]^lf[59]};
  wire signed [31:0] oa, ob;
  phi_step #(.W(32)) u (.clk(clk), .dir(lf[3]), .a(lf[31:0]), .b(lf[63:32]), .oa(oa), .ob(ob));
  assign led = oa[3:0] ^ ob[3:0];
endmodule
