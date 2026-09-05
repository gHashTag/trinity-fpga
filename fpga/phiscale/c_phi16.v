`default_nettype none
module c_phi16 (input wire clk, input wire rst_n, output wire [3:0] led);
  reg [63:0] lf = 64'h1234_5678_9ABC_DEF0;
  always @(posedge clk) lf <= !rst_n ? 64'h1234_5678_9ABC_DEF0 : {lf[62:0], lf[63]^lf[62]^lf[60]^lf[59]};
  wire [31:0] o;
  wire [15:0] oa,ob; phi_step #(.W(16)) u (.clk(clk),.dir(1'b0),.a(lf[15:0]),.b(lf[31:16]),.oa(oa),.ob(ob)); assign o = {oa,ob};
  reg [31:0] q;
  always @(posedge clk) q <= !rst_n ? {32{1'b0}} : o;
  assign led = ^{q, 4'b0} ? (q[3:0] ^ q[31:28]) : 4'b0;
endmodule
