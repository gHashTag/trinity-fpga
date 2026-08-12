`default_nettype none
module sc_scale_step8 (input wire clk, input wire rst_n, output wire [3:0] led);
  reg [127:0] lf = 128'h1234_5678_9ABC_DEF0_0FED_CBA9_8765_4321;
  always @(posedge clk) lf <= !rst_n ? 128'h1234_5678_9ABC_DEF0_0FED_CBA9_8765_4321 : {lf[126:0], lf[127]^lf[126]^lf[120]^lf[110]};
  wire [31:0] o;
  scale_step8 dut (.v(lf[31:0]), .code(lf[39:32]), .out(o));
  reg [31:0] r;
  always @(posedge clk) r <= !rst_n ? 32'b0 : o;
  assign led = r[3:0]^r[7:4]^r[11:8]^r[15:12]^r[19:16]^r[23:20]^r[27:24]^r[31:28];
endmodule
