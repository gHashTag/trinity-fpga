`default_nettype none
module f_apot_requant (input wire clk, input wire rst_n, output wire [3:0] led);
  reg [63:0] lf = 64'h1234_5678_9ABC_DEF0;
  always @(posedge clk) lf <= !rst_n ? 64'h1234_5678_9ABC_DEF0 : {lf[62:0], lf[63]^lf[62]^lf[60]^lf[59]};
  wire [5:0] p, q; wire sg;
  apot_requant #(.W(32)) u (.clk(clk), .v(lf[31:0]), .p(p), .q(q), .sgn(sg));
  reg [31:0] acc; always @(posedge clk) acc <= {19'b0, sg, p, q};
  assign led = acc[3:0] ^ acc[31:28] ^ acc[19:16] ^ acc[11:8];
endmodule
