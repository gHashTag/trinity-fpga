`default_nettype none
module h_mul (input wire clk, input wire rst_n, output wire [3:0] led);
  reg [63:0] lf = 64'h1234_5678_9ABC_DEF0;
  always @(posedge clk) lf <= !rst_n ? 64'h1234_5678_9ABC_DEF0 : {lf[62:0], lf[63]^lf[62]^lf[60]^lf[59]};
  wire signed [31:0] o; wire d;
  scale_mul #(.ACC(32),.AW(16)) u (.clk(clk),.rst(!rst_n),.start(lf[0]),.acc(lf[31:0]),.alpha(lf[47:32]),.out(o),.done(d));
  assign led = o[3:0];
endmodule
