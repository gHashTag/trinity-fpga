`default_nettype none
module h_lns32 (input wire clk, input wire rst_n, output wire [3:0] led);
  reg [63:0] lf = 64'h1234_5678_9ABC_DEF0;
  always @(posedge clk) lf <= !rst_n ? 64'h1234_5678_9ABC_DEF0 : {lf[62:0], lf[63]^lf[62]^lf[60]^lf[59]};
  wire signed [31:0] s;
  lns32_t4096 u (.clk(clk), .x(lf[31:0]), .y(lf[63:32]), .s(s));
  assign led = s[3:0];
endmodule
