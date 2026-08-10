`default_nettype none
module h_apot_sw5 (input wire clk, input wire rst_n, output wire [3:0] led);
  reg [63:0] lf = 64'h1234_5678_9ABC_DEF0;
  always @(posedge clk) lf <= !rst_n ? 64'h1234_5678_9ABC_DEF0 : {lf[62:0], lf[63]^lf[62]^lf[60]^lf[59]};
  wire signed [31:0] o; wire d;
  scale_apot #(.ACC(32),.NT(2),.SW(5)) u (.clk(clk),.rst(!rst_n),.start(lf[0]),.acc(lf[31:0]),.sh(lf[41:32]),.sgn(lf[43:42]),.out(o),.done(d));
  assign led = o[3:0];
endmodule
