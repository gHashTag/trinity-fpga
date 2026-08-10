`default_nettype none
module g_harness (input wire clk, input wire rst_n, output wire [3:0] led);
  reg [63:0] lf = 64'h1234_5678_9ABC_DEF0;
  always @(posedge clk) lf <= !rst_n ? 64'h1234_5678_9ABC_DEF0 : {lf[62:0], lf[63]^lf[62]^lf[60]^lf[59]};
  reg [31:0] acc; always @(posedge clk) acc <= lf[31:0];
  assign led = acc[3:0]^acc[7:4]^acc[11:8]^acc[15:12]^acc[19:16]^acc[23:20]^acc[27:24]^acc[31:28];
endmodule
