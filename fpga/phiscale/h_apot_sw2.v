`default_nettype none
module h_apot_sw2 (input wire clk, input wire rst_n, output wire [3:0] led);
  reg [63:0] lf = 64'h1234_5678_9ABC_DEF0;
  always @(posedge clk) lf <= !rst_n ? 64'h1234_5678_9ABC_DEF0 : {lf[62:0], lf[63]^lf[62]^lf[60]^lf[59]};
  wire signed [31:0] o; wire d;
  scale_apot #(.ACC(32),.NT(2),.SW(2)) u (.clk(clk),.rst(!rst_n),.start(lf[0]),.acc(lf[31:0]),.sh(lf[35:32]),.sgn(lf[37:36]),.out(o),.done(d));
  assign led = o[3:0];
endmodule
