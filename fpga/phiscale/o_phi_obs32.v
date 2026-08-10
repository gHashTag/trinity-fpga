`default_nettype none
module o_phi_obs32 (input wire clk, input wire rst_n, output wire [3:0] led);
  reg [63:0] lf = 64'h1234_5678_9ABC_DEF0;
  always @(posedge clk) lf <= !rst_n ? 64'h1234_5678_9ABC_DEF0 : {lf[62:0], lf[63]^lf[62]^lf[60]^lf[59]};
  wire signed [31:0] oa, ob;
  phi_step #(.W(32)) u (.clk(clk), .dir(lf[3]), .a(lf[31:0]), .b(lf[63:32]), .oa(oa), .ob(ob));
  reg [31:0] r; always @(posedge clk) r <= oa ^ ob;
  assign led = r[3:0] ^ r[31:28] ^ r[19:16] ^ r[11:8];
endmodule
